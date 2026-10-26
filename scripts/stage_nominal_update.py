"""Integra versão nominal atualizada em staging e executa QA rastreável."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fetch_zonas import extrair
from ingest import (
    CHAVE_SECAO,
    agregar_votos,
    construir_secoes,
    criar_qa,
    criar_qa_excecoes,
    escrever_parquet_atomico,
    escrever_votos,
    ler_detalhes,
    normalizar_codigo,
    normalizar_inteiro,
    sha256_arquivo,
)

LOGGER = logging.getLogger("tse.stage_nominal_update")
RAIZ = Path(__file__).resolve().parents[1]
VERSAO = "20261026-144303"
VOTOS_DEFAULT = RAIZ / "data/raw/versoes" / VERSAO / "votacao_secao_2026_BR.zip"
DETALHES_DEFAULT = (
    RAIZ / "data/raw/versoes/20261026-123844" / "detalhe_votacao_secao_2026.zip"
)
OUT_DIR_DEFAULT = RAIZ / "data/interim" / VERSAO
QA_DEFAULT = RAIZ / "reports" / f"qa_integracao_{VERSAO}.json"
SECOES_ANTERIORES_DEFAULT = RAIZ / "data/processed/secoes.parquet"
ZONAS_TURNO2_DEFAULT = RAIZ / "data/processed/zonas_turno2.parquet"
JSON_ZONAS_DEFAULT = RAIZ / "data/raw/api_turno2/zonas"

CHAVE_ZONA = ["turno", "uf", "municipio_codigo", "zona"]
METRICAS = [
    "aptos",
    "comparecimento",
    "abstencao",
    "validos",
    "brancos",
    "nulos",
    "lula",
    "bolsonaro",
    "outros",
]
ORDEM_SECOES = [
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


def validar_zip(caminho: Path, membro: str) -> dict[str, Any]:
    """Rejeita download parcial e registra identidade do ZIP."""
    if caminho.name.endswith(".part"):
        raise ValueError(f"Fonte parcial recusada: {caminho}")
    if not caminho.is_file():
        raise FileNotFoundError(caminho)
    if caminho.with_suffix(caminho.suffix + ".part").exists():
        raise RuntimeError(f"Há download .part ao lado da fonte: {caminho}")
    if not zipfile.is_zipfile(caminho):
        raise ValueError(f"ZIP inválido: {caminho}")
    with zipfile.ZipFile(caminho) as arquivo_zip:
        if membro not in arquivo_zip.namelist():
            raise FileNotFoundError(f"Membro ausente: {membro}")
        info = arquivo_zip.getinfo(membro)
    manifesto_path = caminho.parent / "manifesto.json"
    if not manifesto_path.is_file():
        raise FileNotFoundError(f"Manifesto adjacente ausente: {manifesto_path}")
    manifesto = json.loads(manifesto_path.read_text(encoding="utf-8"))
    sha256 = sha256_arquivo(caminho)
    if manifesto.get("bytes") != caminho.stat().st_size:
        raise ValueError(f"Tamanho diverge do manifesto: {caminho}")
    if str(manifesto.get("sha256", "")).lower() != sha256:
        raise ValueError(f"SHA256 diverge do manifesto: {caminho}")
    return {
        "caminho": str(caminho),
        "fonte_efetiva_versionada": str(caminho),
        "raw_nao_versionado_usado": False,
        "bytes": caminho.stat().st_size,
        "sha256": sha256,
        "membro": membro,
        "membro_bytes_descompactados": info.file_size,
        "manifesto_adjacente": str(manifesto_path),
        "manifesto": manifesto,
    }


def preparar(dataframe: pd.DataFrame, chave: list[str]) -> pd.DataFrame:
    """Normaliza chaves e contagens para comparação exata."""
    resultado = dataframe[chave + METRICAS].copy()
    resultado["turno"] = normalizar_inteiro(resultado["turno"], "turno")
    resultado["uf"] = resultado["uf"].astype("string").str.strip().str.upper()
    for coluna in [item for item in chave if item not in {"turno", "uf"}]:
        resultado[coluna] = normalizar_codigo(resultado[coluna], coluna)
    for metrica in METRICAS:
        resultado[metrica] = normalizar_inteiro(resultado[metrica], metrica)
    return resultado


def reconciliar(
    esquerda: pd.DataFrame,
    direita: pd.DataFrame,
    chave: list[str],
    rotulo_esquerda: str,
    rotulo_direita: str,
) -> dict[str, Any]:
    """Reconcilia chaves e nove métricas, incluindo votos nominais."""
    if esquerda.duplicated(chave).any() or direita.duplicated(chave).any():
        raise ValueError("Chave duplicada antes da reconciliação")
    combinado = esquerda.merge(
        direita,
        on=chave,
        how="outer",
        suffixes=(f"_{rotulo_esquerda}", f"_{rotulo_direita}"),
        indicator=True,
        validate="one_to_one",
    )
    ambos = combinado["_merge"].eq("both")
    divergencia = pd.Series(False, index=combinado.index)
    metricas: dict[str, Any] = {}
    for metrica in METRICAS:
        a = f"{metrica}_{rotulo_esquerda}"
        b = f"{metrica}_{rotulo_direita}"
        delta = combinado[a] - combinado[b]
        mascara = ambos & delta.ne(0)
        divergencia |= mascara
        metricas[metrica] = {
            "divergentes": int(mascara.sum()),
            "soma_delta": int(delta.loc[ambos].sum()),
            "max_abs_delta": int(delta.loc[ambos].abs().max()) if ambos.any() else None,
        }
    exemplos = combinado.loc[divergencia, chave].head(20).to_dict(orient="records")
    return {
        "chave": chave,
        "linhas_esquerda": len(esquerda),
        "linhas_direita": len(direita),
        "chaves_em_ambas": int(ambos.sum()),
        "apenas_esquerda": int(combinado["_merge"].eq("left_only").sum()),
        "apenas_direita": int(combinado["_merge"].eq("right_only").sum()),
        "linhas_com_divergencia": int(divergencia.sum()),
        "metricas": metricas,
        "exemplos_divergencia": exemplos,
    }


def carregar_json_zonas(pasta: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Relê os JSONs oficiais arquivados e calcula hash combinado."""
    padrao = re.compile(
        r"^(?P<uf>[a-z]{2})(?P<municipio>\d+)-z(?P<zona>\d+)-c0001-e006258-u\.json$"
    )
    linhas: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    arquivos = sorted(
        caminho
        for caminho in pasta.glob("*/*.json")
        if not caminho.name.endswith(".meta.json")
    )
    for caminho in arquivos:
        correspondencia = padrao.fullmatch(caminho.name)
        if correspondencia is None:
            raise ValueError(f"Nome de JSON inesperado: {caminho}")
        conteudo = caminho.read_bytes()
        relativo = caminho.relative_to(pasta).as_posix().encode("utf-8")
        digest.update(len(relativo).to_bytes(4, "big"))
        digest.update(relativo)
        digest.update(hashlib.sha256(conteudo).digest())
        objeto = json.loads(conteudo)
        linha, _ = extrair(objeto, "zona")
        linha.update(
            uf=correspondencia["uf"].upper(),
            municipio_codigo=correspondencia["municipio"],
            zona=correspondencia["zona"],
        )
        linhas.append(linha)
    dataframe = pd.DataFrame(linhas)
    return dataframe, {
        "pasta": str(pasta),
        "arquivos": len(arquivos),
        "sha256_combinado_caminhos_e_conteudos": digest.hexdigest(),
    }


