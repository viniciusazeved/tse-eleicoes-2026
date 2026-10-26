"""Inspeciona atualização oficial do detalhe por seção sem promovê-la."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from ingest import iterar_csv_zip, sha256_arquivo

LOGGER = logging.getLogger("tse.inspect_details_update")

VERSAO = "20261026-123844"
RAIZ = Path(__file__).resolve().parents[1]
SOURCE_DEFAULT = (
    RAIZ / "data" / "raw" / "versoes" / VERSAO / "detalhe_votacao_secao_2026.zip"
)
OUT_DIR_DEFAULT = RAIZ / "data" / "interim" / VERSAO
QA_DEFAULT = RAIZ / "reports" / f"qa_detalhes_{VERSAO}.json"
ZONAS_TURNO2_DEFAULT = RAIZ / "data" / "processed" / "zonas_turno2.parquet"
SECOES_PUBLICADAS_DEFAULT = RAIZ / "data" / "processed" / "secoes.parquet"

MEMBRO_BR = "detalhe_votacao_secao_2026_BR.csv"
CHAVE_SECAO = ["turno", "uf", "municipio_codigo", "zona", "secao"]
CHAVE_ZONA = ["turno", "uf", "municipio_codigo", "zona"]
METRICAS = ["aptos", "comparecimento", "abstencao", "validos", "brancos", "nulos"]

COLUNAS_FONTE = [
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
    "NR_LOCAL_VOTACAO",
    "NM_LOCAL_VOTACAO",
    "DS_LOCAL_VOTACAO_ENDERECO",
    "ST_SECAO_INSTALADA",
    "ST_SECAO_ANULADA",
]


def agora_local() -> str:
    """Retorna timestamp local com fuso explícito."""
    return datetime.now().astimezone().isoformat()


def normalizar_inteiro_estrito(serie: pd.Series, nome: str) -> pd.Series:
    """Converte somente valores finitos e matematicamente inteiros."""
    texto = serie.astype("string").str.strip()
    numero = pd.to_numeric(texto, errors="coerce")
    invalido = numero.isna() | ~np.isfinite(numero) | numero.mod(1).ne(0)
    if invalido.any():
        exemplos = texto[invalido].drop_duplicates().head(5).tolist()
        raise ValueError(f"Valores inteiros inválidos em {nome}: {exemplos}")
    return numero.astype("int64")


def normalizar_codigo(serie: pd.Series, nome: str = "codigo") -> pd.Series:
    """Normaliza código integral como texto sem zeros à esquerda."""
    return normalizar_inteiro_estrito(serie, nome).astype("string")


def validar_fonte(caminho: Path) -> dict[str, Any]:
    """Confere existência, término do download e estrutura do ZIP."""
    if caminho.suffix.lower() == ".part" or caminho.name.endswith(".part"):
        raise ValueError("Arquivo .part não pode ser inspecionado")
    if not caminho.is_file():
        raise FileNotFoundError(f"Fonte não encontrada: {caminho}")
    if caminho.with_suffix(caminho.suffix + ".part").exists():
        raise RuntimeError(f"Download ainda possui arquivo .part ao lado de {caminho}")
    if not zipfile.is_zipfile(caminho):
        raise ValueError(f"Fonte não é ZIP válido: {caminho}")

    with zipfile.ZipFile(caminho) as arquivo_zip:
        teste = arquivo_zip.testzip()
        if teste is not None:
            raise ValueError(f"Membro corrompido no ZIP: {teste}")
        membros = [
            {
                "nome": info.filename,
                "bytes_descompactados": info.file_size,
                "bytes_comprimidos": info.compress_size,
            }
            for info in arquivo_zip.infolist()
        ]
        if MEMBRO_BR not in arquivo_zip.namelist():
            raise FileNotFoundError(f"Membro nacional ausente: {MEMBRO_BR}")

    stat = caminho.stat()
    return {
        "caminho": str(caminho),
        "bytes": stat.st_size,
        "sha256": sha256_arquivo(caminho),
        "modificado_em_local": datetime.fromtimestamp(
            stat.st_mtime, tz=datetime.now().astimezone().tzinfo
        ).isoformat(),
        "membros": membros,
    }


def carregar_detalhes(
    caminho: Path, chunk_size: int
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Carrega somente campos contábeis de Presidente."""
    partes: list[pd.DataFrame] = []
    anos: set[str] = set()
    tipos: set[tuple[str, str]] = set()
    eleicoes: set[tuple[str, str]] = set()
    cargos: set[tuple[str, str]] = set()
    geracoes: set[tuple[str, str]] = set()
    linhas_brutas = 0

    for bruto in iterar_csv_zip(caminho, MEMBRO_BR, COLUNAS_FONTE, chunk_size):
        linhas_brutas += len(bruto)
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
                bruto[["CD_ELEICAO", "DS_ELEICAO"]]
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
        geracoes.update(
            map(
                tuple,
                bruto[["DT_GERACAO", "HH_GERACAO"]]
                .drop_duplicates()
                .itertuples(index=False, name=None),
            )
        )

        presidente = bruto.loc[bruto["CD_CARGO"] == "1"].copy()
        if presidente.empty:
            continue
        partes.append(
            pd.DataFrame(
                {
                    "turno": normalizar_inteiro_estrito(
                        presidente["NR_TURNO"], "NR_TURNO"
                    ),
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
                    "aptos": normalizar_inteiro_estrito(
                        presidente["QT_APTOS"], "QT_APTOS"
                    ),
                    "comparecimento": normalizar_inteiro_estrito(
                        presidente["QT_COMPARECIMENTO"], "QT_COMPARECIMENTO"
                    ),
                    "abstencao": normalizar_inteiro_estrito(
                        presidente["QT_ABSTENCOES"], "QT_ABSTENCOES"
                    ),
                    "validos": normalizar_inteiro_estrito(
                        presidente["QT_VOTOS_NOMINAIS"], "QT_VOTOS_NOMINAIS"
                    ),
                    "brancos": normalizar_inteiro_estrito(
                        presidente["QT_VOTOS_BRANCOS"], "QT_VOTOS_BRANCOS"
                    ),
                    "nulos": normalizar_inteiro_estrito(
                        presidente["QT_VOTOS_NULOS"], "QT_VOTOS_NULOS"
                    ),
                    "secao_instalada": presidente["ST_SECAO_INSTALADA"],
                    "secao_anulada": presidente["ST_SECAO_ANULADA"],
                }
            )
        )

    if anos != {"2026"}:
        raise ValueError(f"ANO_ELEICAO inesperado: {sorted(anos)}")
    if tipos != {("2", "Eleição Ordinária")}:
        raise ValueError(f"Tipo de eleição inesperado: {sorted(tipos)}")
    if any(codigo != "1" or descricao != "Presidente" for codigo, descricao in cargos):
        raise ValueError(f"Cargo inesperado no membro nacional: {sorted(cargos)}")
    if not partes:
        raise ValueError("Nenhum registro de Presidente encontrado")

    detalhes = pd.concat(partes, ignore_index=True)
    metadados = {
        "linhas_brutas": linhas_brutas,
        "linhas_presidente": len(detalhes),
        "anos": sorted(anos),
        "tipos_eleicao": sorted([list(item) for item in tipos]),
        "eleicoes": sorted([list(item) for item in eleicoes]),
        "cargos": sorted([list(item) for item in cargos]),
        "geracoes": sorted([list(item) for item in geracoes]),
        "turnos": sorted(detalhes["turno"].unique().tolist()),
    }
    return detalhes, metadados


