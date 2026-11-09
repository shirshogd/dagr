# Generates ../dagr-banner.svg (pixel art as rects) and renders dagr-banner.png + scaled captures.
import os
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.dirname(HERE)
W, H = 1280, 400
C = dict(bg="#1b1633", edge="#3a2f6b", star="#2e2656", yel="#ffc857", yel2="#e09f3e", yel3="#a8601f",
         cyan="#3ee6e0", teal="#14797a", pink="#ff5fa2", white="#f5f1ff", green="#5df08a",
         node="#2d2a6e", ink="#0d0a1f", org="#ff8a3d")
G = {}
def g(ch, rows, top=0):
    w = max(len(r) for r in rows)
    G[ch] = (w, [""] * top + list(rows))
g('a', [".###.", "....#", ".####", "#...#", ".####"], 2)
g('c', [".###.", "#...#", "#....", "#...#", ".###."], 2)
g('d', ["....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"])
g('e', [".###.", "#...#", "#####", "#....", ".####"], 2)
g('f', ["..##", ".#..", "###.", ".#..", ".#..", ".#..", ".#.."])
g('g', [".###.", "#...#", "#...#", "#...#", ".####", "....#", ".###."], 2)
g('h', ["#....", "#....", "#.##.", "##..#", "#...#", "#...#", "#...#"])
g('i', [".#.", "", "##.", ".#.", ".#.", ".#.", "###"])
g('k', ["#....", "#....", "#..#.", "#.#..", "##...", "#.#..", "#..#."])
g('l', ["##.", ".#.", ".#.", ".#.", ".#.", ".#.", "###"])
g('m', ["##.#.", "#.#.#", "#.#.#", "#.#.#", "#.#.#"], 2)
g('n', ["#.##.", "##..#", "#...#", "#...#", "#...#"], 2)
g('o', [".###.", "#...#", "#...#", "#...#", ".###."], 2)
g('p', ["####.", "#...#", "#...#", "#...#", "####.", "#....", "#...."], 2)
g('r', ["####.", "##...", "#....", "#....", "#...."], 2)
g('C', [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."])
g('L', ["#....", "#....", "#....", "#....", "#....", "#....", "#####"])
g('A', [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"])
g('U', ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."])
g('D', ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."])
g('E', ["#####", "#....", "#....", "####.", "#....", "#....", "#####"])
g('s', [".####", "#....", ".###.", "....#", "####."], 2)
g('t', ["..#..", "#####", "..#..", "..#..", "..#..", "...##"], 1)
g('u', ["#...#", "#...#", "#...#", "#...#", ".####"], 2)
g('w', ["#...#", "#...#", "#.#.#", "#.#.#", ".#.#."], 2)
g('y', ["#...#", "#...#", "#...#", ".####", "....#", "....#", ".###."], 2)
g(',', [".#.", ".#.", "#.."], 5)
g('.', ["##", "##"], 5)
g(' ', ["...."])
g('0', [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."])
g('9', [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."])
g('1', ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."])

out = []
def rect(x, y, w, h, c):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{C.get(c, c)}"/>')
def bitmap(rows, x, y, u, cmap):
    for j, row in enumerate(rows):
        i = 0
        while i < len(row):
            ch = row[i]
            if ch in cmap:
                k = i
                while k < len(row) and row[k] == ch:
                    k += 1
                rect(x + i * u, y + j * u, (k - i) * u, u, cmap[ch]); i = k
            else:
                i += 1
def text_w(s, cell):
    return sum((G[ch][0] + 1) * cell for ch in s) - cell
def text(s, x, y, cell, col):
    cx = x
    for ch in s:
        w, rows = G[ch]
        bitmap(rows, cx, y, cell, {"#": col})
        cx += (w + 1) * cell
    return cx
def line(pts, w, col):
    d = "M" + " L".join(f"{a} {b}" for a, b in pts)
    out.append(f'<path d="{d}" fill="none" stroke="{C[col]}" stroke-width="{w}" stroke-linejoin="miter" stroke-linecap="square"/>')

# background + pixel stars
out.append(f'<rect x="2" y="2" width="{W-4}" height="{H-4}" rx="26" fill="{C["bg"]}" stroke="{C["edge"]}" stroke-width="4"/>')
for sx, sy in [(60,22),(230,18),(420,30),(640,16),(700,370),(850,380),(1000,22),(1180,28),(1240,200),(1230,370),(20,380),(560,385),(330,380),(960,385)]:
    rect(sx, sy, 4, 4, "star")
for sx, sy in [(480,26),(1100,372),(26,200)]:
    rect(sx, sy, 8, 4, "star"); rect(sx + 2, sy - 2, 4, 8, "star")

# ---- folders ----
fx, fw = 20, 184
labels = ["CLAUDE.md", "workflows", "stages", "output"]
fy = [46, 128, 210, 292]; fh = 66
cy = [y + 12 + 27 for y in fy]
for y, lab in zip(fy, labels):
    rect(fx, y, 48, 12, "yel2"); rect(fx + 4, y + 4, 40, 8, "yel2")
    rect(fx, y + 12, fw, fh - 12, "yel"); rect(fx + 4, y + 8, fw - 8, 4, "yel")
    rect(fx, y + fh - 8, fw, 8, "yel2"); rect(fx, y + fh - 4, fw, 4, "yel3")
    rect(fx + fw - 4, y + 12, 4, 4, "bg"); rect(fx, y + fh - 4, 4, 4, "bg"); rect(fx + fw - 4, y + fh - 4, 4, 4, "bg")
    text(lab, fx + 14, y + 25, 3, "ink")
    rect(fx + fw - 2, y + 39 - 8, 14, 16, "cyan"); rect(fx + fw + 4, y + 39 - 4, 4, 8, "white")

# ---- DAG ----
ROOT = (270, 199); WK = [(410, 118), (410, 199), (410, 278)]
BX = 498   # badge left
for i in range(4):
    pass
paths = [[(fx + fw + 12, c), (232, c)] for c in cy]
paths.append([(232, cy[0]), (232, cy[3])])
paths.append([(232, 199), (ROOT[0] - 20, 199)])
paths.append([(ROOT[0] + 20, 199), (322, 199)])
paths.append([(322, 118), (322, 278)])
for w_ in WK:
    paths.append([(322, w_[1]), (w_[0] - 20, w_[1])])
    paths.append([(w_[0] + 20, w_[1]), (470, w_[1])])
paths.append([(470, 118), (470, 278)])
paths.append([(470, 199), (BX, 199)])
for p in paths: line(p, 10, "teal")
for p in paths: line(p, 4, "cyan")
for px, py in [(224, cy[0] - 3), (224, cy[3] - 3), (446, 115), (446, 275), (348, 196), (480, 196)]:
    rect(px, py, 6, 6, "white")

def node(cx, cyy, s, border):
    x, y = cx - s // 2, cyy - s // 2
    rect(x + 4, y, s - 8, s, border); rect(x, y + 4, s, s - 8, border)
    rect(x + 8, y + 4, s - 16, s - 8, "node"); rect(x + 4, y + 8, s - 8, s - 16, "node")
    rect(cx - 8, cyy - 8, 16, 4, "white"); rect(cx - 8, cyy, 10, 4, "white")
    rect(cx - 8, cyy + 8, 14, 4, "white")
node(ROOT[0], ROOT[1], 40, "yel")
for w_ in WK: node(w_[0], w_[1], 40, "pink")

# ---- robots (u=6, feet on wires) ----
BOT = ["...A...", "BBBBBBB", "BKBBBKB", "BBBBBBB", ".BBBBB.", ".B...B.", "BB...BB"]
def bot(x, y, body, acc="pink", u=6):
    bitmap(BOT, x, y, u, {"A": acc, "B": body, "K": "ink"})
    rect(x + 3 * u, y - 2, u, 2, acc)
# robot A: carries a file, on the top fan-out wire
bot(338, 118 - 2 - 42, "org", "cyan")
rect(312, 90, 20, 24, "white"); rect(324, 90, 8, 8, "cyan"); rect(316, 102, 12, 3, "ink"); rect(316, 108, 8, 3, "ink")
# robot B: winking, on the bottom fan-out wire
bot(338, 278 - 2 - 42, "green", "yel")
rect(338 + 30, 278 - 2 - 42 + 12, 6, 6, "green"); rect(338 + 30, 278 - 2 - 42 + 15, 6, 3, "ink")
# reviewer with clipboard, standing on the badge
bx, by, bw, bh = BX, 174, 176, 48
rx, ry = 592, by - 42
bot(rx, ry, "white", "pink")
rect(rx + 6, ry + 12, 30, 6, "pink")           # visor
rect(rx + 12, ry + 12, 6, 6, "ink"); rect(rx + 24, ry + 12, 6, 6, "ink")
rect(rx + 46, ry + 2, 24, 34, "yel3"); rect(rx + 50, ry + 8, 16, 24, "white"); rect(rx + 52, ry - 2, 12, 6, "ink")
bitmap(["....#", "...##", "#.##.", ".###.", "..#.."], rx + 52, ry + 14, 3, {"#": "green"})
# badge
rect(bx + 4, by, bw - 8, bh, "green"); rect(bx, by + 4, bw, bh - 8, "green")
rect(bx + 8, by + 4, bw - 16, bh - 8, "ink"); rect(bx + 4, by + 8, bw - 8, bh - 16, "ink")
tx = text("0.91", bx + 14, by + 7, 5, "green")
bitmap(["....#", "...##", "#.##.", ".###.", "..#.."], tx + 10, by + 11, 5, {"#": "white"})
for sx, sy in [(700, 140), (690, 240)]:
    rect(sx, sy - 6, 4, 16, "yel"); rect(sx - 6, sy, 16, 4, "yel")

# ---- title + tagline ----
tx0 = 740
cell = 12
text("dagr", tx0 + 6, 18 + 6, cell, "pink")
text("dagr", tx0, 18, cell, "white")
def segs(parts, x, y, c):
    for s_, col in parts:
        x = text(s_, x, y, c, col)
        x += 0
lines = [[("your folders,", "white")], [("wired into", "white")], [("a ", "white"), ("graph", "cyan"), (" of", "white")], [("agent work", "white")]]
for i, parts in enumerate(lines):
    x = tx0
    for s_, col in parts:
        x = text(s_, x, 150 + i * 56, 7, col)

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" shape-rendering="crispEdges" role="img" '
       f'aria-label="dagr: your folders, wired into a graph of agent work">\n<title>dagr: your folders, wired into a graph of agent work</title>\n'
       + "\n".join(out) + "\n</svg>\n")
open(os.path.join(ASSETS, "dagr-banner.svg"), "w", encoding="utf-8").write(svg)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    try:
        br = p.chromium.launch()
    except Exception:
        br = p.chromium.launch(channel="msedge")
    pg = br.new_page(viewport={"width": W, "height": H})
    pg.set_content(f'<body style="margin:0;background:transparent">{svg}</body>')
    pg.screenshot(path=os.path.join(ASSETS, "dagr-banner.png"), omit_background=True)
    br.close()
from PIL import Image
im = Image.open(os.path.join(ASSETS, "dagr-banner.png")).convert("RGBA")
for tw_ in (400, 830):
    bg = Image.new("RGBA", im.size, "#ffffff"); bg.alpha_composite(im)
    bg.convert("RGB").resize((tw_, round(H * tw_ / W)), Image.LANCZOS).save(os.path.join(ASSETS, "_captures", f"banner-{tw_}.png"))
