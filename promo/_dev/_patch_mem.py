from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------- pages: keep the row cache small (uint8 instead of float32)
pg = HERE / "film" / "pages.py"
s = pg.read_text(encoding="utf-8")
s = s.replace(
    '''def tab_rows():
    """Real extracted tab rows as float grayscale->RGB arrays (white bg)."""
    if "rows" not in _CACHE:
        out = []
        for p in _row_paths():
            try:
                img = _imread_unicode(p)
            except Exception:
                continue
            arr = img.astype(F32) / 255.0
            out.append(np.dstack([arr, arr, arr]))
        _CACHE["rows"] = out
    return _CACHE["rows"]''',
    '''def tab_rows():
    """Real extracted tab rows as uint8 RGB arrays (white bg). ~4x less RAM."""
    if "rows" not in _CACHE:
        out = []
        for p in _row_paths():
            try:
                img = _imread_unicode(p)
            except Exception:
                continue
            out.append(np.dstack([img, img, img]))
        _CACHE["rows"] = out
    return _CACHE["rows"]


def row_f32(i):
    """Float32 [0,1] copy of a cached row."""
    r = tab_rows()[i % len(tab_rows())]
    return r.astype(F32) / 255.0''',
)
s = s.replace('''        src = rows[i]
        img = _resize_w(src, avail_w)''', '''        src = rows[i].astype(F32) / 255.0
        img = _resize_w(src, avail_w)''')
pg.write_text(s, encoding="utf-8")

f = HERE / "film" / "film.py"
s = f.read_text(encoding="utf-8")

# strip texture: convert uint8 -> float once
s = s.replace(
    '''    for i in range(min(n, len(rows))):
        im = rows[i]
        h = int(round(im.shape[0] * width / im.shape[1]))
        parts.append(cv2.resize(im, (width, max(1, h)), interpolation=cv2.INTER_AREA))
        parts.append(np.ones((12, width, 3), F32))
    tex = np.clip(np.concatenate(parts, axis=0) * 0.99, 0, 1)''',
    '''    for i in range(min(n, len(rows))):
        im = rows[i]
        h = int(round(im.shape[0] * width / im.shape[1]))
        r = cv2.resize(im, (width, max(1, h)), interpolation=cv2.INTER_AREA).astype(F32) / 255.0
        parts.append(r)
        parts.append(np.ones((12, width, 3), F32))
    tex = np.clip(np.concatenate(parts, axis=0) * 0.99, 0, 1)''',
)

# S3 rows
s = s.replace('''    for i in idx:
        im = src[i % len(src)]
        h = max(18, int(round(im.shape[0] * w / im.shape[1])))
        r = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)''',
              '''    for i in idx:
        im = src[i % len(src)].astype(F32) / 255.0
        h = max(18, int(round(im.shape[0] * w / im.shape[1])))
        r = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)''')

# polaroids
s = s.replace('''            row = rows[(gi * 5 + k * 3) % len(rows)]
            h, w = row.shape[:2]''',
              '''            row = rows[(gi * 5 + k * 3) % len(rows)].astype(F32) / 255.0
            h, w = row.shape[:2]''')

# review thumbs / preview
s = s.replace('''    im = src[[1, 5, 9, 14, 19, 23, 28, 32][i % 8] % len(src)]
    w = 250''',
              '''    im = src[[1, 5, 9, 14, 19, 23, 28, 32][i % 8] % len(src)].astype(F32) / 255.0
    w = 250''')
s = s.replace('''    im = src[[1, 5, 9, 14, 19, 23, 28, 32][i % 8] % len(src)]
    w = 330''',
              '''    im = src[[1, 5, 9, 14, 19, 23, 28, 32][i % 8] % len(src)].astype(F32) / 255.0
    w = 330''')

# polaroid filter used float rows; it only needs shape + crop — fine.

f.write_text(s, encoding="utf-8")
print("row cache -> uint8, call sites converted")
