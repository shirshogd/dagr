# Tilasmi-palette variant of build.py: banner-tilasmi-light/dark .svg/.png + 400px captures.
import os
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.dirname(HERE)
W, H = 1280, 400
PAPER, INK, ACC, ACCD = "#F2F5F8", "#16171C", "#006AA3", "#3886C1"
PALS = {
 "light": dict(bg=PAPER, edge=INK, star="#D6E0EC", yel="#D6E0EC", yel2="#B7C4D4", yel3="#7F8CA0", cyan=ACC,
   teal="#A9C8DF", pink="#B7C4D4", white=INK, green=ACC, node=PAPER, ink=INK, org="#6B7587", paper=PAPER,
   ftext=INK, inv=PAPER, eyeA=INK, bodyB=INK, eyeB=PAPER, accA=ACC, accB=ACC, accR=INK, bodyR=ACC, eyeR=PAPER,
   visor=INK, badgeo=INK, badgei=ACC, badgef=PAPER, badgec=PAPER, nodeb=INK, spark=ACC, board="#7F8CA0", clipc=INK),
 "dark": dict(bg=INK, edge="#3A3F4D", star="#2E3340", yel="#D2AE63", yel2="#A98746", yel3="#7A6032", cyan=ACCD,
   teal="#1E4562", pink="#2F6C9E", white=PAPER, green=ACCD, node="#232733", ink=INK, org="#F2A541", paper=PAPER,
   ftext=INK, inv=INK, eyeA=INK, bodyB="#3FC1A5", eyeB=INK, accA=ACCD, accB="#F2A541", accR="#F2A541", bodyR="#D6E0EC", eyeR=INK,
   visor=ACCD, badgeo=ACCD, badgei=INK, badgef="#3FC1A5", badgec=PAPER, nodeb=ACCD, spark="#F2A541", board="#4F586B", clipc="#8A94A3"),
}
import sys
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

for MODE in (["dark"] if len(sys.argv) < 2 else sys.argv[1:]):
    C = PALS[MODE]
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
        text(lab, fx + 14, y + 25, 3, "ftext")
        rect(fx + fw - 2, y + 39 - 8, 14, 16, "cyan"); rect(fx + fw + 4, y + 39 - 4, 4, 8, "paper")

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
    node(ROOT[0], ROOT[1], 40, "nodeb")
    for w_ in WK: node(w_[0], w_[1], 40, "nodeb")

    # ---- robots (u=6, feet on wires) ----
    BOT = ["...A...", "BBBBBBB", "BKBBBKB", "BBBBBBB", ".BBBBB.", ".B...B.", "BB...BB"]
    def bot(x, y, body, acc="pink", u=6, eye="ink"):
        bitmap(BOT, x, y, u, {"A": acc, "B": body, "K": eye})
        rect(x + 3 * u, y - 2, u, 2, acc)
    # robot A: carries a file, on the top fan-out wire
    bot(338, 118 - 2 - 42, "org", "accA", eye="eyeA")
    rect(312, 90, 20, 24, "white"); rect(324, 90, 8, 8, "cyan"); rect(316, 102, 12, 3, "inv"); rect(316, 108, 8, 3, "inv")
    # robot B: winking, on the bottom fan-out wire
    bot(338, 278 - 2 - 42, "bodyB", "accB", eye="eyeB")
    rect(338 + 30, 278 - 2 - 42 + 12, 6, 6, "bodyB"); rect(338 + 30, 278 - 2 - 42 + 15, 6, 3, "eyeB")
    # reviewer with clipboard, standing on the badge
    bx, by, bw, bh = BX, 174, 176, 48
    rx, ry = 592, by - 42
    bot(rx, ry, "bodyR", "accR", eye="eyeR")
    rect(rx + 6, ry + 12, 30, 6, "visor")           # visor
    rect(rx + 12, ry + 12, 6, 6, "eyeR"); rect(rx + 24, ry + 12, 6, 6, "eyeR")
    rect(rx + 46, ry + 2, 24, 34, "board"); rect(rx + 50, ry + 8, 16, 24, "paper"); rect(rx + 52, ry - 2, 12, 6, "clipc")
    bitmap(["....#", "...##", "#.##.", ".###.", "..#.."], rx + 52, ry + 14, 3, {"#": "cyan"})
    # badge
    rect(bx + 4, by, bw - 8, bh, "badgeo"); rect(bx, by + 4, bw, bh - 8, "badgeo")
    rect(bx + 8, by + 4, bw - 16, bh - 8, "badgei"); rect(bx + 4, by + 8, bw - 8, bh - 16, "badgei")
    tx = text("0.91", bx + 14, by + 7, 5, "badgef")
    bitmap(["....#", "...##", "#.##.", ".###.", "..#.."], tx + 10, by + 11, 5, {"#": "badgec"})
    for sx, sy in [(700, 140), (690, 240)]:
        rect(sx - 0, sy - 6, 4, 16, "spark"); rect(sx - 6, sy, 16, 4, "spark")

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

    if MODE == "dark":  # Tilasmi signature, top right, embedded as-is (flat, one colour), mark 40px tall, scale 0.5
        import re
        raw = open(os.path.join(HERE, "tilasmi-logo-reversed.svg"), encoding="utf-8").read()
        inner = re.search(r"<svg[^>]*>(.*)</svg>", raw, re.S).group(1)
        inner = re.sub(r"<title.*?</title>|<desc.*?</desc>", "", inner, flags=re.S)
        out.append('<svg x="1082" y="24" width="149" height="53" viewBox="0 0 297.26 106.14" shape-rendering="geometricPrecision">' + inner + '</svg>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" shape-rendering="crispEdges" role="img" '
           f'aria-label="dagr: your folders, wired into a graph of agent work">\n<title>dagr: your folders, wired into a graph of agent work</title>\n'
           + "\n".join(out) + "\n</svg>\n")
    open(os.path.join(ASSETS, ("banner.svg" if MODE == "dark" else f"banner-tilasmi-{MODE}.svg")), "w", encoding="utf-8").write(svg)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            br = p.chromium.launch()
        except Exception:
            br = p.chromium.launch(channel="msedge")
        pg = br.new_page(viewport={"width": W, "height": H})
        pg.set_content(f'<body style="margin:0;background:transparent">{svg}</body>')
        pg.screenshot(path=os.path.join(ASSETS, ("banner.png" if MODE == "dark" else f"banner-tilasmi-{MODE}.png")), omit_background=False)
        br.close()
    from PIL import Image
    im = Image.open(os.path.join(ASSETS, ("banner.png" if MODE == "dark" else f"banner-tilasmi-{MODE}.png"))).convert("RGBA")
    for tw_ in (400, 830):
        bg = Image.new("RGBA", im.size, PALS[MODE]["bg"]); bg.alpha_composite(im)
        bg.convert("RGB").resize((tw_, round(H * tw_ / W)), Image.LANCZOS).save(os.path.join(ASSETS, "_captures", (f"banner-{tw_}.png" if MODE == "dark" else f"banner-tilasmi-{MODE}-{tw_}.png")))
