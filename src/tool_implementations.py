"""
tool_implementations.py

Extracted tool implementation functions (do_* and helpers) from agent_tools.py.
These handle the actual execution logic for each tool type.
"""

import logging
from src.app_context import app_context

# System-domain tools were extracted to src/tools/system.py (slice 1,
# #4082/#4071); the admin manage_* tools live in src/agent_tools/admin_tools
# after the upstream registry migration (#3629). Re-imported here so this
# module stays a working facade.
from src.tools.system import (  # noqa: F401

    _APP_API_BLOCKLIST_METHOD_PATH,
    _APP_API_BLOCKLIST_PREFIXES,
    _skill_dump,
    do_api_call,
    do_app_api,
    do_manage_skills,
    do_manage_tasks,
)

# Admin manage_* tools (endpoints/mcp/webhooks/tokens/settings) live in
# src/agent_tools/admin_tools after the upstream registry migration (#3629).
# Re-exported lazily via __getattr__: src.agent_tools.__init__ imports this
# facade at top level, so a eager `from src.agent_tools.admin_tools import`
# here would re-enter the partially-initialized agent_tools package (circular).
_ADMIN_TOOL_SYMBOLS = (
    "do_manage_endpoints",
    "do_manage_mcp",
    "do_manage_webhooks",
    "do_manage_tokens",
    "do_manage_settings",
    "_MCP_DENIED_COMMANDS",
    "_validate_mcp_command",
    "_mcp_allowed_commands",
)


def __getattr__(name):
    if name in _ADMIN_TOOL_SYMBOLS:
        from src.agent_tools import admin_tools

        return getattr(admin_tools, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Cookbook (model serving) domain extracted to src/tools/cookbook.py
# (slice 1, #4082/#4071). Re-imported here so this module stays a working
# facade. cookbook.py pulls `_internal_headers` / `_INTERNAL_BASE` back
# function-locally from this facade (which re-exports them from _common).
# Shared helpers live in src/tools/_common.py. Re-exported here so the
# function-local `from src.tool_implementations import _INTERNAL_BASE` (and
# friends) used by domain files still resolve through this facade.
from src.tools._common import _INTERNAL_BASE, _internal_headers, _parse_tool_args  # noqa: F401

# Calendar domain extracted to src/tools/calendar.py (slice 1, #4082/#4071).
from src.tools.calendar import do_manage_calendar  # noqa: F401

# Contacts domain extracted to src/tools/contacts.py (slice 1, #4082/#4071).
from src.tools.contacts import do_manage_contact, do_resolve_contact  # noqa: F401
from src.tools.cookbook import (  # noqa: F401
    _MODEL_PROCESS_PATTERNS,
    _cookbook_apply_retry_suggestion,
    _cookbook_env_for_host,
    _cookbook_kill_session,
    _cookbook_register_task,
    _cookbook_servers,
    _ensure_served_endpoint,
    _infer_serve_host,
    _infer_serve_port,
    _resolve_cookbook_host,
    _scan_running_model_processes,
    _string_arg,
    _validate_cookbook_ssh_target,
    do_adopt_served_model,
    do_cancel_download,
    do_download_model,
    do_list_cached_models,
    do_list_cookbook_servers,
    do_list_downloads,
    do_list_serve_presets,
    do_list_served_models,
    do_search_hf_models,
    do_serve_model,
    do_serve_preset,
    do_stop_served_model,
    do_tail_serve_output,
)

# Image domain extracted to src/tools/image.py (slice 1, #4082/#4071).
from src.tools.image import do_edit_image  # noqa: F401

# Notes domain extracted to src/tools/notes.py (slice 1, #4082/#4071).
from src.tools.notes import do_manage_notes  # noqa: F401

# Research domain extracted to src/tools/research.py (slice 1, #4082/#4071).
from src.tools.research import do_manage_research, do_trigger_research  # noqa: F401

# Search domain extracted to src/tools/search.py (slice 1, #4082/#4071).
# Re-imported here so this module stays a working facade.
from src.tools.search import do_search_chats  # noqa: F401

# Vault domain extracted to src/tools/vault.py (slice 1, #4082/#4071).
from src.tools.vault import (  # noqa: F401
    _load_vault_config,
    _run_bw,
    do_vault_get,
    do_vault_search,
    do_vault_unlock,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Active email state
# ---------------------------------------------------------------------------

# When the user has an email reader window open, the frontend tells the
# backend about it on each chat submit. Email tools can resolve "this email"
# without guessing a UID. Cleared between requests by chat_routes.
app_context.caches.active_email_ref: dict[str, str] | None = None


def set_active_email(
    uid: str | None,
    folder: str | None = None,
    account: str | None = None,
    subject: str | None = None,
    sender: str | None = None,
) -> None:
    """Stash the email currently open in the UI. None clears it."""
    if not uid:
        app_context.caches.active_email_ref = None
        return
    app_context.caches.active_email_ref = {
        "uid": str(uid),
        "folder": str(folder or "INBOX"),
        "account": str(account or ""),
        "subject": str(subject or ""),
        "from": str(sender or ""),
    }


def get_active_email() -> dict[str, str] | None:
    return app_context.caches.active_email_ref


def clear_active_email() -> None:
    app_context.caches.active_email_ref = None
