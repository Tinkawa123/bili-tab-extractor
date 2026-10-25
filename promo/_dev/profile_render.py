import cProfile, pstats, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "film"))
import film

for t in [3.2, 5.0, 11.0]:
    t0 = time.time(); film.render(t); print(f"warm t={t} {time.time()-t0:.3f}s")

for t in [5.0, 11.0]:
    pr = cProfile.Profile()
    pr.enable()
    t0 = time.time()
    film.render(t)
    dt = time.time() - t0
    pr.disable()
    print(f"\n=== t={t}  {dt*1000:.0f} ms")
    st = pstats.Stats(pr)
    st.sort_stats("cumulative").print_stats(22)
