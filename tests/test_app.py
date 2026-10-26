from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def linha_secao(
    *,
    turno: int,
    secao: str,
    aptos: int = 100,
    local_codigo: str = "10",
    municipio_codigo: str = "5809",
    zona: str = "1",
) -> dict[str, object]:
    comparecimento = min(80, aptos)
    validos = max(comparecimento - 2, 0)
    lula = validos // 2
    bolsonaro = validos // 3
    return {
        "turno": turno,
        "uf": "RJ",
        "municipio_codigo": municipio_codigo,
        "municipio_nome": "Barra Mansa",
        "zona": zona,
        "secao": secao,
        "local_codigo": local_codigo,
        "local": "Local de teste",
        "aptos": aptos,
        "comparecimento": comparecimento,
        "abstencao": aptos - comparecimento,
        "validos": validos,
        "brancos": 1,
        "nulos": 1,
        "lula": lula,
        "bolsonaro": bolsonaro,
        "outros": validos - lula - bolsonaro,
        "participacao": comparecimento / aptos,
        "lula_validos": lula / validos if validos else None,
        "bolsonaro_validos": bolsonaro / validos if validos else None,
        "lula_aptos": lula / aptos,
        "bolsonaro_aptos": bolsonaro / aptos,
    }


def preparar_app(tmp_path: Path, secoes: list[dict[str, object]]) -> Path:
    shutil.copy2(ROOT / "app.py", tmp_path / "app.py")
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "reports").mkdir()
    pd.DataFrame(secoes).to_parquet(
        tmp_path / "data" / "processed" / "secoes.parquet", index=False
    )
    return tmp_path / "app.py"


def criar_zonas_turno2(tmp_path: Path, *, zona: str = "0001") -> Path:
    caminho = tmp_path / "data" / "processed" / "zonas_turno2.parquet"
    pd.DataFrame(
        [
            {
                "turno": 2,
                "uf": "RJ",
                "municipio_codigo": "05809",
                "municipio_nome": "Barra Mansa",
                "zona": zona,
                "aptos": 102,
                "comparecimento": 82,
                "abstencao": 20,
                "validos": 80,
                "brancos": 1,
                "nulos": 1,
                "lula": 44,
                "bolsonaro": 36,
                "outros": 0,
                "participacao": 82 / 102,
                "lula_validos": 44 / 80,
                "bolsonaro_validos": 36 / 80,
                "lula_aptos": 44 / 102,
                "bolsonaro_aptos": 36 / 102,
            }
        ]
    ).to_parquet(caminho, index=False)
    return caminho


def criar_pareamento_secoes(tmp_path: Path) -> Path:
    caminho = tmp_path / "data" / "processed" / "pareamento_secoes.parquet"
    pd.DataFrame(
        [
            {
                "uf": "RJ",
                "municipio_codigo": "05809",
                "zona": "0001",
                "secao": "0001",
                "municipio_nome_t1": "Barra Mansa",
                "municipio_nome_t2": "Barra Mansa",
                "local_codigo_t1": "0010",
                "local_codigo_t2": "10",
                "aptos_t1": 100,
                "aptos_t2": 100,
                "comparecimento_t1": 80,
                "comparecimento_t2": 82,
                "validos_t1": 78,
                "validos_t2": 80,
                "lula_t1": 40,
                "lula_t2": 44,
                "bolsonaro_t1": 30,
                "bolsonaro_t2": 36,
                "aptos_iguais": True,
                "local_igual": True,
                "elegivel": True,
                "principal": True,
                "delta_participacao": 0.02,
                "delta_lula_validos": 44 / 80 - 40 / 78,
                "delta_bolsonaro_validos": 36 / 80 - 30 / 78,
                "delta_lula": 4,
                "delta_bolsonaro": 6,
            },
            {
                "uf": "RJ",
                "municipio_codigo": "5809",
                "zona": "1",
                "secao": "2",
                "municipio_nome_t1": "Barra Mansa",
                "municipio_nome_t2": "Barra Mansa",
                "local_codigo_t1": "10",
                "local_codigo_t2": "11",
                "aptos_t1": 100,
                "aptos_t2": 100,
                "comparecimento_t1": 80,
                "comparecimento_t2": 79,
                "validos_t1": 78,
                "validos_t2": 77,
                "lula_t1": 40,
                "lula_t2": 42,
                "bolsonaro_t1": 30,
                "bolsonaro_t2": 35,
                "aptos_iguais": True,
                "local_igual": False,
                "elegivel": True,
                "principal": False,
                "delta_participacao": -0.01,
                "delta_lula_validos": 42 / 77 - 40 / 78,
                "delta_bolsonaro_validos": 35 / 77 - 30 / 78,
                "delta_lula": 2,
                "delta_bolsonaro": 5,
            },
        ]
    ).to_parquet(caminho, index=False)
    return caminho


