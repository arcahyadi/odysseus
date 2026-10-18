import re

from fastapi import HTTPException

_REMOTE_HOST_RE = re.compile(r"^(?:[A-Za-z0-9][A-Za-z0-9._-]*@)?[A-Za-z0-9][A-Za-z0-9._-]*$")
_SSH_PORT_RE = re.compile(r"^\d{1,5}$")


def validate_remote_host(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    if not _REMOTE_HOST_RE.match(v):
        raise HTTPException(
            400,
            "Invalid remote_host — must be host or user@host, no SSH option syntax",
        )
    return v


def validate_ssh_port(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    if not _SSH_PORT_RE.fullmatch(str(v)):
        raise HTTPException(400, "Invalid ssh_port")
    port = int(v)
    if port < 1 or port > 65535:
        raise HTTPException(400, "Invalid ssh_port")
    return str(port)

# ─── Registre central (MOD-2) ─────────────────────────────────────────────

def register_validators():
    """Enregistre les fonctions de _validators dans le registre central."""
    from src.route_registry import register_action
    
    register_action("validate_remote_host", validate_remote_host)
    register_action("validate_ssh_port", validate_ssh_port)


# Auto-enregistrement à l'import
try:
    register_validators()
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"Auto-enregistrement _validators échoué: {e}")
