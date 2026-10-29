"""Download the source files from the TSE open data portal (and the TSE-IBGE code table)."""
from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "Data" / "raw" / "tse"
TSE_URL = "https://cdn.tse.jus.br/estatistica/sead/odsele"

FILES = {
    "votacao_candidato_munzona_2022.zip": f"{TSE_URL}/votacao_candidato_munzona/votacao_candidato_munzona_2022.zip",
    "votacao_candidato_munzona_2026.zip": f"{TSE_URL}/votacao_candidato_munzona/votacao_candidato_munzona_2026.zip",
    "detalhe_votacao_munzona_2022.zip": f"{TSE_URL}/detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip",
    "detalhe_votacao_munzona_2026.zip": f"{TSE_URL}/detalhe_votacao_munzona/detalhe_votacao_munzona_2026.zip",
    # TSE and IBGE use different municipality codes; this table links them
    "municipios_brasileiros_tse.csv": "https://raw.githubusercontent.com/betafcc/Municipios-Brasileiros-TSE/"
                                      "master/municipios_brasileiros_tse.csv",
}

# files that change after the runoff: pass --refresh to download them again
REFRESH = ["votacao_candidato_munzona_2026.zip", "detalhe_votacao_munzona_2026.zip"]


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Download the 2026 files again.")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        target = RAW_DIR / name
        if target.exists() and not (args.refresh and name in REFRESH):
            print(f"Already there: {name}")
            continue
        print(f"Downloading: {name}")
        partial = target.with_suffix(".part")
        urllib.request.urlretrieve(url, partial)
        partial.replace(target)


if __name__ == "__main__":
    main()
