"""Build the static charts (PNG), the map files, the interactive page and the post draft.

Three comparisons, all labelled in Brazilian Portuguese:
  (c) Brazil, state by state: the latest round both elections share (the runoff), 2022 vs 2026;
  (b) Brazil, state by state: 2026 first round vs 2026 runoff;
  (a) Goiás, municipality by municipality: 2026 first round vs 2026 runoff.
Titles and numbers are computed, never typed in.
"""
from __future__ import annotations

import json
from pathlib import Path

import geobr
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from shapely.geometry import MultiPolygon
from shapely.geometry.polygon import orient

from build_dataset import ABROAD, REGIONS, STATE_NAMES, UF_REGION

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "Data" / "processed"
DOCS_DIR = ROOT / "docs"  # published by GitHub Pages
IMG_DIR = DOCS_DIR / "img"
GEO_DIR = DOCS_DIR / "geo"
# one post per language, side by side: post_*_pt.md now, post_*_en.md later
PUB_DIR = ROOT / "publication"
LANG = "pt"

# the 2024 IBGE map is the first with Boa Esperança do Norte (MT), installed on 1 January 2025
MESH_YEAR = 2024
LULA, PL_NUMBER, CAIADO = 13, 22, 55
GO = "GO"
PL_NAME = {2022: "Jair Bolsonaro", 2026: "Flávio Bolsonaro"}
ROUND_NAME = {1: "1º turno", 2: "2º turno"}
NAME_PT = {**STATE_NAMES, "DF": "Distrito Federal", ABROAD: "Exterior"}
REGION_PT = {"North": "Norte", "Northeast": "Nordeste", "Central-West": "Centro-Oeste", "Southeast": "Sudeste",
             "South": "Sul", "Abroad": "Exterior"}

PL, PT, OTHERS, CAIADO_COLOR = "#2a78d6", "#e34948", "#c3c2b7", "#d99a1e"
INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
SOURCE = "Fonte: TSE, dados abertos. Votos válidos para presidente."
REPO = "github.com/JeffAirData"
PAGE_URL = "https://jeffairdata.github.io/brasil-eleicoes-para-presidente-2022-2026/"
CODE_URL = "https://github.com/JeffAirData/brasil-eleicoes-para-presidente-2022-2026"

plt.rcParams.update({
    "font.family": "Segoe UI", "font.size": 11, "text.color": INK, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": "#c3c2b7",
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
})


def br(v: float, digits: int = 1) -> str:
    """Number with a decimal comma."""
    return f"{v:.{digits}f}".replace(".", ",")


def thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def millions(n: int) -> str:
    sign = "+" if n > 0 else "−" if n < 0 else ""
    return f"{sign}{br(abs(n) / 1e6)} mi"


def plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def mi_words(n: int) -> str:
    """'10,4 milhões', '1,8 milhão'."""
    v = abs(n) / 1e6
    return f"{br(v)} {'milhão' if v < 2 else 'milhões'}"


def gained(who: str, n: int) -> str:
    """'Lula ganhou 10,4 milhões de votos' (or 'perdeu', when the count fell)."""
    return f"{who} {'ganhou' if n >= 0 else 'perdeu'} {mi_words(n)} de votos"


def margin_text(m1: float, m2: float) -> str:
    """How Lula's lead over Flávio (negative: Flávio ahead) moved from the first round to the runoff."""
    def side(m):
        return ("Lula", "Flávio") if m >= 0 else ("Flávio", "Lula")
    if (m1 >= 0) == (m2 >= 0):
        a, b = side(m1)
        return f"a vantagem de {a} sobre {b} passou de {br(abs(m1))} para {br(abs(m2))} pontos"
    return (f"{side(m1)[0]} liderava por {br(abs(m1))} pontos no 1º turno e {side(m2)[0]} venceu o 2º "
            f"por {br(abs(m2))}")


def load() -> dict:
    state = pd.read_parquet(DATA_DIR / "president_votes_state.parquet")
    national = pd.read_parquet(DATA_DIR / "president_votes_national.parquet")
    turnout = pd.read_parquet(DATA_DIR / "turnout_state.parquet")
    muni = pd.read_parquet(DATA_DIR / "president_votes_municipality.parquet")
    turnout_muni = pd.read_parquet(DATA_DIR / "turnout_municipality.parquet")
    rounds = sorted(set(zip(national["year"], national["round"])))
    if (2026, 2) not in rounds:
        raise ValueError("The 2026 runoff is not in the data: run src/build_dataset.py with the runoff files.")
    return {"state": state, "national": national, "turnout": turnout, "muni": muni, "turnout_muni": turnout_muni,
            "rounds": rounds, "base": 2}


def share(df: pd.DataFrame, year: int, rnd: int, number: int, by: str | None = None):
    sel = df[(df["year"] == year) & (df["round"] == rnd)]
    if by is None:
        return float(sel.loc[sel["number"] == number, "votes"].sum() / sel["votes"].sum() * 100)
    total = sel.groupby(by)["votes"].sum()
    return (sel[sel["number"] == number].groupby(by)["votes"].sum().reindex(total.index, fill_value=0) / total * 100)


def leaders(df: pd.DataFrame, by: str) -> pd.Series:
    """Number of the candidate with the most votes in each group."""
    totals = df.groupby([by, "number"], as_index=False)["votes"].sum()
    return totals.loc[totals.groupby(by)["votes"].idxmax()].set_index(by)["number"]


def candidate_name(d: dict, number: int, year: int = 2026) -> str:
    if number == LULA:
        return "Lula"
    if number == PL_NUMBER:
        return PL_NAME[year]
    nat = d["national"]
    return nat.loc[(nat["year"] == year) & (nat["number"] == number), "candidate"].iloc[0].title()


def candidate_key(number: int) -> str:
    return {LULA: "PT", PL_NUMBER: "PL", CAIADO: "CAIADO"}.get(int(number), "OUTRO")


def candidate_color(number: int) -> str:
    return {LULA: PT, PL_NUMBER: PL, CAIADO: CAIADO_COLOR}.get(int(number), OTHERS)


# ---------------------------------------------------------------- (c) 2022 vs 2026, by state

def state_table(d: dict) -> pd.DataFrame:
    """One row per state (plus voters abroad), on the base round."""
    base = d["base"]
    out = pd.DataFrame({"uf": sorted(STATE_NAMES)})
    out["state"] = out["uf"].map(NAME_PT)
    out["region"] = out["uf"].map(UF_REGION).map(REGION_PT)
    out = out.set_index("uf")
    for year in (2022, 2026):
        out[f"lula_{year}"] = share(d["state"], year, base, LULA, "uf")
        out[f"pl_{year}"] = share(d["state"], year, base, PL_NUMBER, "uf")
        out[f"leader_{year}"] = (out[f"pl_{year}"] > out[f"lula_{year}"]).map({True: "PL", False: "PT"})
        sel = d["state"][(d["state"]["year"] == year) & (d["state"]["round"] == base)]
        out[f"votes_{year}"] = sel.groupby("uf")["votes"].sum()
        t = d["turnout"][(d["turnout"]["year"] == year) & (d["turnout"]["round"] == base)].set_index("uf")
        out[f"registered_{year}"] = t["registered"]
        out[f"abstention_{year}"] = t["pct_abstention"]
    out["lula_change"] = out["lula_2026"] - out["lula_2022"]
    out["pl_change"] = out["pl_2026"] - out["pl_2022"]
    return out.reset_index()


