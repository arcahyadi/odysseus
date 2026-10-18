"""E2E test v6: FULL AGENT MODE project pipeline."""

import json
import sys
import time

import requests

BASE = "http://127.0.0.1:7000"

# Create session
r = requests.post(
    f"{BASE}/api/session",
    data={
        "name": "E2E Agent Pipeline Test",
        "model": "minimax-m3",
        "endpoint_url": "https://opencode.ai/zen/go/v1/chat/completions",
    },
)
if r.status_code != 200:
    print(f"ERROR: {r.status_code} {r.text[:300]}")
    sys.exit(1)

session = r.json()
sid = session.get("id")
print(f"SESSION: {sid}")

# Send AGENT mode with a real project task
msg = "create a complete flask todo app with SQLite database, routes for list/add/delete tasks, and a simple HTML template"
print(f"\nSENDING agent: {msg[:80]}...\n")

start = time.time()
r = requests.post(
    f"{BASE}/api/chat_stream",
    data={"message": msg, "session": sid, "mode": "agent", "use_web": "false", "allow_bash": "true"},
    stream=True,
    timeout=600,
)

lc = 0
phases = []
tools_used = set()
for line in r.iter_lines():
    if line:
        d = line.decode("utf-8", errors="replace")
        lc += 1
        if lc <= 5:
            print(f"[{lc}] {d[:250]}")
            continue

        if d.startswith("data: "):
            try:
                data = json.loads(d[6:])
                t = data.get("type", "")

                if t == "phase_enter":
                    p = data.get("phase", "")
                    phases.append(p)
                    print(f"[{lc}] >>> PHASE ENTER: {p}")
                elif t == "phase_exit":
                    print(f"[{lc}] >>> PHASE EXIT: {data.get('phase', '')}")
                elif t == "mode_detected":
                    print(f"[{lc}] >>> MODE: {data.get('mode', '')}")
                elif t == "tool_call":
                    tool = data.get("tool_name", data.get("name", ""))
                    tools_used.add(tool)
                    print(f"[{lc}] >>> TOOL: {tool}")
                elif t == "tool_result":
                    print(f"[{lc}] >>> TOOL RESULT: {data.get('tool_name', '')}")
                elif t == "model_info":
                    print(f"[{lc}] >>> MODEL: {data.get('model', '')}")
                elif t == "metrics":
                    print(
                        f"[{lc}] >>> METRICS: {data.get('data', {}).get('total_tokens', 0)} tokens, {data.get('data', {}).get('response_time', 0)}s"
                    )
                elif t == "run_status":
                    print(
                        f"[{lc}] >>> STATUS: active={data.get('phase_active')} phase={data.get('phase')} drift={data.get('drift')}"
                    )
                elif t == "budget":
                    print(f"[{lc}] >>> BUDGET: {data}")
                elif "[DONE]" in d:
                    print(f"[{lc}] >>> DONE")
            except:
                pass
        elif "[DONE]" in d:
            print(f"[{lc}] >>> DONE")
        elif lc % 40 == 0:
            print(f"[{lc}] ...")

elapsed = time.time() - start
print(f"\n{'=' * 60}")
print(f"LINES: {lc}")
print(f"ELAPSED: {elapsed:.1f}s")
print(f"PHASES: {phases}")
print(f"TOOLS USED: {sorted(tools_used)}")
print(f"{'=' * 60}")
