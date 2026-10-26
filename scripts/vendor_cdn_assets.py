"""One-shot KaTeX / Mermaid / docs-avatar vendoring script.

Run from the repo root:

    python scripts/vendor_cdn_assets.py

Idempotent — re-fetches each pinned version even if present. Downloads:

- KaTeX 0.16.22 (css + js + fonts)   -> static/lib/katex/
- Mermaid 11                         -> static/lib/mermaid/mermaid.min.js
- docs/index.html testimonial avatars -> docs/assets/

After running, static/index.html and docs/index.html must be edited to
reference the local paths, and core/middleware.py's CSP allow-list must
drop jsdelivr.
"""
from __future__ import annotations

import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KATEX_VER = "0.16.22"
KATEX_BASE = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VER}/dist"
MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"

DOCS_AVATARS = [
    (
        "https://cdn.prod.website-files.com/66708f90d7e407423093fa76/66708f91d7e407423093fd21_john-carter-testimonial-image-dentistry-x-webflow-template.png",
        "docs/assets/coder-guy.png",
    ),
    (
        "https://images.pexels.com/photos/5876695/pexels-photo-5876695.jpeg?auto=compress&cs=tinysrgb&w=160&h=160&fit=crop",
        "docs/assets/corporate-woman.jpg",
    ),
]

UA = "Mozilla/5.0 (Odysseus-vendor)"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"  wrote {path.relative_to(ROOT)}  ({len(data):,} bytes)")


def vendor_katex() -> None:
    print("KaTeX:")
    css = fetch(f"{KATEX_BASE}/katex.min.css")
    write(ROOT / "static/lib/katex/katex.min.css", css)
    write(ROOT / "static/lib/katex/katex.min.js", fetch(f"{KATEX_BASE}/katex.min.js"))

    # Everything after `url(fonts/…)` in the CSS is a font file we need.
    font_paths = sorted(set(re.findall(r"url\((fonts/[^)?#]+)", css.decode("utf-8"))))
    for fp in font_paths:
        write(ROOT / "static/lib/katex" / fp, fetch(f"{KATEX_BASE}/{fp}"))
    print(f"  fonts: {len(font_paths)}")


def vendor_mermaid() -> None:
    print("Mermaid:")
    write(ROOT / "static/lib/mermaid/mermaid.min.js", fetch(MERMAID_URL))


def vendor_docs_avatars() -> None:
    print("Docs avatars:")
    for url, rel in DOCS_AVATARS:
        try:
            write(ROOT / rel, fetch(url))
        except urllib.error.HTTPError as e:
            print(f"  !! {url} -> HTTP {e.code} (skipping; edit docs/index.html by hand)")


def main() -> int:
    vendor_katex()
    vendor_mermaid()
    vendor_docs_avatars()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
