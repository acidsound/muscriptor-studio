from __future__ import annotations

import json
import re
import time
from pathlib import Path

LOG = Path("/content/cloudflared-muscriptor-studio.log")
pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
text = ""

for _ in range(90):
    text = LOG.read_text(encoding="utf-8", errors="replace") if LOG.is_file() else ""
    match = pattern.search(text)
    if match:
        print(json.dumps({"ready": True, "url": match.group(0)}))
        break
    time.sleep(1)
else:
    tail = "\n".join(text.splitlines()[-40:])
    raise RuntimeError(f"Quick Tunnel URL was not issued\n{tail}")
