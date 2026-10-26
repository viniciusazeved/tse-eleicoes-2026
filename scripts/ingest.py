"""Baixa e normaliza os resultados oficiais do TSE para Presidente em 2026."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

LOGGER = logging.getLogger("tse.ingest")

CATALOGO_URL = (
    "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026"
)
RECURSOS = {
    "votacao_secao_2026_BR.zip": (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/"
        "votacao_secao_2026_BR.zip"
    ),
    "detalhe_votacao_secao_2026.zip": (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_secao/"
        "detalhe_votacao_secao_2026.zip"
    ),
}

CHAVE_SECAO = ["turno", "uf", "municipio_codigo", "zona", "secao"]
COLUNAS_VOTOS_FONTE = [
    "DT_GERACAO",
    "HH_GERACAO",
    "ANO_ELEICAO",
    "CD_TIPO_ELEICAO",
    "NM_TIPO_ELEICAO",
    "NR_TURNO",
    "CD_ELEICAO",
    "DS_ELEICAO",
    "SG_UF",
    "CD_MUNICIPIO",
    "NM_MUNICIPIO",
    "NR_ZONA",
    "NR_SECAO",
    "CD_CARGO",
    "DS_CARGO",
    "NR_VOTAVEL",
    "NM_VOTAVEL",
    "QT_VOTOS",
    "NR_LOCAL_VOTACAO",
    "NM_LOCAL_VOTACAO",
    "DS_LOCAL_VOTACAO_ENDERECO",
]
COLUNAS_DETALHE_FONTE = [
    "DT_GERACAO",
    "HH_GERACAO",
    "ANO_ELEICAO",
    "CD_TIPO_ELEICAO",
    "NM_TIPO_ELEICAO",
    "NR_TURNO",
    "CD_ELEICAO",
    "DS_ELEICAO",
    "SG_UF",
    "CD_MUNICIPIO",
    "NM_MUNICIPIO",
    "NR_ZONA",
    "NR_SECAO",
    "CD_CARGO",
    "DS_CARGO",
    "QT_APTOS",
    "QT_COMPARECIMENTO",
    "QT_ABSTENCOES",
    "QT_VOTOS_NOMINAIS",
    "QT_VOTOS_BRANCOS",
    "QT_VOTOS_NULOS",
    "QT_VOTOS_ANULADOS_APU_SEP",
    "NR_LOCAL_VOTACAO",
    "NM_LOCAL_VOTACAO",
    "DS_LOCAL_VOTACAO_ENDERECO",
    "ST_SECAO_INSTALADA",
    "ST_SECAO_ANULADA",
]

SCHEMA_VOTOS = pa.schema(
    [
        pa.field("turno", pa.int8(), nullable=False),
        pa.field("uf", pa.string(), nullable=False),
        pa.field("municipio_codigo", pa.string(), nullable=False),
        pa.field("zona", pa.string(), nullable=False),
        pa.field("secao", pa.string(), nullable=False),
        pa.field("numero", pa.string(), nullable=False),
        pa.field("nome", pa.string(), nullable=False),
        pa.field("votos", pa.int64(), nullable=False),
    ]
)


def agora_local() -> datetime:
    """Retorna a hora local com fuso explícito."""
    return datetime.now().astimezone()


def sha256_arquivo(caminho: Path, tamanho_bloco: int = 1024 * 1024) -> str:
    """Calcula SHA-256 sem carregar o arquivo inteiro em memória."""
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(tamanho_bloco), b""):
            digest.update(bloco)
    return digest.hexdigest()


def baixar_json(sessao: requests.Session, url: str, destino: Path) -> dict[str, Any]:
    """Baixa JSON de forma atômica e devolve o objeto validado."""
    resposta = sessao.get(url, timeout=(30, 180))
    resposta.raise_for_status()
    objeto = resposta.json()
    temporario = destino.with_suffix(destino.suffix + ".part")
    temporario.write_text(
        json.dumps(objeto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporario.replace(destino)
    return objeto


def baixar_zip(sessao: requests.Session, url: str, destino: Path) -> dict[str, Any]:
    """Baixa ZIP, preserva versão anterior e registra metadados HTTP."""
    temporario = destino.with_suffix(destino.suffix + ".part")
    if temporario.exists():
        temporario.unlink()

    digest = hashlib.sha256()
    tamanho = 0
    with sessao.get(url, stream=True, timeout=(30, 600)) as resposta:
        resposta.raise_for_status()
        with temporario.open("wb") as arquivo:
            for bloco in resposta.iter_content(chunk_size=1024 * 1024):
                if not bloco:
                    continue
                arquivo.write(bloco)
                digest.update(bloco)
                tamanho += len(bloco)
        cabecalhos = {
            "etag": resposta.headers.get("ETag"),
            "last_modified": resposta.headers.get("Last-Modified"),
            "content_type": resposta.headers.get("Content-Type"),
        }

    novo_hash = digest.hexdigest()
    acao = "baixado"
    arquivado: str | None = None
    if destino.exists():
        hash_existente = sha256_arquivo(destino)
        if hash_existente == novo_hash:
            temporario.unlink()
            acao = "inalterado"
        else:
            arquivado_path = destino.with_name(
                f"{destino.stem}.{hash_existente[:12]}{destino.suffix}"
            )
            if not arquivado_path.exists():
                destino.replace(arquivado_path)
            else:
                destino.unlink()
            temporario.replace(destino)
            arquivado = arquivado_path.name
            acao = "atualizado"
    else:
        temporario.replace(destino)

    if not zipfile.is_zipfile(destino):
        raise ValueError(f"O recurso baixado não é ZIP válido: {destino}")

    return {
        "url": url,
        "arquivo": destino.name,
        "bytes": tamanho,
        "sha256": novo_hash,
        "acao": acao,
        "versao_anterior_arquivada": arquivado,
        **cabecalhos,
    }


def criar_manifesto(
    pasta_raw: Path,
    catalogo: dict[str, Any],
    metadados_download: list[dict[str, Any]],
) -> dict[str, Any]:
    """Cria manifesto rastreável das fontes brutas presentes."""
    zips = []
    for caminho in sorted(pasta_raw.glob("*.zip")):
        zips.append(
            {
                "arquivo": caminho.name,
                "bytes": caminho.stat().st_size,
                "sha256": sha256_arquivo(caminho),
            }
        )
    resultado = catalogo.get("result", {})
    return {
        "gerado_em": agora_local().isoformat(),
        "catalogo_url": CATALOGO_URL,
        "catalogo_metadata_modified": resultado.get("metadata_modified"),
        "catalogo_notas": resultado.get("notes"),
        "ressalva_tte": (
            "O catálogo informa 39 registros em dupla vinculação de TTE. "
            "Os arquivos são preservados integralmente e nenhuma seção é ajustada."
        ),
        "downloads": metadados_download,
        "arquivos_zip_presentes": zips,
    }


def iterar_csv_zip(
    caminho_zip: Path,
    membro: str,
    colunas: list[str],
    tamanho_chunk: int,
) -> Iterator[pd.DataFrame]:
    """Lê um CSV oficial diretamente do ZIP em blocos."""
    with zipfile.ZipFile(caminho_zip) as arquivo_zip:
        nomes = arquivo_zip.namelist()
        if membro not in nomes:
            raise FileNotFoundError(f"Membro ausente em {caminho_zip.name}: {membro}")
        with arquivo_zip.open(membro) as arquivo_csv:
            yield from pd.read_csv(
                arquivo_csv,
                sep=";",
                encoding="latin1",
                usecols=colunas,
                dtype="string",
                chunksize=tamanho_chunk,
                keep_default_na=False,
                na_filter=False,
                low_memory=False,
            )


def normalizar_inteiro(serie: pd.Series, nome: str) -> pd.Series:
    """Converte somente valores finitos e matematicamente inteiros."""
    convertido = pd.to_numeric(serie, errors="coerce")
    invalido = convertido.isna() | ~np.isfinite(convertido) | convertido.mod(1).ne(0)
    if invalido.any():
        exemplos = serie[invalido].drop_duplicates().head(5).tolist()
        raise ValueError(f"Valores inválidos em {nome}: {exemplos}")
    return convertido.astype("int64")


def normalizar_codigo(serie: pd.Series, nome: str) -> pd.Series:
    """Normaliza código integral como texto sem zeros à esquerda."""
    return normalizar_inteiro(serie, nome).astype("string")


def escrever_votos(
    zip_votos: Path,
    destino: Path,
    tamanho_chunk: int,
) -> dict[str, Any]:
    """Normaliza a votação nominal e grava Parquet em streaming."""
    temporario = destino.with_suffix(destino.suffix + ".part")
    if temporario.exists():
        temporario.unlink()
    escritor: pq.ParquetWriter | None = None
    linhas = 0
    turnos: set[int] = set()
    candidatos: dict[str, set[str]] = {}
    candidatos_por_turno: dict[int, dict[str, set[str]]] = {}
    cargos: set[tuple[str, str]] = set()
    anos: set[str] = set()
    tipos: set[tuple[str, str]] = set()
    eleicoes: set[tuple[str, str, str]] = set()
    geracoes: set[tuple[str, str]] = set()
    votos_minimo: int | None = None

    try:
        for bruto in iterar_csv_zip(
            zip_votos,
            "votacao_secao_2026_BR.csv",
            COLUNAS_VOTOS_FONTE,
            tamanho_chunk,
        ):
            anos.update(bruto["ANO_ELEICAO"].unique().tolist())
            tipos.update(
                map(
                    tuple,
                    bruto[["CD_TIPO_ELEICAO", "NM_TIPO_ELEICAO"]]
                    .drop_duplicates()
                    .itertuples(index=False, name=None),
                )
            )
            eleicoes.update(
                map(
                    tuple,
                    bruto[["NR_TURNO", "CD_ELEICAO", "DS_ELEICAO"]]
                    .drop_duplicates()
                    .itertuples(index=False, name=None),
                )
            )
            geracoes.update(
                map(
                    tuple,
                    bruto[["DT_GERACAO", "HH_GERACAO"]]
                    .drop_duplicates()
                    .itertuples(index=False, name=None),
                )
            )
            cargos.update(
                map(
                    tuple,
                    bruto[["CD_CARGO", "DS_CARGO"]]
                    .drop_duplicates()
                    .itertuples(index=False, name=None),
                )
            )
            presidente = bruto.loc[bruto["CD_CARGO"] == "1"].copy()
            if presidente.empty:
                continue
            if not (presidente["DS_CARGO"] == "Presidente").all():
                raise ValueError("CD_CARGO=1 contém descrição diferente de Presidente")

            votos = pd.DataFrame(
                {
                    "turno": normalizar_inteiro(presidente["NR_TURNO"], "NR_TURNO"),
                    "uf": presidente["SG_UF"],
                    "municipio_codigo": normalizar_codigo(
                        presidente["CD_MUNICIPIO"], "CD_MUNICIPIO"
                    ),
                    "zona": normalizar_codigo(presidente["NR_ZONA"], "NR_ZONA"),
                    "secao": normalizar_codigo(presidente["NR_SECAO"], "NR_SECAO"),
                    "numero": normalizar_codigo(presidente["NR_VOTAVEL"], "NR_VOTAVEL"),
                    "nome": presidente["NM_VOTAVEL"],
                    "votos": normalizar_inteiro(presidente["QT_VOTOS"], "QT_VOTOS"),
                }
            )
            if (votos["votos"] <= 0).any():
                raise ValueError(
                    "A fonte nominal contém linha com QT_VOTOS não positivo"
                )
            for numero, nomes in votos.groupby("numero", sort=False)["nome"]:
                candidatos.setdefault(str(numero), set()).update(
                    nomes.unique().tolist()
                )
            for (turno, numero), nomes in votos.groupby(
                ["turno", "numero"], sort=False
            )["nome"]:
                candidatos_por_turno.setdefault(int(turno), {}).setdefault(
                    str(numero), set()
                ).update(nomes.unique().tolist())
            turnos.update(votos["turno"].unique().tolist())
            minimo_chunk = int(votos["votos"].min())
            votos_minimo = (
                minimo_chunk
                if votos_minimo is None
                else min(votos_minimo, minimo_chunk)
            )

            tabela = pa.Table.from_pandas(
                votos, schema=SCHEMA_VOTOS, preserve_index=False
            )
            if escritor is None:
                escritor = pq.ParquetWriter(
                    temporario,
                    SCHEMA_VOTOS,
                    compression="zstd",
                    use_dictionary=True,
                )
            escritor.write_table(tabela)
            linhas += len(votos)
    finally:
        if escritor is not None:
            escritor.close()

    if linhas == 0:
        raise ValueError("Nenhuma linha de Presidente encontrada na votação por seção")
    if anos != {"2026"}:
        raise ValueError(f"ANO_ELEICAO inesperado na votação: {sorted(anos)}")
    if tipos != {("2", "Eleição Ordinária")}:
        raise ValueError(f"Tipo de eleição inesperado na votação: {sorted(tipos)}")
    if cargos != {("1", "Presidente")}:
        raise ValueError(f"Cargo inesperado na votação: {sorted(cargos)}")
    temporario.replace(destino)
    return {
        "linhas": linhas,
        "turnos": sorted(turnos),
        "cargos_encontrados": sorted([list(item) for item in cargos]),
        "candidatos": {
            numero: sorted(nomes) for numero, nomes in sorted(candidatos.items())
        },
        "candidatos_por_turno": {
            str(turno): {
                numero: sorted(nomes) for numero, nomes in sorted(mapa.items())
            }
            for turno, mapa in sorted(candidatos_por_turno.items())
        },
        "anos": sorted(anos),
        "tipos_eleicao": sorted([list(item) for item in tipos]),
        "eleicoes": sorted([list(item) for item in eleicoes]),
        "geracoes": sorted([list(item) for item in geracoes]),
        "qt_votos_minimo": votos_minimo,
        "politica_zero": (
            "A fonte nominal só apresentou QT_VOTOS positivo. Ausência de linha para um "
            "candidato é interpretada como zero apenas na tabela larga; votos.parquet "
            "preserva exclusivamente as linhas publicadas."
        ),
    }


def ler_detalhes(
    zip_detalhes: Path,
    tamanho_chunk: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Lê o detalhe nacional de Presidente e mantém uma linha por seção."""
    partes: list[pd.DataFrame] = []
    cargos: set[tuple[str, str]] = set()
    anos: set[str] = set()
    tipos: set[tuple[str, str]] = set()
    eleicoes: set[tuple[str, str, str]] = set()
    geracoes: set[tuple[str, str]] = set()
    for bruto in iterar_csv_zip(
        zip_detalhes,
        "detalhe_votacao_secao_2026_BR.csv",
        COLUNAS_DETALHE_FONTE,
        tamanho_chunk,
    ):
        anos.update(bruto["ANO_ELEICAO"].unique().tolist())
        tipos.update(
            map(
                tuple,
                bruto[["CD_TIPO_ELEICAO", "NM_TIPO_ELEICAO"]]
                .drop_duplicates()
                .itertuples(index=False, name=None),
            )
        )
        eleicoes.update(
            map(
                tuple,
                bruto[["NR_TURNO", "CD_ELEICAO", "DS_ELEICAO"]]
                .drop_duplicates()
                .itertuples(index=False, name=None),
            )
        )
        geracoes.update(
            map(
                tuple,
                bruto[["DT_GERACAO", "HH_GERACAO"]]
                .drop_duplicates()
                .itertuples(index=False, name=None),
            )
        )
        cargos.update(
            map(
                tuple,
                bruto[["CD_CARGO", "DS_CARGO"]]
                .drop_duplicates()
                .itertuples(index=False, name=None),
            )
        )
        presidente = bruto.loc[bruto["CD_CARGO"] == "1"].copy()
        if presidente.empty:
            continue
        if not (presidente["DS_CARGO"] == "Presidente").all():
            raise ValueError(
                "CD_CARGO=1 contém descrição diferente de Presidente no detalhe"
            )
        parte = pd.DataFrame(
            {
                "turno": normalizar_inteiro(presidente["NR_TURNO"], "NR_TURNO"),
                "uf": presidente["SG_UF"],
                "municipio_codigo": normalizar_codigo(
                    presidente["CD_MUNICIPIO"], "CD_MUNICIPIO"
                ),
                "municipio_nome": presidente["NM_MUNICIPIO"],
                "zona": normalizar_codigo(presidente["NR_ZONA"], "NR_ZONA"),
                "secao": normalizar_codigo(presidente["NR_SECAO"], "NR_SECAO"),
                "local_codigo": normalizar_codigo(
                    presidente["NR_LOCAL_VOTACAO"], "NR_LOCAL_VOTACAO"
                ),
                "local": presidente["NM_LOCAL_VOTACAO"].replace("", pd.NA),
                "local_endereco": presidente["DS_LOCAL_VOTACAO_ENDERECO"].replace(
                    "", pd.NA
                ),
                "aptos": normalizar_inteiro(presidente["QT_APTOS"], "QT_APTOS"),
                "comparecimento": normalizar_inteiro(
                    presidente["QT_COMPARECIMENTO"], "QT_COMPARECIMENTO"
                ),
                "abstencao": normalizar_inteiro(
                    presidente["QT_ABSTENCOES"], "QT_ABSTENCOES"
                ),
                "validos": normalizar_inteiro(
                    presidente["QT_VOTOS_NOMINAIS"], "QT_VOTOS_NOMINAIS"
                ),
                "brancos": normalizar_inteiro(
                    presidente["QT_VOTOS_BRANCOS"], "QT_VOTOS_BRANCOS"
                ),
                "nulos": normalizar_inteiro(
                    presidente["QT_VOTOS_NULOS"], "QT_VOTOS_NULOS"
                ),
                "anulados_apu_sep": normalizar_inteiro(
                    presidente["QT_VOTOS_ANULADOS_APU_SEP"],
                    "QT_VOTOS_ANULADOS_APU_SEP",
                ),
                "secao_instalada": presidente["ST_SECAO_INSTALADA"],
                "secao_anulada": presidente["ST_SECAO_ANULADA"],
            }
        )
        partes.append(parte)

    if not partes:
        raise ValueError("Nenhum detalhe de Presidente encontrado")
    if anos != {"2026"}:
        raise ValueError(f"ANO_ELEICAO inesperado no detalhe: {sorted(anos)}")
    if tipos != {("2", "Eleição Ordinária")}:
        raise ValueError(f"Tipo de eleição inesperado no detalhe: {sorted(tipos)}")
    if cargos != {("1", "Presidente")}:
        raise ValueError(f"Cargo inesperado no detalhe: {sorted(cargos)}")
    detalhes = pd.concat(partes, ignore_index=True)
    metadados = {
        "linhas": len(detalhes),
        "turnos": sorted(detalhes["turno"].unique().tolist()),
        "cargos_encontrados": sorted([list(item) for item in cargos]),
        "anos": sorted(anos),
        "tipos_eleicao": sorted([list(item) for item in tipos]),
        "eleicoes": sorted([list(item) for item in eleicoes]),
        "geracoes": sorted([list(item) for item in geracoes]),
    }
    return detalhes, metadados


