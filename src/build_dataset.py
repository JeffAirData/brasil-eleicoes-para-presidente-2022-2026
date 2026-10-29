"""Build the presidential election tables (2022 and 2026, every round available) from the TSE files."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "Data" / "raw" / "tse"
OUT_DIR = ROOT / "Data" / "processed"

YEARS = [2022, 2026]
ABROAD = "ZZ"  # TSE code for votes cast outside Brazil

REGIONS = {
    "North": ["AC", "AM", "AP", "PA", "RO", "RR", "TO"],
    "Northeast": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "Central-West": ["DF", "GO", "MS", "MT"],
    "Southeast": ["ES", "MG", "RJ", "SP"],
    "South": ["PR", "RS", "SC"],
    "Abroad": [ABROAD],
}
STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia", "CE": "Ceará",
    "DF": "Federal District", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MG": "Minas Gerais",
    "MS": "Mato Grosso do Sul", "MT": "Mato Grosso", "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco",
    "PI": "Piauí", "PR": "Paraná", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia",
    "RR": "Roraima", "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
    "TO": "Tocantins", ABROAD: "Votes abroad",
}
# TSE code -> IBGE code for municipalities newer than the code table.
# Boa Esperança do Norte (MT) was split from Sorriso and Nova Ubiratã and installed on 1 January 2025;
# IBGE code from servicodados.ibge.gov.br/api/v1/localidades/municipios/5101837
EXTRA_IBGE_CODES = {73709: 5101837}
UF_REGION = {uf: region for region, ufs in REGIONS.items() for uf in ufs}


def read_member(zip_path: Path, suffix: str, usecols: list[str]) -> pd.DataFrame:
    wanted = set(usecols)
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.endswith(suffix)]
        if len(names) != 1:
            raise FileNotFoundError(f"Expected one {suffix} file in {zip_path.name}, found {names}")
        with zf.open(names[0]) as fh:
            df = pd.read_csv(fh, sep=";", encoding="latin1", usecols=lambda c: c in wanted, low_memory=False)
    df.columns = df.columns.str.lower()
    return df


def raw(name: str) -> Path:
    path = RAW_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"{name} not found. Run src/download_tse.py first.")
    return path


def build_votes(year: int) -> pd.DataFrame:
    # the _BR file holds the presidential vote for every state, plus voters abroad
    df = read_member(
        raw(f"votacao_candidato_munzona_{year}.zip"),
        "_BR.csv",
        ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "DS_CARGO", "NR_CANDIDATO",
         "NM_URNA_CANDIDATO", "SG_PARTIDO", "QT_VOTOS_NOMINAIS_VALIDOS"],
    )
    df = df[df["ds_cargo"].str.upper() == "PRESIDENTE"]
    out = (
        df.groupby(["nr_turno", "sg_uf", "cd_municipio", "nm_municipio", "nr_candidato", "nm_urna_candidato",
                    "sg_partido"], as_index=False)["qt_votos_nominais_validos"].sum()
        .rename(columns={
            "nr_turno": "round", "sg_uf": "uf", "cd_municipio": "tse_code", "nm_municipio": "municipality",
            "nr_candidato": "number", "nm_urna_candidato": "candidate", "sg_partido": "party",
            "qt_votos_nominais_validos": "votes",
        })
    )
    out.insert(0, "year", year)
    return out


TURNOUT_COLUMNS = {
    "nr_turno": "round", "sg_uf": "uf", "cd_municipio": "tse_code", "qt_aptos": "registered",
    "qt_comparecimento": "turnout", "qt_abstencoes": "abstentions", "qt_total_votos_validos": "valid",
    "qt_votos_brancos": "blank", "qt_total_votos_nulos": "spoiled",
}


def build_turnout(year: int, by: list[str]) -> pd.DataFrame:
    """Turnout for president, summed by `by` (state, or state and municipality)."""
    df = read_member(
        raw(f"detalhe_votacao_munzona_{year}.zip"),
        "_BR.csv",
        ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "DS_CARGO", "QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES",
         "QT_TOTAL_VOTOS_VALIDOS", "QT_VOTOS_BRANCOS", "QT_TOTAL_VOTOS_NULOS"],
    )
    df = df[df["ds_cargo"].str.upper() == "PRESIDENTE"].drop(columns="ds_cargo")
    if "cd_municipio" not in by:
        df = df.drop(columns="cd_municipio")
    out = df.groupby(by, as_index=False).sum(numeric_only=True).rename(columns=TURNOUT_COLUMNS)
    out.insert(0, "year", year)
    return out


def add_labels(df: pd.DataFrame) -> pd.DataFrame:
    df.insert(df.columns.get_loc("uf") + 1, "state", df["uf"].map(STATE_NAMES))
    df.insert(df.columns.get_loc("uf") + 2, "region", df["uf"].map(UF_REGION))
    if df["state"].isna().any():
        raise ValueError(f"Unknown state codes: {sorted(df.loc[df['state'].isna(), 'uf'].unique())}")
    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    municipal = pd.concat([build_votes(y) for y in YEARS], ignore_index=True)
    codes = pd.read_csv(raw("municipios_brasileiros_tse.csv"), usecols=["codigo_tse", "codigo_ibge"])
    municipal = municipal.merge(codes.rename(columns={"codigo_tse": "tse_code", "codigo_ibge": "ibge_code"}),
                                on="tse_code", how="left")
    municipal["ibge_code"] = municipal["ibge_code"].fillna(municipal["tse_code"].map(EXTRA_IBGE_CODES))
    missing = set(municipal.loc[(municipal["uf"] != ABROAD) & municipal["ibge_code"].isna(), "municipality"])
    if missing:
        raise ValueError(f"No IBGE code for: {sorted(missing)[:20]}")
    municipal["ibge_code"] = municipal["ibge_code"].astype("Int64")
    municipal["pct"] = (municipal["votes"]
                        / municipal.groupby(["year", "round", "tse_code"])["votes"].transform("sum") * 100)
    municipal = add_labels(municipal)

    state = municipal.groupby(["year", "round", "uf", "number", "candidate", "party"], as_index=False)["votes"].sum()
    state["pct"] = state["votes"] / state.groupby(["year", "round", "uf"])["votes"].transform("sum") * 100
    state = add_labels(state)

    national = state.groupby(["year", "round", "number", "candidate", "party"], as_index=False)["votes"].sum()
    national["pct"] = national["votes"] / national.groupby(["year", "round"])["votes"].transform("sum") * 100

    turnout = add_labels(pd.concat([build_turnout(y, ["nr_turno", "sg_uf"]) for y in YEARS], ignore_index=True))
    turnout["pct_abstention"] = turnout["abstentions"] / turnout["registered"] * 100
    turnout_muni = add_labels(pd.concat([build_turnout(y, ["nr_turno", "sg_uf", "cd_municipio"]) for y in YEARS],
                                        ignore_index=True))
    turnout_muni["pct_abstention"] = turnout_muni["abstentions"] / turnout_muni["registered"] * 100

    municipal.to_parquet(OUT_DIR / "president_votes_municipality.parquet", index=False)
    turnout_muni.to_parquet(OUT_DIR / "turnout_municipality.parquet", index=False)
    for name, df in {"president_votes_state": state, "president_votes_national": national,
                     "turnout_state": turnout}.items():
        df.to_parquet(OUT_DIR / f"{name}.parquet", index=False)
        df.to_csv(OUT_DIR / f"{name}.csv", index=False, encoding="utf-8")

    rounds = municipal.groupby(["year", "round"]).agg(
        municipalities=("tse_code", "nunique"), votes=("votes", "sum")).reset_index()
    print(rounds.to_string(index=False))
    latest = national[(national["year"] == 2026) & (national["round"] == national["round"].max())]
    print(latest[["round", "number", "candidate", "votes", "pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
