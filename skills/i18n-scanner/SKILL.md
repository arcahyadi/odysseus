---
name: i18n-scanner
description: Detects hardcoded strings in code and HTML templates — flags missing i18n coverage. Integrated into QUALITY phase.
category: quality
tags: [i18n, internationalization, l10n, audit]
platforms: [web, python, javascript]
when_to_use: "Before any release, after adding new UI, or when adding a new language"
procedure:
  - Scan all .py, .ts, .js, .html files for hardcoded user-visible strings
  - Exclude: code comments, variable names, log messages, test files
  - Flag strings that should be wrapped in i18n function (gettext, i18n.t, etc.)
  - Generate report by file with string + line number
  - Fail build if > 10 new hardcoded strings found
verification:
  - Report shows 0 un-translated UI strings
  - All user-visible text uses i18n wrapper
confidence: 0.85
---

## What it does
Scans the codebase for hardcoded user-visible strings that should be internationalized.

## Integration point
- **Phase:** QUALITY
- **Trigger:** After BUILD completes
- **Event:** `i18n_scan_start`, `i18n_scan_result`

## Detection patterns
| Language | Pattern detected |
|----------|-----------------|
| Python | `"text"`, `'text'` in print(), return, HTML templates |
| JavaScript/TS | String literals in JSX, innerHTML, textContent |
| HTML | Text nodes between tags, placeholder attributes |
| CSS | `content:` properties with readable text |

## Exclusions (not flagged)
- Variable names, function names
- Code comments
- Log/debug messages
- Test assertions
- Regex patterns
- URLs and file paths

## Report format
```json
{
  "file": "static/index.html",
  "line": 42,
  "string": "Welcome to Agent OS",
  "suggestion": "{{ 'welcome' | i18n }}"
}
```
