"""Acontext Memory Service — distillation de sessions agent en SKILL.md.

Exposed on port 8029 (Docker). The AcontextMemoryProvider in
src/memory_provider.py POSTs session-end payloads here. The service:
1. Stores raw session data as JSON
2. When a session is "complete", distills it into a reusable SKILL.md
   using the configured LLM endpoint
3. Writes the SKILL.md to the shared volume for Obsidian/skills import

Gated by ACONTEXT_ENABLED (env, default false). Without it, the provider
never calls this service → startup byte-identical.
"""

import json
import os
import pathlib
import re
from datetime import UTC, datetime

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Acontext Memory Service")

DATA = pathlib.Path(os.environ.get("ACONTEXT_DATA_DIR", "/data/acontext"))
SKILLS_OUT = pathlib.Path(os.environ.get("ACONTEXT_SKILLS_DIR", "/data/skills"))
LLM_ENDPOINT = os.environ.get("ACONTEXT_LLM_ENDPOINT", "http://odysseus:7000/api/chat/completions")
LLM_MODEL = os.environ.get("ACONTEXT_LLM_MODEL", "")
LLM_API_KEY = os.environ.get("ACONTEXT_LLM_API_KEY", "")

DATA.mkdir(parents=True, exist_ok=True)
SKILLS_OUT.mkdir(parents=True, exist_ok=True)

_SESSION_STORE: dict[str, dict] = {}  # session_id → accumulated data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_filename(name: str) -> str:
    """Convert title to safe filename."""
    name = re.sub(r"[^\w\s-]", "", name.lower())
    name = re.sub(r"[-\s]+", "-", name)
    return name.strip("-")[:80]


def _distill_prompt(session_data: dict) -> str:
    """Build a distillation prompt from session data."""
    messages = session_data.get("messages", [])
    summary = session_data.get("summary", "")
    tools_used = session_data.get("tools_used", [])
    run_id = session_data.get("run_id", "unknown")
    project = session_data.get("project", "")

    context = f"## Session Summary\n{summary}\n\n"
    context += f"## Project\n{project}\n\n"
    context += f"## Tools Used\n{', '.join(tools_used[:20])}\n\n"
    context += "## Conversation\n"
    for msg in messages[-20:]:  # last 20 messages
        role = msg.get("role", "?")
        content = str(msg.get("content", ""))[:500]
        context += f"**{role}**: {content}\n\n"

    return f"""You are a knowledge distillation agent. Analyze this agent session and extract reusable patterns, techniques, and learnings into a concise SKILL.md file.

{context}

Write a SKILL.md with this structure:
```markdown
# Skill: [descriptive-name]

## Trigger
[When to use this skill — what user request or situation triggers it]

## Approach
[The step-by-step approach that worked. Be specific — mention exact tools, commands, patterns.]

## Key Learnings
- [Learning 1]
- [Learning 2]
- [Learning 3]

## Pitfalls
- [What to avoid — things that went wrong or wasted time]

## Example
[Concrete example of applying this skill]
```

Be concise. Focus on REUSABLE patterns, not the specific task. Write in English. Output ONLY the SKILL.md content."""


async def _call_llm(prompt: str) -> str | None:
    """Call the configured LLM for distillation. Best-effort: returns None on failure."""
    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 2000,
    }
    if LLM_MODEL:
        payload["model"] = LLM_MODEL

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(LLM_ENDPOINT, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
            return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/sessions/end")
async def session_end(payload: dict = None):
    """Store session-end data. Accumulates per session_id."""
    if not payload:
        raise HTTPException(status_code=400, detail="payload required")

    session_id = payload.get("session_id", "")
    if not session_id:
        session_id = f"anon_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

    # Merge with existing data for this session
    if session_id not in _SESSION_STORE:
        _SESSION_STORE[session_id] = payload
    else:
        existing = _SESSION_STORE[session_id]
        existing["messages"] = (existing.get("messages") or []) + (payload.get("messages") or [])
        existing["tools_used"] = list(set((existing.get("tools_used") or []) + (payload.get("tools_used") or [])))
        if payload.get("summary"):
            existing["summary"] = payload["summary"]

    # Also persist to disk
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    (DATA / f"session_{session_id}_{ts}.json").write_text(json.dumps(payload, indent=2))

    return {"status": "stored", "session_id": session_id, "ts": ts}


@app.post("/api/sessions/complete")
async def session_complete(payload: dict = None):
    """Distill a completed session into a SKILL.md via LLM.

    First stores the final payload, then triggers LLM distillation.
    The resulting SKILL.md is written to the skills output directory.
    """
    if not payload:
        raise HTTPException(status_code=400, detail="payload required")

    # Store first
    store_result = await session_end(payload)

    session_id = store_result["session_id"]
    session_data = _SESSION_STORE.get(session_id, payload)

    # Distill via LLM
    prompt = _distill_prompt(session_data)
    skill_content = await _call_llm(prompt)

    if skill_content:
        # Extract title or use fallback
        title_match = re.search(r"# Skill:\s*(.+)", skill_content)
        title = title_match.group(1).strip() if title_match else f"session-{session_id}"
        filename = _sanitize_filename(title) + ".md"
        skill_path = SKILLS_OUT / filename
        skill_path.write_text(skill_content, encoding="utf-8")

        # Cleanup in-memory store
        _SESSION_STORE.pop(session_id, None)

        return {
            "status": "distilled",
            "session_id": session_id,
            "skill_file": str(skill_path),
            "skill_title": title,
        }

    return {
        "status": "stored_no_distillation",
        "session_id": session_id,
        "hint": "LLM distillation failed — session saved, retry later",
    }


@app.get("/health")
async def health():
    sessions = list(DATA.glob("session_*.json"))
    skills = list(SKILLS_OUT.glob("*.md"))
    return {
        "status": "ok",
        "service": "acontext",
        "sessions_stored": len(sessions),
        "skills_generated": len(skills),
        "llm_endpoint": LLM_ENDPOINT,
    }


@app.get("/api/sessions")
async def list_sessions():
    sessions = sorted(DATA.glob("session_*.json"))
    skills = sorted(SKILLS_OUT.glob("*.md"))
    return {
        "sessions": [s.name for s in sessions[-50:]],
        "skills": [s.name for s in skills[-50:]],
    }


@app.delete("/api/sessions")
async def clear_sessions():
    """Clear all stored sessions and skills (admin)."""
    for f in DATA.glob("session_*.json"):
        f.unlink()
    for f in SKILLS_OUT.glob("*.md"):
        f.unlink()
    _SESSION_STORE.clear()
    return {"status": "cleared"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8029)
