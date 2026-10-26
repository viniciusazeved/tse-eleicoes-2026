"""Distribuição territorial de seções por abstenção, sem dados de candidaturas."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)
REGIOES = {
    "Norte": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
    "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "Sudeste": ["ES", "MG", "RJ", "SP"],
    "Sul": ["PR", "RS", "SC"],
    "Centro-Oeste": ["DF", "GO", "MS", "MT"],
}
SOURCE_DEFAULT = ROOT / "data/processed/secoes.parquet"
OUTPUT_DEFAULT = ROOT / "reports/geografia_comparecimento.csv"


def executar(source: Path, turno: int, output: Path) -> pd.DataFrame:
    """Conta seções por limite de abstenção, mantendo denominadores explícitos."""
    cols = [
        "turno",
        "uf",
        "municipio_codigo",
        "zona",
        "secao",
        "aptos",
        "abstencao",
        "comparecimento",
    ]
    data = pd.read_parquet(source, columns=cols)
    data = data.loc[(data.turno == turno) & (data.uf != "ZZ")].copy()
    if data.empty:
        raise ValueError(f"Nenhuma seção encontrada para o turno {turno}.")
    if data.duplicated(cols[:5]).any():
        raise ValueError("Chaves de seção duplicadas.")
    if not (data.aptos > 0).all():
        raise ValueError("Há seção sem denominador de aptos positivo.")
    if not (data.comparecimento + data.abstencao == data.aptos).all():
        raise ValueError("Balanço de comparecimento e abstenção não fecha.")
    data["regiao"] = data.uf.map(
        {uf: reg for reg, ufs in REGIOES.items() for uf in ufs}
    )
    if data.regiao.isna().any():
        raise ValueError("UF sem região definida.")
    rows = []
    for limite in (10, 5, 2, 0):
        # Comparação inteira evita arredondamento nos limiares inclusivos.
        selected = data.abstencao * 100 <= data.aptos * limite
        total_corte = int(selected.sum())
        for regiao in REGIOES:
            regional = data.regiao == regiao
            n_total = int(regional.sum())
            n_corte = int((selected & regional).sum())
            rows.append(
                {
                    "turno": turno,
                    "abstencao_max_pct": limite,
                    "regiao": regiao,
                    "secoes_regiao": n_total,
                    "secoes_no_corte": n_corte,
                    "secoes_corte_brasil": total_corte,
                    "pct_do_corte_nacional": 100 * n_corte / total_corte
                    if total_corte
                    else None,
                    "pct_das_secoes_regionais": 100 * n_corte / n_total,
                }
            )
    result = pd.DataFrame(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    LOGGER.info(
        "Contagens territoriais: %s",
        result.to_json(orient="records", force_ascii=False),
    )
    return result


def criar_parser() -> argparse.ArgumentParser:
    """Cria os argumentos da análise territorial."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    parser.add_argument("--turno", type=int, default=1, choices=(1, 2))
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    return parser


def main() -> None:
    """Executa a análise a partir dos argumentos de linha de comando."""
    args = criar_parser().parse_args()
    executar(args.source.resolve(), args.turno, args.output.resolve())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
