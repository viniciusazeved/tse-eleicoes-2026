"""Coleta resultados oficiais do segundo turno por município e zona, com rastreio."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

LOGGER = logging.getLogger("tse.zonas")
BASE = "https://resultados.tse.jus.br/oficial"
CICLO = "ele2026"
ELEICAO = "6258"
PLEITO = "3221"
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
THREAD = threading.local()
PARAR = threading.Event()


def agora() -> str:
    """Consulta o relógio local, mantendo o fuso explícito."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def gravar_json(caminho: Path, objeto: Any) -> None:
    """Grava JSON de maneira atômica."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temp = caminho.with_suffix(caminho.suffix + ".part")
    temp.write_text(json.dumps(objeto, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(caminho)


class Coletor:
    """Preserva bytes de cada resposta e metadados, com retomada por cache íntegro."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz

    def obter(self, relativo: str, url: str) -> dict[str, Any]:
        """Consulta recurso oficial; 404 não é repetido e bloqueios interrompem a fila."""
        destino = self.raiz / relativo
        meta = destino.with_suffix(".meta.json")
        if destino.exists() and meta.exists():
            conteudo = destino.read_bytes()
            registro = json.loads(meta.read_text(encoding="utf-8"))
            if (
                registro["url"] != url
                or registro["sha256"] != hashlib.sha256(conteudo).hexdigest()
            ):
                raise ValueError(f"Cache divergente: {destino}")
            return json.loads(conteudo)
        if PARAR.is_set():
            raise RuntimeError("Coleta interrompida por bloqueio HTTP")
        if not hasattr(THREAD, "sessao"):
            THREAD.sessao = requests.Session()
            THREAD.sessao.headers["User-Agent"] = "TSE-public-data-research/1.0"
        for tentativa in range(4):
            if PARAR.is_set():
                raise RuntimeError("Coleta interrompida por bloqueio HTTP")
            try:
                resposta = THREAD.sessao.get(url, timeout=(15, 45))
                if resposta.status_code in (403, 429):
                    PARAR.set()
                    raise RuntimeError(
                        f"HTTP {resposta.status_code}: interromper e respeitar bloqueio: {url}"
                    )
                if resposta.status_code >= 500 and tentativa < 3:
                    time.sleep(2 ** (tentativa + 1))
                    continue
                resposta.raise_for_status()
                conteudo = resposta.content
                objeto = json.loads(conteudo)
                destino.parent.mkdir(parents=True, exist_ok=True)
                temp = destino.with_suffix(".json.part")
                temp.write_bytes(conteudo)
                temp.replace(destino)
                gravar_json(
                    meta,
                    {
                        "url": url,
                        "coletado_em": agora(),
                        "sha256": hashlib.sha256(conteudo).hexdigest(),
                        "bytes": len(conteudo),
                        "http_status": resposta.status_code,
                        "etag": resposta.headers.get("ETag"),
                        "last_modified": resposta.headers.get("Last-Modified"),
                        "data_geracao": objeto.get("dg"),
                        "hora_geracao": objeto.get("hg"),
                        "idg": objeto.get("idg"),
                    },
                )
                return objeto
            except (requests.ConnectionError, requests.Timeout):
                if tentativa == 3:
                    raise
                time.sleep(2 ** (tentativa + 1))
        raise RuntimeError(f"Tentativas esgotadas: {url}")


def inteiro(valor: Any) -> int:
    """Rejeita ausência, fração e valores negativos."""
    texto = str(valor)
    if not texto.isdecimal():
        raise ValueError(f"Contagem inválida: {valor!r}")
    return int(texto)


