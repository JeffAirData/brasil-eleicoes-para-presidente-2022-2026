"""Monta o carrossel do LinkedIn (PDF 4:5) com os gráficos 01 a 05 de docs/img (ou docs/en/img, em inglês).

Uso (na pasta 2º TURNO):
    .venv\\Scripts\\python.exe "publication/Carrocel Painel 2 Linkedin/gerar_carrossel.py"            (português)
    .venv\\Scripts\\python.exe "publication/Carrocel Painel 2 Linkedin/gerar_carrossel.py" --lang en  (inglês)

Segue o estilo dos cartões de src/build_charts.py (cores, fonte Segoe UI, cabeçalho e rodapé).
Os números dos textos foram conferidos em Data/processed em 29/10/2026.
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
LANG = "en" if "--lang" in sys.argv and sys.argv[sys.argv.index("--lang") + 1] == "en" else "pt"
IMG = HERE.parents[1] / "docs" / ("en" if LANG == "en" else "") / "img"   # os gráficos saem de build_charts.py
S = 2                                   # desenha em 2x para o zoom no LinkedIn ficar nítido
W, H = 1080 * S, 1350 * S
M = 86 * S                              # margem lateral, a mesma dos cartões
INK, INK_2, MUTED, BAR, SURFACE = "#0b0b0b", "#52514e", "#898781", "#c3c2b7", "#fcfcfb"
FONTS = "C:/Windows/Fonts/"
H_22X26 = "BRAZIL · PRESIDENT · 2022 vs 2026" if LANG == "en" else "BRASIL · PRESIDENTE · 2022 x 2026"
H_TURNOS = "BRAZIL · PRESIDENT 2026 · FIRST ROUND vs RUNOFF" if LANG == "en" else "BRASIL · PRESIDENTE 2026 · 1º x 2º TURNO"
SOURCE = "Source: TSE" if LANG == "en" else "Fonte: TSE"


def font(size, bold=False):
    return ImageFont.truetype(FONTS + ("segoeuib.ttf" if bold else "segoeui.ttf"), size * S)


def wrap(d, text, f, width):
    lines, line = [], ""
    for word in text.split():
        test = (line + " " + word).strip()
        if d.textlength(test, font=f) <= width:
            line = test
        else:
            lines.append(line); line = word
    return lines + [line]


def paragraph(d, y, text, f, fill, gap=1.3):
    for line in wrap(d, text, f, W - 2 * M):
        d.text((M, y), line, font=f, fill=fill)
        y += int(f.size * gap)
    return y


def frame(header, i, n):
    im = Image.new("RGB", (W, H), SURFACE); d = ImageDraw.Draw(im)
    d.rectangle([M, 138 * S, M + 131 * S, 152 * S], fill=BAR)
    d.text((M, 190 * S), header, font=font(26, True), fill=INK_2)
    d.text((M, H - 92 * S), f"{i}/{n} · {SOURCE} · dadosabertos.tse.jus.br", font=font(22), fill=MUTED)
    return im, d


def chart_slide(img, header, note, i, n):
    im, d = frame(header, i, n)
    top, bottom = 262 * S, H - 130 * S
    f = font(30)
    note_h = len(wrap(d, note, f, W - 2 * M)) * int(f.size * 1.3) + 40 * S if note else 0
    chart = Image.open(IMG / img).convert("RGB")
    scale = min((W - 2 * M + 60 * S) / chart.width, (bottom - top - note_h) / chart.height)
    chart = chart.resize((round(chart.width * scale), round(chart.height * scale)), Image.LANCZOS)
    y = top + (bottom - top - chart.height - note_h) // 2      # centraliza o bloco na vertical
    im.paste(chart, ((W - chart.width) // 2, y))
    if note:
        paragraph(d, y + chart.height + 40 * S, note, f, INK_2)
    return im


def text_slide(header, big, body, i, n, extra=()):
    blocks = [(big, font(66, True), INK, 1.18, 0), (body, font(34), INK_2, 1.3, 50 * S)]
    blocks += [(text, f, fill, 1.3, 36 * S) for text, f, fill in extra]
    im, d = frame(header, i, n)
    height = sum(gap + len(wrap(d, t, f, W - 2 * M)) * int(f.size * g) for t, f, _, g, gap in blocks)
    y = 262 * S + (H - 130 * S - 262 * S - height) // 2        # centraliza o texto na vertical
    for text, f, fill, g, gap in blocks:
        y = paragraph(d, y + gap, text, f, fill, g)
    return im


TEXT = {
    "pt": {
        "cover": ("Flávio Bolsonaro liderou o 1º turno. Lula venceu o 2º.",
                  "No 1º turno de 2026, Flávio teve 47,0% dos votos válidos e Lula, 45,2%. No 2º, Lula ficou com 51,8%. "
                  "Em 5 gráficos: o que mudou desde 2022 e o que mudou entre os turnos, estado por estado."),
        "01": "Lula venceu os dois 2º turnos: contra Jair Bolsonaro em 2022 e contra Flávio Bolsonaro, filho de Jair, em 2026.",
        "02": "O placar nos estados ficou igual: Lula 13, Bolsonaro 14. Só dois trocaram de lado: "
              "o Amapá passou para Lula e o Tocantins, para Bolsonaro.",
        "03": "Maior alta: Distrito Federal, +4,5 pontos. Maior queda: Tocantins, −2,7 pontos.",
        "04": "Só Minas Gerais trocou de lado entre os turnos: Flávio Bolsonaro liderava no 1º, Lula venceu no 2º.",
        "05": "Do 1º para o 2º turno, a diferença ficou mais favorável a Lula em todos os 27 estados e no exterior.",
        "end": ("Confira o seu estado.",
                "Mapas e tabelas com os números de cada estado, feitos com os dados abertos do TSE. "
                "O link está no texto da publicação.",
                "Os números mostram onde o voto mudou, não quem mudou de voto. "
                "Totais conferidos com o relatório oficial de totalização do TSE."),
        "files": ("carrossel", "carrossel_painel_2_linkedin.pdf"),
    },
    "en": {
        "cover": ("Flávio Bolsonaro led the first round. Lula won the runoff.",
                  "In Brazil's 2026 first round, Flávio got 47.0% of the valid votes and Lula 45.2%. In the runoff, "
                  "Lula got 51.8%. In 5 charts: what changed since 2022 and between the rounds, state by state."),
        "01": "Lula won both runoffs: against Jair Bolsonaro in 2022 and against his son, Flávio Bolsonaro, in 2026.",
        "02": "The state count stayed the same: Lula 13, Bolsonaro 14. Only two states switched: "
              "Amapá went to Lula and Tocantins to Bolsonaro.",
        "03": "Biggest gain: the Federal District (Brasília), +4.5 points. Biggest drop: Tocantins, −2.7 points.",
        "04": "Only Minas Gerais switched sides between the rounds: Flávio Bolsonaro led the first round, Lula won the runoff.",
        "05": "From the first round to the runoff, the gap moved toward Lula in all 27 states and abroad.",
        "end": ("Check your state.",
                "Maps and tables with the numbers for every state, built from the TSE's open data. "
                "The link is in the post.",
                "The numbers show where the vote shifted, not who changed their vote. "
                "Totals checked against the TSE's official count report."),
        "files": ("carousel_en", "carousel_panel_2_linkedin_en.pdf"),
    },
}[LANG]

slides = [
    lambda i, n: text_slide(H_22X26, *TEXT["cover"], i, n),
    lambda i, n: chart_slide("01_national_result.png", H_22X26, TEXT["01"], i, n),
    lambda i, n: chart_slide("02_state_maps.png", H_22X26, TEXT["02"], i, n),
    lambda i, n: chart_slide("03_states_shift.png", H_22X26, TEXT["03"], i, n),
    lambda i, n: chart_slide("04_br_turnos_mapas.png", H_TURNOS, TEXT["04"], i, n),
    lambda i, n: chart_slide("05_br_turnos_estados.png", H_TURNOS, TEXT["05"], i, n),
    lambda i, n: text_slide(H_22X26, *TEXT["end"][:2], i, n, extra=[(TEXT["end"][2], font(28), MUTED)]),
]

n = len(slides)
pages = [make(i, n) for i, make in enumerate(slides, 1)]
for i, p in enumerate(pages, 1):
    p.save(HERE / f"{TEXT['files'][0]}_{i:02d}.png")
pages[0].save(HERE / TEXT["files"][1], save_all=True, append_images=pages[1:], resolution=144 * S)
print(f"ok: {n} páginas em {HERE}")
