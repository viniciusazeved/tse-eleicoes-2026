"""Análise descritiva reproduzível, sem classificação de fraude."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import t

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger("tse.analyze")
OUT = ROOT / "reports"
KEY = ["uf", "municipio_codigo", "zona", "secao"]
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
REGIOES = {
    "Norte": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
    "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "Sudeste": ["ES", "MG", "RJ", "SP"],
    "Sul": ["PR", "RS", "SC"],
    "Centro-Oeste": ["DF", "GO", "MS", "MT"],
}


def safe_corr(x: pd.Series, y: pd.Series, method: str = "pearson") -> float | None:
    """Correlação indefinida é ausente, nunca zero."""
    if x.nunique() < 2 or y.nunique() < 2:
        return None
    return float(x.corr(y, method=method))


def fixed_effect_model(
    frame: pd.DataFrame, candidate: str, level: str, weighted: bool
) -> dict:
    """Mínimos quadrados após absorver grupos, IC agrupado por município."""
    d = frame.loc[(frame.aptos > 0) & (frame.validos > 0)].copy()
    d["mun_id"] = d.uf.astype(str) + ":" + d.municipio_codigo.astype(str)
    if level == "local":
        local_column = "local_codigo" if "local_codigo" in d.columns else "local"
        d = d.loc[
            d[local_column].notna()
            & ~d[local_column].astype(str).isin(["", "nan", "None", "-1", "-3"])
        ].copy()
        group = d.mun_id + ":" + d.zona.astype(str) + ":" + d[local_column].astype(str)
    elif level == "municipio":
        group = d.mun_id
    elif level == "uf":
        group = d.uf
    else:
        group = pd.Series("Brasil", index=d.index)
    d["group"] = group
    variation = d.groupby("group").participacao.transform("nunique")
    d = d.loc[variation > 1].copy()
    n, fe, clusters = len(d), d.group.nunique(), d.mun_id.nunique()
    base = {
        "candidato": candidate,
        "efeito_fixo": level,
        "ponderacao": "validos" if weighted else "secao",
        "n": n,
        "grupos": fe,
        "municipios_cluster": clusters,
    }
    if n < 10 or clusters < 2:
        return {**base, "status": "sem suporte"}
    w = d.validos.astype(float).to_numpy() if weighted else np.ones(n)
    la = np.log(d.aptos.to_numpy(dtype=float))
    x = np.column_stack([d.participacao.to_numpy(), la, la**2])
    y = (d[candidate] / d.validos).to_numpy(dtype=float)
    group_ids = pd.factorize(d.group)[0]
    den = np.bincount(group_ids, weights=w)

    def demean(a: np.ndarray) -> np.ndarray:
        means = np.bincount(group_ids, weights=w * a) / den
        return a - means[group_ids]

    x = np.column_stack([demean(x[:, j]) for j in range(x.shape[1])])
    y = demean(y)
    gram = x.T @ (w[:, None] * x)
    rank = np.linalg.matrix_rank(gram)
    if rank < x.shape[1]:
        return {**base, "status": "matriz singular"}
    bread = np.linalg.inv(gram)
    beta = bread @ (x.T @ (w * y))
    residual = y - x @ beta
    scores = (
        pd.DataFrame(x * (w * residual)[:, None])
        .groupby(d.mun_id.to_numpy())
        .sum()
        .to_numpy()
    )
    correction = clusters / (clusters - 1) * (n - 1) / max(1, n - fe - rank)
    covariance = correction * bread @ (scores.T @ scores) @ bread
    se = float(np.sqrt(max(0, covariance[0, 0])))
    critical = float(t.ppf(0.975, clusters - 1))
    return {
        **base,
        "status": "ok",
        "beta": float(beta[0]),
        "pp_por_10pp": float(beta[0] * 10),
        "ic95_inferior": float((beta[0] - critical * se) * 10),
        "ic95_superior": float((beta[0] + critical * se) * 10),
        "r2_dentro": float(1 - np.sum(w * residual**2) / np.sum(w * y**2))
        if np.sum(w * y**2) > 0
        else None,
    }


def aggregate(d: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    z = d.groupby(keys, observed=True, dropna=False)[TOTALS].sum().reset_index()
    z["participacao"] = z.comparecimento / z.aptos.replace(0, np.nan)
    z["lula_validos"] = z.lula / z.validos.replace(0, np.nan)
    z["bolsonaro_validos"] = z.bolsonaro / z.validos.replace(0, np.nan)
    return z


def parear_secoes(d: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Pareia chaves territoriais e explicita elegibilidade e estabilidade cadastral."""
    if not {1, 2} <= set(d.turno.unique()):
        return pd.DataFrame(), {"status": "pendente: ausente um dos turnos"}
    local_column = "local_codigo" if "local_codigo" in d.columns else "local"
    columns = [*KEY, "municipio_nome", *TOTALS, local_column]
    first = d.loc[d.turno.eq(1), columns].rename(columns={local_column: "local_codigo"})
    second = d.loc[d.turno.eq(2), columns].rename(
        columns={local_column: "local_codigo"}
    )
    joined = first.merge(
        second,
        on=KEY,
        how="outer",
        suffixes=("_t1", "_t2"),
        validate="one_to_one",
        indicator=True,
    )
    pairs = joined.loc[joined._merge.eq("both")].drop(columns="_merge").copy()
    local1 = pd.to_numeric(pairs.local_codigo_t1, errors="coerce")
    local2 = pd.to_numeric(pairs.local_codigo_t2, errors="coerce")
    pairs["locais_validos"] = (
        local1.gt(0) & local2.gt(0) & local1.mod(1).eq(0) & local2.mod(1).eq(0)
    )
    pairs["local_igual"] = pairs.locais_validos & local1.eq(local2)
    pairs["aptos_iguais"] = pairs.aptos_t1.eq(pairs.aptos_t2)
    pairs["elegivel"] = (
        pairs.aptos_t1.gt(0)
        & pairs.aptos_t2.gt(0)
        & pairs.validos_t1.gt(0)
        & pairs.validos_t2.gt(0)
    )
    pairs["principal"] = pairs.elegivel & pairs.aptos_iguais & pairs.local_igual
    for turno in (1, 2):
        pairs[f"participacao_t{turno}"] = pairs[f"comparecimento_t{turno}"] / pairs[
            f"aptos_t{turno}"
        ].replace(0, np.nan)
        for candidate in ("lula", "bolsonaro"):
            pairs[f"{candidate}_validos_t{turno}"] = pairs[
                f"{candidate}_t{turno}"
            ] / pairs[f"validos_t{turno}"].replace(0, np.nan)
    for column in ("participacao", "lula_validos", "bolsonaro_validos"):
        pairs[f"delta_{column}"] = pairs[f"{column}_t2"] - pairs[f"{column}_t1"]
    for column in ("comparecimento", "lula", "bolsonaro"):
        pairs[f"delta_{column}"] = pairs[f"{column}_t2"] - pairs[f"{column}_t1"]
    coverage, results = [], []
    for universe, exterior in (("Brasil", False), ("Exterior", True)):
        j = joined.loc[joined.uf.eq("ZZ").eq(exterior)]
        p = pairs.loc[pairs.uf.eq("ZZ").eq(exterior)]
        coverage.append(
            {
                "universo": universe,
                "secoes_t1": int(j._merge.ne("right_only").sum()),
                "secoes_t2": int(j._merge.ne("left_only").sum()),
                "pareadas": len(p),
                "exclusivas_t1": int(j._merge.eq("left_only").sum()),
                "exclusivas_t2": int(j._merge.eq("right_only").sum()),
                "aptos_diferentes": int((~p.aptos_iguais).sum()),
                "local_invalido": int((~p.locais_validos).sum()),
                "local_diferente_valido": int(
                    (p.locais_validos & ~p.local_igual).sum()
                ),
                "inelegiveis": int((~p.elegivel).sum()),
                "elegiveis": int(p.elegivel.sum()),
                "principal": int(p.principal.sum()),
            }
        )
        for sample, mask in (
            ("todos_elegiveis", p.elegivel),
            ("principal", p.principal),
        ):
            g = p.loc[mask]
            for candidate in ("lula", "bolsonaro"):
                results.append(
                    {
                        "universo": universe,
                        "recorte": sample,
                        "candidato": candidate,
                        "secoes": len(g),
                        "pearson": safe_corr(
                            g.delta_participacao, g[f"delta_{candidate}_validos"]
                        ),
                        "spearman": safe_corr(
                            g.delta_participacao,
                            g[f"delta_{candidate}_validos"],
                            "spearman",
                        ),
                        "delta_participacao_medio_pp": float(
                            g.delta_participacao.mean() * 100
                        )
                        if len(g)
                        else None,
                        "delta_apoio_medio_pp": float(
                            g[f"delta_{candidate}_validos"].mean() * 100
                        )
                        if len(g)
                        else None,
                        "delta_participacao_agregada_pp": float(
                            (
                                g.comparecimento_t2.sum() / g.aptos_t2.sum()
                                - g.comparecimento_t1.sum() / g.aptos_t1.sum()
                            )
                            * 100
                        )
                        if len(g)
                        else None,
                        "delta_apoio_agregado_pp": float(
                            (
                                g[f"{candidate}_t2"].sum() / g.validos_t2.sum()
                                - g[f"{candidate}_t1"].sum() / g.validos_t1.sum()
                            )
                            * 100
                        )
                        if len(g)
                        else None,
                        "delta_comparecimento_total": int(g.delta_comparecimento.sum()),
                        "delta_votos_total": int(g[f"delta_{candidate}"].sum()),
                    }
                )
    report = {
        "status": "disponivel",
        "chave": KEY,
        "cobertura_join": {
            str(k): int(v) for k, v in joined._merge.value_counts().items()
        },
        "cobertura": coverage,
        "resultados": results,
        "limites": "Exclusões cadastrais podem se sobrepor. Igualdade de aptos e local não comprova identidade do eleitorado. Diferenças agregadas não identificam fluxos individuais, origem de votos ou fraude. Médias por seção diferem de diferenças entre razões agregadas.",
    }
    return pairs, report


