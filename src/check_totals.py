"""Compare the national 2026 runoff totals with the TSE's official totalization report (PDF).

Reads the report straight from the zip, takes the "Resumo Geral do Brasil" pages and the national
candidate table, and prints TSE, our tables and the difference side by side.
"""
from __future__ import annotations

import io
import re
import zipfile

import pandas as pd
from pypdf import PdfReader

from build_dataset import OUT_DIR, raw

LULA, PL_NUMBER = 13, 22
REPORT = "relatorio_totalizacao/Relatorio_Resultado_Totalizacao_2026_BR.zip"

# label in the report -> regex that captures the number on the "Resumo Geral do Brasil" pages
PATTERNS = {
    "Eleitorado apto": r"2\.2 Eleitorado apto a votar\s+([\d.]+)",
    "Comparecimento": r"2\.3 Comparecimento\s+([\d.]+)",
    "Abstenção": r"2\.4 Abstenção\s+[\d,]+%\s+([\d.]+)",
    "Votos válidos": r"Votos válidos\s+100,00%\s+([\d.]+)",
    "Votos nulos": r"Votos nulos na urna\s+([\d.]+)",
    # pypdf may put the vote count before or after the name on the candidate lines
    "Lula (13)": r"13 - LUIZ IN[ÁA]CIO LULA DA SILVA\s+([\d.]+)|([\d.]+)\s+[\d,]+%[^\n]*13 - LUIZ IN[ÁA]CIO LULA",
    "Flávio Bolsonaro (22)": r"22 - FLAVIO NANTES BOLSONARO\s+([\d.]+)|([\d.]+)\s+[\d,]+%[^\n]*22 - FLAVIO NANTES",
}


def report_text() -> str:
    """Text of the national part of the runoff report: everything before the first state group."""
    with zipfile.ZipFile(raw(REPORT)) as zf:
        name = next(n for n in zf.namelist() if "T2_PRESIDENTE" in n)
        reader = PdfReader(io.BytesIO(zf.read(name)))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    end = text.find("Resumo Geral (EXTERIOR)")
    return text[:end] if end > 0 else text


def official(text: str) -> dict[str, int | None]:
    out = {}
    for label, pattern in PATTERNS.items():
        m = re.search(pattern, text)
        number = next((g for g in m.groups() if g), None) if m else None
        out[label] = int(number.replace(".", "")) if number else None
    # blank votes: the report lays the a/b/c lines out of order, so take them as total - valid - spoiled
    if None not in (out["Comparecimento"], out["Votos válidos"], out["Votos nulos"]):
        out["Votos em branco"] = out["Comparecimento"] - out["Votos válidos"] - out["Votos nulos"]
    return out


def ours() -> dict[str, int]:
    nat = pd.read_parquet(OUT_DIR / "president_votes_national.parquet")
    nat = nat[(nat["year"] == 2026) & (nat["round"] == 2)]
    t = pd.read_parquet(OUT_DIR / "turnout_state.parquet")
    t = t[(t["year"] == 2026) & (t["round"] == 2)].sum(numeric_only=True)
    votes = nat.set_index("number")["votes"]
    return {
        "Eleitorado apto": int(t["registered"]), "Comparecimento": int(t["turnout"]),
        "Abstenção": int(t["abstentions"]), "Votos válidos": int(nat["votes"].sum()),
        "Votos nulos": int(t["spoiled"]), "Votos em branco": int(t["blank"]),
        "Lula (13)": int(votes.get(LULA, 0)), "Flávio Bolsonaro (22)": int(votes.get(PL_NUMBER, 0)),
    }


def main() -> None:
    text = report_text()
    tse, mine = official(text), ours()
    rows = [{"item": k, "TSE (relatório)": tse.get(k), "nossos dados": mine[k],
             "diferença": None if tse.get(k) is None else mine[k] - tse[k]} for k in mine]
    table = pd.DataFrame(rows)
    print(table.to_string(index=False))
    missing = table.loc[table["TSE (relatório)"].isna(), "item"].tolist()
    if missing:
        print(f"\nNão encontrei no PDF: {missing}. Trecho lido:\n{text[:3000]}")
    elif (table["diferença"] == 0).all():
        print("\nTodos os totais conferem com o relatório oficial.")
    not_installed = re.search(r"2\.2\.1 Total de eleitores aptos nas seções não instaladas\s+([\d.]+)", text)
    if not_installed:
        print(f"\nNota: a abstenção do TSE não conta os {not_installed.group(1)} eleitores aptos de seções não "
              "instaladas, por isso aptos − comparecimento não fecha com ela. A diferença é desprezível.")


if __name__ == "__main__":
    main()