def extrair(
    obj: dict[str, Any], abrangencia: str
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Normaliza EA20 sem inventar seções e identifica os candidatos pelo registro real."""
    if any(
        obj.get(k) != v
        for k, v in {"ele": ELEICAO, "t": "2", "f": "o", "tpabr": abrangencia}.items()
    ):
        raise ValueError("Eleição, turno, fase ou abrangência inesperada")
    cargos = [c for c in obj["carg"] if c["cd"] == "1"]
    if len(cargos) != 1:
        raise ValueError("Cargo presidencial ausente ou duplicado")
    candidatos = [c for a in cargos[0]["agr"] for p in a["par"] for c in p["cand"]]
    if len({c["n"] for c in candidatos}) != len(candidatos):
        raise ValueError("Número de candidato repetido")
    mapa = {c["n"]: c for c in candidatos}
    if "13" not in mapa or "22" not in mapa:
        raise ValueError("Finalistas esperados não encontrados")
    if (
        "LULA" not in mapa["13"]["nmu"].upper()
        or "FLAVIO" not in mapa["22"]["nm"].upper()
    ):
        raise ValueError(
            "Identidade dos finalistas não corresponde ao contrato de 2026"
        )
    for candidato in candidatos:
        if candidato["dvt"] != "Válido":
            raise ValueError("Destinação de votos exige tratamento explícito")
    e, v, s = obj["e"], obj["v"], obj["s"]
    linha = {
        "turno": 2,
        "aptos": inteiro(e["te"]),
        "comparecimento": inteiro(e["c"]),
        "abstencao": inteiro(e["a"]),
        "validos": inteiro(v["vv"]),
        "brancos": inteiro(v["vb"]),
        "nulos": inteiro(v["tvn"]),
        "lula": inteiro(mapa["13"]["vap"]),
        "bolsonaro": inteiro(mapa["22"]["vap"]),
        "outros": sum(
            inteiro(c["vap"]) for c in candidatos if c["n"] not in {"13", "22"}
        ),
        "secoes_total": inteiro(s["ts"]),
        "secoes_totalizadas": inteiro(s["st"]),
        "secoes_nao_totalizadas": inteiro(s["snt"]),
        "secoes_instaladas": inteiro(s["si"]),
        "secoes_nao_instaladas": inteiro(s["sni"]),
        "eleitores_totalizados": inteiro(e["est"]),
        "eleitores_nao_totalizados": inteiro(e["esnt"]),
        "eleitores_instaladas": inteiro(e["esi"]),
        "eleitores_nao_instaladas": inteiro(e["esni"]),
        "totalizacao_final": obj.get("tf"),
        "andamento": obj.get("and"),
        "geracao_data": obj["dg"],
        "geracao_hora": obj["hg"],
        "totalizacao_data": obj.get("dt"),
        "totalizacao_hora": obj.get("ht"),
        "idg": obj["idg"],
    }
    identidades = [
        {k: c[k] for k in ("n", "sqcand", "nm", "nmu", "dvt")} for c in candidatos
    ]
    return linha, identidades


def validar_linha(linha: dict[str, Any]) -> list[str]:
    """Reporta inconsistências sem corrigir valores oficiais artificialmente."""
    falhas = []
    if linha["comparecimento"] + linha["abstencao"] != linha["eleitores_instaladas"]:
        falhas.append("comparecimento_abstencao_vs_eleitores_instaladas")
    if (
        linha["eleitores_instaladas"] + linha["eleitores_nao_instaladas"]
        != linha["eleitores_totalizados"]
    ):
        falhas.append("eleitorado_instalado_nao_instalado_vs_totalizado")
    if linha["validos"] + linha["brancos"] + linha["nulos"] != linha["comparecimento"]:
        falhas.append("votos_vs_comparecimento")
    if linha["lula"] + linha["bolsonaro"] + linha["outros"] != linha["validos"]:
        falhas.append("candidatos_vs_validos")
    if (
        linha["eleitores_totalizados"] + linha["eleitores_nao_totalizados"]
        != linha["aptos"]
    ):
        falhas.append("eleitorado_totalizado_vs_aptos")
    return falhas


def executar(raiz: Path, concorrencia: int) -> dict[str, Any]:
    """Descobre chaves via EA16 e compara as somas com Brasil e UFs."""
    inicio = agora()
    coletor = Coletor(raiz / "data/raw/api_turno2")
    coletor.obter("config/ele-c.json", f"{BASE}/comum/config/ele-c.json")
    config = coletor.obter(
        "config/mun-e006258-cm.json",
        f"{BASE}/{CICLO}/{ELEICAO}/config/mun-e006258-cm.json",
    )
    if config["f"] != "o":
        raise ValueError("Configuração municipal não oficial")
    ufs = sorted(a["cd"] for a in config["abr"])
    if len(ufs) != 28 or "zz" not in ufs or len(set(ufs)) != len(ufs):
        raise ValueError("Cobertura UF/exterior inesperada")
    chaves_ea12 = {
        (a["cd"], m["cd"], z) for a in config["abr"] for m in a["mu"] for z in m["z"]
    }
    tarefas: dict[tuple[str, str, str], str] = {}
    for uf in ufs:
        nome = f"{uf}-p003221-cs.json"
        cs = coletor.obter(
            f"config/{nome}", f"{BASE}/{CICLO}/arquivo-urna/{PLEITO}/config/{uf}/{nome}"
        )
        if cs["f"] != "o" or cs["cdp"] != PLEITO:
            raise ValueError(f"Configuração de seções incorreta: {uf}")
        for abr in cs["abr"]:
            if abr["cd"] != uf:
                raise ValueError(f"UF inesperada em EA16: {abr['cd']}")
            for mun in abr["mu"]:
                for zona in mun["zon"]:
                    chave = (uf, mun["cd"], zona["cd"])
                    if chave in tarefas:
                        raise ValueError(f"Chave EA16 duplicada: {chave}")
                    tarefas[chave] = mun["nm"]
    LOGGER.info(
        "Descobertas %s chaves de município/zona em %s UFs, incluindo exterior",
        len(tarefas),
        len(ufs),
    )
    linhas, erros, inconsistencias = [], [], []
    identidades_todas: dict[str, dict[str, str]] = {}

    def tarefa(
        chave: tuple[str, str, str], municipio_nome: str
    ) -> tuple[dict[str, Any], list[dict[str, str]]]:
        uf, municipio, zona = chave
        nome = f"{uf}{municipio}-z{zona}-c0001-e006258-u.json"
        url = f"{BASE}/{CICLO}/{ELEICAO}/dados/{uf}/{nome}"
        obj = coletor.obter(f"zonas/{uf}/{nome}", url)
        if obj["cdabr"] != zona:
            raise ValueError("Código de zona não corresponde à URL")
        linha, identidade = extrair(obj, "zona")
        linha.update(
            uf=uf.upper(),
            municipio_codigo=municipio,
            municipio_nome=municipio_nome,
            zona=zona,
            fonte_url=url,
        )
        return linha, identidade

    with ThreadPoolExecutor(max_workers=concorrencia) as pool:
        futuros = {
            pool.submit(tarefa, chave, nome): chave for chave, nome in tarefas.items()
        }
        for indice, futuro in enumerate(as_completed(futuros), start=1):
            chave = futuros[futuro]
            try:
                linha, identidades = futuro.result()
                linhas.append(linha)
                for identidade in identidades:
                    identidades_todas[identidade["sqcand"]] = identidade
                falhas = validar_linha(linha)
                if falhas:
                    inconsistencias.append({"chave": chave, "falhas": falhas})
            except (
                requests.RequestException,
                ValueError,
                RuntimeError,
                KeyError,
                OSError,
            ) as erro:
                erros.append({"chave": chave, "erro": str(erro)})
                LOGGER.warning("Falha em %s: %s", chave, erro)
                if PARAR.is_set():
                    for pendente in futuros:
                        pendente.cancel()
                    break
            if indice % 250 == 0:
                LOGGER.info(
                    "Processados %s/%s; falhas %s", indice, len(tarefas), len(erros)
                )
    if not linhas:
        raise RuntimeError("Nenhuma zona normalizada")
    quadro = (
        pd.DataFrame(linhas)
        .sort_values(["uf", "municipio_codigo", "zona"])
        .reset_index(drop=True)
    )
    destino = raiz / "data/processed/zonas_turno2.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    temp = destino.with_suffix(".parquet.part")
    quadro.to_parquet(temp, index=False)
    temp.replace(destino)
    referencias = {}
    conciliacao = {}
    for uf in ["br", *ufs]:
        nome = f"{uf}-c0001-e006258-u.json"
        obj = coletor.obter(
            f"referencias/{nome}", f"{BASE}/{CICLO}/{ELEICAO}/dados/{uf}/{nome}"
        )
        ref, _ = extrair(obj, "br" if uf == "br" else "uf")
        referencias[uf] = ref
        subconjunto = quadro if uf == "br" else quadro[quadro["uf"] == uf.upper()]
        conciliacao[uf] = {
            coluna: {
                "soma_zonas": int(subconjunto[coluna].sum()),
                "oficial": ref[coluna],
                "diferenca": int(subconjunto[coluna].sum()) - ref[coluna],
            }
            for coluna in [
                *METRICAS,
                "secoes_total",
                "secoes_totalizadas",
                "secoes_nao_totalizadas",
                "eleitores_instaladas",
                "eleitores_nao_instaladas",
            ]
        }
    todas_somas = all(
        item["diferenca"] == 0
        for escopo in conciliacao.values()
        for item in escopo.values()
    )
    qa = {
        "inicio": inicio,
        "fim": agora(),
        "unidade": "municipio_zona",
        "eleicao": ELEICAO,
        "pleito": PLEITO,
        "turno": 2,
        "fonte": "TSE oficial, EA16 e EA20",
        "candidatos": list(identidades_todas.values()),
        "observacao_bolsonaro": "Coluna bolsonaro refere-se a FLAVIO BOLSONARO, número 22, conforme cadastro oficial de 2026.",
        "denominadores": "aptos=e.te; comparecimento+abstencao=e.esi=eleitores_instaladas. Secoes nao instaladas permanecem no cadastro, sem fabricar abstencoes. Taxas oficiais de participacao usam eleitores_instaladas.",
        "esperadas_ea16": len(tarefas),
        "coletadas": len(quadro),
        "ufs": ufs,
        "chaves_so_ea12": sorted(chaves_ea12 - set(tarefas)),
        "chaves_so_ea16": sorted(set(tarefas) - chaves_ea12),
        "falhas_coleta": erros,
        "inconsistencias_linha": inconsistencias,
        "zonas_com_secoes_nao_totalizadas": int(
            (quadro["secoes_nao_totalizadas"] > 0).sum()
        ),
        "andamento": quadro["andamento"].value_counts(dropna=False).to_dict(),
        "totalizacao_final": quadro["totalizacao_final"]
        .value_counts(dropna=False)
        .to_dict(),
        "conciliacao": conciliacao,
        "referencias_oficiais": referencias,
        "conciliacao_todas_somas_exatas": todas_somas,
        "coleta_completa": len(quadro) == len(tarefas) and not erros,
        "apto_para_auditoria": len(quadro) == len(tarefas)
        and not erros
        and not inconsistencias
        and todas_somas,
        "arquivo": str(destino),
        "sha256_parquet": hashlib.sha256(destino.read_bytes()).hexdigest(),
        "limite": "Agregados por municipio/zona. Nao substitui censo de secoes nem permite comparar secoes no mesmo local.",
    }
    gravar_json(raiz / "reports/qa_zonas_turno2.json", qa)
    LOGGER.info(
        "Coleta encerrada: %s/%s chaves; conciliação exata: %s",
        len(quadro),
        len(tarefas),
        todas_somas,
    )
    return qa


def main() -> None:
    """Executa coleta com até quatro conexões concorrentes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 5))
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    resultado = executar(args.root, args.workers)
    if not resultado["apto_para_auditoria"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
