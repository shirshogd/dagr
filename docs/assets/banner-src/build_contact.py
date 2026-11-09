# Generates ../contact.svg + contact.png (1280x200) reusing build.py's palette, font and helpers.
import os
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.dirname(HERE)
src = open(os.path.join(HERE, "build.py"), encoding="utf-8").read()
head = src.split("# background + pixel stars")[0]     # palette, glyphs, rect/bitmap/text helpers
exec(compile(head, "build_head", "exec"))
W, H = 1280, 200
out.clear()
g('O', [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."])
g('N', ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"])
g('T', ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."])
g('M', ["#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"])
g(':', ["##", "##", "", "", "##", "##"], 2)
g('@', [".#####.", "#.....#", "#.###.#", "#.#.#.#", "#.####.", "#......", ".#####."])
g('-', ["###"], 3)

out.append(f'<rect x="2" y="2" width="{W-4}" height="{H-4}" rx="26" fill="{C["bg"]}" stroke="{C["edge"]}" stroke-width="4"/>')
for sx, sy in [(60,16),(420,20),(700,14),(1000,18),(1240,100),(1230,180),(20,180),(560,184),(900,182),(300,182)]:
    rect(sx, sy, 4, 4, "star")
for sx, sy in [(1150,24),(30,100)]:
    rect(sx, sy, 8, 4, "star"); rect(sx + 2, sy - 2, 4, 8, "star")

# pixel envelope (u=8, 14x10 cells = 112x80)
ex, ey, u = 44, 62, 8
ENV = ["WWWWWWWWWWWWWW",
       "WYWWWWWWWWWWYW",
       "WWYWWWWWWWWYWW",
       "WWWYWWWWWWYWWW",
       "WWWWYWWWWYWWWW",
       "WWWWWYYYYWWWWW",
       "WWWWWWWWWWWWWW",
       "WWWWWWWWWWWWWW",
       "WWWWWWWWWWWWWW",
       "WWWWWWWWWWWWWW"]
bitmap(ENV, ex, ey, u, {"W": "white", "Y": "yel3"})
rect(ex, ey - u, 14 * u, u, "ink"); rect(ex, ey + 10 * u, 14 * u, u, "ink")
rect(ex - u, ey, u, 10 * u, "ink"); rect(ex + 14 * u, ey, u, 10 * u, "ink")
# pink heart seal
bitmap([".#.#.", "#####", "#####", ".###.", "..#.."], ex + 5 * u - 4, ey + 4 * u, 4, {"#": "pink"})
for sx, sy in [(ex + 14 * u + 14, ey - 4), (ex - 24, ey + 60)]:
    rect(sx, sy - 6, 4, 16, "yel"); rect(sx - 6, sy, 16, 4, "yel")

tx0 = 200
text("CONTACT ME", tx0 + 5, 20 + 5, 9, "pink")
text("CONTACT ME", tx0, 20, 9, "white")
x = text("work with me:", tx0, 118, 5, "cyan")
text("shirsho@tilasmi.com", x + 5 * 3, 118, 5, "yel")
print("line2 right edge", x)

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" shape-rendering="crispEdges" role="img" '
       f'aria-label="Contact me. Work with me: shirsho@tilasmi.com">\n<title>Contact me. Work with me: shirsho@tilasmi.com</title>\n'
       + "\n".join(out) + "\n</svg>\n")
open(os.path.join(ASSETS, "contact.svg"), "w", encoding="utf-8").write(svg)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    try:
        br = p.chromium.launch()
    except Exception:
        br = p.chromium.launch(channel="msedge")
    pg = br.new_page(viewport={"width": W, "height": H})
    pg.set_content(f'<body style="margin:0;background:transparent">{svg}</body>')
    pg.screenshot(path=os.path.join(ASSETS, "contact.png"), omit_background=True)
    br.close()
from PIL import Image
im = Image.open(os.path.join(ASSETS, "contact.png")).convert("RGBA")
bg = Image.new("RGBA", im.size, "#ffffff"); bg.alpha_composite(im)
bg.convert("RGB").resize((400, round(H * 400 / W)), Image.LANCZOS).save(os.path.join(ASSETS, "_captures", "contact-400.png"))
