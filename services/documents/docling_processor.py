"""Docling-powered PDF → Markdown conversion with table extraction.

Requires the optional ``docling`` dependency (MIT, IBM).  When docling is
not installed or the ``ODYSSEUS_DOCLING`` kill-switch is off, callers
should fall back to ``src.document_processor._process_pdf`` (pypdf).

Public API
----------
- ``DoclingProcessor.pdf_to_markdown(file_path)`` → clean Markdown
- ``DoclingProcessor.extract_tables(file_path)``  → list of table dicts
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class DoclingProcessor:
    """Thin wrapper around Docling's ``DocumentConverter``.

    Instantiate once and reuse — ``DocumentConverter`` caches models.
    All public methods are **sync** because Docling's converter is
    synchronous internally; the async signatures in the original spec
    are kept for forward-compat if Docling adds an async API later.
    """

    def __init__(self) -> None:
        from src.docling_runtime import load_docling_converter

        self._converter = load_docling_converter()
        self._available = self._converter is not None

    @property
    def available(self) -> bool:
        """True if the converter loaded successfully."""
        return self._available

    # ------------------------------------------------------------------
    # pdf_to_markdown
    # ------------------------------------------------------------------
    def pdf_to_markdown(self, file_path: str) -> str | None:
        """Convert a PDF to Markdown preserving tables, layout, headings.

        Returns the Markdown string, or ``None`` if docling is unavailable
        or the conversion fails.
        """
        if not self._available:
            return None
        if not file_path or not os.path.isfile(file_path):
            logger.warning("Docling: file not found: %s", file_path)
            return None
        try:
            result = self._converter.convert(file_path)
            markdown = getattr(result, "document", None)
            if markdown is None:
                # Older docling versions return the result directly
                markdown = getattr(result, "markdown", None) or str(result)
            # DocumentConverter returns a DoclingDocument; call export
            # to get a Markdown string.
            if hasattr(markdown, "export_to_markdown"):
                return markdown.export_to_markdown()
            if hasattr(markdown, "export"):
                return markdown.export(to_format="md")
            # Fallback: string representation
            text = str(markdown).strip()
            return text if text else None
        except Exception as exc:
            logger.warning("Docling PDF conversion failed for %s: %s", file_path, exc)
            return None

    # ------------------------------------------------------------------
    # extract_tables
    # ------------------------------------------------------------------
    def extract_tables(self, file_path: str) -> list[dict[str, Any]]:
        """Extract tables from a PDF as a list of structured dicts.

        Each dict has keys:
            - ``page`` (int): 1-based page number
            - ``caption`` (str|None): table caption if detected
            - ``headers`` (list[str]): column headers
            - ``rows`` (list[list[str]]): data rows

        Returns an empty list when docling is unavailable or no tables
        are found.
        """
        if not self._available:
            return []
        if not file_path or not os.path.isfile(file_path):
            return []
        try:
            result = self._converter.convert(file_path)
            doc = getattr(result, "document", result)
            tables: list[dict[str, Any]] = []
            # DoclingDocument exposes tables via the dataaccessor
            if hasattr(doc, "tables"):
                for tbl in doc.tables:
                    table_dict: dict[str, Any] = {
                        "page": getattr(tbl, "page", 0),
                        "caption": getattr(tbl, "caption", None),
                        "headers": [],
                        "rows": [],
                    }
                    # Extract header row
                    if hasattr(tbl, "export_to_dataframe"):
                        try:
                            df = tbl.export_to_dataframe()
                            table_dict["headers"] = list(df.columns.astype(str))
                            table_dict["rows"] = [[str(c) for c in row] for row in df.values.tolist()]
                        except Exception:
                            pass
                    tables.append(table_dict)
            return tables
        except Exception as exc:
            logger.warning("Docling table extraction failed for %s: %s", file_path, exc)
            return []


# Module-level singleton (lightweight; converter loads models lazily).
_default_processor: DoclingProcessor | None = None


def get_docling_processor() -> DoclingProcessor:
    """Return (and cache) the module-level ``DoclingProcessor``."""
    global _default_processor
    if _default_processor is None:
        _default_processor = DoclingProcessor()
    return _default_processor
