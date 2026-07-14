from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

URL = "http://127.0.0.1:7860/api/health"
LOG = Path("/content/muscriptor-studio.log")
last_error = None

for _ in range(120):
    try:
        with urllib.request.urlopen(URL, timeout=3) as response:
            payload = json.load(response)
        if payload.get("ok") is True:
            print(json.dumps({"ready": True, "health": payload, "url": URL}))
            break
    except Exception as exc:
        last_error = repr(exc)
    time.sleep(1)
else:
    tail = ""
    if LOG.is_file():
        tail = "\n".join(LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-40:])
    raise RuntimeError(f"Studio server did not become ready: {last_error}\n{tail}")