def headline(d: dict, states: pd.DataFrame) -> dict:
    base, nat = d["base"], d["national"]
    brazil = states[states["uf"] != ABROAD]
    t = d["turnout"][d["turnout"]["round"] == base].groupby("year")[["registered", "abstentions"]].sum()
    low, high = brazil.loc[brazil["lula_change"].idxmin()], brazil.loc[brazil["lula_change"].idxmax()]
    abroad = states[states["uf"] == ABROAD].iloc[0]
    return {
        "abroad": {"votes": int(abroad["votes_2026"]),
                   "pct_of_total": float(abroad["votes_2026"] / states["votes_2026"].sum() * 100),
                   **{f"{k}_{y}": float(abroad[f"{k}_{y}"]) for k in ("lula", "pl") for y in (2022, 2026)}},
        "base": base, "round_name": ROUND_NAME[base],
        "lula_2022": share(nat, 2022, base, LULA), "lula_2026": share(nat, 2026, base, LULA),
        "pl_2022": share(nat, 2022, base, PL_NUMBER), "pl_2026": share(nat, 2026, base, PL_NUMBER),
        "lula_states_2022": int((brazil["leader_2022"] == "PT").sum()),
        "lula_states_2026": int((brazil["leader_2026"] == "PT").sum()),
        "flipped_to_pl": int(((brazil["leader_2022"] == "PT") & (brazil["leader_2026"] == "PL")).sum()),
        "flipped_to_pt": int(((brazil["leader_2022"] == "PL") & (brazil["leader_2026"] == "PT")).sum()),
        "flipped_to_pl_names": brazil.loc[(brazil["leader_2022"] == "PT") & (brazil["leader_2026"] == "PL"),
                                          "state"].sort_values().tolist(),
        "flipped_to_pt_names": brazil.loc[(brazil["leader_2022"] == "PL") & (brazil["leader_2026"] == "PT"),
                                          "state"].sort_values().tolist(),
        "lula_fell_in": int((brazil["lula_change"] < 0).sum()),
        "lula_rose_in": int((brazil["lula_change"] > 0).sum()), "n_states": len(brazil),
        "biggest_drop": (low["state"], float(low["lula_change"])),
        "biggest_gain": (high["state"], float(high["lula_change"])),
        "abstention_2022": float(t.loc[2022, "abstentions"] / t.loc[2022, "registered"] * 100),
        "abstention_2026": float(t.loc[2026, "abstentions"] / t.loc[2026, "registered"] * 100),
    }


def lula_trend(h: dict) -> str:
    """The majority direction of Lula's share across states, with the extreme in that direction."""
    if h["lula_rose_in"] > h["lula_fell_in"]:
        state, value = h["biggest_gain"]
        return (f"A fatia de Lula subiu em {h['lula_rose_in']} de {h['n_states']} estados. "
                f"Maior alta: {state}, com {br(value)} pontos.")
    state, value = h["biggest_drop"]
    return (f"A fatia de Lula caiu em {h['lula_fell_in']} de {h['n_states']} estados. "
            f"Maior queda: {state}, com {br(abs(value))} pontos.")


def abroad_note(h: dict) -> str:
    a = h["abroad"]
    return (f"{NAME_PT[ABROAD]} (no total nacional, fora do mapa): {thousands(a['votes'])} votos válidos · "
            f"Lula {br(a['lula_2026'])}%, {PL_NAME[2026]} {br(a['pl_2026'])}%")


def abstention_note(h: dict) -> str:
    before, after = round(h["abstention_2022"]), round(h["abstention_2026"])
    return "Igual a 2022." if before == after else f"Em 2022, eram {before} em 100."


# ---------------------------------------------------------------- (b) 2026 first round vs runoff, by state

def rounds_table(d: dict) -> pd.DataFrame:
    """One row per state (plus voters abroad): 2026 first round vs 2026 runoff."""
    st = d["state"][d["state"]["year"] == 2026]
    out = pd.DataFrame({"uf": sorted(STATE_NAMES)})
    out["state"] = out["uf"].map(NAME_PT)
    out["region"] = out["uf"].map(UF_REGION).map(REGION_PT)
    out = out.set_index("uf")
    for rnd in (1, 2):
        out[f"lula_{rnd}t"] = share(st, 2026, rnd, LULA, "uf")
        out[f"pl_{rnd}t"] = share(st, 2026, rnd, PL_NUMBER, "uf")
        out[f"margin_{rnd}t"] = out[f"lula_{rnd}t"] - out[f"pl_{rnd}t"]
        out[f"leader_{rnd}t"] = leaders(st[st["round"] == rnd], "uf")
        t = d["turnout"][(d["turnout"]["year"] == 2026) & (d["turnout"]["round"] == rnd)].set_index("uf")
        out[f"abstention_{rnd}t"] = t["pct_abstention"]
    out["others_1t"] = 100 - out["lula_1t"] - out["pl_1t"]
    out["flipped"] = out["leader_1t"] != out["leader_2t"]
    return out.reset_index()


def rounds_headline(d: dict, rt: pd.DataFrame) -> dict:
    nat = d["national"][d["national"]["year"] == 2026]
    votes = nat.pivot_table(index="number", columns="round", values="votes", aggfunc="sum").fillna(0)
    brazil = rt[rt["uf"] != ABROAD]
    flips = brazil[brazil["flipped"]]
    t = d["turnout"][d["turnout"]["year"] == 2026].groupby("round")[
        ["registered", "abstentions", "turnout", "blank", "spoiled"]].sum()
    lula_1t, pl_1t = share(nat, 2026, 1, LULA), share(nat, 2026, 1, PL_NUMBER)
    return {
        "lula_1t": lula_1t, "pl_1t": pl_1t, "others_1t": 100 - lula_1t - pl_1t,
        "lula_2t": share(nat, 2026, 2, LULA), "pl_2t": share(nat, 2026, 2, PL_NUMBER),
        "lula_gain_votes": int(votes.loc[LULA, 2] - votes.loc[LULA, 1]),
        "pl_gain_votes": int(votes.loc[PL_NUMBER, 2] - votes.loc[PL_NUMBER, 1]),
        "others_votes_1t": int(votes[1].sum() - votes.loc[LULA, 1] - votes.loc[PL_NUMBER, 1]),
        "valid_1t": int(votes[1].sum()), "valid_2t": int(votes[2].sum()),
        # net balances between the rounds: where the extra valid votes came from, not who voted for whom
        "turnout_change": int(t.loc[2, "turnout"] - t.loc[1, "turnout"]),
        "blank_spoiled_change": int(t.loc[2, ["blank", "spoiled"]].sum() - t.loc[1, ["blank", "spoiled"]].sum()),
        "n_flipped": len(flips),
        "flips": [{"state": r.state, "from": candidate_name(d, r.leader_1t), "to": candidate_name(d, r.leader_2t)}
                  for r in flips.sort_values("state").itertuples()],
        "lula_states_1t": int((brazil["leader_1t"] == LULA).sum()),
        "lula_states_2t": int((brazil["leader_2t"] == LULA).sum()),
        "pl_states_1t": int((brazil["leader_1t"] == PL_NUMBER).sum()),
        "pl_states_2t": int((brazil["leader_2t"] == PL_NUMBER).sum()),
        "n_states": len(brazil),
        "abstention_1t": float(t.loc[1, "abstentions"] / t.loc[1, "registered"] * 100),
        "abstention_2t": float(t.loc[2, "abstentions"] / t.loc[2, "registered"] * 100),
    }


def flips_sentence(rh: dict) -> str:
    if not rh["n_flipped"]:
        return "Nenhum estado mudou de candidato preferido entre os turnos."
    names = ", ".join(f"{f['state']} ({f['from']} → {f['to']})" for f in rh["flips"])
    verb = "mudou" if rh["n_flipped"] == 1 else "mudaram"
    return f"{plural(rh['n_flipped'], 'estado', 'estados')} {verb} de candidato preferido entre os turnos: {names}."


# ---------------------------------------------------------------- (a) Goiás, 2026 first round vs runoff