def resumo_mascara(mascara: pd.Series) -> dict[str, int]:
    """Resume conformidade booleana."""
    return {
        "conformes": int(mascara.sum()),
        "divergentes": int((~mascara).sum()),
    }


def exemplos_linhas(
    dataframe: pd.DataFrame, mascara: pd.Series, limite: int = 20
) -> list[dict[str, Any]]:
    """Converte amostra de linhas divergentes para JSON."""
    return (
        dataframe.loc[mascara]
        .head(limite)
        .replace({np.nan: None})
        .to_dict(orient="records")
    )


def qa_estrutura(detalhes: pd.DataFrame) -> dict[str, Any]:
    """Verifica chaves, balanços e situações das seções."""
    duplicada = detalhes.duplicated(CHAVE_SECAO, keep=False)
    balanco_aptos = detalhes["aptos"] == (
        detalhes["comparecimento"] + detalhes["abstencao"]
    )
    balanco_votos = detalhes["comparecimento"] == (
        detalhes["validos"] + detalhes["brancos"] + detalhes["nulos"]
    )
    nao_negativo = (detalhes[METRICAS] >= 0).all(axis=1)
    participacao_valida = detalhes["comparecimento"] <= detalhes["aptos"]

    por_turno = {}
    for turno, grupo in detalhes.groupby("turno", sort=True):
        por_turno[str(int(turno))] = {
            "secoes": len(grupo),
            "ufs": sorted(grupo["uf"].unique().tolist()),
            "municipios": int(
                grupo[["uf", "municipio_codigo"]].drop_duplicates().shape[0]
            ),
            "zonas": int(grupo[CHAVE_ZONA].drop_duplicates().shape[0]),
            "totais": {coluna: int(grupo[coluna].sum()) for coluna in METRICAS},
            "situacao_instalada": {
                str(chave): int(valor)
                for chave, valor in grupo["secao_instalada"]
                .value_counts(dropna=False)
                .items()
            },
            "situacao_anulada": {
                str(chave): int(valor)
                for chave, valor in grupo["secao_anulada"]
                .value_counts(dropna=False)
                .items()
            },
        }

    colunas_exemplo = CHAVE_SECAO + METRICAS + ["secao_instalada", "secao_anulada"]
    return {
        "chave": CHAVE_SECAO,
        "duplicatas": int(duplicada.sum()),
        "duplicatas_exemplos": exemplos_linhas(detalhes[colunas_exemplo], duplicada),
        "faltantes": {
            coluna: int(detalhes[coluna].isna().sum()) for coluna in detalhes.columns
        },
        "checks": {
            "aptos_igual_comparecimento_mais_abstencao": resumo_mascara(balanco_aptos),
            "comparecimento_igual_validos_mais_brancos_mais_nulos": resumo_mascara(
                balanco_votos
            ),
            "metricas_nao_negativas": resumo_mascara(nao_negativo),
            "comparecimento_menor_ou_igual_aptos": resumo_mascara(participacao_valida),
        },
        "excecoes_aptos": exemplos_linhas(detalhes[colunas_exemplo], ~balanco_aptos),
        "excecoes_votos": exemplos_linhas(detalhes[colunas_exemplo], ~balanco_votos),
        "por_turno": por_turno,
    }


