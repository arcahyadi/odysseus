"""Batch E2E tests — 3 different project types."""

import json
import time

import requests

BASE = "http://127.0.0.1:7000"
PROJECTS = [
    {
        "name": "P2-FastAPI-Books",
        "msg": "create a FastAPI REST API file main.py for a book library with CRUD endpoints (POST/GET/PUT/DELETE) using Pydantic models and in-memory dict storage. Include requirements.txt",
    },
    {
        "name": "P3-Data-Analysis",
        "msg": "write a python script analysis.py that generates a sample CSV with columns date,product,quantity,price, reads it, calculates total revenue per product, and prints a report",
    },
    {
        "name": "P4-Landing-Page",
        "msg": "build a single index.html landing page for a startup called CloudBoard with hero section, features grid, dark theme, responsive CSS, contact form",
    },
]

results = []

for proj in PROJECTS:
    print(f"\n{'=' * 60}")
    print(f"  {proj['name']}")
    print(f"{'=' * 60}")

    # Create session
    r = requests.post(
        f"{BASE}/api/session",
        data={
            "name": proj["name"],
            "model": "minimax-m3",
            "endpoint_url": "https://opencode.ai/zen/go/v1/chat/completions",
        },
    )
    if r.status_code != 200:
        print(f"  FAIL session: {r.status_code}")
        results.append({"project": proj["name"], "status": "FAIL", "error": "session"})
        continue

    sid = r.json()["id"]
    print(f"  Session: {sid[:8]}...")

    # Run agent
    t0 = time.time()
    phases = []
    mode = "?"
    tokens = 0

    try:
        r = requests.post(
            f"{BASE}/api/chat_stream",
            data={"message": proj["msg"], "session": sid, "mode": "agent", "use_web": "false"},
            stream=True,
            timeout=300,
        )

        for line in r.iter_lines():
            if line and line.startswith(b"data: "):
                try:
                    d = json.loads(line[6:])
                    t = d.get("type", "")
                    if t == "phase_enter":
                        phases.append(d.get("phase", ""))
                    elif t == "mode_detected":
                        mode = d.get("mode", "")
                    elif t == "metrics":
                        tokens = d.get("data", {}).get("total_tokens", 0)
                except:
                    pass
    except Exception as e:
        print(f"  ERROR: {e}")

    elapsed = time.time() - t0
    status = "PASS" if len(phases) >= 5 else "PARTIAL"

    print(f"  MODE: {mode} | PHASES: {len(phases)} | TOKENS: {tokens} | TIME: {elapsed:.0f}s")
    print(f"  FLOW: {' -> '.join(phases) if phases else 'none'}")

    results.append(
        {
            "project": proj["name"],
            "status": status,
            "mode": mode,
            "phases": len(phases),
            "tokens": tokens,
            "time": elapsed,
            "flow": " -> ".join(phases),
        }
    )

# Summary
print(f"\n{'=' * 60}")
print("  RESUME")
print(f"{'=' * 60}")
passed = sum(1 for r in results if r["status"] == "PASS")
total_tokens = sum(r["tokens"] for r in results)
for r in results:
    icon = "[OK]" if r["status"] == "PASS" else "[--]"
    print(f"  {icon} {r['project']}: {r['mode']} | {r['phases']} phases | {r['tokens']} tokens | {r['time']:.0f}s")
print(f"\n  PASS: {passed}/{len(results)} | TOTAL TOKENS: {total_tokens}")
