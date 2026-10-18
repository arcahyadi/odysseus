"""Helpers for the optional Docling document-processing dependency.

Docling (MIT, IBM) converts PDFs to Markdown with layout awareness, table
extraction, multi-column reading order, and heading detection. It is
**optional**: install with ``pip install -r requirements-optional.txt``.
When absent, callers degrade gracefully to pypdf — the MIT core never
hard-depends on it.

Mirrors the lazy-import pattern in ``src/markitdown_runtime.py``.
"""

import logging
import os

logger = logging.getLogger(__name__)

DOCLING_MISSING = (
    "Advanced PDF extraction requires docling. Install optional "
    "dependencies with `pip install -r requirements-optional.txt`. "
    "Falling back to pypdf."
)


def is_docling_enabled() -> bool:
    """Return True if Docling processing is allowed by the kill-switch.

    ODYSSEUS_DOCLING=off (or unset) → False  (use pypdf)
    ODYSSEUS_DOCLING=on              → True   (use Docling)
    """
    val = os.environ.get("ODYSSEUS_DOCLING", "").strip().lower()
    if not val:
        return False
    return val in ("on", "1", "true", "yes")


def load_docling_converter():
    """Return a Docling ``DocumentConverter`` instance, or *None* on failure.

    This never raises — callers should check for *None* and fall back
    to the pypdf path.
    """
    if not is_docling_enabled():
        return None
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        logger.info("Docling DocumentConverter loaded successfully")
        return converter
    except ImportError:
        logger.warning(DOCLING_MISSING)
        return None
    except Exception as exc:
        logger.warning("Docling init failed: %s", exc)
        return None