def validar_candidatos(meta_votos: dict[str, Any]) -> dict[str, Any]:
    """Confere números especiais e finalistas do segundo turno."""
    por_turno = meta_votos["candidatos_por_turno"]
    mapa_turno2 = por_turno.get("2", {})
    esperados = {"13", "22", "95", "96"}
    nomes = {
        numero: " | ".join(valores).upper() for numero, valores in mapa_turno2.items()
    }
    identidade_ok = (
        "LUIZ INÁCIO LULA DA SILVA" in nomes.get("13", "")
        and "FLAVIO NANTES BOLSONARO" in nomes.get("22", "")
        and "VOTO BRANCO" in nomes.get("95", "")
        and "VOTO NULO" in nomes.get("96", "")
    )
    return {
        "numeros_turno2": sorted(mapa_turno2),
        "numeros_esperados_turno2": sorted(esperados),
        "faltantes_turno2": sorted(esperados - set(mapa_turno2)),
        "extras_turno2": sorted(set(mapa_turno2) - esperados),
        "identidades_turno2_conferidas": identidade_ok,
        "mapeamento_por_turno": por_turno,
    }


def escrever_json_atomico(objeto: dict[str, Any], destino: Path) -> None:
    """Grava JSON de QA sem deixar resultado parcial."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(destino.suffix + ".part")
    temporario.write_text(
        json.dumps(objeto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporario.replace(destino)


def executar(args: argparse.Namespace) -> dict[str, Any]:
    """Produz integração em staging e reconciliações independentes."""
    source_votos = args.source_votos.resolve()
    source_detalhes = args.source_detalhes.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    fonte_votos = validar_zip(source_votos, "votacao_secao_2026_BR.csv")
    fonte_detalhes = validar_zip(source_detalhes, "detalhe_votacao_secao_2026_BR.csv")
    votos_path = out_dir / "votos.parquet"
    LOGGER.info("Normalizando votação nominal em staging")
    meta_votos = escrever_votos(source_votos, votos_path, args.chunk_size)
    LOGGER.info("Lendo detalhe auditado")
    detalhes, meta_detalhes = ler_detalhes(source_detalhes, args.chunk_size)
    LOGGER.info("Pareando detalhe e votação por seção")
    agregados = agregar_votos(votos_path)
    secoes_com_qa, qa_join = construir_secoes(detalhes, agregados)
    qa_base = criar_qa(secoes_com_qa, votos_path, meta_votos, meta_detalhes, qa_join)
    candidatos = validar_candidatos(meta_votos)

    atual_t1 = preparar(secoes_com_qa.loc[secoes_com_qa["turno"].eq(1)], CHAVE_SECAO)
    anterior = pd.read_parquet(args.secoes_anteriores.resolve())
    anterior_t1 = preparar(anterior.loc[anterior["turno"].eq(1)], CHAVE_SECAO)
    reconciliacao_t1 = reconciliar(
        atual_t1, anterior_t1, CHAVE_SECAO, "atual", "anterior"
    )

    atual_t2 = preparar(
        secoes_com_qa.loc[secoes_com_qa["turno"].eq(2)]
        .groupby(CHAVE_ZONA, as_index=False)[METRICAS]
        .sum(),
        CHAVE_ZONA,
    )
    zonas = pd.read_parquet(args.zonas_turno2.resolve())
    zonas_t2 = preparar(zonas.loc[zonas["turno"].eq(2)], CHAVE_ZONA)
    reconciliacao_t2_zonas = reconciliar(
        atual_t2, zonas_t2, CHAVE_ZONA, "secoes", "zonas"
    )
    json_zonas, fonte_json = carregar_json_zonas(args.json_zonas.resolve())
    json_t2 = preparar(json_zonas, CHAVE_ZONA)
    reconciliacao_t2_json = reconciliar(atual_t2, json_t2, CHAVE_ZONA, "secoes", "json")

    turnos_ok = meta_votos["turnos"] == [1, 2] and meta_detalhes["turnos"] == [1, 2]
    eleicoes_ok = meta_votos["eleicoes"] == meta_detalhes["eleicoes"]
    cobertura_ok = qa_base["cobertura"]["secoes_por_turno"] == {
        "1": 499248,
        "2": 499248,
    }
    candidatos_ok = (
        not candidatos["faltantes_turno2"]
        and not candidatos["extras_turno2"]
        and candidatos["identidades_turno2_conferidas"]
    )
    reconciliacoes = [
        reconciliacao_t1,
        reconciliacao_t2_zonas,
        reconciliacao_t2_json,
    ]
    reconciliacoes_ok = all(
        item["apenas_esquerda"] == 0
        and item["apenas_direita"] == 0
        and item["linhas_com_divergencia"] == 0
        for item in reconciliacoes
    )
    checks_base_ok = all(
        nome == "aptos_igual_comparecimento_mais_abstencao"
        or resultado["divergentes"] == 0
        for nome, resultado in qa_base["checks"].items()
    )
    aptos_excecao = qa_base["checks"]["aptos_igual_comparecimento_mais_abstencao"][
        "divergentes"
    ]
    mascara_aptos = secoes_com_qa["aptos"].ne(
        secoes_com_qa["comparecimento"] + secoes_com_qa["abstencao"]
    )
    excecoes_aptos = secoes_com_qa.loc[mascara_aptos]
    aptos_por_turno = {
        str(int(turno)): int(total)
        for turno, total in excecoes_aptos.groupby("turno").size().items()
    }
    aptos_ok = bool(
        aptos_excecao == 82
        and aptos_por_turno == {"1": 41, "2": 41}
        and excecoes_aptos["uf"].eq("ZZ").all()
        and excecoes_aptos["secao_instalada"].eq("Não").all()
        and excecoes_aptos["comparecimento"].eq(0).all()
        and excecoes_aptos["abstencao"].eq(0).all()
    )
    mascara_sem_nominal = secoes_com_qa["soma_votos_arquivo"].eq(0)
    secoes_sem_nominal = secoes_com_qa.loc[mascara_sem_nominal]
    sem_nominal_por_turno = {
        str(int(turno)): int(total)
        for turno, total in secoes_sem_nominal.groupby("turno").size().items()
    }
    join_ok = bool(
        qa_join["linhas_nominais_sem_detalhe"] == 0
        and qa_join["detalhes_sem_linhas_nominais"] == 85
        and len(secoes_sem_nominal) == 85
        and sem_nominal_por_turno == {"1": 42, "2": 43}
        and secoes_sem_nominal["uf"].eq("ZZ").all()
        and secoes_sem_nominal["comparecimento"].eq(0).all()
    )
    unicidade_ok = bool(
        qa_base["unicidade"]["duplicatas_secoes"] == 0
        and qa_base["unicidade"]["duplicatas_votos"] == 0
    )
    contagens_nao_negativas = bool(
        secoes_com_qa[METRICAS].ge(0).all(axis=None)
        and meta_votos["qt_votos_minimo"] >= 0
    )

    qa = {
        "gerado_em": datetime.now().astimezone().isoformat(),
        "gerado_em_utc": datetime.now(UTC).isoformat(),
        "comando": " ".join(sys.argv),
        "comando_reproducao": (
            "uv run python scripts/stage_nominal_update.py "
            f'--source-votos "{source_votos}" '
            f'--source-detalhes "{source_detalhes}" '
            f'--out-dir "{out_dir}" '
            f'--qa "{args.qa.resolve()}" '
            f'--secoes-anteriores "{args.secoes_anteriores.resolve()}" '
            f'--zonas-turno2 "{args.zonas_turno2.resolve()}" '
            f'--json-zonas "{args.json_zonas.resolve()}" '
            f"--chunk-size {args.chunk_size}"
        ),
        "fontes": {
            "votacao": fonte_votos,
            "detalhe": fonte_detalhes,
            "json_zonas": fonte_json,
        },
        "metadados_votacao": meta_votos,
        "metadados_detalhe": meta_detalhes,
        "candidatos": candidatos,
        "qa_base": qa_base,
        "reconciliacao_primeiro_turno": reconciliacao_t1,
        "reconciliacao_segundo_turno_zonas": reconciliacao_t2_zonas,
        "reconciliacao_segundo_turno_json": reconciliacao_t2_json,
        "checks_integracao": {
            "ambos_turnos": turnos_ok,
            "eleicoes_coincidem_entre_fontes": eleicoes_ok,
            "cobertura_499248_por_turno": cobertura_ok,
            "candidatos_turno2": candidatos_ok,
            "checks_contabeis": checks_base_ok,
            "contagens_nao_negativas": contagens_nao_negativas,
            "chaves_unicas": unicidade_ok,
            "pareamento_nominal_detalhe": join_ok,
            "excecoes_aptos_esperadas_41_por_turno": aptos_ok,
            "reconciliacoes_integrais": reconciliacoes_ok,
        },
        "politica_ausencia_zero": (
            "A fonte nominal contém somente QT_VOTOS positivo. Ausências são convertidas "
            "em zero apenas na tabela larga após reconciliação integral de válidos, brancos "
            "e nulos com o detalhe; votos.parquet conserva apenas linhas publicadas."
        ),
        "caracterizacao_excecoes": {
            "aptos_por_turno": aptos_por_turno,
            "sem_linha_nominal_por_turno": sem_nominal_por_turno,
            "aptos_apenas_zz_nao_instaladas_comparecimento_e_abstencao_zero": aptos_ok,
            "sem_nominal_apenas_zz_e_comparecimento_zero": join_ok,
        },
        "staging": {
            "diretorio": str(out_dir),
            "promovido": False,
        },
        "limites": [
            "Dados permanecem em staging até revisão independente.",
            "A integração não identifica causalidade, autoria do voto ou fraude.",
            "As 41 seções não instaladas no exterior por turno permanecem sem abstenção fabricada.",
        ],
    }
    qa["apto_para_revisao_independente"] = all(qa["checks_integracao"].values())

    secoes = (
        secoes_com_qa[ORDEM_SECOES]
        .sort_values(CHAVE_SECAO, kind="stable")
        .reset_index(drop=True)
    )
    escrever_parquet_atomico(secoes, out_dir / "secoes.parquet")
    criar_qa_excecoes(secoes_com_qa).to_csv(
        out_dir / "qa_excecoes.csv", index=False, encoding="utf-8-sig"
    )
    escrever_json_atomico(qa, out_dir / "qa_integracao.json")
    escrever_json_atomico(
        {
            "gerado_em": qa["gerado_em"],
            "votacao": fonte_votos,
            "detalhe": fonte_detalhes,
        },
        out_dir / "fontes.json",
    )
    escrever_json_atomico(qa, args.qa.resolve())
    if not qa["apto_para_revisao_independente"]:
        raise ValueError(
            "Integração em staging contém falha de QA; consultar relatório"
        )
    return qa


def revalidar_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    """Reemite o QA a partir dos Parquets fechados, sem reescrevê-los."""
    source_votos = args.source_votos.resolve()
    source_detalhes = args.source_detalhes.resolve()
    out_dir = args.out_dir.resolve()
    votos_path = out_dir / "votos.parquet"
    secoes_path = out_dir / "secoes.parquet"
    qa_path = out_dir / "qa_integracao.json"
    for caminho in (votos_path, secoes_path, qa_path):
        if not caminho.is_file():
            raise FileNotFoundError(caminho)

    anterior = json.loads(qa_path.read_text(encoding="utf-8"))
    fonte_votos = validar_zip(source_votos, "votacao_secao_2026_BR.csv")
    fonte_detalhes = validar_zip(source_detalhes, "detalhe_votacao_secao_2026_BR.csv")
    secoes = pd.read_parquet(secoes_path)
    votos = pd.read_parquet(votos_path)

    duplicatas_secoes = int(secoes.duplicated(CHAVE_SECAO).sum())
    chave_votos = CHAVE_SECAO + ["numero"]
    duplicatas_votos = int(votos.duplicated(chave_votos).sum())
    unicidade_ok = duplicatas_secoes == 0 and duplicatas_votos == 0

    chaves_com_votos = votos[CHAVE_SECAO].drop_duplicates()
    join = secoes[CHAVE_SECAO].merge(
        chaves_com_votos,
        on=CHAVE_SECAO,
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    sem_nominal_chaves = join.loc[join["_merge"].eq("left_only"), CHAVE_SECAO]
    sem_detalhe = int(join["_merge"].eq("right_only").sum())
    secoes_sem_nominal = secoes.merge(
        sem_nominal_chaves,
        on=CHAVE_SECAO,
        how="inner",
        validate="one_to_one",
    )
    sem_nominal_por_turno = {
        str(int(turno)): int(total)
        for turno, total in secoes_sem_nominal.groupby("turno").size().items()
    }
    join_ok = bool(
        sem_detalhe == 0
        and len(secoes_sem_nominal) == 85
        and sem_nominal_por_turno == {"1": 42, "2": 43}
        and secoes_sem_nominal["uf"].eq("ZZ").all()
        and secoes_sem_nominal["comparecimento"].eq(0).all()
    )

    mascara_aptos = secoes["aptos"].ne(secoes["comparecimento"] + secoes["abstencao"])
    excecoes_aptos = secoes.loc[mascara_aptos]
    aptos_por_turno = {
        str(int(turno)): int(total)
        for turno, total in excecoes_aptos.groupby("turno").size().items()
    }
    aptos_ok = bool(
        len(excecoes_aptos) == 82
        and aptos_por_turno == {"1": 41, "2": 41}
        and excecoes_aptos["uf"].eq("ZZ").all()
        and excecoes_aptos["secao_instalada"].eq("Não").all()
        and excecoes_aptos["comparecimento"].eq(0).all()
        and excecoes_aptos["abstencao"].eq(0).all()
    )

    votos_agregados = agregar_votos(votos_path)
    votos_agregados = votos_agregados.rename(
        columns={
            "lula": "lula_votos",
            "bolsonaro": "bolsonaro_votos",
            "outros": "outros_votos",
        }
    )
    metricas_nominais = ["validos", "brancos", "nulos", "lula", "bolsonaro", "outros"]
    conferir_votos = secoes[CHAVE_SECAO + metricas_nominais].merge(
        votos_agregados[
            CHAVE_SECAO
            + [
                "validos_votos",
                "brancos_votos",
                "nulos_votos",
                "lula_votos",
                "bolsonaro_votos",
                "outros_votos",
            ]
        ],
        on=CHAVE_SECAO,
        how="left",
        validate="one_to_one",
    )
    colunas_votos_agregados = [f"{metrica}_votos" for metrica in metricas_nominais]
    conferir_votos[colunas_votos_agregados] = (
        conferir_votos[colunas_votos_agregados].fillna(0).astype("int64")
    )
    contabilidade_ok = bool(
        secoes["comparecimento"]
        .eq(
            secoes["validos"]
            + secoes["brancos"]
            + secoes["nulos"]
            + secoes["anulados_apu_sep"]
        )
        .all()
        and secoes["validos"]
        .eq(secoes["lula"] + secoes["bolsonaro"] + secoes["outros"])
        .all()
        and conferir_votos["validos"].eq(conferir_votos["validos_votos"]).all()
        and conferir_votos["brancos"].eq(conferir_votos["brancos_votos"]).all()
        and conferir_votos["nulos"].eq(conferir_votos["nulos_votos"]).all()
        and conferir_votos["lula"].eq(conferir_votos["lula_votos"]).all()
        and conferir_votos["bolsonaro"].eq(conferir_votos["bolsonaro_votos"]).all()
        and conferir_votos["outros"].eq(conferir_votos["outros_votos"]).all()
    )
    contagens_nao_negativas = bool(
        secoes[METRICAS].ge(0).all(axis=None) and votos["votos"].ge(0).all()
    )

    mapa_por_turno: dict[str, dict[str, list[str]]] = {}
    for (turno, numero), grupo in votos.groupby(["turno", "numero"], sort=True):
        mapa_por_turno.setdefault(str(int(turno)), {})[str(numero)] = sorted(
            grupo["nome"].unique().tolist()
        )
    candidatos = validar_candidatos({"candidatos_por_turno": mapa_por_turno})
    candidatos_ok = bool(
        not candidatos["faltantes_turno2"]
        and not candidatos["extras_turno2"]
        and candidatos["identidades_turno2_conferidas"]
    )
    cobertura_ok = bool(
        len(secoes) == 998_496
        and secoes.groupby("turno").size().to_dict() == {1: 499_248, 2: 499_248}
        and sorted(votos["turno"].unique().tolist()) == [1, 2]
    )

    atual_t1 = preparar(secoes.loc[secoes["turno"].eq(1)], CHAVE_SECAO)
    anterior_t1_bruto = pd.read_parquet(args.secoes_anteriores.resolve())
    anterior_t1 = preparar(
        anterior_t1_bruto.loc[anterior_t1_bruto["turno"].eq(1)], CHAVE_SECAO
    )
    reconciliacao_t1 = reconciliar(
        atual_t1, anterior_t1, CHAVE_SECAO, "atual", "anterior"
    )
    atual_t2 = preparar(
        secoes.loc[secoes["turno"].eq(2)]
        .groupby(CHAVE_ZONA, as_index=False)[METRICAS]
        .sum(),
        CHAVE_ZONA,
    )
    zonas = pd.read_parquet(args.zonas_turno2.resolve())
    zonas_t2 = preparar(zonas.loc[zonas["turno"].eq(2)], CHAVE_ZONA)
    reconciliacao_t2_zonas = reconciliar(
        atual_t2, zonas_t2, CHAVE_ZONA, "secoes", "zonas"
    )
    json_zonas, fonte_json = carregar_json_zonas(args.json_zonas.resolve())
    reconciliacao_t2_json = reconciliar(
        atual_t2, preparar(json_zonas, CHAVE_ZONA), CHAVE_ZONA, "secoes", "json"
    )
    reconciliacoes = [
        reconciliacao_t1,
        reconciliacao_t2_zonas,
        reconciliacao_t2_json,
    ]
    reconciliacoes_ok = all(
        item["apenas_esquerda"] == 0
        and item["apenas_direita"] == 0
        and item["linhas_com_divergencia"] == 0
        for item in reconciliacoes
    )

    qa = anterior
    qa.update(
        gerado_em=datetime.now().astimezone().isoformat(),
        gerado_em_utc=datetime.now(UTC).isoformat(),
        comando=" ".join(sys.argv),
        modo_execucao="revalidacao_snapshot_sem_reescrita_dos_parquets",
        fontes={
            "votacao": fonte_votos,
            "detalhe": fonte_detalhes,
            "json_zonas": fonte_json,
        },
        candidatos=candidatos,
        reconciliacao_primeiro_turno=reconciliacao_t1,
        reconciliacao_segundo_turno_zonas=reconciliacao_t2_zonas,
        reconciliacao_segundo_turno_json=reconciliacao_t2_json,
        hashes_staging={
            "secoes.parquet": sha256_arquivo(secoes_path),
            "votos.parquet": sha256_arquivo(votos_path),
        },
        checks_integracao={
            "fontes_versionadas_com_manifestos_validos": True,
            "ambos_turnos_e_cobertura": cobertura_ok,
            "candidatos_turno2": candidatos_ok,
            "checks_contabeis_inclusive_nominal": contabilidade_ok,
            "contagens_nao_negativas": contagens_nao_negativas,
            "chaves_unicas": unicidade_ok,
            "pareamento_nominal_detalhe": join_ok,
            "excecoes_aptos_esperadas_41_por_turno": aptos_ok,
            "reconciliacoes_integrais": reconciliacoes_ok,
        },
        caracterizacao_excecoes={
            "aptos_por_turno": aptos_por_turno,
            "sem_linha_nominal_por_turno": sem_nominal_por_turno,
            "aptos_apenas_zz_nao_instaladas_comparecimento_e_abstencao_zero": aptos_ok,
            "sem_nominal_apenas_zz_e_comparecimento_zero": join_ok,
        },
    )
    qa["apto_para_revisao_independente"] = all(qa["checks_integracao"].values())
    escrever_json_atomico(qa, qa_path)
    escrever_json_atomico(qa, args.qa.resolve())
    escrever_json_atomico(
        {
            "gerado_em": qa["gerado_em"],
            "votacao": fonte_votos,
            "detalhe": fonte_detalhes,
        },
        out_dir / "fontes.json",
    )
    if not qa["apto_para_revisao_independente"]:
        raise ValueError("Revalidação do snapshot contém falha de QA")
    return qa


def criar_parser() -> argparse.ArgumentParser:
    """Cria argumentos com caminhos de versão explícitos."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-votos", type=Path, default=VOTOS_DEFAULT)
    parser.add_argument("--source-detalhes", type=Path, default=DETALHES_DEFAULT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT)
    parser.add_argument("--qa", type=Path, default=QA_DEFAULT)
    parser.add_argument(
        "--secoes-anteriores", type=Path, default=SECOES_ANTERIORES_DEFAULT
    )
    parser.add_argument("--zonas-turno2", type=Path, default=ZONAS_TURNO2_DEFAULT)
    parser.add_argument("--json-zonas", type=Path, default=JSON_ZONAS_DEFAULT)
    parser.add_argument("--chunk-size", type=int, default=250_000)
    parser.add_argument(
        "--qa-only",
        action="store_true",
        help="Revalida Parquets existentes e reemite QA sem reescrever dados.",
    )
    return parser


def main() -> int:
    """Ponto de entrada."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    try:
        args = criar_parser().parse_args()
        qa = revalidar_snapshot(args) if args.qa_only else executar(args)
    except Exception:
        LOGGER.exception("Falha na integração nominal em staging")
        return 1
    LOGGER.info(
        "Integração pronta para revisão: %s", qa["apto_para_revisao_independente"]
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
