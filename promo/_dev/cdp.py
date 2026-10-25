"""Minimal Chrome DevTools Protocol driver (no external deps beyond websocket-client).

Used to render deterministic canvas frames of the promo film to PNG/JPEG.
"""
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

import websocket  # websocket-client

CHROME_CANDIDATES = [
    r"C:\Users\20849\AppData\Local\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_chrome():
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("Chrome not found")


def free_port(start=9400, end=9900):
    import socket

    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("no free port")


class Browser:
    def __init__(self, width=1920, height=1080, port=None, profile=None, timeout=30):
        self.width, self.height = width, height
        self.port = port or free_port()
        self.profile = profile or str(Path(__file__).parent / "_chrome_profile" / str(self.port))
        self.proc = None
        self._msg_id = 0
        self.ws = None
        self.timeout = timeout

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.close()

    def start(self):
        try:
            self._start()
        except Exception:
            self.close()
            raise
        return self

    def _start(self):
        Path(self.profile).mkdir(parents=True, exist_ok=True)
        args = [
            find_chrome(),
            "--headless=new",
            f"--remote-debugging-port={self.port}",
            "--remote-allow-origins=*",
            "--no-sandbox",
            "--disable-crashpad",
            "--disable-dev-shm-usage",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--force-device-scale-factor=1",
            "--hide-scrollbars",
            "--mute-audio",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={self.width},{self.height}",
            f"--user-data-dir={self.profile}",
            "about:blank",
        ]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        version = None
        for _ in range(300):
            try:
                version = json.loads(
                    urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/version", timeout=1).read()
                )
                break
            except Exception:
                time.sleep(0.1)
        if not version:
            raise RuntimeError("Chrome did not start")
        self.ws = websocket.create_connection(version["webSocketDebuggerUrl"], timeout=self.timeout)
        self.version = version


    def _send(self, method, params=None, session_id=None):
        self._msg_id += 1
        mid = self._msg_id
        msg = {"id": mid, "method": method, "params": params or {}}
        if session_id:
            msg["sessionId"] = session_id
        self.ws.send(json.dumps(msg))
        while True:
            data = json.loads(self.ws.recv())
            if data.get("id") == mid:
                if "error" in data:
                    raise RuntimeError(f"{method}: {data['error']}")
                return data.get("result", {})

    def new_page(self):
        target = self._send("Target.createTarget", {"url": "about:blank"})
        tid = target["targetId"]
        sess = self._send("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        page = Page(self, sess, tid)
        page.send("Page.enable")
        page.send("Runtime.enable")
        page.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": self.width, "height": self.height, "deviceScaleFactor": 1, "mobile": False},
        )
        return page

    def close(self):
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass


class Page:
    def __init__(self, browser, session_id, target_id):
        self.browser = browser
        self.session_id = session_id
        self.target_id = target_id

    def send(self, method, params=None):
        return self.browser._send(method, params, self.session_id)

    def goto(self, url, wait_ready=True):
        self.send("Page.navigate", {"url": url})
        # wait for load event
        deadline = time.time() + 30
        while time.time() < deadline:
            r = self.send(
                "Runtime.evaluate",
                {"expression": "document.readyState", "returnByValue": True},
            )
            if r.get("result", {}).get("value") == "complete":
                break
            time.sleep(0.05)
        if wait_ready:
            self.evaluate("window.ready", await_promise=True)
        return self

    def evaluate(self, expression, await_promise=False, timeout=None):
        params = {"expression": expression, "returnByValue": True}
        if await_promise:
            params["awaitPromise"] = True
        self.send("Runtime.evaluate", params)
        # ignore result payload; caller can use evaluate_value for values

    def evaluate_value(self, expression, await_promise=False, timeout=120):
        params = {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": await_promise,
            "timeout": int(timeout * 1000),
        }
        try:
            res = self.send("Runtime.evaluate", params)
        except Exception as e:
            raise RuntimeError(f"evaluate failed: {e}")
        r = res.get("result", {})
        if r.get("subtype") == "error":
            raise RuntimeError(f"JS error: {r.get('description')}")
        return r.get("value")

    def screenshot(self, fmt="jpeg", quality=95):
        params = {"format": fmt, "fromSurface": True, "captureBeyondViewport": False}
        if fmt == "jpeg":
            params["quality"] = quality
        import base64

        res = self.send("Page.captureScreenshot", params)
        return base64.b64decode(res["data"])
