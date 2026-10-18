"""End-to-End System Test — 4 projects, user simulation, local deployment verification."""

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

BASE = "http://127.0.0.1:7000"
PROJECTS_DIR = Path("data/e2e-projects")
RESULTS = []


def create_session(name):
    r = requests.post(
        f"{BASE}/api/session",
        data={"name": name, "model": "minimax-m3", "endpoint_url": "https://opencode.ai/zen/go/v1/chat/completions"},
    )
    if r.status_code != 200:
        return None
    return r.json()["id"]


def run_agent(session_id, message, timeout=600):
    """Run an agent project and capture all events."""
    r = requests.post(
        f"{BASE}/api/chat_stream",
        data={"message": message, "session": session_id, "mode": "agent", "use_web": "false"},
        stream=True,
        timeout=timeout,
    )

    phases = []
    mode = "unknown"
    model = "unknown"
    tokens = 0
    errors = []
    memories = 0

    for line in r.iter_lines():
        if not line or not line.startswith(b"data: "):
            continue
        try:
            data = json.loads(line[6:])
            t = data.get("type", "")

            if t == "phase_enter":
                phases.append(data.get("phase", ""))
            elif t == "mode_detected":
                mode = data.get("mode", "")
            elif t == "model_info":
                model = data.get("model", "")
            elif t == "metrics":
                tokens = data.get("data", {}).get("total_tokens", 0)
            elif t == "memories_used":
                memories = len(data.get("data", []))
            elif t == "error":
                errors.append(str(data)[:100])
        except:
            pass

    return {"mode": mode, "model": model, "phases": phases, "tokens": tokens, "memories": memories, "errors": errors}


