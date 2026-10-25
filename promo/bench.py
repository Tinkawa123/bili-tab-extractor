import time, sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from cdp import Browser

HERE = Path(__file__).parent
OUT = HERE / "_test"
OUT.mkdir(exist_ok=True)

t0 = time.time()
with Browser(width=1920, height=1080, port=9333) as b:
    print("startup", round(time.time() - t0, 2), "s", b.version.get("Browser"))
    page = b.new_page()
    t1 = time.time()
    page.goto((HERE / "bench.html").as_uri())
    print("load", round(time.time() - t1, 2), "s")

    # pure JS render timing
    js = """(() => { const t0=performance.now(); for(let i=0;i<60;i++) window.renderFrame(i/60); return (performance.now()-t0)/60; })()"""
    print("JS renderFrame avg ms:", round(page.evaluate_value(js), 2))

    for i, t in enumerate([6.0, 12.4, 21.0, 33.7]):
        t2 = time.time()
        page.evaluate_value(f"window.renderFrame({t})")
        tjs = time.time() - t2
        t3 = time.time()
        png = page.screenshot("png")
        tpng = time.time() - t3
        t4 = time.time()
        jpg = page.screenshot("jpeg", 95)
        tjpg = time.time() - t4
        (OUT / f"bench_{i}.png").write_bytes(png)
        (OUT / f"bench_{i}.jpg").write_bytes(jpg)
        print(f"t={t} js={tjs*1000:.0f}ms png={tpng*1000:.0f}ms({len(png)//1024}KB) jpg={tjpg*1000:.0f}ms({len(jpg)//1024}KB)")

    # burst of 60 jpeg frames
    t5 = time.time()
    for i in range(60):
        page.evaluate_value(f"window.renderFrame({i/30})")
        page.screenshot("jpeg", 95)
    dt = time.time() - t5
    print(f"burst 60 frames: {dt:.2f}s  => {dt/60*1000:.1f} ms/frame, 1800 frames ~ {dt*30:.1f}s")
