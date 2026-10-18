"""i18n Scanner — detects hardcoded user-visible strings."""

import json
import os
import re
from pathlib import Path

# Patterns that indicate a string is user-visible (not code)
UI_PATTERNS = [
    (r'print\(["\']([^"\']{3,})["\']', "Python print()"),
    (r'return\s+["\']([^"\']{3,})["\']', "Python return string"),
    (r">\s*([A-Z][a-z].{2,50}?)\s*<", "HTML text node"),
    (r'placeholder=["\']([^"\']{2,})["\']', "HTML placeholder"),
    (r'alt=["\']([^"\']{2,})["\']', "HTML alt text"),
    (r'aria-label=["\']([^"\']{2,})["\']', "HTML aria-label"),
    (r'title=["\']([^"\']{3,})["\']', "HTML title"),
    (r'innerHTML\s*=\s*["\']([^"\']{3,})["\']', "JS innerHTML"),
    (r'textContent\s*=\s*["\']([^"\']{3,})["\']', "JS textContent"),
]

EXCLUDE_PATTERNS = [
    r"console\.(log|debug|warn|error)",
    r"logging\.",
    r"logger\.",
    r"#",
    r"//",
    r"pass",
    r"assert",
    r"url",
    r"http",
    r"api/",
]


def scan_file(filepath: Path) -> list:
    """Scan a file for hardcoded UI strings."""
    results = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except:
        return results

    for pattern, source_type in UI_PATTERNS:
        for match in re.finditer(pattern, content):
            string = match.group(1).strip()
            if len(string) < 3:
                continue
            # Check exclusions
            line_start = content.rfind("\n", 0, match.start()) + 1
            line_text = content[line_start : content.find("\n", match.start())]
            if any(re.search(p, line_text, re.IGNORECASE) for p in EXCLUDE_PATTERNS):
                continue
            # Skip if already using i18n
            if "i18n" in line_text.lower() or "gettext" in line_text.lower() or "_(" in line_text:
                continue

            line_num = content[: match.start()].count("\n") + 1
            results.append(
                {
                    "file": str(filepath),
                    "line": line_num,
                    "string": string[:100],
                    "source": source_type,
                    "suggestion": f"Replace with i18n call: _('{string[:50]}...')"
                    if len(string) > 50
                    else f"Replace with i18n call: _('{string}')",
                }
            )

    return results


def scan_directory(root: str = ".") -> dict:
    """Scan all relevant files in directory."""
    all_results = []
    extensions = {".py", ".html", ".js", ".ts", ".tsx", ".vue", ".jsx"}
    exclude_dirs = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build", "data", "logs"}

    root_path = Path(root)
    for filepath in root_path.rglob("*"):
        if any(excl in filepath.parts for excl in exclude_dirs):
            continue
        if filepath.suffix in extensions and filepath.is_file():
            results = scan_file(filepath)
            all_results.extend(results)

    return {
        "total_hardcoded": len(all_results),
        "files_affected": len(set(r["file"] for r in all_results)),
        "issues": all_results[:100],  # Cap at 100 for report size
        "recommendation": "Wrap all user-visible strings in i18n function",
        "status": "FAIL" if len(all_results) > 10 else "PASS",
    }


if __name__ == "__main__":
    import sys

    root = sys.argv[1] if len(sys.argv) > 1 else "."
    result = scan_directory(root)
    outfile = "data/i18n-report.json"
    os.makedirs("data", exist_ok=True)
    with open(outfile, "w") as f:
        json.dump(result, f, indent=2)
    print(f"i18n scan: {result['total_hardcoded']} hardcoded strings in {result['files_affected']} files")
    print(f"Report: {outfile}")
    print(f"Status: {result['status']}")