def escrever_qa_zonas(
    tmp_path: Path, parquet: Path, *, apto: bool = True, sha: str | None = None
) -> None:
    sha_real = hashlib.sha256(parquet.read_bytes()).hexdigest()
    conteudo = {
        "apto_para_auditoria": apto,
        "sha256_parquet": sha if sha is not None else sha_real,
    }
    (tmp_path / "reports" / "qa_zonas_turno2.json").write_text(
        json.dumps(conteudo), encoding="utf-8"
    )


def executar(app_path: Path) -> AppTest:
    return AppTest.from_file(str(app_path), default_timeout=40).run()


def test_zonas_normalizam_municipio_e_zona_apos_qa(tmp_path: Path) -> None:
    app_path = preparar_app(tmp_path, [linha_secao(turno=1, secao="1")])
    parquet = criar_zonas_turno2(tmp_path)
    escrever_qa_zonas(tmp_path, parquet)

    app = executar(app_path)

    assert not app.exception
    metricas = {metrica.label: metrica.value for metrica in app.metric}
    assert metricas["Zonas correspondentes"] == "1"
    assert len(app.get("plotly_chart")) == 3
    assert any(
        "conferidos com os totais oficiais" in sucesso.value for sucesso in app.success
    )


def test_zonas_ficam_bloqueadas_quando_sha_nao_confere(tmp_path: Path) -> None:
    app_path = preparar_app(tmp_path, [linha_secao(turno=1, secao="1")])
    parquet = criar_zonas_turno2(tmp_path)
    escrever_qa_zonas(tmp_path, parquet, sha="0" * 64)

    app = executar(app_path)

    assert not app.exception
    assert len(app.get("plotly_chart")) == 2
    assert any("não coincide" in aviso.value for aviso in app.warning)
    assert all(metrica.label != "Zonas correspondentes" for metrica in app.metric)


def test_zonas_ficam_bloqueadas_sem_aprovacao_do_qa(tmp_path: Path) -> None:
    app_path = preparar_app(tmp_path, [linha_secao(turno=1, secao="1")])
    parquet = criar_zonas_turno2(tmp_path)
    escrever_qa_zonas(tmp_path, parquet, apto=False)

    app = executar(app_path)

    assert not app.exception
    assert any("não foi liberada" in aviso.value for aviso in app.warning)
    assert all(metrica.label != "Zonas correspondentes" for metrica in app.metric)


def test_pareamento_exige_aptos_e_local_iguais_e_informa_cobertura(
    tmp_path: Path,
) -> None:
    secoes = [
        linha_secao(turno=1, secao="1", aptos=100, local_codigo="10"),
        linha_secao(turno=1, secao="2", aptos=100, local_codigo="10"),
        linha_secao(turno=1, secao="3", aptos=100, local_codigo="10"),
        linha_secao(
            turno=2,
            secao="0001",
            aptos=100,
            local_codigo="0010",
            municipio_codigo="05809",
            zona="0001",
        ),
        linha_secao(turno=2, secao="0002", aptos=101, local_codigo="0010"),
        linha_secao(turno=2, secao="0003", aptos=100, local_codigo="0011"),
    ]
    app_path = preparar_app(tmp_path, secoes)

    app = executar(app_path)

    assert not app.exception
    metricas = {metrica.label: metrica.value for metrica in app.metric}
    assert metricas["Seções elegíveis no 1º turno"] == "3"
    assert metricas["Pareadas com aptos e local iguais"] == "1"
    assert metricas["Excluídas do pareamento"] == "2"
    assert any(
        "não demonstra que as mesmas pessoas" in legenda.value
        for legenda in app.caption
    )


def test_pareamento_processado_prioriza_recorte_principal(tmp_path: Path) -> None:
    secoes = [
        linha_secao(turno=1, secao="1", aptos=100, local_codigo="10"),
        linha_secao(turno=1, secao="2", aptos=100, local_codigo="10"),
        linha_secao(turno=2, secao="1", aptos=100, local_codigo="10"),
        linha_secao(turno=2, secao="2", aptos=100, local_codigo="11"),
    ]
    app_path = preparar_app(tmp_path, secoes)
    criar_pareamento_secoes(tmp_path)

    app = executar(app_path)

    assert not app.exception
    metricas = {metrica.label: metrica.value for metrica in app.metric}
    assert metricas["Chaves correspondentes"] == "2"
    assert metricas["Chaves elegíveis"] == "2"
    assert metricas["Recorte principal"] == "1"
    assert metricas["Seções no recorte"] == "1"
    assert app.radio[0].value == "principal"
    assert any(
        "não representa fluxo individual" in legenda.value for legenda in app.caption
    )