def qa_exterior(detalhes: pd.DataFrame) -> dict[str, Any]:
    """Resume separadamente as seções do exterior."""
    exterior = detalhes.loc[detalhes["uf"] == "ZZ"].copy()
    balanco_aptos = exterior["aptos"] == (
        exterior["comparecimento"] + exterior["abstencao"]
    )
    balanco_votos = exterior["comparecimento"] == (
        exterior["validos"] + exterior["brancos"] + exterior["nulos"]
    )
    return {
        "linhas": len(exterior),
        "por_turno": {
            str(int(turno)): {
                "secoes": len(grupo),
                "aptos": int(grupo["aptos"].sum()),
                "comparecimento": int(grupo["comparecimento"].sum()),
                "abstencao": int(grupo["abstencao"].sum()),
                "nao_instaladas": int((grupo["secao_instalada"] != "Sim").sum()),
            }
            for turno, grupo in exterior.groupby("turno", sort=True)
        },
        "aptos_divergentes": int((~balanco_aptos).sum()),
        "votos_divergentes": int((~balanco_votos).sum()),
    }


def preparar_comparacao(dataframe: pd.DataFrame, chave: list[str]) -> pd.DataFrame:
    """Normaliza tipos dos campos usados em reconciliação."""
    resultado = dataframe[chave + METRICAS].copy()
    resultado["turno"] = normalizar_inteiro_estrito(resultado["turno"], "turno")
    resultado["uf"] = resultado["uf"].astype("string").str.strip()
    for coluna in [item for item in chave if item not in {"turno", "uf"}]:
        resultado[coluna] = normalizar_codigo(resultado[coluna], coluna)
    for coluna in METRICAS:
        resultado[coluna] = normalizar_inteiro_estrito(resultado[coluna], coluna)
    return resultado