def goias_table(d: dict, shapes) -> pd.DataFrame:
    """One row per municipality of Goiás: 2026 first round vs 2026 runoff."""
    m = d["muni"][(d["muni"]["year"] == 2026) & (d["muni"]["uf"] == GO)].copy()
    m["ibge_code"] = m["ibge_code"].astype(int)
    out = pd.DataFrame(index=pd.Index(sorted(m["ibge_code"].unique()), name="ibge_code"))
    out["name"] = out.index.map(shapes.set_index("id")["name_muni"])
    if out["name"].isna().any():
        raise ValueError("Municipalities of Goiás missing from the IBGE map.")
    for rnd in (1, 2):
        sel = m[m["round"] == rnd]
        out[f"lula_{rnd}t"] = share(sel, 2026, rnd, LULA, "ibge_code")
        out[f"pl_{rnd}t"] = share(sel, 2026, rnd, PL_NUMBER, "ibge_code")
        out[f"leader_{rnd}t"] = leaders(sel, "ibge_code")
        out[f"valid_{rnd}t"] = sel.groupby("ibge_code")["votes"].sum()
        out[f"margin_{rnd}t"] = out[f"lula_{rnd}t"] - out[f"pl_{rnd}t"]
    out["caiado_1t"] = share(m, 2026, 1, CAIADO, "ibge_code")
    out["lula_gain"] = out["lula_2t"] - out["lula_1t"]
    out["pl_gain"] = out["pl_2t"] - out["pl_1t"]
    out["margin_change"] = out["margin_2t"] - out["margin_1t"]
    out["flipped"] = out["leader_1t"] != out["leader_2t"]

    codes = m[["tse_code", "ibge_code"]].drop_duplicates().set_index("tse_code")["ibge_code"]
    t = d["turnout_muni"][(d["turnout_muni"]["year"] == 2026) & (d["turnout_muni"]["uf"] == GO)].copy()
    t["ibge_code"] = t["tse_code"].map(codes)
    for rnd in (1, 2):
        out[f"abstention_{rnd}t"] = t[t["round"] == rnd].set_index("ibge_code")["pct_abstention"]
    return out.reset_index()


def goias_headline(d: dict, gt: pd.DataFrame) -> dict:
    st = d["state"][(d["state"]["uf"] == GO)]
    flips = gt[gt["flipped"]]
    biggest = gt.loc[gt["margin_change"].abs().idxmax()]
    others_1t = gt[~gt["leader_1t"].isin([LULA, PL_NUMBER])]
    t = d["turnout"][(d["turnout"]["year"] == 2026) & (d["turnout"]["uf"] == GO)].set_index("round")
    return {
        "n": len(gt), "n_flipped": len(flips),
        "flipped_to_pl": int((flips["leader_2t"] == PL_NUMBER).sum()),
        "flipped_to_lula": int((flips["leader_2t"] == LULA).sum()),
        "lula_led_1t": int((gt["leader_1t"] == LULA).sum()), "lula_led_2t": int((gt["leader_2t"] == LULA).sum()),
        "pl_led_1t": int((gt["leader_1t"] == PL_NUMBER).sum()), "pl_led_2t": int((gt["leader_2t"] == PL_NUMBER).sum()),
        "other_led_1t": [{"name": r.name, "leader": candidate_name(d, r.leader_1t)} for r in others_1t.itertuples()],
        "lula_1t": share(st, 2026, 1, LULA), "lula_2t": share(st, 2026, 2, LULA),
        "pl_1t": share(st, 2026, 1, PL_NUMBER), "pl_2t": share(st, 2026, 2, PL_NUMBER),
        "caiado_1t": share(st, 2026, 1, CAIADO),
        "biggest": {"name": biggest["name"], "change": float(biggest["margin_change"]),
                    "flipped": bool(biggest["flipped"]), "margin_1t": float(biggest["margin_1t"]),
                    "margin_2t": float(biggest["margin_2t"]), "caiado_1t": float(biggest["caiado_1t"])},
        "pl_gain_above_lula": int((gt["pl_gain"] > gt["lula_gain"]).sum()),
        "lula_grew": int((gt["lula_gain"] > 0).sum()), "pl_grew": int((gt["pl_gain"] > 0).sum()),
        "corr_caiado_pl": float(gt["caiado_1t"].corr(gt["pl_gain"])),
        "abstention_1t": float(t.loc[1, "pct_abstention"]), "abstention_2t": float(t.loc[2, "pct_abstention"]),
    }


def gains_sentence(rh: dict) -> str:
    return (f"Do 1º para o 2º turno, {gained('Lula', rh['lula_gain_votes'])} e "
            f"{gained('Flávio', rh['pl_gain_votes'])}.")


def flows_sentence(rh: dict) -> str:
    """Where the runoff's extra votes came from, as net balances (exact: they add up to the two gains)."""
    both = rh["lula_gain_votes"] + rh["pl_gain_votes"]
    tc, bs = rh["turnout_change"], rh["blank_spoiled_change"]
    return (f"Juntos, os dois ganharam {mi_words(both)} de votos. Os candidatos eliminados tinham "
            f"{mi_words(rh['others_votes_1t'])} no 1º turno; o restante veio de {'mais' if tc >= 0 else 'menos'} "
            f"eleitores indo votar ({mi_words(tc)}) e de {'menos' if bs <= 0 else 'mais'} votos brancos e nulos "
            f"({mi_words(bs)}). São saldos: mostram de onde veio o aumento, não quem votou em quem.")


def grew_sentence(gh: dict) -> str:
    if gh["lula_grew"] == gh["n"] and gh["pl_grew"] == gh["n"]:
        return f"Lula e Flávio cresceram nas {gh['n']} cidades."
    return f"Lula cresceu em {gh['lula_grew']} das {gh['n']} cidades; Flávio, em {gh['pl_grew']}."


def biggest_sentence(gh: dict) -> str:
    b = gh["biggest"]
    return (f"A maior mudança foi em {b['name']}: {margin_text(b['margin_1t'], b['margin_2t'])}"
            f"{'' if b['flipped'] else ', sem troca de lado'}. Caiado tinha {br(b['caiado_1t'])}% ali no 1º turno.")


def corr_sentence(r: float) -> str:
    """Plain-language reading of the Caiado / Flávio correlation; aggregated data, no claim about voters."""
    if r >= 0.5:
        return "Onde Caiado foi mais votado no 1º turno, Flávio tendeu a crescer mais no 2º turno"
    if r <= -0.5:
        return "Onde Caiado foi mais votado no 1º turno, Flávio tendeu a crescer menos no 2º turno"
    return "Não há relação clara entre o voto em Caiado no 1º turno e o crescimento de Flávio no 2º turno"


# ---------------------------------------------------------------- posts

def hundred(v: float) -> int:
    """Share as 'out of every 100 votes', the way the posts say it."""
    return round(v)


