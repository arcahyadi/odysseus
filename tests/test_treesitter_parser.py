"""Smoke test for Tree-sitter service.

Run with:
    ODYSSEUS_TREESITTER=on python -m pytest tests/test_treesitter_parser.py -v

Requires: tree-sitter tree-sitter-python (pip install tree-sitter tree-sitter-python)
"""

from __future__ import annotations

import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _enable():
    os.environ["ODYSSEUS_TREESITTER"] = "on"


def _disable():
    os.environ.pop("ODYSSEUS_TREESITTER", None)


class TestKillSwitch:
    def test_off_by_default(self):
        _disable()
        from services.code.treesitter_parser import TreeSitterService

        assert TreeSitterService.parse_file("app.py") is None
        assert TreeSitterService.find_functions("app.py") is None
        assert TreeSitterService.extract_symbols("app.py") is None
        assert TreeSitterService.syntax_diff("a", "b") is None

    def test_on_with_valid_file(self):
        _enable()
        try:
            from services.code.treesitter_parser import TreeSitterService

            result = TreeSitterService.parse_file("app.py")
            # Should succeed if tree-sitter is installed
            if result is not None:
                assert "type" in result
                assert "children" in result
        finally:
            _disable()


class TestParseFile:
    def test_parse_app_py(self):
        _enable()
        try:
            from services.code.treesitter_parser import TreeSitterService

            result = TreeSitterService.parse_file("app.py")
            if result is None:
                # tree-sitter not installed — skip gracefully
                return
            assert result["type"] == "module"
            # app.py has top-level definitions
            assert len(result.get("children", [])) > 10
        finally:
            _disable()

    def test_parse_nonexistent(self):
        _enable()
        try:
            from services.code.treesitter_parser import TreeSitterService

            result = TreeSitterService.parse_file("nonexistent_xyz.py")
            assert result is None
        finally:
            _disable()


class TestFindFunctions:
    def test_app_py_functions(self):
        _enable()
        try:
            from services.code.treesitter_parser import TreeSitterService

            funcs = TreeSitterService.find_functions("app.py")
            if funcs is None:
                return  # tree-sitter not installed
            names = [f["name"] for f in funcs]
            # app.py defines register_static_mime_types and async route handlers
            assert "register_static_mime_types" in names
            # All should have valid line numbers
            for f in funcs:
                assert f["line"] > 0
                assert f["end_line"] >= f["line"]
                assert f["kind"] in ("function", "method")
        finally:
            _disable()


class TestExtractSymbols:
    def test_app_py_symbols(self):
        _enable()
        try:
            from services.code.treesitter_parser import TreeSitterService

            syms = TreeSitterService.extract_symbols("app.py")
            if syms is None:
                return
            names = [s["name"] for s in syms]
            kinds = [s["kind"] for s in syms]
            assert "register_static_mime_types" in names
            assert "function" in kinds
        finally:
            _disable()


class TestSyntaxDiff:
    def test_changed_function(self):
        _enable()
        try:
            from services.code.treesitter_parser import TreeSitterService

            old = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
            new = "def foo():\n    return 1\n\ndef bar():\n    return 3\n"
            diff = TreeSitterService.syntax_diff(old, new)
            if diff is None:
                return
            # bar changed line numbers due to body change
            changed_names = [c["name"] for c in diff["changed"]]
            assert "bar" in changed_names
            assert diff["added"] == []
            assert diff["removed"] == []
        finally:
            _disable()

    def test_added_function(self):
        _enable()
        try:
            from services.code.treesitter_parser import TreeSitterService

            old = "def foo():\n    return 1\n"
            new = "def foo():\n    return 1\n\ndef baz():\n    return 42\n"
            diff = TreeSitterService.syntax_diff(old, new)
            if diff is None:
                return
            added_names = [a["name"] for a in diff["added"]]
            assert "baz" in added_names
        finally:
            _disable()

    def test_removed_function(self):
        _enable()
        try:
            from services.code.treesitter_parser import TreeSitterService

            old = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
            new = "def foo():\n    return 1\n"
            diff = TreeSitterService.syntax_diff(old, new)
            if diff is None:
                return
            removed_names = [r["name"] for r in diff["removed"]]
            assert "bar" in removed_names
        finally:
            _disable()


class TestFindCallers:
    def test_find_callers(self):
        _enable()
        try:
            # Create a temp file to test caller finding
            import tempfile

            from services.code.treesitter_parser import TreeSitterService

            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write("def helper():\n    pass\n\ndef main():\n    helper()\n    helper()\n")
                tmp = f.name
            try:
                callers = TreeSitterService.find_callers(tmp, "helper")
                if callers is None:
                    return
                assert len(callers) == 2
                assert callers[0]["line"] == 5  # first call
                assert callers[1]["line"] == 6  # second call
            finally:
                os.unlink(tmp)
        finally:
            _disable()
