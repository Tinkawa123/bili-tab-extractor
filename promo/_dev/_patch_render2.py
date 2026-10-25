from pathlib import Path

p = Path(__file__).resolve().parent / "render.py"
s = p.read_text(encoding="utf-8")

s = s.replace(
    '''    w.add_argument("--quality", type=int, default=95)

    args = ap.parse_args()''',
    '''    w.add_argument("--quality", type=int, default=95)
    w.add_argument("--threads", type=int, default=0)

    args = ap.parse_args()''',
)
s = s.replace(
    '''    elif args.cmd == "_worker":
        render_chunk(args.start, args.end, args.fps, args.scale, Path(args.outdir), args.quality)''',
    '''    elif args.cmd == "_worker":
        if getattr(args, "threads", 0):
            os.environ["DSH_CV_THREADS"] = str(args.threads)
        render_chunk(args.start, args.end, args.fps, args.scale, Path(args.outdir), args.quality)''',
)
p.write_text(s, encoding="utf-8")
print("fixed render.py --threads")
