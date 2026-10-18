"""Trace the exact decision path the system takes."""

import json
import sys

import requests

BASE = "http://127.0.0.1:7000"

print("Creating session...")
r = requests.post(
    f"{BASE}/api/session",
    data={
        "name": "Trace Test",
        "model": "minimax-m3",
        "endpoint_url": "https://opencode.ai/zen/go/v1/chat/completions",
    },
)
if r.status_code != 200:
    print(f"ERROR: {r.status_code} {r.text[:200]}")
    sys.exit(1)
sid = r.json()["id"]
print(f"Session: {sid[:8]}...\n")

print("Sending agent message...")
r = requests.post(
    f"{BASE}/api/chat_stream",
    data={"message": "write a python hello.py", "session": sid, "mode": "agent"},
    stream=True,
    timeout=120,
)

events = []
for line in r.iter_lines():
    if line and line.startswith(b"data: "):
        try:
            data = json.loads(line[6:])
            t = data.get("type", "")
            if t in [
                "mode_detected",
                "phase_enter",
                "phase_exit",
                "model_info",
                "run_status",
                "metrics",
                "memories_used",
                "web_sources",
                "budget",
                "tool_call",
                "agent_prep",
            ]:
                events.append(data)
        except:
            pass

print("=" * 70)
print("ARBRE DE DECISION EXECUTE — CHEMIN REEL")
print("=" * 70)

for i, e in enumerate(events):
    t = e.get("type", "")

    if t == "model_info":
        print(f"\n[{i}] MODEL SELECTIONNE: {e.get('model')}")
    elif t == "mode_detected":
        mode = e.get("mode")
        print(f"\n[{i}] MODE DETECTE: {mode}")
        print(f"    -> Decision: {'PIPELINE 7 PHASES' if mode == 'agent' else 'CHAT SIMPLE'}")
    elif t == "phase_enter":
        phase = e.get("phase")
        agents = e.get("agents", [])
        model = e.get("model", "")
        tools = e.get("tools", [])
        print(f"\n[{i}] PHASE ENTER: {phase} (etape {e.get('index', 1)}/{e.get('total', 7)})")
        if agents:
            print(f"    -> Agents spawnes: {agents}")
        if model:
            print(f"    -> Modele route: {model}")
        if tools:
            print(f"    -> Outils autorises: {tools}")
    elif t == "phase_exit":
        print(f"[{i}] PHASE EXIT: {e.get('phase')}")
    elif t == "run_status":
        print(f"[{i}] STATUS: phase_active={e.get('phase_active')}, phase={e.get('phase')}, drift={e.get('drift')}")
    elif t == "metrics":
        d = e.get("data", {})
        tokens = d.get("total_tokens", 0)
        ttft = d.get("time_to_first_token", 0)
        model = d.get("model", "")
        print(f"[{i}] METRICS: {tokens} tokens, TTFT={ttft}s, model={model}")
    elif t == "memories_used":
        mems = e.get("data", [])
        print(f"[{i}] MEMOIRES RAPPELEES: {len(mems)} facts")
        for m in mems[:3]:
            text = m.get("text", "")[:100]
            mtype = m.get("type", "?")
            print(f"    -> [{mtype}] {text}")
    elif t == "web_sources":
        srcs = e.get("data", [])
        print(f"[{i}] WEB SEARCH: {len(srcs)} resultats via SearXNG")
    elif t == "agent_prep":
        d = e.get("data", {})
        print(f"[{i}] AGENT PREP: tool_selection={d.get('tool_selection')}s, prompt_build={d.get('prompt_build')}s")

print(f"\n{'=' * 70}")
print(f"TOTAL: {len(events)} decisions tracees dans l'arbre")
print(f"{'=' * 70}")
