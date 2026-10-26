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