def names_list(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " e " + names[-1]


def post_footer(tags: str, teaser: str = "") -> str:
    return (f"\n\nOs números mostram onde o voto mudou, não quem mudou de voto."
            f"{f'{chr(10)}{chr(10)}{teaser}' if teaser else ''}\n\nCódigo e dados: {CODE_URL}\n\n{tags}\n")


def images_note(panel: str, cards: str) -> str:
    img = IMG_DIR.relative_to(ROOT).as_posix()
    return f"Imagens: `{img}/{panel}` (1200x1500) e o carrossel `{img}/{cards}`.\n\n---\n\n"


def rounds_teaser(rh: dict) -> str:
    flips = [f["state"] for f in rh["flips"]]
    if not flips:
        return "Amanhã: o Brasil estado por estado. Nenhum estado trocou de lado entre os turnos."
    if len(flips) == 1:
        return f"Amanhã: o Brasil estado por estado. Só {flips[0]} trocou de lado entre os turnos."
    return f"Amanhã: o Brasil estado por estado. {len(flips)} estados trocaram de lado entre os turnos."


def post_goias(gh: dict, rh: dict) -> str:
    won = "e venceu no estado" if gh["pl_2t"] > gh["lula_2t"] else "mas Lula venceu no estado"
    return images_note("painel_1_goias.png", "card_a1.png` a `card_a3.png") + f"""\
No 1º turno, {hundred(gh['lula_1t'])} de cada 100 votos em Goiás foram para Lula. No 2º, foram {hundred(gh['lula_2t'])}.

Peguei os dados oficiais do TSE e comparei os dois turnos de 2026 nas {gh['n']} cidades do estado:

- Lula era o mais votado em {gh['lula_led_1t']} cidades. No 2º turno, em {gh['lula_led_2t']}.
- {plural(gh['n_flipped'], 'cidade trocou', 'cidades trocaram')} de candidato preferido entre um turno e outro.
- Flávio Bolsonaro foi de {hundred(gh['pl_1t'])} para {hundred(gh['pl_2t'])} de cada 100 votos {won}.
- {grew_sentence(gh)}
- Ronaldo Caiado, ex-governador, tinha {hundred(gh['caiado_1t'])} de cada 100 votos no 1º turno.
- {corr_sentence(gh['corr_caiado_pl'])}.
- {biggest_sentence(gh)}

Quer ver a sua cidade? É só digitar o nome:
{PAGE_URL}#parte-3""" + post_footer("#Eleições2026 #Goiás #DadosAbertos #TSE #DataScience",
                                      rounds_teaser(rh))


def post_states(rh: dict) -> str:
    flips = rh["flips"]
    if not flips:
        flip_line = "Nenhum estado trocou de candidato preferido entre os turnos."
    elif len(flips) == 1:
        f = flips[0]
        flip_line = f"Só {f['state']} trocou de lado: {f['from']} liderava no 1º turno, {f['to']} venceu no 2º."
    else:
        flip_line = flips_sentence(rh)
    return images_note("painel_2_estados.png", "card_b1.png` a `card_b3.png") + f"""\
No 1º turno de 2026, Lula teve {hundred(rh['lula_1t'])} de cada 100 votos válidos e Flávio Bolsonaro, {hundred(rh['pl_1t'])}. \
No 2º, Lula ficou com {hundred(rh['lula_2t'])} e Flávio com {hundred(rh['pl_2t'])}.

Comparei os dois turnos estado por estado, com os dados oficiais do TSE:

- Lula foi o mais votado em {rh['lula_states_1t']} de {rh['n_states']} estados no 1º turno e em {rh['lula_states_2t']} no 2º.
- {flip_line}
- {gains_sentence(rh)}
- {flows_sentence(rh)}

Veja cada estado, 1º x 2º turno:
{PAGE_URL}#parte-2""" + post_footer(
        "#Eleições2026 #DadosAbertos #TSE #DataScience",
        "Amanhã: o 2º turno de 2026 comparado ao de 2022, Lula contra Jair e contra Flávio Bolsonaro.")


def post_runoffs(h: dict) -> str:
    rn = h["round_name"]
    turns = []
    if h["flipped_to_pl_names"]:
        turns.append(f"{names_list(h['flipped_to_pl_names'])} passou para Bolsonaro" if len(h["flipped_to_pl_names"]) == 1
                     else f"{names_list(h['flipped_to_pl_names'])} passaram para Bolsonaro")
    if h["flipped_to_pt_names"]:
        turns.append(f"{names_list(h['flipped_to_pt_names'])} passou para Lula" if len(h["flipped_to_pt_names"]) == 1
                     else f"{names_list(h['flipped_to_pt_names'])} passaram para Lula")
    turns_line = ("Trocas: " + "; ".join(turns) + ".") if turns else "Nenhum estado trocou de lado."
    a = h["abroad"]
    return images_note("painel_3_2022x2026.png", "card_1.png` a `card_5.png") + f"""\
Em 2022, Lula teve {br(h['lula_2022'])}% dos votos válidos no {rn} contra Jair Bolsonaro. Em 2026, teve {br(h['lula_2026'])}% contra Flávio Bolsonaro, filho de Jair.

Comparei os dois {rn}s estado por estado, com os dados oficiais do TSE:

- Lula venceu em {h['lula_states_2022']} de {h['n_states']} estados em 2022 e em {h['lula_states_2026']} em 2026. {turns_line}
- {lula_trend(h)}
- No exterior, Lula teve {br(a['lula_2026'])}% em 2026 ({br(a['lula_2022'])}% em 2022).
- Cerca de 1 em cada {round(100 / h['abstention_2026'])} eleitores aptos não votou, mesmo com o voto obrigatório para a maioria.

Escolha um estado e veja o mapa cidade por cidade:
{PAGE_URL}#parte-1""" + post_footer("#Eleições2026 #DadosAbertos #TSE #DataScience")


def write_posts(h: dict, rh: dict, gh: dict) -> None:
    """The three posts of the series, one per comparison, rebuilt with the current numbers on every run."""
    PUB_DIR.mkdir(parents=True, exist_ok=True)
    posts = {"post_1_goias": post_goias(gh, rh), "post_2_estados": post_states(rh),
             "post_3_2022x2026": post_runoffs(h)}
    for name, text in posts.items():
        (PUB_DIR / f"{name}_{LANG}.md").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- charts

def draw_bars(ax, rows: list, scale: float = 1.0) -> None:
    """Stacked 100% bars, one per (label, [(name, share, color), ...]); a small last part is labelled at the right."""
    for row, (label, parts) in enumerate(rows):
        y = len(rows) - 1 - row
        left = 0.0
        for k, (name, value, color) in enumerate(parts):
            ax.barh(y, value, left=left, color=color, height=0.5, edgecolor=SURFACE, linewidth=2)
            if value >= 9:
                ax.text(left + value / 2, y, f"{br(value)}%", ha="center", va="center", color="white",
                        fontsize=13 * scale, fontweight="bold")
                ax.text(left + value / 2, y + 0.33, name, ha="center", va="bottom", color=INK_2,
                        fontsize=10 * scale)
            elif value >= 0.5 and k == len(parts) - 1:
                ax.text(101, y, f"{name}\n{br(value)}%", ha="left", va="center", color=INK_2, fontsize=10 * scale)
            left += value
        ax.text(-1.5, y, label, ha="right", va="center", fontsize=11.5 * scale, fontweight="bold", linespacing=1.25)
    ax.axvline(50, color=INK, linewidth=0.8, linestyle=(0, (2, 3)), ymin=0.02, ymax=0.9)
    ax.set_xlim(0, 109)
    ax.set_ylim(-0.45, len(rows) - 1 + 0.75)
    ax.axis("off")


def national_rows(d: dict, rounds=None) -> list:
    rows = []
    for year, rnd in rounds or d["rounds"]:
        lula, pl = share(d["national"], year, rnd, LULA), share(d["national"], year, rnd, PL_NUMBER)
        rows.append((f"{year}\n{ROUND_NAME[rnd]}", [("Lula (PT)", lula, PT), (f"{PL_NAME[year]} (PL)", pl, PL),
                                                     ("Outros", 100 - lula - pl, OTHERS)]))
    return rows


def draw_national(ax, d: dict, scale: float = 1.0) -> None:
    draw_bars(ax, national_rows(d), scale)


def draw_state_maps(axes, geo, h: dict, fontsize: float = 15) -> None:
    for ax, year in zip(axes, (2022, 2026)):
        geo.plot(ax=ax, color=geo[f"leader_{year}"].map({"PL": PL, "PT": PT}), edgecolor=SURFACE, linewidth=0.7)
        n_pt = h[f"lula_states_{year}"]
        ax.set_title(f"{year}: Lula {n_pt} × {h['n_states'] - n_pt} {PL_NAME[year].split()[0]} Bolsonaro",
                     fontsize=fontsize, fontweight="bold", color=INK)
        ax.axis("off")


def draw_leader_maps(axes, geo, titles, fontsize: float = 15, edge: float = 0.7) -> None:
    """Map of who came first, one per round; places that changed leader get a dark outline on the runoff map."""
    for ax, rnd, title in zip(axes, (1, 2), titles):
        geo.plot(ax=ax, color=geo[f"leader_{rnd}t"].map(candidate_color), edgecolor=SURFACE, linewidth=edge)
        if rnd == 2 and geo["flipped"].any():
            geo[geo["flipped"]].boundary.plot(ax=ax, color=INK, linewidth=edge * 2.4)
        ax.set_title(title, fontsize=fontsize, fontweight="bold", color=INK)
        ax.axis("off")


def leader_legend(fig, y: float, fontsize: float, numbers=(LULA, PL_NUMBER), flipped: bool = False,
                  d: dict | None = None) -> None:
    if d is None:
        handles = [Patch(color=PT, label="Lula (PT) à frente"), Patch(color=PL, label="Bolsonaro (PL) à frente")]
    else:
        handles = [Patch(color=candidate_color(n), label=f"{candidate_name(d, n)} à frente") for n in numbers]
    if flipped:
        handles.append(Patch(facecolor="none", edgecolor=INK, linewidth=2, label="mudou de líder"))
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), frameon=False, fontsize=fontsize,
               bbox_to_anchor=(0.5, y))


