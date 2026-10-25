from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------- 1) printed ink: keep paper white, darken ink (gamma), instead of dimming the whole page
pg = HERE / "film" / "pages.py"
s = pg.read_text(encoding="utf-8")
s = s.replace("region *= np.clip((im - 0.03) * 0.80, 0, 1)", "region *= np.clip(im ** 1.45, 0, 1)")
pg.write_text(s, encoding="utf-8")

f = HERE / "film" / "film.py"
s = f.read_text(encoding="utf-8")

# ---------- 2) five rows per page so the notation fills the sheet
s = s.replace("    starts = [0, 7, 14]", "    starts = [0, 5, 10]")
s = s.replace('pages.build_page(list(range(0, 7)), "Paranoid", "Black Sabbath · 吉他谱", 1, 3)',
              'pages.build_page(list(range(0, 5)), "Paranoid", "Black Sabbath · 吉他谱", 1, 3)')

# ---------- 3) the page stack: light shadows only (full-page alpha shadows read as black bars)
old = '''    if back > 0:
        sc3 = 0.5
        w3, h3 = int(p1.w * sc3), int(p1.h * sc3)
        # stack of three pages
        for k, (ox, oy, rot, spr) in enumerate([(34, 26, 3.0, _page(2)), (17, 13, 1.5, p2), (0, 0, 0.0, p1)]):
            q = pages.page_quad(cx + ox, cy + oy + 10, w3, h3, rz=rot, ry=-8)
            blit_perspective(img, shadow(spr.scaled(w3, h3), 30, 0.55), q + np.array([0, 16], F32), back)
            blit_perspective(img, spr.scaled(w3, h3), q, back)'''
new = '''    if back > 0:
        sc3 = 0.5
        w3, h3 = int(p1.w * sc3), int(p1.h * sc3)
        # stack of three pages: only the bottom page casts a soft shadow
        for k, (ox, oy, rot, spr) in enumerate([(34, 26, 3.0, _page(2)), (17, 13, 1.5, p2), (0, 0, 0.0, p1)]):
            q = pages.page_quad(cx + ox, cy + oy + 10, w3, h3, rz=rot, ry=-8)
            if k == 0:
                sh = shadow(spr.scaled(w3, h3), 46, 0.5)
                blit_perspective(img, sh, q + np.array([0, 22], F32), back)
            blit_perspective(img, spr.scaled(w3, h3), q, back)
            # thin darker edge to read as stacked paper
            if k > 0:
                blit_perspective(img, rounded_border(w3, h3, 3, 2, D.hexc("#8A7F6C"), opacity=0.35), q, back)'''
assert old in s
s = s.replace(old, new)

f.write_text(s, encoding="utf-8")
print("patched pages/stacks")
