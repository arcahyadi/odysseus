"""
Command Validator — Valide les commandes bash avant exécution.
Phase 12 : Sandbox — scope whitelist + patterns dangereux bloqués.
Pattern inspiré de HexStrike (défensif uniquement).
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    allowed: bool
    risk_level: str  # "safe", "warning", "blocked"
    reason: str
    sanitized_command: str | None = None  # Commande après sanitisation (si applicable)


# Patterns BLOQUÉS — dangereux irréversibles
BLOCKED_PATTERNS = [
    # Destruction fichiers/disques
    (r"rm\s+-rf\s+[/~]", "rm -rf sur / ou ~ bloqué"),
    (r"rm\s+-rf\s+\*", "rm -rf * bloqué"),
    (r"mkfs\b", "formatage disque bloqué"),
    (r"dd\s+if=.*of=/dev/(sd|hd|nvme|disk)", "dd sur device bloqué"),
    (r":\s*\(\s*\)\s*\{.*\}.*:", "fork bomb bloqué"),
    # DB destruction
    (r"DROP\s+DATABASE", "DROP DATABASE bloqué"),
    (r"DROP\s+TABLE\s+(?!IF\s+EXISTS\s+test)", "DROP TABLE bloqué (sauf tables test)"),
    (r"TRUNCATE\s+TABLE\s+(?!test)", "TRUNCATE TABLE bloqué (sauf tables test)"),
    # Git dangereux
    (r"git\s+push\s+.*--force(?!-with-lease)", "git push --force bloqué (utiliser --force-with-lease)"),
    (r"git\s+reset\s+--hard\s+HEAD~[2-9]", "git reset --hard HEAD~2+ bloqué"),
    # Réseau dangereux
    (r"curl\s+.*\|\s*(bash|sh|python)", "pipe curl vers shell bloqué"),
    (r"wget\s+.*-O-\s*\|\s*(bash|sh)", "pipe wget vers shell bloqué"),
    # Secrets
    (r'echo\s+["\'].*\b(password|secret|token|key)\b.*["\']', "affichage de secret bloqué"),
    # Processus
    (r"kill\s+-9\s+1\b", "kill PID 1 bloqué"),
    (r"killall\s+-9", "killall -9 bloqué"),
]

# Patterns WARNING — dangereux mais parfois légitimes
WARNING_PATTERNS = [
    (r"chmod\s+777", "chmod 777 déconseillé"),
    (r"sudo\s+", "sudo détecté — vérifier la nécessité"),
    (r"eval\s+", "eval détecté — risque injection"),
    (r"exec\s+", "exec détecté — risque injection"),
    (r"\$\(.*curl", "substitution commande avec curl — vérifier l'URL"),
    (r"git\s+push\s+.*main", "push vers main — confirmer que c'est intentionnel"),
    (r"drop\s+table\s+IF\s+EXISTS", "DROP TABLE IF EXISTS — opération destructive"),
]

# Whitelist de commandes TOUJOURS autorisées (tests, builds, lectures)
SAFE_PREFIXES = [
    "pytest",
    "npm test",
    "npm run test",
    "cargo test",
    "go test",
    "jest",
    "vitest",
    "playwright",
    "ls ",
    "ls\n",
    "cat ",
    "head ",
    "tail ",
    "grep ",
    "find ",
    "echo ",
    "pwd",
    "env",
    "which ",
    "python --version",
    "node --version",
    "git status",
    "git log",
    "git diff",
    "git show",
    "git branch",
    "docker ps",
    "docker logs",
    "pip list",
    "pip show",
]

# Opérateurs de chaînage / substitution shell qui invalident le short-circuit whitelist.
# Présents → on ne blanchit pas sur le préfixe, on passe par les checks bloquants.
_CHAIN_OPERATORS = re.compile(r"[;|&`\n]|\$\(|\|\||&&|>")


def validate_command(command: str, session_id: str | None = None) -> ValidationResult:
    """
    Valide une commande bash.
    Retourne ValidationResult avec allowed=False si bloqué.
    """
    if not command or not command.strip():
        return ValidationResult(allowed=True, risk_level="safe", reason="commande vide")

    cmd = command.strip()

    # Whitelist — toujours safe, MAIS seulement pour une commande simple.
    # Une commande chaînée (`;`, `&&`, `||`, `|`, backtick, `$(`, redirection, retour
    # ligne) ne doit PAS être blanchie par son préfixe : `ls /tmp; rm -rf /` doit
    # tomber dans les checks bloquants (bug M3.4). Les chaînes bénignes retombent
    # sur "validée" (safe) plus bas de toute façon.
    if not _CHAIN_OPERATORS.search(cmd):
        for prefix in SAFE_PREFIXES:
            if cmd.startswith(prefix):
                return ValidationResult(allowed=True, risk_level="safe", reason=f"whitelisté: {prefix}")

    # Check patterns bloqués
    for pattern, reason in BLOCKED_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            logger.warning(f"Command BLOCKED [{session_id}]: {reason} | cmd: {cmd[:100]}")
            return ValidationResult(allowed=False, risk_level="blocked", reason=reason)

    # Check patterns warning
    warnings = []
    for pattern, reason in WARNING_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            warnings.append(reason)

    if warnings:
        logger.info(f"Command WARNING [{session_id}]: {'; '.join(warnings)}")
        return ValidationResult(
            allowed=True,  # Warning = autorisé mais loggué
            risk_level="warning",
            reason="; ".join(warnings),
        )

    return ValidationResult(allowed=True, risk_level="safe", reason="validée")


def validate_and_log(command: str, session_id: str | None = None) -> tuple[bool, str]:
    """
    Raccourci : valide + log. Retourne (allowed, reason).
    Usage dans builtin_actions.py :
        ok, reason = validate_and_log(command, session_id)
        if not ok: return {"error": f"🛡️ SANDBOX: {reason}"}
    """
    result = validate_command(command, session_id)
    return result.allowed, result.reason