def chart_national(d: dict, h: dict) -> None:
    fig, ax = plt.subplots(figsize=(11, 1.6 + 1.25 * len(d["rounds"])))
    draw_national(ax, d)
    fig.suptitle(f"Brasil, {h['round_name']}: Lula {br(h['lula_2022'])}% em 2022, {br(h['lula_2026'])}% em 2026",
                 x=0.02, ha="left", fontsize=16, fontweight="bold")
    fig.text(0.02, 0.01, SOURCE + " Linha pontilhada: 50%.", color=MUTED, fontsize=9)
    fig.savefig(IMG_DIR / "01_national_result.png", dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def chart_state_maps(geo, h: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.3))
    draw_state_maps(axes, geo, h)
    leader_legend(fig, 0.075, 11)
    fig.suptitle(f"Quem liderou em cada estado, {h['round_name']}: "
                 f"{h['flipped_to_pl']} viraram para Bolsonaro, {h['flipped_to_pt']} para Lula",
                 x=0.03, ha="left", fontsize=17, fontweight="bold")
    fig.text(0.03, 0.045, abroad_note(h), color=INK_2, fontsize=10)
    fig.text(0.03, 0.015, SOURCE + " 26 estados e o Distrito Federal.", color=MUTED, fontsize=9)
    fig.subplots_adjust(top=0.84, bottom=0.14, wspace=0.02)
    fig.savefig(IMG_DIR / "02_state_maps.png", dpi=100)
    plt.close(fig)


def chart_state_shift(states: pd.DataFrame, h: dict) -> None:
    df = states[states["uf"] != ABROAD].sort_values("lula_2026").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9, 11))
    for y, row in df.iterrows():
        ax.plot([row["lula_2022"], row["lula_2026"]], [y, y], color="#c3c2b7", linewidth=2, zorder=1)
    ax.scatter(df["lula_2022"], df.index, s=70, color=SURFACE, edgecolor=PT, linewidth=1.8, zorder=2, label="2022")
    ax.scatter(df["lula_2026"], df.index, s=70, color=PT, edgecolor=SURFACE, linewidth=1, zorder=3, label="2026")
    # votes abroad: listed apart, below the states, since they belong to no state
    abroad, y_abroad = h["abroad"], -2.0
    ax.plot([abroad["lula_2022"], abroad["lula_2026"]], [y_abroad, y_abroad], color="#c3c2b7", linewidth=2, zorder=1)
    ax.scatter([abroad["lula_2022"]], [y_abroad], s=70, color=SURFACE, edgecolor=PT, linewidth=1.8, zorder=2)
    ax.scatter([abroad["lula_2026"]], [y_abroad], s=70, color=PT, edgecolor=SURFACE, linewidth=1, zorder=3)
    ax.axhline(-1.0, color=GRID, linewidth=1)
    ax.set_yticks([y_abroad, *df.index], [NAME_PT[ABROAD], *(f"{s}  ·  {r}" for s, r in zip(df["state"], df["region"]))])
    ax.tick_params(axis="y", colors=INK_2, length=0)
    ax.set_ylim(y_abroad - 0.8, len(df) - 0.2)
    ax.axvline(50, color=INK, linewidth=0.8, linestyle=(0, (2, 3)))
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel(f"Votos válidos de Lula, {h['round_name']} (%)")
    ax.legend(frameon=False, loc="upper left", fontsize=11)
    ax.set_title(lula_trend(h).split(". ")[0], loc="left", fontsize=16, fontweight="bold", color=INK, pad=14)
    fig.text(0.02, 0.0, SOURCE + " Linha pontilhada: 50%.", color=MUTED, fontsize=9)
    fig.savefig(IMG_DIR / "03_states_shift.png", dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def chart_br_rounds_maps(state_shapes, rt: pd.DataFrame, rh: dict, d: dict) -> None:
    geo = state_shapes.merge(rt, left_on="abbrev_state", right_on="uf", how="inner")
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.5))
    titles = [f"1º turno: Lula {rh['lula_states_1t']} × {rh['pl_states_1t']} Flávio",
              f"2º turno: Lula {rh['lula_states_2t']} × {rh['pl_states_2t']} Flávio"]
    draw_leader_maps(axes, geo, titles)
    numbers = sorted(set(rt["leader_1t"]) | set(rt["leader_2t"]), key=lambda n: (n != LULA, n != PL_NUMBER, n))
    leader_legend(fig, 0.075, 11, numbers, flipped=bool(rh["n_flipped"]), d=d)
    title = (f"2026: {plural(rh['n_flipped'], 'estado mudou', 'estados mudaram')} de candidato preferido "
             f"entre os turnos" if rh["n_flipped"] else "2026: nenhum estado mudou de candidato preferido entre os turnos")
    fig.suptitle(title, x=0.03, ha="left", fontsize=17, fontweight="bold")
    fig.text(0.03, 0.045, flips_sentence(rh) if rh["n_flipped"] else "", color=INK_2, fontsize=10)
    fig.text(0.03, 0.015, SOURCE + " Cor: candidato mais votado em cada estado.", color=MUTED, fontsize=9)
    fig.subplots_adjust(top=0.84, bottom=0.14, wspace=0.02)
    fig.savefig(IMG_DIR / "04_br_turnos_mapas.png", dpi=100)
    plt.close(fig)


def chart_br_rounds_margin(rt: pd.DataFrame, rh: dict) -> None:
    df = rt[rt["uf"] != ABROAD].sort_values("margin_2t").reset_index(drop=True)
    abroad = rt[rt["uf"] == ABROAD].iloc[0]
    fig, ax = plt.subplots(figsize=(9, 11))
    y_abroad = -2.0
    rows = [*((y, r) for y, r in df.iterrows()), (y_abroad, abroad)]
    for y, r in rows:
        color = PT if r["margin_2t"] > 0 else PL
        ax.plot([r["margin_1t"], r["margin_2t"]], [y, y], color="#c3c2b7", linewidth=2, zorder=1)
        ax.scatter([r["margin_1t"]], [y], s=70, color=SURFACE, edgecolor=INK_2, linewidth=1.6, zorder=2)
        ax.scatter([r["margin_2t"]], [y], s=70, color=color, edgecolor=SURFACE, linewidth=1, zorder=3)
    ax.axhline(-1.0, color=GRID, linewidth=1)
    labels = [f"{s}  ·  {r}" for s, r in zip(df["state"], df["region"])]
    ax.set_yticks([y_abroad, *df.index], [NAME_PT[ABROAD], *labels])
    for tick, flipped in zip(ax.get_yticklabels()[1:], df["flipped"]):
        if flipped:
            tick.set_fontweight("bold")
            tick.set_color(INK)
    ax.tick_params(axis="y", colors=INK_2, length=0)
    ax.set_ylim(y_abroad - 0.8, len(df) - 0.2)
    ax.axvline(0, color=INK, linewidth=0.8, linestyle=(0, (2, 3)))
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Vantagem de Lula sobre Flávio, em pontos (negativo: Flávio à frente)")
    ax.legend(handles=[Line2D([], [], marker="o", ls="", markerfacecolor=SURFACE, markeredgecolor=INK_2, ms=8,
                              label="1º turno"),
                       Line2D([], [], marker="o", ls="", markerfacecolor=PT, markeredgecolor=SURFACE, ms=8,
                              label="2º turno (cor de quem venceu)")],
              frameon=False, loc="upper left", fontsize=11)
    ax.set_title("2026: a vantagem de Lula sobre Flávio no 1º e no 2º turno", loc="left", fontsize=16,
                 fontweight="bold", color=INK, pad=14)
    fig.text(0.02, 0.0, SOURCE + " Em negrito: estados que mudaram de candidato preferido.", color=MUTED, fontsize=9)
    fig.savefig(IMG_DIR / "05_br_turnos_estados.png", dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def chart_go_rounds_maps(go_geo, gh: dict, d: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 7))
    titles = [f"1º turno: Lula à frente em {gh['lula_led_1t']}", f"2º turno: Lula à frente em {gh['lula_led_2t']}"]
    draw_leader_maps(axes, go_geo, titles, edge=0.4)
    numbers = sorted(set(go_geo["leader_1t"]) | set(go_geo["leader_2t"]),
                     key=lambda n: (n != LULA, n != PL_NUMBER, n))
    leader_legend(fig, 0.06, 11, numbers, flipped=bool(gh["n_flipped"]), d=d)
    title = (f"Goiás: {plural(gh['n_flipped'], 'município mudou', 'municípios mudaram')} de candidato preferido "
             f"entre os turnos" if gh["n_flipped"] else "Goiás: nenhum município mudou de candidato preferido")
    fig.suptitle(title, x=0.03, ha="left", fontsize=17, fontweight="bold")
    fig.text(0.03, 0.015, SOURCE + f" {gh['n']} municípios. Cor: candidato mais votado.", color=MUTED, fontsize=9)
    fig.subplots_adjust(top=0.86, bottom=0.12, wspace=0.02)
    fig.savefig(IMG_DIR / "06_go_turnos_mapas.png", dpi=100)
    plt.close(fig)