def reconciliar(
    esquerda: pd.DataFrame,
    direita: pd.DataFrame,
    chave: list[str],
    nome_esquerda: str,
    nome_direita: str,
) -> dict[str, Any]:
    """Compara chaves e métricas contábeis entre duas fontes."""
    combinado = esquerda.merge(
        direita,
        on=chave,
        how="outer",
        suffixes=(f"_{nome_esquerda}", f"_{nome_direita}"),
        indicator=True,
        validate="one_to_one",
    )
    apenas_esquerda = combinado["_merge"] == "left_only"
    apenas_direita = combinado["_merge"] == "right_only"
    ambos = combinado["_merge"] == "both"

    metricas = {}
    divergencia_qualquer = pd.Series(False, index=combinado.index)
    for metrica in METRICAS:
        coluna_esquerda = f"{metrica}_{nome_esquerda}"
        coluna_direita = f"{metrica}_{nome_direita}"
        delta = combinado[coluna_esquerda] - combinado[coluna_direita]
        divergente = ambos & delta.ne(0)
        divergencia_qualquer |= divergente
        metricas[metrica] = {
            "divergentes": int(divergente.sum()),
            "soma_delta": int(delta.loc[ambos].sum()),
            "max_abs_delta": int(delta.loc[ambos].abs().max()) if ambos.any() else None,
        }

    colunas_exemplo = chave.copy()
    for metrica in METRICAS:
        colunas_exemplo.extend(
            [f"{metrica}_{nome_esquerda}", f"{metrica}_{nome_direita}"]
        )
    return {
        "chave": chave,
        "linhas_esquerda": len(esquerda),
        "linhas_direita": len(direita),
        "chaves_em_ambas": int(ambos.sum()),
        "apenas_esquerda": int(apenas_esquerda.sum()),
        "apenas_direita": int(apenas_direita.sum()),
        "linhas_com_alguma_divergencia": int(divergencia_qualquer.sum()),
        "metricas": metricas,
        "exemplos_apenas_esquerda": exemplos_linhas(combinado[chave], apenas_esquerda),
        "exemplos_apenas_direita": exemplos_linhas(combinado[chave], apenas_direita),
        "exemplos_divergencias": exemplos_linhas(
            combinado[colunas_exemplo], divergencia_qualquer
        ),
    }


def reconciliar_turno2(detalhes: pd.DataFrame, caminho_zonas: Path) -> dict[str, Any]:
    """Reconcilia o segundo turno agregado por município e zona."""
    colunas = CHAVE_ZONA + METRICAS
    detalhe_turno2 = detalhes.loc[detalhes["turno"] == 2, colunas]
    detalhe_zona = detalhe_turno2.groupby(CHAVE_ZONA, as_index=False)[METRICAS].sum()
    zonas = pd.read_parquet(caminho_zonas, columns=colunas)
    zonas = zonas.loc[pd.to_numeric(zonas["turno"], errors="coerce") == 2]
    return reconciliar(
        preparar_comparacao(detalhe_zona, CHAVE_ZONA),
        preparar_comparacao(zonas, CHAVE_ZONA),
        CHAVE_ZONA,
        "detalhe",
        "zonas",
    )


