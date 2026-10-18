#!/usr/bin/env python3
"""CSS refactor pipeline for Odysseus — 1.22MB → target <200KB.

Strategy:
1. Extract :root variables → static/css/tokens.css (shared, always loaded)
2. Strip comments + collapse whitespace → static/css/style.min.css (served)
3. Optional: purge unused CSS with browser coverage data

Phase 1 (this script): comment strip + whitespace collapse.
Phase 2 (future): purgecss against index.html + login.html.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_IN = ROOT / "static" / "style.css"
TOKENS_OUT = ROOT / "static" / "css" / "tokens.css"
MIN_OUT = ROOT / "static" / "css" / "style.min.css"
HTML_FILES = [
    ROOT / "static" / "index.html",
    ROOT / "static" / "login.html",
]


def extract_tokens(css: str) -> str:
    """Extract :root and :root.light blocks as tokens.css."""
    roots = []
    for match in re.finditer(r":root(\.[\w-]+)?\s*\{[^}]*\}", css, re.DOTALL):
        roots.append(match.group(0))
    return "\n\n".join(roots) + "\n"


def strip_comments(css: str) -> str:
    """Remove CSS comments (/* ... */)."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def collapse_whitespace(css: str) -> str:
    """Collapse multiple spaces/newlines, keep single selectors per line."""
    # Remove leading/trailing whitespace per line
    lines = []
    for line in css.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
    result = "\n".join(lines)
    # Collapse multiple blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)
    # Collapse spaces around braces
    result = re.sub(r"\s*\{\s*", " { ", result)
    result = re.sub(r"\s*\}\s*", " }\n", result)
    # Collapse spaces around colon/semicolon
    result = re.sub(r":\s+", ": ", result)
    result = re.sub(r";\s+", "; ", result)
    return result


def extract_selectors_used_in_html(html_files: list[Path]) -> set[str]:
    """Quick scan: find class names and IDs referenced in HTML files."""
    used = set()
    for hf in html_files:
        if not hf.exists():
            continue
        html = hf.read_text(encoding="utf-8", errors="ignore")
        # class="..."
        for m in re.finditer(r'class=["\']([^"\']+)["\']', html):
            for cls in m.group(1).split():
                used.add(f".{cls}")
        # id="..."
        for m in re.finditer(r'id=["\']([^"\']+)["\']', html):
            used.add(f"#{m.group(1)}")
    return used


def main():
    css = CSS_IN.read_text(encoding="utf-8")

    # 1. Extract tokens
    tokens = extract_tokens(css)
    Path(TOKENS_OUT.parent).mkdir(parents=True, exist_ok=True)
    TOKENS_OUT.write_text(tokens, encoding="utf-8")
    print(f"[tokens] {TOKENS_OUT} ({len(tokens)} bytes)")

    # 2. Strip comments + collapse
    cleaned = strip_comments(css)
    collapsed = collapse_whitespace(cleaned)

    # 3. Write minified
    MIN_OUT.write_text(collapsed, encoding="utf-8")
    size_before = CSS_IN.stat().st_size
    size_after = MIN_OUT.stat().st_size
    reduction = (1 - size_after / size_before) * 100
    print(f"[minify] {MIN_OUT}")
    print(f"  Before: {size_before:,} bytes ({CSS_IN.stat().st_size / 1024:.0f} KB)")
    print(f"  After:  {size_after:,} bytes ({size_after / 1024:.0f} KB)")
    print(f"  Reduction: {reduction:.1f}%")

    # 4. Quick HTML selector scan
    used = extract_selectors_used_in_html(HTML_FILES)
    print(f"[purge-scan] Found {len(used)} class/ID references in HTML files")

    # 5. Estimate: count CSS rules
    rule_count = len(re.findall(r"\{[^}]*\}", cleaned))
    print(f"[stats] ~{rule_count} CSS rule blocks in cleaned file")

    if size_after > 200 * 1024:
        print(f"\n[warning] Still {size_after / 1024:.0f} KB — target is 200 KB.")
        print("  Next: run purgecss or similar to remove unused selectors.")
        print(f"  {len(used)} selectors found in HTML — many CSS rules may be dead.")
    else:
        print("\n[success] Under 200 KB target!")


if __name__ == "__main__":
    main()
