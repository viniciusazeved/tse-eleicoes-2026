"""Compara turnos exclusivamente no nível município/zona."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
KEY = ["uf", "municipio_codigo", "zona"]
TOTALS = [
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


def normalized(d: pd.DataFrame) -> pd.DataFrame:
    """Remove apenas zeros de preenchimento dos identificadores numéricos."""
    d = d.copy()
    for col in ["municipio_codigo", "zona"]:
        d[col] = pd.to_numeric(d[col], errors="raise").astype("int64").astype(str)
    return d


def main() -> None:
    path = ROOT / "data/processed/zonas_turno2.parquet"
    qa = json.loads((REPORTS / "qa_zonas_turno2.json").read_text(encoding="utf-8"))
    if (
        not qa["apto_para_auditoria"]
        or hashlib.sha256(path.read_bytes()).hexdigest() != qa["sha256_parquet"]
    ):
        raise ValueError("Segundo turno incompleto ou sem QA compatível")
    first = pd.read_parquet(ROOT / "data/processed/zonas.parquet")
    first = normalized(first[first.turno.eq(1)])
    second = normalized(pd.read_parquet(path))
    if first.duplicated(KEY).any() or second.duplicated(KEY).any():
        raise ValueError("Chave município/zona duplicada")
    merged = first[KEY + TOTALS].merge(
        second[KEY + ["municipio_nome"] + TOTALS],
        on=KEY,
        how="outer",
        suffixes=("_1", "_2"),
        validate="one_to_one",
        indicator=True,
    )
    coverage = merged._merge.value_counts().to_dict()
    merged = merged.loc[merged._merge.eq("both")].copy()
    merged["aptos_iguais"] = merged.aptos_1.eq(merged.aptos_2)
    for turn in [1, 2]:
        merged[f"participacao_{turn}"] = merged[f"comparecimento_{turn}"] / merged[
            f"aptos_{turn}"
        ].replace(0, np.nan)
        for cand in ["lula", "bolsonaro"]:
            merged[f"{cand}_validos_{turn}"] = merged[f"{cand}_{turn}"] / merged[
                f"validos_{turn}"
            ].replace(0, np.nan)
    for col in ["participacao", "lula_validos", "bolsonaro_validos"]:
        merged[f"delta_{col}_pp"] = (merged[f"{col}_2"] - merged[f"{col}_1"]) * 100
    merged["delta_comparecimento"] = merged.comparecimento_2 - merged.comparecimento_1
    merged["delta_lula"] = merged.lula_2 - merged.lula_1
    merged["delta_bolsonaro"] = merged.bolsonaro_2 - merged.bolsonaro_1
    merged.drop(columns="_merge").to_csv(REPORTS / "zonas_comparacao.csv", index=False)
    results = []
    for sample, z in [
        ("Brasil", merged[merged.uf.ne("ZZ")]),
        ("Exterior", merged[merged.uf.eq("ZZ")]),
    ]:
        totals = {
            str(turn): {col: int(z[f"{col}_{turn}"].sum()) for col in TOTALS}
            for turn in [1, 2]
        }
        corrs = []
        valid = z[
            (z.validos_1 > 0) & (z.validos_2 > 0) & (z.aptos_1 > 0) & (z.aptos_2 > 0)
        ]
        for cand in ["lula", "bolsonaro"]:
            for turn in [1, 2]:
                corrs.append(
                    {
                        "tipo": "entre_zonas",
                        "turno": turn,
                        "candidato": cand,
                        "n": len(valid),
                        "pearson": float(
                            valid[f"participacao_{turn}"].corr(
                                valid[f"{cand}_validos_{turn}"]
                            )
                        ),
                        "spearman": float(
                            valid[f"participacao_{turn}"].corr(
                                valid[f"{cand}_validos_{turn}"], method="spearman"
                            )
                        ),
                    }
                )
            stable = valid[valid.aptos_iguais]
            corrs.append(
                {
                    "tipo": "diferenca_turnos_aptos_iguais",
                    "candidato": cand,
                    "n": len(stable),
                    "pearson": float(
                        stable.delta_participacao_pp.corr(
                            stable[f"delta_{cand}_validos_pp"]
                        )
                    ),
                    "spearman": float(
                        stable.delta_participacao_pp.corr(
                            stable[f"delta_{cand}_validos_pp"], method="spearman"
                        )
                    ),
                }
            )
        results.append(
            {
                "universo": sample,
                "zonas_pareadas": len(z),
                "zonas_aptos_iguais": int(z.aptos_iguais.sum()),
                "totais": totals,
                "correlacoes": corrs,
            }
        )
    report = {
        "gerado_em": datetime.now().astimezone().isoformat(),
        "granularidade": "município/zona, não seção",
        "cobertura_join": {str(k): int(v) for k, v in coverage.items()},
        "resultados": results,
        "limites": "A comparação não identifica transferência individual de votos, preferência dos novos comparecentes nem votos tardios. Exterior inclui aptos de seções não instaladas; a taxa aqui usa todos os registros aptos e não reproduz necessariamente a taxa oficial de eleitorado instalado.",
    }
    (REPORTS / "resumo_zonas2.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    with duckdb.connect(str(ROOT / "data/tse2026.duckdb")) as con:
        con.execute(
            "CREATE OR REPLACE TABLE zonas_turno2 AS SELECT * FROM read_parquet(?)",
            [path.as_posix()],
        )
        con.execute(
            "CREATE OR REPLACE TABLE comparacao_zonas AS SELECT * FROM read_csv_auto(?)",
            [(REPORTS / "zonas_comparacao.csv").as_posix()],
        )


if __name__ == "__main__":
    main()
