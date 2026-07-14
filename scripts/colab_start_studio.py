from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path("/content/muscriptor-studio")
PID_FILE = Path("/content/muscriptor-studio.pid")
LOG_FILE = Path("/content/muscriptor-studio.log")
PORT = os.environ.get("STUDIO_PORT", "7860")

if PID_FILE.is_file():
    try:
        os.kill(int(PID_FILE.read_text(encoding="utf-8").strip()), signal.SIGTERM)
    except (ValueError, ProcessLookupError):
        pass

log = LOG_FILE.open("w", encoding="utf-8")
process = subprocess.Popen(
    [
        sys.executable,
        str(ROOT / "server.py"),
        "--host",
        "127.0.0.1",
        "--port",
        PORT,
        "--deployment",
        "colab-t4",
    ],
    cwd=ROOT,
    env=os.environ.copy(),
    stdout=log,
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
PID_FILE.write_text(str(process.pid), encoding="utf-8")
print(json.dumps({"started": True, "pid": process.pid, "port": int(PORT), "log": str(LOG_FILE)}))