def verify_project(project_dir, expected_files, start_cmd=None, test_url=None):
    """Verify a project was created and can be deployed."""
    result = {"files_found": [], "files_missing": [], "deploy_ok": False, "deploy_error": ""}

    if not project_dir.exists():
        result["files_missing"] = [str(f) for f in expected_files]
        return result

    for f in expected_files:
        full_path = project_dir / f
        if full_path.exists():
            size = full_path.stat().st_size
            result["files_found"].append(f"{f} ({size}B)")
        else:
            result["files_missing"].append(f)

    # Try to start the app
    if start_cmd:
        try:
            proc = subprocess.Popen(
                start_cmd,
                shell=True,
                cwd=str(project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
            )
            time.sleep(3)  # Wait for startup

            if test_url:
                try:
                    r = requests.get(test_url, timeout=5)
                    if r.status_code == 200:
                        result["deploy_ok"] = True
                        result["deploy_response"] = r.text[:200]
                except:
                    result["deploy_error"] = f"Cannot reach {test_url}"
            else:
                poll = proc.poll()
                if poll is not None:
                    stderr = proc.stderr.read().decode("utf-8", errors="replace")[:300]
                    result["deploy_error"] = f"Process exited with code {poll}: {stderr}"
                else:
                    result["deploy_ok"] = True  # Still running = probably working

            proc.terminate()
            time.sleep(1)
        except Exception as e:
            result["deploy_error"] = str(e)[:200]

    return result


def print_section(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def print_phase_flow(phases, mode):
    flow = " -> ".join(phases) if phases else "no phases"
    print(f"  MODE: {mode}")
    print(f"  FLOW: {flow}")
    print(f"  PHASES: {len(phases)} phases")


def print_verify(result):
    ok = "[OK]" if not result["files_missing"] else "[FAIL]"
    deploy = "[OK]" if result["deploy_ok"] else ("[FAIL]" if result["deploy_error"] else "—")
    print(f"  FILES: {ok} {len(result['files_found'])} found, {len(result['files_missing'])} missing")
    if result["files_found"]:
        for f in result["files_found"]:
            print(f"    [FILE] {f}")
    if result["files_missing"]:
        for f in result["files_missing"]:
            print(f"    [FAIL] MISSING: {f}")
    print(f"  DEPLOY: {deploy}")
    if result["deploy_error"]:
        print(f"    Error: {result['deploy_error'][:100]}")
    if result.get("deploy_response"):
        print(f"    Response: {result['deploy_response'][:100]}")


# ===================================================================
# TEST SUITE
# ===================================================================

print("=" * 70)
print("  AGENT OS — TEST SYSTEME COMPLET (4 PROJETS)")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# Clean up previous projects
if PROJECTS_DIR.exists():
    shutil.rmtree(PROJECTS_DIR)
PROJECTS_DIR.mkdir(parents=True)

# ===================================================================
# PROJECT 1: Flask Todo App (Web Application)
# ===================================================================
print_section("PROJET 1/4: Flask Todo App (Application Web)")

sid = create_session("E2E-P1-Flask-Todo")
if not sid:
    print("  [FAIL] Session creation failed")
    sys.exit(1)

result1 = run_agent(
    sid,
    "build a complete flask todo app with SQLite database, HTML template with Bootstrap, routes for list/add/delete tasks. Create requirements.txt. Make it ready to run with 'python app.py'",
)
print_phase_flow(result1["phases"], result1["mode"])
print(f"  TOKENS: {result1['tokens']} | MEMORIES: {result1['memories']} | ERRORS: {len(result1['errors'])}")

# Verify files + try to start
p1_dir = PROJECTS_DIR / "p1-flask-todo"
# Copy from wherever the agent created files
possible_dirs = [Path("."), Path("app"), Path("flask_todo"), Path("todo")]
for d in possible_dirs:
    if (d / "app.py").exists():
        shutil.copytree(d, p1_dir, dirs_exist_ok=True)
        break

v1 = verify_project(p1_dir, ["app.py", "requirements.txt"], start_cmd="python app.py", test_url="http://127.0.0.1:5000")
print_verify(v1)
RESULTS.append({"project": "Flask Todo App", **result1, "verify": v1})

# ===================================================================
# PROJECT 2: FastAPI Book Library (REST API)
# ===================================================================
print_section("PROJET 2/4: FastAPI Book Library (API REST)")

sid = create_session("E2E-P2-FastAPI-Books")
if not sid:
    print("  [FAIL] Session creation failed")
else:
    result2 = run_agent(
        sid,
        "create a FastAPI REST API for a book library with CRUD endpoints: POST /books, GET /books, GET /books/{id}, PUT /books/{id}, DELETE /books/{id}. Use Pydantic models. Store in memory (Python dict). Include main.py and requirements.txt. Make it ready to run with 'uvicorn main:app --reload'",
    )
    print_phase_flow(result2["phases"], result2["mode"])
    print(f"  TOKENS: {result2['tokens']} | MEMORIES: {result2['memories']} | ERRORS: {len(result2['errors'])}")

    p2_dir = PROJECTS_DIR / "p2-fastapi-books"
    for d in possible_dirs + [Path("api"), Path("books"), Path("fastapi_books")]:
        if (d / "main.py").exists():
            shutil.copytree(d, p2_dir, dirs_exist_ok=True)
            break

    v2 = verify_project(
        p2_dir,
        ["main.py", "requirements.txt"],
        start_cmd="uvicorn main:app --port 8001",
        test_url="http://127.0.0.1:8001/docs",
    )
    print_verify(v2)
    RESULTS.append({"project": "FastAPI Books API", **result2, "verify": v2})

# ===================================================================
# PROJECT 3: Python Data Analysis (Script)
# ===================================================================
print_section("PROJET 3/4: Python Data Analysis (Script)")

sid = create_session("E2E-P3-Data-Analysis")
if not sid:
    print("  [FAIL] Session creation failed")
else:
    result3 = run_agent(
        sid,
        "write a python data analysis script that generates a sample sales CSV with columns date,product,quantity,price, then reads it, calculates total revenue per product, and prints a summary report with matplotlib bar chart saved as chart.png",
    )
    print_phase_flow(result3["phases"], result3["mode"])
    print(f"  TOKENS: {result3['tokens']} | MEMORIES: {result3['memories']} | ERRORS: {len(result3['errors'])}")

    p3_dir = PROJECTS_DIR / "p3-data-analysis"
    for d in possible_dirs + [Path("analysis"), Path("data_analysis")]:
        if (d / "analysis.py").exists() or (d / "main.py").exists():
            shutil.copytree(d, p3_dir, dirs_exist_ok=True)
            break

    script_file = "analysis.py" if (p3_dir / "analysis.py").exists() else "main.py"
    v3 = verify_project(
        p3_dir,
        [script_file, "chart.png"] if (p3_dir / script_file).exists() else [script_file],
        start_cmd=f"python {script_file}" if (p3_dir / script_file).exists() else None,
    )
    print_verify(v3)
    RESULTS.append({"project": "Data Analysis Script", **result3, "verify": v3})

# ===================================================================
# PROJECT 4: HTML Landing Page (Static Site)
# ===================================================================
print_section("PROJET 4/4: HTML Landing Page (Site Statique)")

sid = create_session("E2E-P4-Landing-Page")
if not sid:
    print("  [FAIL] Session creation failed")
else:
    result4 = run_agent(
        sid,
        "build a modern responsive HTML/CSS landing page for a startup called 'CloudBoard'. Include: hero section with CTA button, features grid (3 features), pricing table (3 tiers), contact form. Use embedded CSS (no framework), dark theme, smooth scroll. Single index.html file.",
    )
    print_phase_flow(result4["phases"], result4["mode"])
    print(f"  TOKENS: {result4['tokens']} | MEMORIES: {result4['memories']} | ERRORS: {len(result4['errors'])}")

    p4_dir = PROJECTS_DIR / "p4-landing-page"
    for d in possible_dirs + [Path("landing"), Path("site"), Path("cloudboard")]:
        if (d / "index.html").exists():
            shutil.copytree(d, p4_dir, dirs_exist_ok=True)
            break

    v4 = verify_project(
        p4_dir, ["index.html"], start_cmd="python -m http.server 8002", test_url="http://127.0.0.1:8002"
    )
    print_verify(v4)
    RESULTS.append({"project": "Landing Page", **result4, "verify": v4})

# ===================================================================
# FINAL SUMMARY
# ===================================================================
print_section("RESUME FINAL")

total = len(RESULTS)
phases_ok = sum(1 for r in RESULTS if len(r.get("phases", [])) >= 5)
mode_agent = sum(1 for r in RESULTS if r.get("mode") == "agent")
files_ok = sum(1 for r in RESULTS if not r.get("verify", {}).get("files_missing"))
deploy_ok = sum(1 for r in RESULTS if r.get("verify", {}).get("deploy_ok"))
total_tokens = sum(r.get("tokens", 0) for r in RESULTS)

print(f"\n  PROJETS EXECUTES: {total}")
for r in RESULTS:
    p = r["project"]
    m = r.get("mode", "?")
    ph = len(r.get("phases", []))
    tk = r.get("tokens", 0)
    f_ok = "[OK]" if not r.get("verify", {}).get("files_missing") else "[FAIL]"
    d_ok = "[OK]" if r.get("verify", {}).get("deploy_ok") else "—"
    print(f"  {f_ok} {d_ok} {p}: {m} | {ph} phases | {tk} tokens")

print(f"\n  MODE AGENT: {mode_agent}/{total}")
print(f"  PHASES >= 5: {phases_ok}/{total}")
print(f"  FICHIERS CREES: {files_ok}/{total}")
print(f"  DEPLOIEMENT LOCAL: {deploy_ok}/{total}")
print(f"  TOTAL TOKENS: {total_tokens}")

# Check traces
traces_dir = Path("data/traces")
trace_files = sorted(traces_dir.glob("events-*.jsonl"))
if trace_files:
    latest = trace_files[-1]
    print(f"  EVENT TRACES: {latest.name} ({latest.stat().st_size} bytes)")

print(f"\n{'=' * 70}")
print(f"  SCORE: {files_ok + deploy_ok}/{total * 2} checks passes")
print(f"{'=' * 70}")
