from __future__ import annotations

import json
import os
import signal
from pathlib import Path

stopped = []
for name in ["/content/cloudflared-muscriptor-studio.pid", "/content/muscriptor-studio.pid"]:
    path = Path(name)
    if not path.is_file():
        continue
    try:
        os.kill(int(path.read_text(encoding="utf-8").strip()), signal.SIGTERM)
        stopped.append(name)
    except (ValueError, ProcessLookupError):
        pass
    path.unlink(missing_ok=True)
print(json.dumps({"stopped": stopped}))
