"""
agentseal_runner.py — AgentSeal injection vulnerability probe.

Scans agent prompts and outputs for prompt-injection signatures, SQL
injection patterns, and dangerous command shell metacharacters.

Kill-switch: ODYSSEUS_AGENTSEAL=on
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any
from src.app_context import app_context


logger = logging.getLogger(__name__)

# Core injection patterns (modelled after OWASP + prompt-injection taxonomies)
_INJECTION_PATTERNS = [
    # Prompt-injection / instruction override
    (
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)", re.IGNORECASE),
        "prompt_override",
    ),
    (re.compile(r"you\s+are\s+now\s+(DAN|GPT|acting\s+as)", re.IGNORECASE), "role_hijack"),
    (re.compile(r"system\s*(prompt|message|instruction)", re.IGNORECASE), "system_leak"),
    (re.compile(r"<\|im_start\|>|<\|im_end\|>", re.IGNORECASE), "token_injection"),
    (re.compile(r"```\s*(system|instruction|output_format)\s*\n", re.IGNORECASE), "fenced_injection"),
    # SQL injection
    (
        re.compile(
            r"(\bUNION\b.*\bSELECT\b|\bSELECT\b.*\bFROM\b.*\bWHERE\b.*--|\bINSERT\b.*\bINTO\b.*\bVALUES\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        "sql_injection",
    ),
    (re.compile(r"'?\s*;\s*(DROP|DELETE|UPDATE|ALTER)\s+", re.IGNORECASE), "sql_destructive"),
    # Shell injection
    (re.compile(r"[;&|`$]\s*(wget|curl|nc|bash|sh|powershell|cmd|python|perl|ruby)", re.IGNORECASE), "shell_command"),
    (re.compile(r"\$\(|`[^`]`|\$\{[^}]+\}", re.IGNORECASE), "shell_expansion"),
    # Path traversal
    (re.compile(r"\.\.\/\.\.\/|\.\.\\\.\.\\", re.IGNORECASE), "path_traversal"),
    # Data exfiltration
    (
        re.compile(r"(send|upload|post|forward).*(api|secret|token|password|key|credential)", re.IGNORECASE),
        "data_exfil",
    ),
    # Encoded payloads
    (re.compile(r"(base64_decode|atob|fromCharCode|eval\s*\(|Function\s*\()", re.IGNORECASE), "encoded_payload"),
]


@dataclass
class SealFinding:
    pattern_type: str
    matched_text: str
    severity: str = "medium"


@dataclass
class AuditReport:
    session_id: str
    prompts_scanned: int = 0
    outputs_scanned: int = 0
    findings: list[SealFinding] = field(default_factory=list)
    risk_level: str = "low"
    summary: str = ""

    def __post_init__(self):
        severities = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        if self.findings:
            worst = max(severities.get(f.severity, 0) for f in self.findings)
            self.risk_level = {v: k for k, v in severities.items()}.get(worst, "low")
        self.summary = (
            f"Audit complete: {len(self.findings)} finding(s), "
            f"risk={self.risk_level}, "
            f"prompts={self.prompts_scanned}, outputs={self.outputs_scanned}"
        )


def _agentseal_enabled() -> bool:
    return os.getenv("ODYSSEUS_AGENTSEAL", "").strip().lower() in ("1", "true", "yes", "on")


def _scan_text(text: str, source: str = "text") -> list[SealFinding]:
    findings = []
    for pattern, ptype in _INJECTION_PATTERNS:
        for match in pattern.finditer(text):
            severity = "medium"
            if ptype in ("sql_destructive", "shell_command", "token_injection", "path_traversal"):
                severity = "high"
            elif ptype in ("prompt_override", "role_hijack", "system_leak"):
                severity = "medium"
            elif ptype in ("data_exfil", "encoded_payload"):
                severity = "critical"
            findings.append(
                SealFinding(
                    pattern_type=ptype,
                    matched_text=match.group(0)[:200],
                    severity=severity,
                )
            )
    return findings


class AgentSealRunner:
    """Scans agent inputs and outputs for injection vulnerabilities."""

    def __init__(self):
        self._session_store: dict[str, AuditReport] = {}
        self._enabled = _agentseal_enabled()
        if not self._enabled:
            logger.info("AgentSeal is disabled (ODYSSEUS_AGENTSEAL not on)")

    def scan_prompt(self, text: str, session_id: str | None = None) -> list[dict[str, Any]]:
        """Scan a user prompt for injection signatures.

        Args:
            text: The prompt to scan.
            session_id: Optional session for audit tracking.

        Returns:
            List of finding dicts with keys: pattern_type, matched_text, severity.
        """
        if not self._enabled:
            return []
        findings = _scan_text(text, source="prompt")
        if session_id and findings:
            report = self._session_store.setdefault(session_id, AuditReport(session_id=session_id))
            report.prompts_scanned += 1
            report.findings.extend(findings)
        logger.info("AgentSeal scanned prompt: %d findings", len(findings))
        return [
            {"pattern_type": f.pattern_type, "matched_text": f.matched_text, "severity": f.severity} for f in findings
        ]

    def scan_output(self, text: str, session_id: str | None = None) -> list[dict[str, Any]]:
        """Scan an agent output for injection or exfiltration signatures.

        Args:
            text: The output text to scan.
            session_id: Optional session for audit tracking.

        Returns:
            List of finding dicts with keys: pattern_type, matched_text, severity.
        """
        if not self._enabled:
            return []
        findings = _scan_text(text, source="output")
        if session_id and findings:
            report = self._session_store.setdefault(session_id, AuditReport(session_id=session_id))
            report.outputs_scanned += 1
            report.findings.extend(findings)
        logger.info("AgentSeal scanned output: %d findings", len(findings))
        return [
            {"pattern_type": f.pattern_type, "matched_text": f.matched_text, "severity": f.severity} for f in findings
        ]

    def audit_session(self, session_id: str) -> dict[str, Any]:
        """Generate an audit report for an entire session.

        Args:
            session_id: The session identifier.

        Returns:
            Dict with keys: session_id, prompts_scanned, outputs_scanned,
            findings, risk_level, summary.
        """
        if not self._enabled:
            return {
                "session_id": session_id,
                "enabled": False,
                "prompts_scanned": 0,
                "outputs_scanned": 0,
                "findings": [],
                "risk_level": "low",
                "summary": "AgentSeal disabled",
            }
        report = self._session_store.get(session_id)
        if not report:
            return {
                "session_id": session_id,
                "prompts_scanned": 0,
                "outputs_scanned": 0,
                "findings": [],
                "risk_level": "low",
                "summary": "No data recorded for this session.",
            }
        findings_serialized = [
            {"pattern_type": f.pattern_type, "matched_text": f.matched_text, "severity": f.severity}
            for f in report.findings
        ]
        return {
            "session_id": report.session_id,
            "prompts_scanned": report.prompts_scanned,
            "outputs_scanned": report.outputs_scanned,
            "findings": findings_serialized,
            "risk_level": report.risk_level,
            "summary": report.summary,
        }


app_context.caches.agentseal_instance: AgentSealRunner | None = None


def get_agentseal() -> AgentSealRunner:
    if app_context.caches.agentseal_instance is None:
        app_context.caches.agentseal_instance = AgentSealRunner()
    return app_context.caches.agentseal_instance
