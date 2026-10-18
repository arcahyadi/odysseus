# AgentSeal security probe configuration
# AgentSeal audits agent runtimes for injection vulnerabilities,
# MCP poisoning, and malicious skills. 300+ probes.
#
# Install: pip install agentseal
# Run:     agentseal probe --project . --output json
# CI:      agentseal probe --project . --ci --fail-on critical
#
# Kill-switch: ODYSSEUS_AGENTSEAL (default OFF).
# When "on", AgentSeal runs post-session in the MEMORY_OBSERVE phase.
# See: https://github.com/getagentseal/agentseal

# AgentSeal probes — OFF by default (requires pip install agentseal).
# When "on"/"1", the session-end loop runs agentseal probe --ci and feeds
# findings (severity, count) to the Observer and trace writer.
ODYSSEUS_AGENTSEAL=off
