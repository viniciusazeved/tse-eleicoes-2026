"""Auditoria independente dos ZIPs e das estimativas publicadas."""

from __future__ import annotations

import json
import logging
from os import environ
from pathlib import Path
from zipfile import ZipFile

import duckdb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from scipy.stats import pearsonr, spearmanr, t

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(environ.get("TSE_REVIEW_DATA_DIR", ROOT / "data/processed"))
REPORTS = Path(environ.get("TSE_REVIEW_REPORTS_DIR", ROOT / "reports"))
DETAIL_ZIP = ROOT / "data/raw/versoes/20261026-123844/detalhe_votacao_secao_2026.zip"
VOTES_ZIP = ROOT / "data/raw/versoes/20261026-144303/votacao_secao_2026_BR.zip"
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
    if not DETAIL_ZIP.exists() or not VOTES_ZIP.exists():
        pytest.skip(
            "Auditoria bruta requer os ZIPs oficiais versionados, não incluídos no clone público"
        )
    section = pd.read_parquet(DATA / "secoes.parquet")
    section[KEY] = section[KEY].astype(str)
    expected = section.set_index(KEY).sort_index()
    with (
        ZipFile(DETAIL_ZIP) as archive,
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
    batches = pq.ParquetFile(DATA / "votos.parquet").iter_batches(batch_size=300_000)
    count_votes = 0
    with (
        ZipFile(VOTES_ZIP) as archive,
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
            nominal = chunk.rename(
                columns=RENAME
                | {"NR_VOTAVEL": "numero", "NM_VOTAVEL": "nome", "QT_VOTOS": "votos"}
            )[[*KEY, "numero", "nome", "votos"]].reset_index(drop=True)
            processed = next(batches).to_pandas()
            pd.testing.assert_frame_equal(
                nominal.astype(str), processed.astype(str), check_dtype=False
            )
            count_votes += len(nominal)
            candidate_totals.append(
                chunk.groupby(["NR_TURNO", "NR_VOTAVEL", "NM_VOTAVEL"]).QT_VOTOS.sum()
            )
            chunk["kind"] = chunk.NR_VOTAVEL.map(
                {"13": "lula", "22": "bolsonaro", "95": "brancos", "96": "nulos"}
            ).fillna("outros")
            partials.append(chunk.groupby(SOURCE_KEY + ["kind"]).QT_VOTOS.sum())
    totals = pd.concat(candidate_totals).groupby(level=[0, 1, 2]).sum()
    assert next(batches, None) is None
    assert set(totals.loc["2"].index.get_level_values(0)) == {"13", "22", "95", "96"}
    LOGGER.info("Todas as %s linhas nominais conferidas individualmente", count_votes)
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


def test_first_turn_all_candidate_lines_preserved() -> None:
    """Compara linhas do primeiro turno com o ZIP inicial preservado."""
    original = ROOT / "data/raw/votacao_secao_2026_BR.zip"
    if not original.exists():
        pytest.skip(
            "Preservação do primeiro turno requer o ZIP inicial arquivado localmente"
        )
    with duckdb.connect() as connection:
        connection.from_parquet(str(DATA / "votos.parquet")).filter(
            "turno=1"
        ).create_view("current_votes")
        connection.execute(
            "CREATE TABLE previous_votes AS SELECT * FROM current_votes WHERE FALSE"
        )
        with (
            ZipFile(original) as archive,
            archive.open("votacao_secao_2026_BR.csv") as handle,
        ):
            for chunk in pd.read_csv(
                handle,
                sep=";",
                encoding="latin1",
                dtype=str,
                chunksize=300_000,
                usecols=SOURCE_KEY + ["NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS"],
            ):
                assert set(chunk.NR_TURNO) == {"1"}
                nominal = chunk.rename(
                    columns=RENAME
                    | {
                        "NR_VOTAVEL": "numero",
                        "NM_VOTAVEL": "nome",
                        "QT_VOTOS": "votos",
                    }
                )[[*KEY, "numero", "nome", "votos"]]
                connection.register("original_chunk", nominal)
                connection.execute(
                    "INSERT INTO previous_votes SELECT * FROM original_chunk"
                )
        for left, right in [
            ("current_votes", "previous_votes"),
            ("previous_votes", "current_votes"),
        ]:
            assert (
                connection.execute(
                    f"SELECT COUNT(*) FROM (SELECT * FROM {left} EXCEPT ALL SELECT * FROM {right})"
                ).fetchone()[0]
                == 0
            )


@pytest.mark.parametrize("turn", [1, 2])
@pytest.mark.parametrize("candidate", ["lula", "bolsonaro"])
@pytest.mark.parametrize("minimum", [1, 100])
@pytest.mark.parametrize("weighted", [False, True])
def test_national_local_estimates_independently(
    turn: int, candidate: str, minimum: int, weighted: bool, level: str = "local"
) -> None:
    """Recalcula correlação e FE local com transformações e solver separados."""
    section = pd.read_parquet(DATA / "secoes.parquet")
    section = section.loc[
        section.turno.eq(turn)
        & section.uf.ne("ZZ")
        & section.validos.gt(0)
        & section.aptos.gt(0)
    ].copy()
    participation = section.comparecimento / section.aptos
    share = section[candidate] / section.validos
    correlations = pd.read_csv(REPORTS / "correlacoes.csv")
    result = correlations.loc[
        correlations.turno.eq(turn)
        & correlations.recorte.eq("Brasil")
        & correlations.candidato.eq(candidate)
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
    if level == "municipio":
        section["place"] = section.municipality
    elif level == "uf":
        section["place"] = section.uf
    elif level == "nacional":
        section["place"] = "Brasil"
    section["x"] = participation
    section["y"] = share
    section["la"] = np.log(section.aptos)
    section["la2"] = section.la**2
    section = section.loc[section.aptos.ge(minimum)].copy()
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
    models = pd.read_csv(REPORTS / "modelos.csv")
    actual = models.loc[
        models.turno.eq(turn)
        & models.candidato.eq(candidate)
        & models.efeito_fixo.eq(level)
        & models.aptos_minimos.eq(minimum)
        & models.ponderacao.eq("validos" if weighted else "secao")
    ].iloc[0]
    assert actual.pp_por_10pp == pytest.approx(beta[0] * 10, abs=1e-8)
    assert actual.ic95_inferior == pytest.approx((beta[0] - margin) * 10, abs=1e-8)
    assert actual.ic95_superior == pytest.approx((beta[0] + margin) * 10, abs=1e-8)
    LOGGER.info(
        "Turno %s candidato %s aptos_min %s: Pearson %.12f; Spearman %.12f; FE %s peso=%s n=%s grupos=%s clusters=%s: %.10f pp/10pp, IC95 [%.10f, %.10f]",
        turn,
        candidate,
        minimum,
        result.pearson,
        result.spearman,
        level,
        weighted,
        n,
        groups,
        clusters,
        beta[0] * 10,
        (beta[0] - margin) * 10,
        (beta[0] + margin) * 10,
    )


@pytest.mark.parametrize("turn", [1, 2])
@pytest.mark.parametrize("level", ["nacional", "uf", "municipio"])
def test_report_other_geographic_models(turn: int, level: str) -> None:
    """Recalcula também os outros seis modelos mostrados na tabela do relatório."""
    test_national_local_estimates_independently(turn, "lula", 1, True, level)


def test_second_round_original_json_and_pairing() -> None:
    """Confere todos os EA20 originais e explica o saldo das não instaladas."""
    raw_root = ROOT / "data/raw/api_turno2"
    if not (raw_root / "zonas").exists():
        pytest.skip(
            "Auditoria EA20 requer os JSONs oficiais originais arquivados localmente"
        )
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
    sections = pd.read_parquet(DATA / "secoes.parquet")
    first = sections.loc[sections.turno.eq(1)].copy()
    second = sections.loc[sections.turno.eq(2)].copy()
    second[["municipio_codigo", "zona"]] = second[["municipio_codigo", "zona"]].astype(
        int
    )
    pd.testing.assert_frame_equal(
        raw, second.groupby(key)[raw.columns].sum().sort_index(), check_dtype=False
    )
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


@pytest.mark.parametrize("turn", [1, 2])
def test_published_totals_and_thresholds(turn: int) -> None:
    """Verifica diretamente totais e cortes com denominadores agregados."""
    sections = pd.read_parquet(DATA / "secoes.parquet")
    national = sections[sections.uf.ne("ZZ") & sections.turno.eq(turn)]
    summary = json.loads((REPORTS / "resumo.json").read_text(encoding="utf-8"))
    totals = next(
        row
        for row in summary["totais"]
        if row["universo"] == "Brasil" and row["turno"] == turn
    )
    for column in [
        "aptos",
        "comparecimento",
        "abstencao",
        "validos",
        "lula",
        "bolsonaro",
    ]:
        assert totals[column] == national[column].sum()
    cuts = pd.read_csv(REPORTS / "cortes.csv")
    for row in cuts[cuts.universo.eq("Brasil") & cuts.turno.eq(turn)].itertuples():
        above = national.comparecimento / national.aptos >= row.corte
        subset = national.loc[above if row.grupo == "acima_ou_igual" else ~above]
        assert row.secoes == len(subset)
        assert row.aptos == subset.aptos.sum()
        if len(subset):
            assert row.lula_validos == pytest.approx(
                subset.lula.sum() / subset.validos.sum()
            )


def test_pairing_independent() -> None:
    """Refaz pareamento por índice e verifica todas as diferenças publicadas."""
    sections = pd.read_parquet(DATA / "secoes.parquet")
    key = KEY[1:]
    first = sections.loc[sections.turno.eq(1)].set_index(key).sort_index()
    second = sections.loc[sections.turno.eq(2)].set_index(key).sort_index()
    pd.testing.assert_index_equal(first.index, second.index)
    eligible = (
        first.aptos.gt(0)
        & second.aptos.gt(0)
        & first.validos.gt(0)
        & second.validos.gt(0)
    )
    local1, local2 = first.local_codigo.astype(int), second.local_codigo.astype(int)
    valid_local = local1.gt(0) & local2.gt(0)
    same_local = valid_local & local1.eq(local2)
    same_size = first.aptos.eq(second.aptos)
    principal = eligible & same_size & same_local
    processed = (
        pd.read_parquet(DATA / "pareamento_secoes.parquet").set_index(key).sort_index()
    )
    assert np.array_equal(processed.principal, principal)
    assert np.array_equal(processed.elegivel, eligible)
    report = json.loads((REPORTS / "resumo.json").read_text(encoding="utf-8"))[
        "pareamento_turnos_secoes"
    ]
    for coverage in report["cobertura"]:
        scope = first.index.get_level_values("uf") == "ZZ"
        if coverage["universo"] == "Brasil":
            scope = ~scope
        assert coverage["pareadas"] == scope.sum()
        assert coverage["exclusivas_t1"] == coverage["exclusivas_t2"] == 0
        assert coverage["principal"] == (principal & scope).sum()
        assert coverage["elegiveis"] == (eligible & scope).sum()
        assert coverage["aptos_diferentes"] == (~same_size & scope).sum()
        assert coverage["local_invalido"] == (~valid_local & scope).sum()
        assert (
            coverage["local_diferente_valido"]
            == (valid_local & ~same_local & scope).sum()
        )
        LOGGER.info("Cobertura independente: %s", coverage)
    for row in report["resultados"]:
        scope = first.index.get_level_values("uf") == "ZZ"
        if row["universo"] == "Brasil":
            scope = ~scope
        mask = scope & (principal if row["recorte"] == "principal" else eligible)
        one, two = first.loc[mask], second.loc[mask]
        candidate = row["candidato"]
        delta_participation = (
            two.comparecimento / two.aptos - one.comparecimento / one.aptos
        )
        delta_share = two[candidate] / two.validos - one[candidate] / one.validos
        assert row["secoes"] == len(one)
        assert row["pearson"] == pytest.approx(
            pearsonr(delta_participation, delta_share).statistic, abs=1e-12
        )
        assert row["spearman"] == pytest.approx(
            spearmanr(delta_participation, delta_share).statistic, abs=1e-12
        )
        assert row["delta_participacao_medio_pp"] == pytest.approx(
            delta_participation.mean() * 100
        )
        assert row["delta_apoio_medio_pp"] == pytest.approx(delta_share.mean() * 100)
        assert row["delta_participacao_agregada_pp"] == pytest.approx(
            (
                two.comparecimento.sum() / two.aptos.sum()
                - one.comparecimento.sum() / one.aptos.sum()
            )
            * 100
        )
        assert row["delta_apoio_agregado_pp"] == pytest.approx(
            (
                two[candidate].sum() / two.validos.sum()
                - one[candidate].sum() / one.validos.sum()
            )
            * 100
        )
        assert (
            row["delta_comparecimento_total"]
            == two.comparecimento.sum() - one.comparecimento.sum()
        )
        assert row["delta_votos_total"] == two[candidate].sum() - one[candidate].sum()
        LOGGER.info("Pareamento independente: %s", row)


def test_regional_cuts_independent() -> None:
    """Confere totais regionais, votos e as quarenta linhas territoriais."""
    regions = {
        "Norte": ["AC", "AM", "AP", "PA", "RO", "RR", "TO"],
        "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
        "Centro-Oeste": ["DF", "GO", "MS", "MT"],
        "Sudeste": ["ES", "MG", "RJ", "SP"],
        "Sul": ["PR", "RS", "SC"],
    }
    sections = pd.read_parquet(DATA / "secoes.parquet")
    report = pd.read_csv(REPORTS / "cortes_regioes.csv")
    assert len(report) == 40
    geography = pd.concat(
        [
            pd.read_csv(ROOT / "reports/geografia_comparecimento.csv"),
            pd.read_csv(ROOT / "reports/geografia_comparecimento_turno2.csv"),
        ]
    )
    for row in report.itertuples():
        threshold = round(100 - row.corte * 100)
        national = sections.loc[
            sections.turno.eq(row.turno) & sections.uf.ne("ZZ") & sections.aptos.gt(0)
        ]
        regional = national.loc[national.uf.isin(regions[row.regiao])]
        chosen = regional.loc[regional.abstencao * 100 <= threshold * regional.aptos]
        national_count = (national.abstencao * 100 <= threshold * national.aptos).sum()
        assert row.secoes_regiao == len(regional)
        assert row.secoes_no_corte == len(chosen)
        assert row.secoes_corte_brasil == national_count
        assert row.percentual_corte_nacional == pytest.approx(
            100 * len(chosen) / national_count
        )
        for column in [
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
            assert getattr(row, column) == chosen[column].sum()
        for candidate in ["lula", "bolsonaro"]:
            if chosen.validos.sum():
                assert getattr(row, f"{candidate}_validos") == pytest.approx(
                    chosen[candidate].sum() / chosen.validos.sum()
                )
            else:
                assert pd.isna(getattr(row, f"{candidate}_validos"))
        prior = geography.loc[
            geography.turno.eq(row.turno)
            & geography.regiao.eq(row.regiao)
            & geography.abstencao_max_pct.eq(threshold)
        ]
        assert len(prior) == 1
        assert int(prior.iloc[0].secoes_no_corte) == len(chosen)