def reconciliar_turno1(detalhes: pd.DataFrame, caminho_secoes: Path) -> dict[str, Any]:
    """Confere o primeiro turno contra o detalhe já publicado."""
    colunas = CHAVE_SECAO + METRICAS
    detalhe_turno1 = detalhes.loc[detalhes["turno"] == 1, colunas]
    publicadas = pd.read_parquet(caminho_secoes, columns=colunas)
    publicadas = publicadas.loc[
        pd.to_numeric(publicadas["turno"], errors="coerce") == 1
    ]
    return reconciliar(
        preparar_comparacao(detalhe_turno1, CHAVE_SECAO),
        preparar_comparacao(publicadas, CHAVE_SECAO),
        CHAVE_SECAO,
        "atualizado",
        "publicado",
    )


def escrever_parquet_atomico(dataframe: pd.DataFrame, destino: Path) -> None:
    """Grava Parquet de staging sem substituir arquivo válido em caso de falha."""
    temporario = destino.with_suffix(destino.suffix + ".part")
    if temporario.exists():
        temporario.unlink()
    dataframe.to_parquet(temporario, index=False, compression="zstd")
    temporario.replace(destino)


def escrever_json_atomico(objeto: dict[str, Any], destino: Path) -> None:
    """Grava relatório JSON em UTF-8 de forma atômica."""
    temporario = destino.with_suffix(destino.suffix + ".part")
    if temporario.exists():
        temporario.unlink()
    temporario.write_text(
        json.dumps(objeto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporario.replace(destino)


def executar(args: argparse.Namespace) -> dict[str, Any]:
    """Executa inspeção contábil da versão atualizada."""
    fonte = args.source.resolve()
    out_dir = args.out_dir.resolve()
    qa_destino = args.qa.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    qa_destino.parent.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Validando ZIP %s", fonte)
    fonte_meta = validar_fonte(fonte)
    LOGGER.info("Lendo detalhe nacional em blocos")
    detalhes, conteudo_meta = carregar_detalhes(fonte, args.chunk_size)

    staging_destino = out_dir / "detalhes_presidente.parquet"
    escrever_parquet_atomico(detalhes, staging_destino)

    estrutura = qa_estrutura(detalhes)
    exterior = qa_exterior(detalhes)
    LOGGER.info("Reconciliando segundo turno por município e zona")
    turno2 = reconciliar_turno2(detalhes, args.zonas_turno2.resolve())
    LOGGER.info("Conferindo integridade do primeiro turno publicado")
    turno1 = reconciliar_turno1(detalhes, args.secoes_publicadas.resolve())

    relatorio = {
        "gerado_em": agora_local(),
        "gerado_em_utc": datetime.now(UTC).isoformat(),
        "escopo": (
            "Inspeção estrutural, contábil e de disponibilidade. Nenhum campo nominal "
            "de candidato foi lido ou analisado."
        ),
        "fonte": fonte_meta,
        "conteudo": conteudo_meta,
        "staging": {
            "caminho": str(staging_destino),
            "linhas": len(detalhes),
            "promovido": False,
        },
        "estrutura": estrutura,
        "exterior": exterior,
        "reconciliacao_turno2_zonas": turno2,
        "integridade_turno1_publicado": turno1,
        "limites": [
            "A inspeção não usa votação nominal nem compara candidaturas.",
            "O staging não substitui os arquivos publicados.",
            "A reconciliação do segundo turno usa somente métricas contábeis agregadas.",
        ],
    }
    escrever_json_atomico(relatorio, qa_destino)
    LOGGER.info("Relatório gravado em %s", qa_destino)
    return relatorio


def criar_parser() -> argparse.ArgumentParser:
    """Cria argumentos de linha de comando."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT)
    parser.add_argument("--qa", type=Path, default=QA_DEFAULT)
    parser.add_argument("--zonas-turno2", type=Path, default=ZONAS_TURNO2_DEFAULT)
    parser.add_argument(
        "--secoes-publicadas", type=Path, default=SECOES_PUBLICADAS_DEFAULT
    )
    parser.add_argument("--chunk-size", type=int, default=250_000)
    return parser


def main() -> int:
    """Ponto de entrada."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        executar(criar_parser().parse_args())
    except Exception:
        LOGGER.exception("Falha na inspeção do detalhe atualizado")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
