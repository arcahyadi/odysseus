"""Test P1: Flask Todo App."""

import json
import time

import requests

BASE = "http://127.0.0.1:7000"

r = requests.post(
    f"{BASE}/api/session",
    data={
        "name": "P1-Flask-Todo",
        "model": "minimax-m3",
        "endpoint_url": "https://opencode.ai/zen/go/v1/chat/completions",
    },
)
sid = r.json()["id"]
print(f"SESSION: {sid[:8]}...")

print("SENDING: build a flask todo app...")
t0 = time.time()

r = requests.post(
    f"{BASE}/api/chat_stream",
    data={
        "message": "build a complete flask todo app with SQLite and Bootstrap. Create app.py, requirements.txt, and templates/index.html. Make it ready to run.",
        "session": sid,
        "mode": "agent",
    },
    stream=True,
    timeout=300,
)

phases = []
for line in r.iter_lines():
    if line and line.startswith(b"data: "):
        try:
            d = json.loads(line[6:])
            t = d.get("type", "")
            if t == "phase_enter":
                p = d.get("phase", "")
                phases.append(p)
                print(f"  PHASE: {p}")
            elif t == "mode_detected":
                print(f"  MODE: {d.get('mode')}")
            elif t == "model_info":
                print(f"  MODEL: {d.get('model')}")
            elif t == "metrics":
                m = d.get("data", {})
                print(f"  METRICS: {m.get('total_tokens')} tokens, {m.get('response_time')}s")
            elif t == "memories_used":
                print(f"  MEMORIES: {len(d.get('data', []))} facts")
        except:
            pass

elapsed = time.time() - t0
print(f"DONE: {len(phases)} phases in {elapsed:.0f}s")
print(f"PHASES: {phases}")

# Check files created
import os

files_found = []
for root, dirs, files in os.walk("."):
    for f in files:
        if f in ["app.py", "requirements.txt", "index.html"]:
            fp = os.path.join(root, f)
            files_found.append(f"{f} ({os.path.getsize(fp)}B)")
print(f"FILES: {files_found}")
