from pathlib import Path

p = Path(__file__).resolve().parent / "film" / "pages.py"
s = p.read_text(encoding="utf-8")

old = """        region = page[y : y + h, x_ink : x_ink + w]
        # normalise each strip's paper white to 1.0 so it melts into the sheet
        hi = float(np.percentile(im, 96)) or 1.0
        im = np.clip(im / max(0.55, hi), 0, 1)
        region *= np.clip(im ** 1.6, 0, 1)"""
new = """        region = page[y : y + h, x_ink : x_ink + w]
        # flatten the strip's own background (video lighting / highlights) onto
        # pure white so the notation reads as ink printed on this sheet
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41))
        bg = cv2.morphologyEx(im.astype(np.float32), cv2.MORPH_CLOSE, k)
        bg = np.maximum(bg, 0.35)
        im = np.clip(im / bg, 0, 1)
        im = np.clip((im - 0.06) / 0.94, 0, 1)
        region *= np.clip(im ** 1.9, 0, 1)"""
assert old in s
s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("row background flattened")
