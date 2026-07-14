from __future__ import annotations

import json
import os
import signal
import subprocess
import urllib.request
from pathlib import Path

BINARY = Path("/content/cloudflared")
PID_FILE = Path("/content/cloudflared-muscriptor-studio.pid")
LOG_FILE = Path("/content/cloudflared-muscriptor-studio.log")

if not BINARY.is_file():
    urllib.request.urlretrieve(
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
        BINARY,
    )
    BINARY.chmod(0o755)

if PID_FILE.is_file():
    try:
        os.kill(int(PID_FILE.read_text(encoding="utf-8").strip()), signal.SIGTERM)
    except (ValueError, ProcessLookupError):
        pass

log = LOG_FILE.open("w", encoding="utf-8")
process = subprocess.Popen(
    [str(BINARY), "tunnel", "--url", "http://127.0.0.1:7860", "--no-autoupdate", "--protocol", "http2"],
    stdout=log,
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
PID_FILE.write_text(str(process.pid), encoding="utf-8")
print(json.dumps({"started": True, "pid": process.pid, "log": str(LOG_FILE)}))
