"""E2E test v2: real agent pipeline."""

import sys

import requests

BASE = "http://127.0.0.1:7000"

# 1. Create session (uses Form data, not JSON!)
print("Creating session...")
r = requests.post(
    f"{BASE}/api/session",
    data={
        "name": "E2E Agent Test",
        "model": "minimax-m3",
        "endpoint_url": "https://opencode.ai/zen/go/v1/chat/completions",
    },
)
print(f"POST /session -> {r.status_code}")
if r.status_code != 200:
    print(f"ERROR: {r.text[:300]}")
    sys.exit(1)

session = r.json()
sid = session.get("id")
print(f"SESSION: {sid} | name={session.get('name')} | model={session.get('model')}")

# 2. Send agent message
msg = "write a python file hello.py that prints hello world"
print(f"\nSENDING agent: {msg}\n")

r = requests.post(
    f"{BASE}/api/chat_stream",
    data={"message": msg, "session": sid, "mode": "agent", "use_web": "false"},
    stream=True,
    timeout=300,
)

lc = 0
phases = set()
for line in r.iter_lines():
    if line:
        d = line.decode("utf-8", errors="replace")
        lc += 1
        if lc <= 10:
            print(f"[{lc}] {d[:200]}")
        elif "phase" in d.lower() or "agent" in d.lower() or "tool" in d.lower() or "done" in d.lower():
            print(f"[{lc}] >>> {d[:300]}")
        elif lc % 30 == 0:
            print(f"[{lc}] ...")

print(f"\nLINES: {lc}")
