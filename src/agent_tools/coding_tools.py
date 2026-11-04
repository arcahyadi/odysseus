import json
import os
import re
from typing import Any, Dict, List

from src.constants import DATA_DIR


_TODO_DIR = os.path.join(DATA_DIR, "agent_todos")


def _safe_session_id(value: str) -> str:
    value = value or "current"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:120] or "current"


class TodoWriteTool:
    async def execute(self, content: str, ctx: dict) -> dict:
        try:
            args = json.loads(content) if (content or "").strip().startswith("{") else {"todos": []}
        except (json.JSONDecodeError, TypeError):
            return {"error": "todowrite: JSON object required", "exit_code": 1}
        todos = args.get("todos")
        if not isinstance(todos, list):
            return {"error": "todowrite: todos must be a list", "exit_code": 1}

        normalized: List[Dict[str, Any]] = []
        allowed_statuses = {"pending", "in_progress", "completed"}
        allowed_priorities = {"low", "medium", "high"}
        active_count = 0
        for item in todos:
            if not isinstance(item, dict):
                return {"error": "todowrite: each todo must be an object", "exit_code": 1}
            content_text = str(item.get("content") or item.get("text") or "").strip()
            if not content_text:
                return {"error": "todowrite: todo content required", "exit_code": 1}
            status = str(item.get("status") or "pending").strip()
            if status not in allowed_statuses:
                return {"error": f"todowrite: invalid status {status!r}", "exit_code": 1}
            if status == "in_progress":
                active_count += 1
            priority = str(item.get("priority") or "medium").strip()
            if priority not in allowed_priorities:
                priority = "medium"
            normalized.append({
                "content": content_text,
                "status": status,
                "priority": priority,
            })
        if active_count > 1:
            return {"error": "todowrite: only one todo can be in_progress", "exit_code": 1}

        session_id = _safe_session_id(str(ctx.get("session_id") or args.get("session_id") or "current"))
        os.makedirs(_TODO_DIR, exist_ok=True)
        path = os.path.join(_TODO_DIR, f"{session_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"todos": normalized}, f, ensure_ascii=False, indent=2)

        lines = []
        for item in normalized:
            marker = {"pending": " ", "in_progress": ">", "completed": "x"}[item["status"]]
            lines.append(f"[{marker}] {item['content']} ({item['priority']})")
        return {
            "output": "Updated todo list:\n" + ("\n".join(lines) if lines else "(empty)"),
            "exit_code": 0,
            "todos": normalized,
        }
