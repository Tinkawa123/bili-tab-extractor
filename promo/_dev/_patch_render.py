from pathlib import Path

p = Path(__file__).resolve().parent / "render.py"
s = p.read_text(encoding="utf-8")

s = s.replace(
    """    ap.add_argument("--quality", type=int, default=95)
    a = ap.parse_args()
    render_chunk(a.start, a.end, a.fps, a.scale, Path(a.outdir), a.quality)""",
    """    ap.add_argument("--quality", type=int, default=95)
    ap.add_argument("--threads", type=int, default=0)
    a = ap.parse_args()
    if a.threads:
        os.environ["DSH_CV_THREADS"] = str(a.threads)
    render_chunk(a.start, a.end, a.fps, a.scale, Path(a.outdir), a.quality)""",
)
s = s.replace(
    """                "--quality", str(args.quality),
            ],""",
    """                "--quality", str(args.quality),
                "--threads", str(args.threads),
            ],""",
)
s = s.replace(
    """                sys.executable,
                str(HERE / "render.py"),
                "_worker",""",
    """                sys.executable,
                str(HERE / "render.py"),
                "_worker",""",
)
# parent: thread count per worker
s = s.replace(
    '    v.add_argument("--preset", default="medium")',
    '    v.add_argument("--preset", default="medium")\n    v.add_argument("--threads", type=int, default=2)',
)
# worker: apply override before importing film
s = s.replace(
    """def render_chunk(start, end, fps, scale, outdir, quality=95):
    import film
""",
    """def render_chunk(start, end, fps, scale, outdir, quality=95):
    import cv2 as _cv2

    thr = os.environ.get("DSH_CV_THREADS")
    if thr:
        _cv2.setNumThreads(int(thr))
    import film
""",
)
p.write_text(s, encoding="utf-8")
print("patched render.py")