def executar(data_dir: Path, out: Path, database: Path | None = None) -> dict:
    """Gera análises em destinos explícitos, permitindo revisão anterior à promoção."""
    out.mkdir(parents=True, exist_ok=True)
    d = pd.read_parquet(data_dir / "secoes.parquet")
    if d.duplicated(["turno", *KEY]).any():
        raise ValueError("Chaves de seção duplicadas; análise interrompida")
    required = set(TOTALS + ["turno", *KEY])
    if missing := required - set(d.columns):
        raise ValueError(f"Campos ausentes: {missing}")
    d["participacao"] = d.comparecimento / d.aptos.replace(0, np.nan)
    d["lula_validos"] = d.lula / d.validos.replace(0, np.nan)
    d["bolsonaro_validos"] = d.bolsonaro / d.validos.replace(0, np.nan)
    d["universo"] = np.where(d.uf.eq("ZZ"), "Exterior", "Brasil")
    summary = {
        "gerado_em": datetime.now().astimezone().isoformat(),
        "turnos_secoes": sorted(int(v) for v in d.turno.unique()),
        "natureza": "Censo dos registros publicados; associações observacionais não identificam fraude.",
        "totais": [],
    }
    national = aggregate(d, ["turno", "universo"])
    national["secoes"] = d.groupby(["turno", "universo"]).size().to_numpy()
    summary["totais"] = national.to_dict("records")
    national.to_csv(out / "totais.csv", index=False)
    for level, keys in [
        ("ufs", ["turno", "uf"]),
        ("municipios", ["turno", "uf", "municipio_codigo", "municipio_nome"]),
        ("zonas", ["turno", "uf", "municipio_codigo", "municipio_nome", "zona"]),
    ]:
        aggregate(d, keys).to_parquet(data_dir / f"{level}.parquet", index=False)
    bins = [0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 1.00000001]
    labels = [
        "0 a <50%",
        "50 a <60%",
        "60 a <70%",
        "70 a <80%",
        "80 a <90%",
        "90 a <95%",
        "95 a <98%",
        "98 a 100%",
    ]
    faixas, thresholds, correlations, models, regional_cuts = [], [], [], [], []
    for (turno, universo), g in d.groupby(["turno", "universo"]):
        g = g.loc[(g.aptos > 0) & (g.validos > 0)].copy()
        g["faixa"] = pd.cut(g.participacao, bins=bins, labels=labels, right=False)
        for faixa, h in g.groupby("faixa", observed=True):
            faixas.append(
                {
                    "turno": int(turno),
                    "universo": universo,
                    "faixa": str(faixa),
                    "secoes": len(h),
                    **{c: int(h[c].sum()) for c in TOTALS},
                    "lula_validos": float(h.lula.sum() / h.validos.sum()),
                    "bolsonaro_validos": float(h.bolsonaro.sum() / h.validos.sum()),
                }
            )
        for threshold in [0.9, 0.95, 0.98, 1.0]:
            for side, h in [
                ("acima_ou_igual", g[g.participacao >= threshold]),
                ("abaixo", g[g.participacao < threshold]),
            ]:
                thresholds.append(
                    {
                        "turno": int(turno),
                        "universo": universo,
                        "corte": threshold,
                        "grupo": side,
                        "secoes": len(h),
                        "ufs": h.uf.nunique(),
                        "municipios": h[["uf", "municipio_codigo"]]
                        .drop_duplicates()
                        .shape[0],
                        **{c: int(h[c].sum()) for c in TOTALS},
                        "lula_validos": float(h.lula.sum() / h.validos.sum())
                        if h.validos.sum()
                        else None,
                        "bolsonaro_validos": float(h.bolsonaro.sum() / h.validos.sum())
                        if h.validos.sum()
                        else None,
                    }
                )
        for scope, h in [(universo, g), *[(uf, k) for uf, k in g.groupby("uf")]]:
            for cand in ["lula", "bolsonaro", "outros"]:
                y = h[cand] / h.validos
                correlations.append(
                    {
                        "turno": int(turno),
                        "universo": universo,
                        "recorte": scope,
                        "candidato": cand,
                        "secoes": len(h),
                        "pearson": safe_corr(h.participacao, y),
                        "spearman": safe_corr(h.participacao, y, "spearman"),
                    }
                )
        if universo != "Brasil":
            continue
        for percentage in (90, 95, 98, 100):
            selected = g.comparecimento * 100 >= g.aptos * percentage
            national_count = int(selected.sum())
            for region, states in REGIOES.items():
                regional = g.uf.isin(states)
                h = g.loc[selected & regional]
                regional_cuts.append(
                    {
                        "turno": int(turno),
                        "regiao": region,
                        "corte": percentage / 100,
                        "secoes_regiao": int(regional.sum()),
                        "secoes_no_corte": len(h),
                        "secoes_corte_brasil": national_count,
                        "percentual_corte_nacional": 100 * len(h) / national_count
                        if national_count
                        else None,
                        **{column: int(h[column].sum()) for column in TOTALS},
                        "lula_validos": float(h.lula.sum() / h.validos.sum())
                        if h.validos.sum()
                        else None,
                        "bolsonaro_validos": float(h.bolsonaro.sum() / h.validos.sum())
                        if h.validos.sum()
                        else None,
                    }
                )
        levels = ["nacional", "uf", "municipio"] + (
            ["local"] if {"local_codigo", "local"} & set(g.columns) else []
        )
        for minimum in [1, 100]:
            for cand in ["lula", "bolsonaro"]:
                for level in levels:
                    for weighted in [False, True]:
                        result = fixed_effect_model(
                            g[g.aptos >= minimum], cand, level, weighted
                        )
                        models.append(
                            {"turno": int(turno), "aptos_minimos": minimum, **result}
                        )
        LOGGER.info("Analisado turno %s, %s seções Brasil", turno, len(g))
    pd.DataFrame(faixas).to_csv(out / "faixas.csv", index=False)
    pd.DataFrame(thresholds).to_csv(out / "cortes.csv", index=False)
    pd.DataFrame(correlations).to_csv(out / "correlacoes.csv", index=False)
    pd.DataFrame(models).to_csv(out / "modelos.csv", index=False)
    pd.DataFrame(regional_cuts).to_csv(out / "cortes_regioes.csv", index=False)
    # Distribuição descritiva completa, não seleção por candidato.
    descriptions = []
    for (turno, universo), g in d.groupby(["turno", "universo"]):
        for col in ["aptos", "participacao", "lula_validos", "bolsonaro_validos"]:
            desc = (
                g[col]
                .describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
                .to_dict()
            )
            descriptions.append(
                {"turno": int(turno), "universo": universo, "variavel": col, **desc}
            )
    pd.DataFrame(descriptions).to_csv(out / "distribuicoes.csv", index=False)
    votes_path = data_dir / "votos.parquet"
    if votes_path.exists():
        v = pd.read_parquet(votes_path)
        totals = (
            v.groupby(["turno", "numero", "nome"], dropna=False)
            .votos.sum()
            .reset_index()
        )
        totals.to_csv(out / "todos_candidatos.csv", index=False)
        all_correlations = []
        # Seção sem linha de um candidato tem zero somente no universo reconciliado pela ingestão.
        for turno, g in d[d.uf.ne("ZZ") & d.validos.gt(0)].groupby("turno"):
            idx = pd.MultiIndex.from_frame(g[KEY])
            vg = v[
                v.turno.eq(turno)
                & ~v.numero.astype(str).isin(["95", "96", "97", "98", "99"])
            ]
            for (number, name), cv in vg.groupby(["numero", "nome"]):
                vc = cv.groupby(KEY).votos.sum().reindex(idx, fill_value=0).to_numpy()
                y = pd.Series(vc / g.validos.to_numpy())
                x = pd.Series(g.participacao.to_numpy())
                all_correlations.append(
                    {
                        "turno": int(turno),
                        "numero": str(number),
                        "nome": name,
                        "pearson": safe_corr(x, y),
                        "spearman": safe_corr(x, y, "spearman"),
                        "votos_brasil": int(vc.sum()),
                    }
                )
        pd.DataFrame(all_correlations).to_csv(
            out / "correlacoes_candidatos.csv", index=False
        )
    summary["comparacao_turnos_secoes"] = (
        "disponivel"
        if {1, 2} <= set(d.turno.unique())
        else "pendente: segundo turno ainda ausente no arquivo por seção"
    )
    pairs, pairing_summary = parear_secoes(d)
    summary["pareamento_turnos_secoes"] = pairing_summary
    if not pairs.empty:
        pairs.to_parquet(data_dir / "pareamento_secoes.parquet", index=False)
        pd.DataFrame(pairing_summary["resultados"]).to_csv(
            out / "pareamento_secoes.csv", index=False
        )
    (out / "resumo.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    if database is not None:
        database.parent.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(str(database)) as con:
            for name in [
                "secoes",
                "votos",
                "ufs",
                "municipios",
                "zonas",
                "pareamento_secoes",
            ]:
                path = (data_dir / f"{name}.parquet").as_posix()
                if Path(path).exists():
                    con.execute(
                        f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_parquet(?)",
                        [path],
                    )
    LOGGER.info("Relatórios gerados em %s", out)
    return summary


def main() -> None:
    """Seleciona entradas e saídas da análise."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--reports-dir", type=Path, default=OUT)
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    executar(args.data_dir.resolve(), args.reports_dir.resolve(), args.database)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    main()
