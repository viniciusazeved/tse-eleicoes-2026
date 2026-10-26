"""Confere absorção de efeitos fixos contra regressão com indicadoras."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.formula.api as smf

spec = importlib.util.spec_from_file_location(
    "analysis", Path(__file__).resolve().parents[1] / "scripts/analyze.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("weighted", [False, True])
def test_fixed_effect_matches_dummy_regression(weighted: bool) -> None:
    rng = np.random.default_rng(20261026)
    n = 240
    d = pd.DataFrame(
        {
            "uf": "SP",
            "municipio_codigo": np.repeat(np.arange(12), 20).astype(str),
            "zona": "1",
            "local_codigo": np.tile(np.repeat(["1", "2"], 10), 12),
        }
    )
    d["aptos"] = rng.integers(100, 500, n)
    d["participacao"] = rng.uniform(0.6, 0.95, n)
    d["validos"] = (d.aptos * d.participacao).astype(int)
    d["lula"] = (
        (d.validos * (0.2 + 0.3 * d.participacao + rng.normal(0, 0.03, n)))
        .round()
        .astype(int)
    )
    d["share"] = d.lula / d.validos
    d["loga"] = np.log(d.aptos)
    d["localid"] = d.municipio_codigo + ":" + d.local_codigo
    weights = d.validos if weighted else np.ones(n)
    direct = smf.wls(
        "share ~ participacao + loga + I(loga**2) + C(localid)", d, weights=weights
    ).fit(cov_type="cluster", cov_kwds={"groups": d.municipio_codigo})
    actual = module.fixed_effect_model(d, "lula", "local", weighted)
    assert actual["status"] == "ok"
    assert actual["beta"] == pytest.approx(direct.params["participacao"], rel=1e-8)


def test_missing_variation_is_not_zero_effect() -> None:
    d = pd.DataFrame(
        {
            "uf": ["SP"] * 20,
            "municipio_codigo": ["1"] * 20,
            "zona": ["1"] * 20,
            "aptos": [100] * 20,
            "validos": [80] * 20,
            "participacao": [0.8] * 20,
            "lula": [40] * 20,
        }
    )
    actual = module.fixed_effect_model(d, "lula", "municipio", False)
    assert actual["status"] == "sem suporte"
    assert "beta" not in actual


def _section(turn: int, section: str, **changes) -> dict:
    row = {
        "turno": turn,
        "uf": "SP",
        "municipio_codigo": "1",
        "municipio_nome": "Município",
        "zona": "1",
        "secao": section,
        "local_codigo": "1001",
        "aptos": 100,
        "comparecimento": 80,
        "abstencao": 20,
        "validos": 70,
        "brancos": 5,
        "nulos": 5,
        "lula": 35,
        "bolsonaro": 35,
        "outros": 0,
    }
    return row | changes


@pytest.mark.parametrize("invalid_local", [None, "-1", "-3", "0"])
def test_pairing_requires_valid_equal_local_and_equal_electorate(invalid_local) -> None:
    rows = [
        _section(1, "1"),
        _section(2, "1", comparecimento=90, abstencao=10, validos=80, lula=45),
        _section(1, "2"),
        _section(2, "2", aptos=101, abstencao=21),
        _section(1, "3", local_codigo=invalid_local),
        _section(2, "3", local_codigo=invalid_local),
        _section(1, "4"),
        _section(2, "4", validos=0, lula=0, bolsonaro=0),
        _section(1, "5"),
        _section(2, "6"),
        _section(1, "7"),
        _section(2, "7", local_codigo="1002"),
    ]
    pairs, summary = module.parear_secoes(pd.DataFrame(rows))
    assert len(pairs) == 5
    assert summary["cobertura_join"] == {"both": 5, "left_only": 1, "right_only": 1}
    assert set(pairs.loc[pairs.principal, "secao"]) == {"1"}
    assert not pairs.loc[pairs.secao.eq("3"), "local_igual"].item()
    assert not pairs.loc[pairs.secao.eq("4"), "elegivel"].item()
    p = pairs.set_index("secao").loc["1"]
    assert p.delta_participacao == pytest.approx(0.1)
    assert p.delta_lula_validos == pytest.approx(45 / 80 - 35 / 70)
    assert p.delta_lula == 10
    result = next(
        r
        for r in summary["resultados"]
        if r["universo"] == "Brasil"
        and r["recorte"] == "principal"
        and r["candidato"] == "lula"
    )
    assert result["secoes"] == 1
    assert result["pearson"] is None
    assert result["delta_participacao_medio_pp"] == pytest.approx(10)


def test_pairing_rejects_duplicate_keys() -> None:
    rows = [_section(1, "1"), _section(1, "1"), _section(2, "1")]
    with pytest.raises(pd.errors.MergeError):
        module.parear_secoes(pd.DataFrame(rows))