def chart_go_caiado(gt: pd.DataFrame, gh: dict) -> None:
    fig, ax = plt.subplots(figsize=(10, 7.5))
    size = gt["valid_2t"] / gt["valid_2t"].max() * 1400 + 12
    ax.scatter(gt["caiado_1t"], gt["pl_gain"], s=size, color=PL, alpha=0.45, edgecolor=SURFACE, linewidth=0.6)
    for r in gt.nlargest(3, "valid_2t").itertuples():
        ax.annotate(r.name, (r.caiado_1t, r.pl_gain), xytext=(8, 8), textcoords="offset points", fontsize=10,
                    color=INK)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("Votos válidos de Ronaldo Caiado no 1º turno (%)")
    ax.set_ylabel("Crescimento de Flávio do 1º para o 2º turno (pontos)")
    ax.set_title(corr_sentence(gh["corr_caiado_pl"]), loc="left", fontsize=15, fontweight="bold", color=INK, pad=28)
    ax.text(0, 1.02, f"Cada bolha é um dos {gh['n']} municípios de Goiás, do tamanho do seu eleitorado. "
                     f"Correlação: {br(gh['corr_caiado_pl'], 2)}.",
            transform=ax.transAxes, fontsize=10.5, color=INK_2)
    fig.text(0.02, 0.0, SOURCE + " Dados agregados por município: mostram onde o voto mudou, não quem mudou.",
             color=MUTED, fontsize=9)
    fig.savefig(IMG_DIR / "07_go_caiado.png", dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def draw_cards(cards: list, header: str, prefix: str, footer: str) -> None:
    for i, (color, number, text) in enumerate(cards, start=1):
        fig = plt.figure(figsize=(10.8, 10.8))
        fig.add_artist(plt.Rectangle((0.08, 0.86), 0.12, 0.012, color=color, transform=fig.transFigure))
        fig.text(0.08, 0.80, header, fontsize=20, color=INK_2, fontweight="bold")
        fig.text(0.08, 0.50, number, fontsize=118 if len(number) <= 9 else 96, fontweight="bold", color=INK,
                 va="center")
        fig.text(0.08, 0.33, text, fontsize=30, color=INK_2, va="top", linespacing=1.35)
        fig.text(0.08, 0.06, f"{i}/{len(cards)} · {footer} · {REPO}", fontsize=16, color=MUTED)
        fig.savefig(IMG_DIR / f"{prefix}{i}.png", dpi=100)
        plt.close(fig)


def chart_cards(h: dict) -> None:
    rn = h["round_name"]
    rose = h["lula_rose_in"] > h["lula_fell_in"]
    state, value = h["biggest_gain"] if rose else h["biggest_drop"]
    cards = [
        (PT, f"{round(h['lula_2022'])} → {round(h['lula_2026'])}",
         f"de cada 100 votos foram para Lula\nno {rn}, em 2022 e em 2026"),
        (PL, f"{round(h['pl_2022'])} → {round(h['pl_2026'])}",
         "de cada 100 votos foram para a\nfamília Bolsonaro: Jair em 2022,\no filho Flávio em 2026"),
        (PT, f"{h['lula_states_2022']} → {h['lula_states_2026']}",
         f"dos {h['n_states']} estados do Brasil\ncom Lula em primeiro"),
        (PT, f"{h['lula_rose_in'] if rose else h['lula_fell_in']} de {h['n_states']}",
         f"estados onde a fatia de Lula\n{'subiu' if rose else 'caiu'}. Maior {'alta' if rose else 'queda'}: "
         f"{state},\n{br(abs(value))} pontos"),
        (OTHERS, f"1 em {round(100 / h['abstention_2026'])}",
         "dos eleitores aptos não votou,\nmesmo com o voto obrigatório\npara a maioria. " + abstention_note(h)),
    ]
    draw_cards(cards, "BRASIL · PRESIDENTE · 2022 x 2026", "card_", f"Fonte: TSE, {rn}")


def chart_cards_rounds(rh: dict) -> None:
    names = [f["state"] for f in rh["flips"]]
    listed = ", ".join(names[:3]) + (" e outros" if len(names) > 3 else "")
    cards = [
        (OTHERS, str(rh["n_flipped"]),
         f"{'estado mudou' if rh['n_flipped'] == 1 else 'estados mudaram'} de candidato\npreferido entre o 1º e o 2º turno"
         + (f":\n{listed}" if names else "")),
        (PT, millions(rh["lula_gain_votes"]),
         f"votos para Lula entre os turnos:\nde {br(rh['lula_1t'])}% para {br(rh['lula_2t'])}%\ndos votos válidos"),
        (PL, millions(rh["pl_gain_votes"]),
         f"votos para Flávio entre os turnos:\nde {br(rh['pl_1t'])}% para {br(rh['pl_2t'])}%. Os outros\n"
         f"candidatos tinham {millions(rh['others_votes_1t']).lstrip('+')} no 1º turno"),
    ]
    draw_cards(cards, "BRASIL · PRESIDENTE 2026 · 1º x 2º TURNO", "card_b", "Fonte: TSE")


def chart_cards_goias(gh: dict) -> None:
    # fixed colors: red for Lula, blue for Flávio, amber for Caiado, gray for counts
    cards = [
        (PT, f"{gh['lula_led_1t']} → {gh['lula_led_2t']}",
         f"dos {gh['n']} municípios de Goiás\ncom Lula à frente,\nno 1º e no 2º turno"),
        (OTHERS, str(gh["n_flipped"]),
         f"{'cidade trocou' if gh['n_flipped'] == 1 else 'cidades trocaram'} de candidato\n"
         f"preferido entre os turnos:\n{gh['flipped_to_lula']} para Lula, {gh['flipped_to_pl']} para Flávio"),
        (CAIADO_COLOR, f"{br(gh['caiado_1t'])}%",
         f"dos votos de Goiás foram para\nRonaldo Caiado no 1º turno. No 2º,\n"
         f"Flávio foi de {br(gh['pl_1t'])}% a {br(gh['pl_2t'])}% no estado"),
    ]
    draw_cards(cards, "GOIÁS · PRESIDENTE 2026 · 1º x 2º TURNO", "card_a", "Fonte: TSE")


def draw_panel(filename: str, title: str, subtitle: str, tiles: list, bar_rows: list, maps_title: str,
               draw_maps, legend, notes: list[str]) -> None:
    """One 1200x1500 panel per post, all in the layout of the first-round summary panel:
    four number tiles, the 100% bars, two maps side by side, notes and source."""
    fig = plt.figure(figsize=(12, 15))
    fig.text(0.05, 0.955, title, fontsize=34, fontweight="bold")
    fig.text(0.05, 0.925, subtitle, fontsize=18, color=INK_2)
    for k, (color, number, caption) in enumerate(tiles):
        x = 0.05 + k * 0.232
        fig.add_artist(plt.Rectangle((x, 0.875), 0.05, 0.006, color=color, transform=fig.transFigure))
        fig.text(x, 0.835, number, fontsize=35 if len(number) <= 8 else 30, fontweight="bold", va="center")
        fig.text(x, 0.808, caption, fontsize=15.5, color=INK_2, va="top", linespacing=1.3)

    fig.text(0.05, 0.725, "De cada 100 votos válidos", fontsize=20, fontweight="bold")
    draw_bars(fig.add_axes([0.12, 0.53, 0.86, 0.185]), bar_rows, scale=1.15)

    fig.text(0.05, 0.495, maps_title, fontsize=20, fontweight="bold")
    draw_maps([fig.add_axes([0.02, 0.135, 0.48, 0.335]), fig.add_axes([0.50, 0.135, 0.48, 0.335])])
    legend(fig)
    for k, note in enumerate(notes):
        fig.text(0.05, 0.068 - k * 0.022, note, fontsize=14, color=INK_2)
    fig.text(0.05, 0.016, SOURCE, fontsize=13, color=MUTED)
    fig.text(0.95, 0.016, REPO, fontsize=13, color=MUTED, ha="right")
    fig.savefig(IMG_DIR / filename, dpi=100)
    plt.close(fig)


def panel_goias(d: dict, go_geo, gh: dict) -> None:
    st = d["state"][d["state"]["uf"] == GO]
    rows = []
    for rnd in (1, 2):
        parts = [("Lula (PT)", share(st, 2026, rnd, LULA), PT), ("Flávio Bolsonaro (PL)", share(st, 2026, rnd, PL_NUMBER), PL)]
        if rnd == 1:
            parts.append(("Ronaldo Caiado (PSD)", share(st, 2026, 1, CAIADO), CAIADO_COLOR))
        parts.append(("Outros", 100 - sum(p[1] for p in parts), OTHERS))
        rows.append((f"2026\n{ROUND_NAME[rnd]}", parts))
    numbers = sorted(set(go_geo["leader_1t"]) | set(go_geo["leader_2t"]), key=lambda n: (n != LULA, n != PL_NUMBER, n))
    draw_panel(
        "painel_1_goias.png", "Como Goiás votou para presidente",
        f"2026, 1º x 2º turno · {gh['n']} municípios",
        [(PT, f"{hundred(gh['lula_1t'])} → {hundred(gh['lula_2t'])}", "de cada 100 votos\npara Lula"),
         (PL, f"{hundred(gh['pl_1t'])} → {hundred(gh['pl_2t'])}", "de cada 100 votos\npara Flávio"),
         (PT, f"{gh['lula_led_1t']} → {gh['lula_led_2t']}", "cidades com\nLula à frente"),
         (OTHERS, str(gh["n_flipped"]), "cidades trocaram\nde candidato")],
        rows, "Quem ficou em primeiro em cada cidade",
        lambda axes: draw_leader_maps(axes, go_geo, ["1º turno", "2º turno"], fontsize=17, edge=0.4),
        lambda fig: leader_legend(fig, 0.088, 15, numbers, flipped=bool(gh["n_flipped"]), d=d),
        [f"{grew_sentence(gh)} {corr_sentence(gh['corr_caiado_pl'])}.",
         f"Correlação entre o voto em Caiado (1º turno) e o crescimento de Flávio, cidade a cidade: "
         f"{br(gh['corr_caiado_pl'], 2)}."])


def panel_states(d: dict, state_shapes, rt: pd.DataFrame, rh: dict) -> None:
    geo = state_shapes.merge(rt, left_on="abbrev_state", right_on="uf", how="inner")
    numbers = sorted(set(rt["leader_1t"]) | set(rt["leader_2t"]), key=lambda n: (n != LULA, n != PL_NUMBER, n))
    draw_panel(
        "painel_2_estados.png", "Como o Brasil votou: 1º x 2º turno",
        "2026 · 26 estados e o Distrito Federal",
        [(PT, f"{hundred(rh['lula_1t'])} → {hundred(rh['lula_2t'])}", "de cada 100 votos\npara Lula"),
         (PL, f"{hundred(rh['pl_1t'])} → {hundred(rh['pl_2t'])}", "de cada 100 votos\npara Flávio"),
         (OTHERS, str(rh["n_flipped"]), f"{'estado trocou' if rh['n_flipped'] == 1 else 'estados trocaram'}\nde candidato"),
         (OTHERS, millions(rh["others_votes_1t"]).lstrip("+"), "votos dos candidatos\neliminados")],
        national_rows(d, [(2026, 1), (2026, 2)]), "Quem ficou em primeiro em cada estado",
        lambda axes: draw_leader_maps(axes, geo, [f"1º turno: Lula {rh['lula_states_1t']} × {rh['pl_states_1t']} Flávio",
                                                  f"2º turno: Lula {rh['lula_states_2t']} × {rh['pl_states_2t']} Flávio"],
                                      fontsize=17),
        lambda fig: leader_legend(fig, 0.088, 15, numbers, flipped=bool(rh["n_flipped"]), d=d),
        [flips_sentence(rh), gains_sentence(rh)])


def panel_runoffs(d: dict, geo, h: dict) -> None:
    draw_panel(
        "painel_3_2022x2026.png", "Como o Brasil votou para presidente",
        f"2022 x 2026, {h['round_name']} · 26 estados e o Distrito Federal",
        [(PT, f"{hundred(h['lula_2022'])} → {hundred(h['lula_2026'])}", "de cada 100 votos\npara Lula"),
         (PL, f"{hundred(h['pl_2022'])} → {hundred(h['pl_2026'])}", "de cada 100 votos\npara um Bolsonaro"),
         (PT, f"{h['lula_states_2022']} → {h['lula_states_2026']}", f"de {h['n_states']} estados\ncom Lula à frente"),
         (OTHERS, f"1 em {round(100 / h['abstention_2026'])}", "dos eleitores\naptos não votou")],
        national_rows(d), f"Quem ficou em primeiro em cada estado ({h['round_name']})",
        lambda axes: draw_state_maps(axes, geo, h, 17),
        lambda fig: leader_legend(fig, 0.088, 15),
        [abroad_note(h)])


# ---------------------------------------------------------------- maps and page

def rounded(obj, digits: int = 3):
    """Round every coordinate so the map files stay small."""
    if isinstance(obj, float):
        return round(obj, digits)
    if isinstance(obj, list):
        return [rounded(x, digits) for x in obj]
    if isinstance(obj, dict):
        return {k: rounded(v, digits) for k, v in obj.items()}
    return obj


def to_geojson(gdf, tolerance: float) -> dict:
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.simplify(tolerance).map(clockwise)
    return rounded(json.loads(gdf.to_json(drop_id=True)))


def clockwise(geom):
    """Plotly fills the outside of a polygon whose outer ring runs counter-clockwise."""
    if geom.geom_type == "Polygon":
        return orient(geom, sign=-1.0)
    if geom.geom_type == "MultiPolygon":
        return MultiPolygon([orient(part, sign=-1.0) for part in geom.geoms])
    return geom


def build_municipal_maps(d: dict, shapes) -> None:
    """One small file per state, loaded by the page only when that state is opened."""
    base = d["base"]
    votes = d["muni"][d["muni"]["ibge_code"].notna()]
    fields = [(f"{name}_{year}", year, base, number) for year in (2022, 2026)
              for name, number in (("lula", LULA), ("pl", PL_NUMBER))]
    fields += [(f"{name}_2026_1t", 2026, 1, number) for name, number in (("lula", LULA), ("pl", PL_NUMBER))]
    data = pd.DataFrame({col: share(votes, year, rnd, number, "ibge_code") for col, year, rnd, number in fields}).round(1)

    merged = shapes.merge(data, left_on="id", right_index=True, how="left")
    unmatched = sorted(merged.loc[merged["lula_2026"].isna(), "name_muni"])
    if unmatched:
        print(f"No mapa sem votos: {unmatched}")
    if len(unmatched) > 5:
        raise ValueError("Too many municipalities on the map have no votes: the code table is out of date.")
    cols = ["id", "name_muni", *(f[0] for f in fields), "geometry"]
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    for uf, part in merged.groupby("abbrev_state"):
        minx, miny, maxx, maxy = part.total_bounds
        payload = {"bounds": [round(minx, 2), round(miny, 2), round(maxx, 2), round(maxy, 2)],
                   "geojson": to_geojson(part[cols].rename(columns={"name_muni": "name"}), 0.01)}
        (GEO_DIR / f"{uf}.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                                            encoding="utf-8")


def r1(v: float) -> float:
    return round(float(v), 1)


def build_page(d: dict, states: pd.DataFrame, state_shapes, h: dict, rt: pd.DataFrame, rh: dict,
               gt: pd.DataFrame, gh: dict) -> None:
    base, nat = d["base"], d["national"]
    context = [{"year": y, "round": ROUND_NAME[r], "lula": r1(share(nat, y, r, LULA)),
                "pl": r1(share(nat, y, r, PL_NUMBER)), "pl_name": PL_NAME[y]} for y, r in d["rounds"]]
    by_state = {}
    for year, rnd in d["rounds"]:
        lula, pl = share(d["state"], year, rnd, LULA, "uf"), share(d["state"], year, rnd, PL_NUMBER, "uf")
        for uf in lula.index:
            by_state.setdefault(uf, []).append({"year": int(year), "round": ROUND_NAME[rnd],
                                                "lula": r1(lula[uf]), "pl": r1(pl[uf])})

    regions = []
    for region in REGIONS:
        sel = d["state"][(d["state"]["region"] == region) & (d["state"]["round"] == base)]
        regions.append({"name": REGION_PT[region],
                        **{f"{n}_{y}": r1(share(sel, y, base, num))
                           for y in (2022, 2026) for n, num in (("lula", LULA), ("pl", PL_NUMBER))}})

    records = [
        {"uf": r.uf, "name": r.state, "region": r.region, "registered": int(r.registered_2026),
         "lula22": r1(r.lula_2022), "lula26": r1(r.lula_2026), "pl22": r1(r.pl_2022),
         "pl26": r1(r.pl_2026), "lead22": r.leader_2022, "lead26": r.leader_2026,
         "abst22": r1(r.abstention_2022), "abst26": r1(r.abstention_2026), "rounds": by_state[r.uf]}
        for r in states.itertuples()
    ]
    rounds_rows = [
        {"uf": r.uf, "name": r.state, "region": r.region, "lula1": r1(r.lula_1t), "pl1": r1(r.pl_1t),
         "lula2": r1(r.lula_2t), "pl2": r1(r.pl_2t), "lead1": candidate_name(d, r.leader_1t),
         "key1": candidate_key(r.leader_1t), "lead2": candidate_name(d, r.leader_2t),
         "key2": candidate_key(r.leader_2t), "flipped": bool(r.flipped)}
        for r in rt.itertuples()
    ]
    goias_rows = [
        {"id": int(r.ibge_code), "name": r.name, "lula1": r1(r.lula_1t), "pl1": r1(r.pl_1t),
         "caiado1": r1(r.caiado_1t), "lula2": r1(r.lula_2t), "pl2": r1(r.pl_2t),
         "lead1": candidate_name(d, r.leader_1t), "key1": candidate_key(r.leader_1t),
         "lead2": candidate_name(d, r.leader_2t), "key2": candidate_key(r.leader_2t), "flipped": bool(r.flipped),
         "shift": r1(r.margin_change), "abst1": r1(r.abstention_1t), "abst2": r1(r.abstention_2t)}
        for r in gt.itertuples()
    ]
    data = {
        "round": h["round_name"], "pl_name": PL_NAME, "states": records, "regions": regions, "context": context,
        "national": {**{k: r1(h[k]) for k in ("lula_2022", "lula_2026", "pl_2022", "pl_2026",
                                               "abstention_2022", "abstention_2026")},
                     "lula_change": r1(h["lula_2026"] - h["lula_2022"]),
                     "pl_change": r1(h["pl_2026"] - h["pl_2022"])},
        "counts": {k: h[k] for k in ("lula_states_2022", "lula_states_2026", "n_states", "lula_fell_in",
                                     "lula_rose_in")},
        "abroad": {k: (v if isinstance(v, int) else r1(v)) for k, v in h["abroad"].items()},
        "rounds": {"states": rounds_rows, "flips_text": flips_sentence(rh),
                   "gains_text": f"{gains_sentence(rh)} {flows_sentence(rh)}",
                   **{k: r1(rh[k]) for k in ("lula_1t", "lula_2t", "pl_1t", "pl_2t", "others_1t",
                                             "abstention_1t", "abstention_2t")},
                   **{k: rh[k] for k in ("lula_gain_votes", "pl_gain_votes", "others_votes_1t", "n_flipped",
                                         "lula_states_1t", "lula_states_2t", "n_states")}},
        "goias": {"rows": goias_rows, "corr_text": corr_sentence(gh["corr_caiado_pl"]),
                  "grew_text": grew_sentence(gh), "biggest_text": biggest_sentence(gh),
                  "corr": round(gh["corr_caiado_pl"], 2), "biggest": gh["biggest"],
                  **{k: r1(gh[k]) for k in ("lula_1t", "lula_2t", "pl_1t", "pl_2t", "caiado_1t",
                                            "abstention_1t", "abstention_2t")},
                  **{k: gh[k] for k in ("n", "n_flipped", "lula_led_1t", "lula_led_2t", "pl_led_1t",
                                        "pl_led_2t", "flipped_to_pl", "flipped_to_lula", "other_led_1t")}},
    }
    shapes = to_geojson(state_shapes[["abbrev_state", "geometry"]].rename(columns={"abbrev_state": "uf"}), 0.05)

    html = (Path(__file__).parent / "page_template.html").read_text(encoding="utf-8")
    html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    html = html.replace("__STATES_GEO__", json.dumps(shapes, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__CODE_URL__", CODE_URL)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")


def main() -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    d = load()
    states = state_table(d)
    h = headline(d, states)
    rt = rounds_table(d)
    rh = rounds_headline(d, rt)
    # summary_states.csv belongs to the frozen first-round page; the runoff one gets its own name
    states.to_csv(DATA_DIR / "summary_states_runoff_2022_2026.csv", index=False, encoding="utf-8")
    rt.to_csv(DATA_DIR / "summary_states_rounds_2026.csv", index=False, encoding="utf-8")

    state_shapes = geobr.read_state(year=2020)
    geo = state_shapes.merge(states, left_on="abbrev_state", right_on="uf", how="left")
    if geo["lula_2026"].isna().any() or len(geo) != h["n_states"]:
        raise ValueError("States on the map and in the data do not match.")
    muni_shapes = geobr.read_municipality(code_muni="all", year=MESH_YEAR)
    muni_shapes["id"] = muni_shapes["code_muni"].astype(int)

    gt = goias_table(d, muni_shapes)
    gh = goias_headline(d, gt)
    gt.to_csv(DATA_DIR / "summary_goias_rounds_2026.csv", index=False, encoding="utf-8")
    go_geo = muni_shapes[muni_shapes["abbrev_state"] == GO].merge(gt, left_on="id", right_on="ibge_code")
    if len(go_geo) != gh["n"]:
        raise ValueError(f"Goiás: {gh['n']} municipalities with votes, {len(go_geo)} on the map.")

    chart_national(d, h)
    chart_state_maps(geo, h)
    chart_state_shift(states, h)
    chart_cards(h)
    chart_br_rounds_maps(state_shapes, rt, rh, d)
    chart_br_rounds_margin(rt, rh)
    chart_cards_rounds(rh)
    chart_go_rounds_maps(go_geo, gh, d)
    chart_go_caiado(gt, gh)
    chart_cards_goias(gh)
    build_municipal_maps(d, muni_shapes)
    panel_goias(d, go_geo, gh)
    panel_states(d, state_shapes, rt, rh)
    panel_runoffs(d, geo, h)
    build_page(d, states, state_shapes, h, rt, rh, gt, gh)
    write_posts(h, rh, gh)
    print(f"(c) {h['round_name']} 2022 x 2026 · (b) {plural(rh['n_flipped'], 'estado mudou', 'estados mudaram')} · "
          f"(a) Goiás: {gh['n']} municípios, {plural(gh['n_flipped'], 'mudou', 'mudaram')}")
    print(f"Gráficos em {IMG_DIR}, página em {DOCS_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
