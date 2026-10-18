"""Tests for the Docling document processing integration.

Covers:
- kill-switch gating (ODYSSEUS_DOCLING)
- DoclingProcessor availability / fallback
- _process_pdf Docling fast-path vs pypdf fallback
- import-pdf format=markdown route
- No regression when docling is not installed
"""

import os
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# 1. Kill-switch gating
# ---------------------------------------------------------------------------


class TestDoclingKillSwitch:
    """is_docling_enabled() respects ODYSSEUS_DOCLING env var."""

    def test_default_off(self):
        """Unset env → disabled."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ODYSSEUS_DOCLING", None)
            from src.docling_runtime import is_docling_enabled

            assert is_docling_enabled() is False

    def test_on_values(self):
        """'on', '1', 'true', 'yes' → enabled."""
        from src.docling_runtime import is_docling_enabled

        for val in ("on", "1", "true", "yes", "ON", "True"):
            with patch.dict(os.environ, {"ODYSSEUS_DOCLING": val}):
                assert is_docling_enabled() is True, f"Expected True for {val!r}"

    def test_off_values(self):
        """'off', '0', 'false', '', random → disabled."""
        from src.docling_runtime import is_docling_enabled

        for val in ("off", "0", "false", "", "no", "garbage"):
            with patch.dict(os.environ, {"ODYSSEUS_DOCLING": val}):
                assert is_docling_enabled() is False, f"Expected False for {val!r}"


# ---------------------------------------------------------------------------
# 2. DoclingProcessor availability
# ---------------------------------------------------------------------------


class TestDoclingProcessor:
    """DoclingProcessor graceful degradation."""

    def test_unavailable_when_docling_not_installed(self):
        """If docling import fails → available=False, no crash."""
        import services.documents.docling_processor as mod

        # Reset singleton
        mod._default_processor = None
        with patch.dict(os.environ, {"ODYSSEUS_DOCLING": "on"}):
            with patch("src.docling_runtime.load_docling_converter", return_value=None):
                proc = mod.DoclingProcessor()
                assert proc.available is False
                assert proc.pdf_to_markdown("/nonexistent.pdf") is None
                assert proc.extract_tables("/nonexistent.pdf") == []

    def test_available_when_converter_loads(self):
        """If converter loads → available=True."""
        import services.documents.docling_processor as mod

        mod._default_processor = None
        fake_converter = MagicMock()
        with patch("src.docling_runtime.load_docling_converter", return_value=fake_converter):
            proc = mod.DoclingProcessor()
            assert proc.available is True

    def test_singleton_getter(self):
        """get_docling_processor() caches."""
        import services.documents.docling_processor as mod

        mod._default_processor = None
        fake_converter = MagicMock()
        with patch("src.docling_runtime.load_docling_converter", return_value=fake_converter):
            p1 = mod.get_docling_processor()
            p2 = mod.get_docling_processor()
            assert p1 is p2


# ---------------------------------------------------------------------------
# 3. _process_pdf Docling fast-path vs pypdf fallback
# ---------------------------------------------------------------------------


class TestProcessPdfDocling:
    """_process_pdf tries docling first, falls back to pypdf."""

    def test_fallback_when_killswitch_off(self):
        """Kill-switch off → pypdf path used (no docling attempt)."""
        from src.document_processor import _process_pdf

        # When ODYSSEUS_DOCLING is not set, docling_md stays None
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ODYSSEUS_DOCLING", None)
            # Mock pypdf (the module _process_pdf imports locally) to avoid
            # needing a real PDF file.
            fake_reader = MagicMock()
            fake_page = MagicMock()
            fake_page.extract_text.return_value = "Hello from pypdf"
            fake_page.images = []
            fake_reader.pages = [fake_page]
            with patch("pypdf.PdfReader", return_value=fake_reader) as mock_reader:
                result = _process_pdf("/fake/test.pdf")
        assert mock_reader.called
        assert "Hello from pypdf" in result
        assert "Docling Markdown" not in result

    def test_docling_path_used_when_enabled(self):
        """When kill-switch on and docling returns markdown → Docling Markdown marker."""
        from src.document_processor import _process_pdf

        with patch.dict(os.environ, {"ODYSSEUS_DOCLING": "on"}):
            with patch("src.docling_runtime.is_docling_enabled", return_value=True):
                with patch("services.documents.docling_processor.get_docling_processor") as mock_get:
                    mock_proc = MagicMock()
                    mock_proc.available = True
                    mock_proc.pdf_to_markdown.return_value = "# Table\n| A | B |\n|---|---|\n| 1 | 2 |"
                    mock_get.return_value = mock_proc
                    result = _process_pdf("/fake/test.pdf")
                    assert "[PDF content — Docling Markdown]" in result
                    assert "# Table" in result
                    assert "| A | B |" in result

    def test_docling_fallback_on_failure(self):
        """When docling returns None → pypdf path."""
        from src.document_processor import _process_pdf

        with patch.dict(os.environ, {"ODYSSEUS_DOCLING": "on"}):
            with patch("src.docling_runtime.is_docling_enabled", return_value=True):
                with patch("services.documents.docling_processor.get_docling_processor") as mock_get:
                    mock_proc = MagicMock()
                    mock_proc.available = True
                    mock_proc.pdf_to_markdown.return_value = None  # Docling failed
                    mock_get.return_value = mock_proc
                    # pypdf path: mock the reader (module imported locally)
                    fake_reader = MagicMock()
                    fake_page = MagicMock()
                    fake_page.extract_text.return_value = "fallback text"
                    fake_page.images = []
                    fake_reader.pages = [fake_page]
                    with patch("pypdf.PdfReader", return_value=fake_reader) as mock_reader:
                        result = _process_pdf("/fake/test.pdf")
                        # Should NOT contain Docling marker
                        assert "Docling Markdown" not in result
                        assert mock_reader.called


# ---------------------------------------------------------------------------
# 4. _CATEGORY_ORDER includes Document Processing
# ---------------------------------------------------------------------------


class TestKillswitchRegistry:
    """Kill-switch registry has the Docling entry."""

    def test_docling_switch_registered(self):
        from src.killswitch_registry import read_states

        states = read_states()
        env_vars = {s["env_var"] for s in states}
        assert "ODYSSEUS_DOCLING" in env_vars

    def test_category_order_includes_doc_processing(self):
        from src.killswitch_registry import categories

        cats = categories()
        assert "Document Processing" in cats


# ---------------------------------------------------------------------------
# 5. services/documents package structure
# ---------------------------------------------------------------------------


class TestPackageStructure:
    """Verify required files exist."""

    def test_docling_runtime_exists(self):
        assert os.path.isfile(os.path.join("src", "docling_runtime.py"))

    def test_docling_processor_exists(self):
        assert os.path.isfile(os.path.join("services", "documents", "docling_processor.py"))

    def test_services_documents_init_exists(self):
        assert os.path.isfile(os.path.join("services", "documents", "__init__.py"))

    def test_docling_in_optional_requirements(self):
        with open("requirements-optional.txt") as f:
            content = f.read()
        assert "docling" in content


# ---------------------------------------------------------------------------
# 6. strip_pdf_content_marker unchanged
# ---------------------------------------------------------------------------


class TestStripPdfContentMarker:
    """Existing strip_pdf_content_marker behavior preserved."""

    def test_removes_marker(self):
        from src.document_processor import strip_pdf_content_marker

        text = "\n\n[PDF content]:\n\n[Page 1 text]:\nHello world"
        result = strip_pdf_content_marker(text)
        assert result == "[Page 1 text]:\nHello world"

    def test_none_safe(self):
        from src.document_processor import strip_pdf_content_marker

        assert strip_pdf_content_marker(None) == ""

    def test_empty_safe(self):
        from src.document_processor import strip_pdf_content_marker

        assert strip_pdf_content_marker("") == ""
