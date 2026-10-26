"""Auditoria independente dos ZIPs e das estimativas publicadas."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest
from scipy.stats import pearsonr, spearmanr, t

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)
SOURCE_KEY = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
KEY = ["turno", "uf", "municipio_codigo", "zona", "secao"]
RENAME = dict(zip(SOURCE_KEY, KEY, strict=True))
DETAIL = {
    "QT_APTOS": "aptos",
    "QT_COMPARECIMENTO": "comparecimento",
    "QT_ABSTENCOES": "abstencao",
    "QT_VOTOS_NOMINAIS": "validos",
    "QT_VOTOS_BRANCOS": "brancos",
    "QT_VOTOS_NULOS": "nulos",
    "NR_LOCAL_VOTACAO": "local_codigo",
}


def test_raw_sources_match_processed() -> None:
    """Relê fontes originais e reconcilia toda seção, sem chamar ingestão."""
    section = pd.read_parquet(ROOT / "data/processed/secoes.parquet")
    section[KEY] = section[KEY].astype(str)
    expected = section.set_index(KEY).sort_index()
    with (
        ZipFile(ROOT / "data/raw/detalhe_votacao_secao_2026.zip") as archive,
        archive.open("detalhe_votacao_secao_2026_BR.csv") as handle,
    ):
        source = pd.read_csv(
            handle,
            sep=";",
            encoding="latin1",
            dtype=str,
            usecols=SOURCE_KEY
            + list(DETAIL)
            + ["CD_CARGO", "ANO_ELEICAO", "NM_TIPO_ELEICAO"],
        )
    assert set(source.CD_CARGO) == {"1"}
    assert set(source.ANO_ELEICAO) == {"2026"}
    LOGGER.info("Tipo de eleição original: %s", source.NM_TIPO_ELEICAO.unique())
    source = source.rename(columns=RENAME | DETAIL).set_index(KEY).sort_index()
    pd.testing.assert_index_equal(source.index, expected.index)
    assert source.index.is_unique
    for column in DETAIL.values():
        assert source[column].astype(str).equals(expected[column].astype(str)), column
    partials = []
    candidate_totals = []
    with (
        ZipFile(ROOT / "data/raw/votacao_secao_2026_BR.zip") as archive,
        archive.open("votacao_secao_2026_BR.csv") as handle,
    ):
        for chunk in pd.read_csv(
            handle,
            sep=";",
            encoding="latin1",
            dtype=str,
            chunksize=300_000,
            usecols=SOURCE_KEY
            + ["CD_CARGO", "NR_VOTAVEL", "QT_VOTOS", "NM_VOTAVEL", "ANO_ELEICAO"],
        ):
            assert set(chunk.CD_CARGO) == {"1"}
            assert set(chunk.ANO_ELEICAO) == {"2026"}
            chunk["QT_VOTOS"] = chunk.QT_VOTOS.astype("int64")
            assert chunk.QT_VOTOS.gt(0).all()
            candidate_totals.append(
                chunk.groupby(["NR_VOTAVEL", "NM_VOTAVEL"]).QT_VOTOS.sum()
            )
            chunk["kind"] = chunk.NR_VOTAVEL.map(
                {"13": "lula", "22": "bolsonaro", "95": "brancos", "96": "nulos"}
            ).fillna("outros")
            partials.append(chunk.groupby(SOURCE_KEY + ["kind"]).QT_VOTOS.sum())
    totals = pd.concat(candidate_totals).groupby(level=[0, 1]).sum()
    LOGGER.info("Totais originais, Brasil mais exterior:\n%s", totals.to_string())
    wide = pd.concat(partials).groupby(level=list(range(6))).sum().unstack(fill_value=0)
    wide.index.names = KEY
    assert wide.index.difference(expected.index).empty
    wide = wide.reindex(expected.index, fill_value=0)
    for column in ["lula", "bolsonaro", "outros", "brancos", "nulos"]:
        assert np.array_equal(wide[column], expected[column]), column
    assert np.array_equal(
        wide[["lula", "bolsonaro", "outros"]].sum(axis=1), expected.validos
    )
    LOGGER.info("Todas as %s seções reconciliadas em campos e votos", len(expected))


@pytest.mark.parametrize("weighted", [False, True])
def test_national_local_estimates_independently(weighted: bool) -> None:
    """Recalcula correlação e FE local com transformações e solver separados."""
    section = pd.read_parquet(ROOT / "data/processed/secoes.parquet")
    section = section.loc[
        section.uf.ne("ZZ") & section.validos.gt(0) & section.aptos.gt(0)
    ].copy()
    participation = section.comparecimento / section.aptos
    share = section.lula / section.validos
    correlations = pd.read_csv(ROOT / "reports/correlacoes.csv")
    result = correlations.loc[
        correlations.recorte.eq("Brasil") & correlations.candidato.eq("lula")
    ].iloc[0]
    assert result.pearson == pytest.approx(
        pearsonr(participation, share).statistic, abs=1e-12
    )
    assert result.spearman == pytest.approx(
        spearmanr(participation, share).statistic, abs=1e-12
    )
    section["municipality"] = section.uf + ":" + section.municipio_codigo.astype(str)
    section["place"] = (
        section.municipality
        + ":"
        + section.zona.astype(str)
        + ":"
        + section.local_codigo.astype(str)
    )
    section["x"] = participation
    section["y"] = share
    section["la"] = np.log(section.aptos)
    section["la2"] = section.la**2
    section = section.loc[section.groupby("place").x.transform("nunique").gt(1)].copy()
    section["weight"] = section.validos if weighted else 1.0
    variables = ["x", "la", "la2", "y"]
    sums = (
        section[variables]
        .mul(section.weight, axis=0)
        .groupby(section.place)
        .transform("sum")
    )
    means = sums.div(section.groupby("place").weight.transform("sum"), axis=0)
    within = section[variables] - means
    matrix = within[["x", "la", "la2"]].to_numpy()
    target = within.y.to_numpy()
    weights = section.weight.to_numpy()
    root_weights = np.sqrt(weights)
    weighted_matrix = matrix * root_weights[:, None]
    beta, _, rank, _ = np.linalg.lstsq(
        weighted_matrix, target * root_weights, rcond=None
    )
    residual = target - matrix @ beta
    scores = (
        pd.DataFrame(matrix * (weights * residual)[:, None])
        .groupby(section.municipality.to_numpy())
        .sum()
    )
    bread = np.linalg.inv(weighted_matrix.T @ weighted_matrix)
    n, groups, clusters = (
        len(section),
        section.place.nunique(),
        section.municipality.nunique(),
    )
    correction = clusters / (clusters - 1) * (n - 1) / (n - groups - rank)
    covariance = bread @ scores.to_numpy().T @ scores.to_numpy() @ bread * correction
    margin = t.ppf(0.975, clusters - 1) * np.sqrt(covariance[0, 0])
    models = pd.read_csv(ROOT / "reports/modelos.csv")
    actual = models.loc[
        models.candidato.eq("lula")
        & models.efeito_fixo.eq("local")
        & models.aptos_minimos.eq(1)
        & models.ponderacao.eq("validos" if weighted else "secao")
    ].iloc[0]
    assert actual.pp_por_10pp == pytest.approx(beta[0] * 10, abs=1e-8)
    assert actual.ic95_inferior == pytest.approx((beta[0] - margin) * 10, abs=1e-8)
    assert actual.ic95_superior == pytest.approx((beta[0] + margin) * 10, abs=1e-8)
    LOGGER.info(
        "Pearson %.12f; Spearman %.12f; FE local peso=%s n=%s grupos=%s clusters=%s: %.10f pp/10pp, IC95 [%.10f, %.10f]",
        result.pearson,
        result.spearman,
        weighted,
        n,
        groups,
        clusters,
        beta[0] * 10,
        (beta[0] - margin) * 10,
        (beta[0] + margin) * 10,
    )


def test_second_round_original_json_and_pairing() -> None:
    """Confere todos os EA20 originais e explica o saldo das não instaladas."""
    raw_root = ROOT / "data/raw/api_turno2"
    rows = []
    expected_keys = set()
    for path in (raw_root / "config").glob("*-p003221-cs.json"):
        obj = json.loads(path.read_text(encoding="utf-8"))
        for coverage in obj["abr"]:
            for municipality in coverage["mu"]:
                for zone in municipality["zon"]:
                    expected_keys.add(
                        (
                            coverage["cd"].upper(),
                            int(municipality["cd"]),
                            int(zone["cd"]),
                        )
                    )
    for path in (raw_root / "zonas").glob("*/*-u.json"):
        obj = json.loads(path.read_text(encoding="utf-8"))
        assert obj["ele"] == "6258" and obj["t"] == "2" and obj["f"] == "o"
        assert obj["tf"] == "s" and obj["and"] == "f"
        assert int(obj["e"]["c"]) + int(obj["e"]["a"]) == int(obj["e"]["esi"])
        municipality = int(path.name[2:7])
        zone = int(obj["cdabr"])
        row = {
            "uf": path.parent.name.upper(),
            "municipio_codigo": municipality,
            "zona": zone,
        }
        for original, target in [
            ("te", "aptos"),
            ("c", "comparecimento"),
            ("a", "abstencao"),
        ]:
            row[target] = int(obj["e"][original])
        for original, target in [
            ("vv", "validos"),
            ("vb", "brancos"),
            ("tvn", "nulos"),
        ]:
            row[target] = int(obj["v"][original])
        cargo = next(item for item in obj["carg"] if item["cd"] == "1")
        votes = {
            candidate["n"]: int(candidate["vap"])
            for coalition in cargo["agr"]
            for party in coalition["par"]
            for candidate in party["cand"]
        }
        assert set(votes) == {"13", "22"}
        row.update(lula=votes["13"], bolsonaro=votes["22"])
        rows.append(row)
    key = ["uf", "municipio_codigo", "zona"]
    raw = pd.DataFrame(rows).set_index(key).sort_index()
    assert raw.index.is_unique
    assert set(raw.index) == expected_keys
    processed = pd.read_parquet(ROOT / "data/processed/zonas_turno2.parquet")
    processed[["municipio_codigo", "zona"]] = processed[
        ["municipio_codigo", "zona"]
    ].astype(int)
    pd.testing.assert_frame_equal(
        raw, processed.set_index(key).sort_index()[raw.columns], check_dtype=False
    )
    assert raw.lula.add(raw.bolsonaro).equals(raw.validos)
    assert raw.validos.add(raw.brancos).add(raw.nulos).equals(raw.comparecimento)
    for coverage in [
        "br",
        *[value.lower() for value in raw.index.get_level_values("uf").unique()],
    ]:
        reference = json.loads(
            (raw_root / f"referencias/{coverage}-c0001-e006258-u.json").read_text(
                encoding="utf-8"
            )
        )
        subset = raw if coverage == "br" else raw.loc[coverage.upper()]
        for original, target in [
            ("te", "aptos"),
            ("c", "comparecimento"),
            ("a", "abstencao"),
        ]:
            assert subset[target].sum() == int(reference["e"][original])
        assert subset.validos.sum() == int(reference["v"]["vv"])
    first = pd.read_parquet(ROOT / "data/processed/secoes.parquet")
    first[["municipio_codigo", "zona"]] = first[["municipio_codigo", "zona"]].astype(
        int
    )
    balance = raw.aptos - raw.comparecimento - raw.abstencao
    missing = (
        first[first.secao_instalada.ne("Sim")]
        .groupby(key)
        .aptos.sum()
        .reindex(raw.index, fill_value=0)
    )
    assert balance.equals(missing)
    first_groups = first.groupby(key)[raw.columns].sum()
    assert set(raw.index) == set(first_groups.index)
    report = json.loads(
        (ROOT / "reports/resumo_zonas2.json").read_text(encoding="utf-8")
    )
    for result in report["resultados"]:
        geography = raw.index.get_level_values("uf") == "ZZ"
        if result["universo"] == "Brasil":
            geography = ~geography
        second_scope = raw.loc[geography]
        first_scope = first_groups.reindex(second_scope.index)
        assert len(second_scope) == result["zonas_pareadas"]
        stable = first_scope.aptos == second_scope.aptos
        assert stable.sum() == result["zonas_aptos_iguais"]
        usable = first_scope.validos.gt(0) & second_scope.validos.gt(0)
        for item in result["correlacoes"]:
            candidate = item["candidato"]
            if item["tipo"] == "entre_zonas":
                base = first_scope if item["turno"] == 1 else second_scope
                sample = base.loc[usable]
                x = sample.comparecimento / sample.aptos
                y = sample[candidate] / sample.validos
            else:
                one = first_scope.loc[usable & stable]
                two = second_scope.loc[usable & stable]
                x = two.comparecimento / two.aptos - one.comparecimento / one.aptos
                y = two[candidate] / two.validos - one[candidate] / one.validos
            assert item["n"] == len(x)
            assert item["pearson"] == pytest.approx(pearsonr(x, y).statistic, abs=1e-12)
            assert item["spearman"] == pytest.approx(
                spearmanr(x, y).statistic, abs=1e-12
            )
            LOGGER.info(
                "Correlação auditada %s %s candidato=%s turno=%s n=%s Pearson=%.12f",
                result["universo"],
                item["tipo"],
                candidate,
                item.get("turno", "delta"),
                item["n"],
                item["pearson"],
            )
    for coverage, subset in [
        ("Brasil", raw.loc[raw.index.get_level_values("uf") != "ZZ"]),
        ("Exterior", raw.loc["ZZ"]),
    ]:
        totals = subset.sum()
        LOGGER.info(
            "2t %s: %s, participacao %.12f, Lula validos %.12f",
            coverage,
            totals.to_dict(),
            totals.comparecimento / totals.aptos,
            totals.lula / totals.validos,
        )
    LOGGER.info(
        "2t %s zonas conciliadas integralmente; saldo ZZ %s aptos em %s zonas corresponde às não instaladas no 1t",
        len(raw),
        balance.sum(),
        balance.ne(0).sum(),
    )


def test_published_totals_and_thresholds() -> None:
    """Verifica diretamente totais e cortes com denominadores agregados."""
    sections = pd.read_parquet(ROOT / "data/processed/secoes.parquet")
    national = sections[sections.uf.ne("ZZ")]
    summary = json.loads((ROOT / "reports/resumo.json").read_text(encoding="utf-8"))
    totals = next(row for row in summary["totais"] if row["universo"] == "Brasil")
    for column in [
        "aptos",
        "comparecimento",
        "abstencao",
        "validos",
        "lula",
        "bolsonaro",
    ]:
        assert totals[column] == national[column].sum()
    cuts = pd.read_csv(ROOT / "reports/cortes.csv")
    for row in cuts[cuts.universo.eq("Brasil")].itertuples():
        above = national.comparecimento / national.aptos >= row.corte
        subset = national.loc[above if row.grupo == "acima_ou_igual" else ~above]
        assert row.secoes == len(subset)
        assert row.aptos == subset.aptos.sum()
        if len(subset):
            assert row.lula_validos == pytest.approx(
                subset.lula.sum() / subset.validos.sum()
            )