def agregar_votos(votos_parquet: Path) -> pd.DataFrame:
    """Agrega linhas nominais por seção sem preencher o Parquet longo."""
    caminho_sql = votos_parquet.as_posix().replace("'", "''")
    consulta = f"""
        SELECT
            turno,
            uf,
            municipio_codigo,
            zona,
            secao,
            SUM(CASE WHEN numero = '13' THEN votos ELSE 0 END)::BIGINT AS lula,
            SUM(CASE WHEN numero = '22' THEN votos ELSE 0 END)::BIGINT AS bolsonaro,
            SUM(CASE WHEN numero NOT IN ('13', '22', '95', '96')
                     THEN votos ELSE 0 END)::BIGINT AS outros,
            SUM(CASE WHEN numero = '95' THEN votos ELSE 0 END)::BIGINT AS brancos_votos,
            SUM(CASE WHEN numero = '96' THEN votos ELSE 0 END)::BIGINT AS nulos_votos,
            SUM(CASE WHEN numero NOT IN ('95', '96')
                     THEN votos ELSE 0 END)::BIGINT AS validos_votos,
            SUM(votos)::BIGINT AS soma_votos_arquivo
        FROM read_parquet('{caminho_sql}')
        GROUP BY turno, uf, municipio_codigo, zona, secao
    """
    with duckdb.connect() as conexao:
        return conexao.execute(consulta).df()


