"""Monta o carrossel do LinkedIn (PDF 4:5) com os gráficos 01 a 05 de docs/img.

Uso (na pasta 2º TURNO):
    .venv\\Scripts\\python.exe "publication/Carrocel Painel 2 Linkedin/gerar_carrossel.py"

Segue o estilo dos cartões de src/build_charts.py (cores, fonte Segoe UI, cabeçalho e rodapé).
Os números dos textos foram conferidos em Data/processed em 29/10/2026.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
IMG = HERE.parents[1] / "docs" / "img"   # os gráficos saem de build_charts.py
S = 2                                   # desenha em 2x para o zoom no LinkedIn ficar nítido
W, H = 1080 * S, 1350 * S
M = 86 * S                              # margem lateral, a mesma dos cartões
INK, INK_2, MUTED, BAR, SURFACE = "#0b0b0b", "#52514e", "#898781", "#c3c2b7", "#fcfcfb"
FONTS = "C:/Windows/Fonts/"
H_22X26 = "BRASIL · PRESIDENTE · 2022 x 2026"
H_TURNOS = "BRASIL · PRESIDENTE 2026 · 1º x 2º TURNO"


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
    d.text((M, H - 92 * S), f"{i}/{n} · Fonte: TSE · dadosabertos.tse.jus.br", font=font(22), fill=MUTED)
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


slides = [
    lambda i, n: text_slide(
        H_22X26, "Flávio Bolsonaro liderou o 1º turno. Lula venceu o 2º.",
        "No 1º turno de 2026, Flávio teve 47,0% dos votos válidos e Lula, 45,2%. No 2º, Lula ficou com 51,8%. "
        "Em 5 gráficos: o que mudou desde 2022 e o que mudou entre os turnos, estado por estado.", i, n),
    lambda i, n: chart_slide(
        "01_national_result.png", H_22X26,
        "Lula venceu os dois 2º turnos: contra Jair Bolsonaro em 2022 e contra Flávio Bolsonaro, filho de Jair, em 2026.",
        i, n),
    lambda i, n: chart_slide(
        "02_state_maps.png", H_22X26,
        "O placar nos estados ficou igual: Lula 13, Bolsonaro 14. Só dois trocaram de lado: "
        "o Amapá passou para Lula e o Tocantins, para Bolsonaro.", i, n),
    lambda i, n: chart_slide(
        "03_states_shift.png", H_22X26,
        "Maior alta: Distrito Federal, +4,5 pontos. Maior queda: Tocantins, −2,7 pontos.", i, n),
    lambda i, n: chart_slide(
        "04_br_turnos_mapas.png", H_TURNOS,
        "Só Minas Gerais trocou de lado entre os turnos: Flávio Bolsonaro liderava no 1º, Lula venceu no 2º.", i, n),
    lambda i, n: chart_slide(
        "05_br_turnos_estados.png", H_TURNOS,
        "Do 1º para o 2º turno, a diferença ficou mais favorável a Lula em todos os 27 estados e no exterior.", i, n),
    lambda i, n: text_slide(
        H_22X26, "Confira o seu estado.",
        "Mapas e tabelas com os números de cada estado, feitos com os dados abertos do TSE. "
        "O link está no texto da publicação.", i, n,
        extra=[("Os números mostram onde o voto mudou, não quem mudou de voto. "
                "Totais conferidos com o relatório oficial de totalização do TSE.", font(28), MUTED)]),
]

n = len(slides)
pages = [make(i, n) for i, make in enumerate(slides, 1)]
for i, p in enumerate(pages, 1):
    p.save(HERE / f"carrossel_{i:02d}.png")
pages[0].save(HERE / "carrossel_painel_2_linkedin.pdf", save_all=True, append_images=pages[1:], resolution=144 * S)
print(f"ok: {n} páginas em {HERE}")
