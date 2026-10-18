---
name: pa11y-accessibility
description: WCAG 2.1 AA accessibility scanner — audits HTML for a11y violations. Integrated into QUALITY phase.
category: quality
tags: [accessibility, wcag, a11y, audit]
platforms: [web]
when_to_use: "After any UI change, before release, or when user asks 'is this accessible?'"
procedure:
  - Run pa11y on the target URL
  - Parse violations (error, warning, notice)
  - Generate report sorted by severity
  - Fail build if errors found (WCAG AA non-compliant)
  - Suggest fixes for each violation
verification:
  - All WCAG 2.1 AA criteria passing
  - Zero error-level violations
  - Report visible in QUALITY phase output
confidence: 0.9
---

## What it does
Scans any URL or HTML file for WCAG 2.1 AA accessibility violations using pa11y.

## Integration point
- **Phase:** QUALITY
- **Trigger:** Automatic after BUILD completes, before AUTOEVAL
- **Event:** `accessibility_audit_start`, `accessibility_audit_result`

## Usage
```bash
# Via MCP server (Docker)
mcp__pa11y__audit --url http://localhost:7000
mcp__pa11y__audit --file static/index.html
```

## Severity levels
| Level | Action |
|-------|--------|
| Error | WCAG violation → BLOCK release |
| Warning | Potential issue → WARN in report |
| Notice | Best practice → INFO only |

## Common violations detected
- Missing alt text on images
- Low color contrast (< 4.5:1 for normal text)
- Missing form labels
- Empty buttons/links
- Missing document language
- Keyboard trap (tabindex issues)
- ARIA misuse