def contar_duplicatas_votos(votos_parquet: Path) -> tuple[int, int]:
    """Conta linhas e chaves duplicadas no Parquet longo."""
    caminho_sql = votos_parquet.as_posix().replace("'", "''")
    consulta = f"""
        SELECT
            COUNT(*)::BIGINT AS linhas,
            COUNT(*) - COUNT(DISTINCT
                (turno, uf, municipio_codigo, zona, secao, numero)
            ) AS duplicatas
        FROM read_parquet('{caminho_sql}')
    """
    with duckdb.connect() as conexao:
        linha = conexao.execute(consulta).fetchone()
    assert linha is not None
    return int(linha[0]), int(linha[1])


def construir_secoes(
    detalhes: pd.DataFrame,
    votos_agregados: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Valida a junção e calcula as métricas por seção."""
    duplicatas_detalhe = int(detalhes.duplicated(CHAVE_SECAO, keep=False).sum())
    duplicatas_agregado = int(votos_agregados.duplicated(CHAVE_SECAO, keep=False).sum())
    if duplicatas_detalhe or duplicatas_agregado:
        raise ValueError(
            "Chave de seção não única antes da junção: "
            f"detalhe={duplicatas_detalhe}, votos={duplicatas_agregado}"
        )

    secoes = detalhes.merge(
        votos_agregados,
        on=CHAVE_SECAO,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    chaves_votos_sem_detalhe = votos_agregados.merge(
        detalhes[CHAVE_SECAO], on=CHAVE_SECAO, how="left", indicator=True
    )
    votos_sem_detalhe = int((chaves_votos_sem_detalhe["_merge"] == "left_only").sum())
    detalhes_sem_votos = int((secoes["_merge"] == "left_only").sum())

    colunas_agregadas = [
        "lula",
        "bolsonaro",
        "outros",
        "brancos_votos",
        "nulos_votos",
        "validos_votos",
        "soma_votos_arquivo",
    ]
    mascara_sem_votos = secoes["_merge"] == "left_only"
    mascara_sem_comparecimento = secoes["comparecimento"] == 0
    if (mascara_sem_votos & ~mascara_sem_comparecimento).any():
        exemplos = secoes.loc[
            mascara_sem_votos & ~mascara_sem_comparecimento, CHAVE_SECAO
        ].head(5)
        raise ValueError(
            "Há seção com comparecimento positivo sem votação nominal: "
            f"{exemplos.to_dict(orient='records')}"
        )
    secoes.loc[mascara_sem_votos, colunas_agregadas] = 0
    secoes[colunas_agregadas] = secoes[colunas_agregadas].astype("int64")
    secoes = secoes.drop(columns="_merge")

    secoes["participacao"] = np.where(
        secoes["aptos"] > 0, secoes["comparecimento"] / secoes["aptos"], np.nan
    )
    secoes["lula_validos"] = np.where(
        secoes["validos"] > 0, secoes["lula"] / secoes["validos"], np.nan
    )
    secoes["bolsonaro_validos"] = np.where(
        secoes["validos"] > 0, secoes["bolsonaro"] / secoes["validos"], np.nan
    )
    secoes["lula_aptos"] = np.where(
        secoes["aptos"] > 0, secoes["lula"] / secoes["aptos"], np.nan
    )
    secoes["bolsonaro_aptos"] = np.where(
        secoes["aptos"] > 0, secoes["bolsonaro"] / secoes["aptos"], np.nan
    )

    qa_join = {
        "detalhes_sem_linhas_nominais": detalhes_sem_votos,
        "linhas_nominais_sem_detalhe": votos_sem_detalhe,
        "join_validado": "one_to_one",
    }
    return secoes, qa_join


def resumo_booleano(mascara: pd.Series) -> dict[str, int]:
    """Resume número de linhas conformes e divergentes."""
    return {
        "conformes": int(mascara.sum()),
        "divergentes": int((~mascara).sum()),
    }


def criar_qa(
    secoes: pd.DataFrame,
    votos_parquet: Path,
    meta_votos: dict[str, Any],
    meta_detalhes: dict[str, Any],
    qa_join: dict[str, Any],
) -> dict[str, Any]:
    """Executa verificações estruturais e contábeis."""
    linhas_votos, duplicatas_votos = contar_duplicatas_votos(votos_parquet)
    aptos_fecha = secoes["aptos"] == secoes["comparecimento"] + secoes["abstencao"]
    detalhe_fecha = secoes["comparecimento"] == (
        secoes["validos"]
        + secoes["brancos"]
        + secoes["nulos"]
        + secoes["anulados_apu_sep"]
    )
    nominal_fecha = secoes["validos"] == secoes["validos_votos"]
    branco_fecha = secoes["brancos"] == secoes["brancos_votos"]
    nulo_fecha = secoes["nulos"] == secoes["nulos_votos"]
    total_arquivo_fecha = secoes["soma_votos_arquivo"] == (
        secoes["validos"] + secoes["brancos"] + secoes["nulos"]
    )
    soma_candidatos_fecha = secoes["validos"] == (
        secoes["lula"] + secoes["bolsonaro"] + secoes["outros"]
    )

    nulos_por_coluna = {
        coluna: int(secoes[coluna].isna().sum()) for coluna in secoes.columns
    }
    return {
        "gerado_em": agora_local().isoformat(),
        "gerado_em_utc": datetime.now(UTC).isoformat(),
        "fonte": {
            "turnos_votacao": meta_votos["turnos"],
            "turnos_detalhe": meta_detalhes["turnos"],
            "candidatos_por_numero": meta_votos["candidatos"],
            "cargos_votacao": meta_votos["cargos_encontrados"],
            "cargos_detalhe": meta_detalhes["cargos_encontrados"],
            "politica_zero": meta_votos["politica_zero"],
            "observacao_turno_2": (
                "O pipeline registra apenas os turnos presentes nos ZIPs oficiais no momento "
                "da execução. Não cria linhas para turno ausente."
            ),
        },
        "cobertura": {
            "linhas_secoes": len(secoes),
            "linhas_votos": linhas_votos,
            "turnos": sorted(secoes["turno"].unique().tolist()),
            "ufs": sorted(secoes["uf"].unique().tolist()),
            "secoes_por_turno": {
                str(int(turno)): int(total)
                for turno, total in secoes.groupby("turno").size().items()
            },
            "exterior": {
                "codigo_uf": "ZZ",
                "linhas": int((secoes["uf"] == "ZZ").sum()),
                "municipios": int(
                    secoes.loc[secoes["uf"] == "ZZ", "municipio_codigo"].nunique()
                ),
            },
        },
        "unicidade": {
            "chave_secoes": CHAVE_SECAO,
            "duplicatas_secoes": int(secoes.duplicated(CHAVE_SECAO).sum()),
            "chave_votos": CHAVE_SECAO + ["numero"],
            "duplicatas_votos": duplicatas_votos,
        },
        "join": qa_join,
        "checks": {
            "aptos_igual_comparecimento_mais_abstencao": resumo_booleano(aptos_fecha),
            "comparecimento_igual_validos_brancos_nulos_anulados": resumo_booleano(
                detalhe_fecha
            ),
            "validos_igual_soma_candidatos": resumo_booleano(soma_candidatos_fecha),
            "validos_igual_fonte_nominal": resumo_booleano(nominal_fecha),
            "brancos_igual_fonte_nominal": resumo_booleano(branco_fecha),
            "nulos_igual_fonte_nominal": resumo_booleano(nulo_fecha),
            "soma_votos_arquivo_igual_validos_brancos_nulos": resumo_booleano(
                total_arquivo_fecha
            ),
        },
        "faltantes": nulos_por_coluna,
        "ressalva_tte": (
            "O catálogo do TSE informa 39 registros de eleitores em dupla vinculação de TTE. "
            "Nenhum valor foi subtraído das seções; os totais publicados foram preservados."
        ),
    }


def criar_qa_excecoes(secoes: pd.DataFrame) -> pd.DataFrame:
    """Materializa as seções que exigem interpretação cuidadosa no QA."""
    falha_balanco_aptos = secoes["aptos"] != (
        secoes["comparecimento"] + secoes["abstencao"]
    )
    sem_linha_nominal = secoes["soma_votos_arquivo"] == 0
    excecoes = secoes.loc[
        falha_balanco_aptos | sem_linha_nominal,
        CHAVE_SECAO
        + [
            "municipio_nome",
            "local_codigo",
            "local",
            "aptos",
            "comparecimento",
            "abstencao",
            "validos",
            "brancos",
            "nulos",
            "anulados_apu_sep",
            "secao_instalada",
            "secao_anulada",
        ],
    ].copy()
    excecoes["falha_aptos_igual_comparecimento_mais_abstencao"] = (
        falha_balanco_aptos.loc[excecoes.index]
    )
    excecoes["sem_linha_nominal_publicada"] = sem_linha_nominal.loc[excecoes.index]
    excecoes["delta_aptos"] = (
        excecoes["aptos"] - excecoes["comparecimento"] - excecoes["abstencao"]
    )
    excecoes["observacao"] = np.where(
        excecoes["falha_aptos_igual_comparecimento_mais_abstencao"],
        "Seção não instalada no exterior; aptos publicados sem comparecimento ou abstenção.",
        "Seção instalada no exterior, sem comparecimento e sem votação nominal.",
    )
    return excecoes.reset_index(drop=True)


def escrever_parquet_atomico(dataframe: pd.DataFrame, destino: Path) -> None:
    """Grava DataFrame em Parquet e troca o destino apenas após sucesso."""
    temporario = destino.with_suffix(destino.suffix + ".part")
    if temporario.exists():
        temporario.unlink()
    dataframe.to_parquet(
        temporario,
        engine="pyarrow",
        compression="zstd",
        index=False,
    )
    temporario.replace(destino)


def executar(args: argparse.Namespace) -> None:
    """Executa download, normalização e QA."""
    raiz = args.raiz.resolve()
    pasta_raw = raiz / "data" / "raw"
    pasta_processed = raiz / "data" / "processed"
    pasta_raw.mkdir(parents=True, exist_ok=True)
    pasta_processed.mkdir(parents=True, exist_ok=True)

    catalogo_path = pasta_raw / "catalogo_resultados_2026.json"
    metadados_download: list[dict[str, Any]] = []
    if args.skip_download:
        if not catalogo_path.exists():
            raise FileNotFoundError(f"Catálogo local ausente: {catalogo_path}")
        catalogo = json.loads(catalogo_path.read_text(encoding="utf-8"))
        for nome, url in RECURSOS.items():
            caminho = pasta_raw / nome
            if not caminho.exists():
                raise FileNotFoundError(f"Fonte bruta ausente: {caminho}")
            metadados_download.append(
                {
                    "url": url,
                    "arquivo": nome,
                    "bytes": caminho.stat().st_size,
                    "sha256": sha256_arquivo(caminho),
                    "acao": "reutilizado_local",
                }
            )
    else:
        with requests.Session() as sessao:
            sessao.headers.update({"User-Agent": "TSE-2026-ingest/1.0"})
            LOGGER.info("Baixando catálogo oficial")
            catalogo = baixar_json(sessao, CATALOGO_URL, catalogo_path)
            for nome, url in RECURSOS.items():
                LOGGER.info("Baixando %s", nome)
                metadados_download.append(baixar_zip(sessao, url, pasta_raw / nome))

    manifesto = criar_manifesto(pasta_raw, catalogo, metadados_download)
    manifesto_path = pasta_raw / "manifesto.json"
    manifesto_path.write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Preserva a versão vigente até a validação integral da candidata.
    votos_destino = pasta_processed / "votos.candidato.parquet"
    LOGGER.info("Normalizando votação nominal")
    meta_votos = escrever_votos(
        pasta_raw / "votacao_secao_2026_BR.zip",
        votos_destino,
        args.chunk_size,
    )
    LOGGER.info("Lendo detalhes por seção")
    detalhes, meta_detalhes = ler_detalhes(
        pasta_raw / "detalhe_votacao_secao_2026.zip",
        args.chunk_size,
    )
    LOGGER.info("Agregando votos e validando junção")
    votos_agregados = agregar_votos(votos_destino)
    secoes, qa_join = construir_secoes(detalhes, votos_agregados)

    qa = criar_qa(
        secoes,
        votos_destino,
        meta_votos,
        meta_detalhes,
        qa_join,
    )

    # Interrompe a promoção de dados inconsistentes, inclusive em futuras versões.
    falhas = []
    if qa["join"]["linhas_nominais_sem_detalhe"]:
        falhas.append("votos sem seção correspondente")
    if qa["unicidade"]["duplicatas_secoes"] or qa["unicidade"]["duplicatas_votos"]:
        falhas.append("chaves duplicadas")
    for nome_check, resultado_check in qa["checks"].items():
        if (
            nome_check != "aptos_igual_comparecimento_mais_abstencao"
            and resultado_check["divergentes"]
        ):
            falhas.append(nome_check)
    diferenca_aptos = secoes["aptos"] - secoes["comparecimento"] - secoes["abstencao"]
    excecao_nao_instalada = (
        secoes["uf"].eq("ZZ")
        & secoes["secao_instalada"].eq("Não")
        & secoes["comparecimento"].eq(0)
        & secoes["abstencao"].eq(0)
        & secoes["validos"].eq(0)
        & diferenca_aptos.ge(0)
    )
    if (diferenca_aptos.ne(0) & ~excecao_nao_instalada).any():
        falhas.append("aptos não reconciliados fora da exceção documentada")
    for coluna_contagem in [
        "aptos",
        "comparecimento",
        "abstencao",
        "validos",
        "brancos",
        "nulos",
        "lula",
        "bolsonaro",
        "outros",
    ]:
        if secoes[coluna_contagem].lt(0).any():
            falhas.append(f"contagem negativa: {coluna_contagem}")
    if falhas:
        raise ValueError(f"Base não promovida: {falhas}")
    qa["apto_para_analise"] = True
    qa_excecoes = criar_qa_excecoes(secoes)
    qa_excecoes.to_csv(
        pasta_processed / "qa_excecoes.csv",
        index=False,
        encoding="utf-8-sig",
    )

    ordem = [
        "turno",
        "uf",
        "municipio_codigo",
        "municipio_nome",
        "zona",
        "secao",
        "local_codigo",
        "local",
        "local_endereco",
        "aptos",
        "comparecimento",
        "abstencao",
        "validos",
        "brancos",
        "nulos",
        "anulados_apu_sep",
        "lula",
        "bolsonaro",
        "outros",
        "participacao",
        "lula_validos",
        "bolsonaro_validos",
        "lula_aptos",
        "bolsonaro_aptos",
        "secao_instalada",
        "secao_anulada",
    ]
    secoes = (
        secoes[ordem].sort_values(CHAVE_SECAO, kind="stable").reset_index(drop=True)
    )
    secoes_destino = pasta_processed / "secoes.parquet"
    escrever_parquet_atomico(secoes, secoes_destino)
    votos_destino.replace(pasta_processed / "votos.parquet")

    qa_path = pasta_processed / "qa_ingestao.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")

    LOGGER.info(
        "Concluído: %s seções, %s linhas nominais, turnos %s",
        f"{len(secoes):,}",
        f"{meta_votos['linhas']:,}",
        meta_votos["turnos"],
    )


def criar_parser() -> argparse.ArgumentParser:
    """Cria a interface de linha de comando."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raiz",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Raiz do projeto TSE",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Reutiliza ZIPs e catálogo já presentes em data/raw",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=250_000,
        help="Número de linhas por bloco de leitura",
    )
    return parser


def main() -> int:
    """Ponto de entrada do script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        executar(criar_parser().parse_args())
    except Exception:
        LOGGER.exception("Falha na ingestão")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
