"""Tree-sitter service — incremental syntax parsing for Odysseus agent tools.

Complements CBM (graph-level intelligence) with syntax-level precision:
AST extraction, symbol discovery, function signatures, call-site search,
and structural diffs.

Gated behind the ``ODYSSEUS_TREESITTER`` kill-switch (default OFF).
When OFF, all methods return ``None`` so callers fall back gracefully.

Languages supported: Python (initial).  Adding JS/Go/Rust/Bash is a
matter of wiring another ``tree-sitter-<lang>`` grammar.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

_TRUTHY = ("1", "true", "yes", "on")
_logger = logging.getLogger(__name__)


def _kill_switch_enabled() -> bool:
    """Return True when ODYSSEUS_TREESITTER env var is truthy."""
    raw = os.environ.get("ODYSSEUS_TREESITTER", "off")
    return str(raw).strip().lower() in _TRUTHY


def _try_import():
    """Lazy-import tree-sitter; return (Parser, Language) or (None, None)."""
    try:
        import tree_sitter_python as tspython
        from tree_sitter import Language, Parser

        return Parser, Language, tspython
    except ImportError:
        return None, None, None


# Singleton — created once, reused across calls.
_parser_cache: dict[str, Any] = {}
_available: bool | None = None


def _get_parser(ext: str = ".py"):
    """Get or create a tree-sitter parser for the given file extension."""
    global _available
    if _available is False:
        return None
    if ext in _parser_cache:
        return _parser_cache[ext]

    Parser, Language, tspython = _try_import()
    if Parser is None:
        _available = False
        _logger.warning("tree-sitter not installed — install tree-sitter tree-sitter-python")
        return None

    lang_map = {
        ".py": (tspython, "python"),
    }
    if ext not in lang_map:
        _logger.debug("tree-sitter: no grammar for %s", ext)
        return None

    mod, lang_name = lang_map[ext]
    try:
        lang = Language(mod.language())
        parser = Parser(lang)
        _parser_cache[ext] = parser
        _available = True
        return parser
    except Exception as exc:
        _available = False
        _logger.warning("tree-sitter init failed: %s", exc)
        return None


class TreeSitterService:
    """Facade for tree-sitter operations.

    Every public method is a no-op when the kill-switch is OFF or
    tree-sitter is not installed — callers simply get ``None``.
    """

    # ── public API ──────────────────────────────────────────────────

    @staticmethod
    def parse_file(filepath: str) -> dict[str, Any] | None:
        """Parse a source file and return its AST as a nested dict.

        Returns ``None`` when the kill-switch is OFF or the file cannot
        be parsed.
        """
        if not _kill_switch_enabled():
            return None
        path = Path(filepath)
        ext = path.suffix.lower()
        parser = _get_parser(ext)
        if parser is None:
            return None
        try:
            source = path.read_bytes()
        except (OSError, UnicodeDecodeError):
            return None
        try:
            tree = parser.parse(source)
        except Exception as exc:
            _logger.debug("tree-sitter parse error on %s: %s", filepath, exc)
            return None
        return _node_to_dict(tree.root_node, source, depth=0, max_depth=4)

    @staticmethod
    def find_functions(filepath: str) -> list[dict[str, Any]] | None:
        """Extract all function/method definitions with signatures.

        Returns a list of dicts: ``{name, line, end_line, params, kind}``.
        """
        if not _kill_switch_enabled():
            return None
        path = Path(filepath)
        ext = path.suffix.lower()
        parser = _get_parser(ext)
        if parser is None:
            return None
        try:
            source = path.read_bytes()
        except (OSError, UnicodeDecodeError):
            return None
        try:
            tree = parser.parse(source)
        except Exception:
            return None
        query = parser.language.query("(function_definition name: (identifier) @fn)" if ext == ".py" else "")
        if not query:
            # Fallback: walk the tree manually
            return _walk_functions_manual(tree.root_node, source)
        from tree_sitter import QueryCursor

        capture_groups = QueryCursor(query).captures(tree.root_node)
        results = []
        text = source.decode("utf-8", errors="replace")
        lines = text.split("\n")
        for node in capture_groups.get("fn", []):
            # Walk up to find the full function_definition node
            func_node = node
            while func_node and func_node.type != "function_definition":
                func_node = func_node.parent
            if func_node is None:
                func_node = node
            name = _node_text(node, source)
            start_line = func_node.start_point[0] + 1
            end_line = func_node.end_point[0] + 1
            # Extract parameters
            params_node = _find_child(func_node, "parameters")
            params = _node_text(params_node, source).strip("()") if params_node else ""
            # Check if it's a method (parent is class_definition)
            kind = "method" if func_node.parent and func_node.parent.type == "class_definition" else "function"
            results.append(
                {
                    "name": name,
                    "line": start_line,
                    "end_line": end_line,
                    "params": params,
                    "kind": kind,
                }
            )
        return results

    @staticmethod
    def find_callers(filepath: str, function_name: str) -> list[dict[str, Any]] | None:
        """Find all call sites of ``function_name`` in a file.

        Returns a list of dicts: ``{line, column, context}``.
        """
        if not _kill_switch_enabled():
            return None
        path = Path(filepath)
        ext = path.suffix.lower()
        parser = _get_parser(ext)
        if parser is None:
            return None
        try:
            source = path.read_bytes()
        except (OSError, UnicodeDecodeError):
            return None
        try:
            tree = parser.parse(source)
        except Exception:
            return None
        text = source.decode("utf-8", errors="replace")
        lines = text.split("\n")
        results = []
        if ext == ".py":
            query = parser.language.query(f"(call function: (identifier) @caller (#eq? @caller {function_name}))")
            from tree_sitter import QueryCursor

            capture_groups = QueryCursor(query).captures(tree.root_node)
            for node in capture_groups.get("caller", []):
                line_num = node.start_point[0] + 1
                col = node.start_point[1]
                context = lines[line_num - 1].strip() if line_num <= len(lines) else ""
                results.append(
                    {
                        "line": line_num,
                        "column": col,
                        "context": context,
                    }
                )
        return results

    @staticmethod
    def syntax_diff(old_code: str, new_code: str) -> dict[str, Any] | None:
        """Structural diff: identify which functions/classes changed.

        Returns ``{changed: [...], added: [...], removed: [...]}`` where
        each entry has ``{name, kind, line}``.  Returns ``None`` when
        the kill-switch is OFF.
        """
        if not _kill_switch_enabled():
            return None
        parser = _get_parser(".py")
        if parser is None:
            return None
        try:
            old_tree = parser.parse(old_code.encode("utf-8"))
            new_tree = parser.parse(new_code.encode("utf-8"))
        except Exception:
            return None
        old_syms = _extract_top_symbols(old_tree, old_code.encode("utf-8"), ".py", parser)
        new_syms = _extract_top_symbols(new_tree, new_code.encode("utf-8"), ".py", parser)
        old_map = {s["name"]: s for s in old_syms}
        new_map = {s["name"]: s for s in new_syms}
        old_names = set(old_map)
        new_names = set(new_map)
        return {
            "changed": [
                {**old_map[n], "new_line": new_map[n]["line"]}
                for n in old_names & new_names
                if old_map[n]["line"] != new_map[n]["line"] or _body_changed(old_map[n], new_map[n], old_code, new_code)
            ],
            "added": [new_map[n] for n in new_names - old_names],
            "removed": [old_map[n] for n in old_names - new_names],
        }

    @staticmethod
    def extract_symbols(filepath: str) -> list[dict[str, Any]] | None:
        """Extract all top-level symbols (functions, classes, variables).

        Returns a list of dicts: ``{name, kind, line, end_line}``.
        """
        if not _kill_switch_enabled():
            return None
        path = Path(filepath)
        ext = path.suffix.lower()
        parser = _get_parser(ext)
        if parser is None:
            return None
        try:
            source = path.read_bytes()
        except (OSError, UnicodeDecodeError):
            return None
        try:
            tree = parser.parse(source)
        except Exception:
            return None
        return _extract_top_symbols(tree, source, ext, parser)


# ── internal helpers ───────────────────────────────────────────────────


def _node_text(node, source: bytes) -> str:
    """Extract the text of a tree-sitter node."""
    start = node.start_byte
    end = node.end_byte
    return source[start:end].decode("utf-8", errors="replace")


def _find_child(node, type_name: str):
    """Find first child of a given type."""
    for child in node.children:
        if child.type == type_name:
            return child
    return None


def _walk_functions_manual(node, source: bytes, depth: int = 0) -> list[dict[str, Any]]:
    """Walk tree to find function definitions (fallback when query fails)."""
    results = []
    if node.type == "function_definition":
        name_child = _find_child(node, "identifier")
        name = _node_text(name_child, source) if name_child else "<anonymous>"
        params_node = _find_child(node, "parameters")
        params = _node_text(params_node, source).strip("()") if params_node else ""
        kind = "method" if node.parent and node.parent.type == "class_definition" else "function"
        results.append(
            {
                "name": name,
                "line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "params": params,
                "kind": kind,
            }
        )
    for child in node.children:
        results.extend(_walk_functions_manual(child, source, depth + 1))
    return results


def _node_to_dict(node, source: bytes, depth: int = 0, max_depth: int = 4) -> dict[str, Any]:
    """Convert a tree-sitter node to a dict (for AST summary)."""
    d: dict[str, Any] = {
        "type": node.type,
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
    }
    # Leaf nodes: include text (truncated)
    if not node.children or depth >= max_depth:
        text = _node_text(node, source).strip()
        if len(text) > 200:
            text = text[:200] + "…"
        d["text"] = text
    if node.children and depth < max_depth:
        d["children"] = [_node_to_dict(c, source, depth + 1, max_depth) for c in node.children]
    return d


def _extract_top_symbols(tree, source: bytes, ext: str, parser) -> list[dict[str, Any]]:
    """Extract top-level symbols from an AST."""
    results = []
    root = tree.root_node
    text = source.decode("utf-8", errors="replace")
    for child in root.children:
        if child.type == "function_definition":
            name_node = _find_child(child, "identifier")
            name = _node_text(name_node, source) if name_node else "<anon>"
            params_node = _find_child(child, "parameters")
            params = _node_text(params_node, source).strip("()") if params_node else ""
            kind = "method" if child.parent and child.parent.type == "class_definition" else "function"
            results.append(
                {
                    "name": name,
                    "kind": kind,
                    "line": child.start_point[0] + 1,
                    "end_line": child.end_point[0] + 1,
                    "params": params,
                }
            )
        elif child.type == "class_definition":
            name_node = _find_child(child, "identifier")
            name = _node_text(name_node, source) if name_node else "<anon>"
            results.append(
                {
                    "name": name,
                    "kind": "class",
                    "line": child.start_point[0] + 1,
                    "end_line": child.end_point[0] + 1,
                }
            )
        elif child.type == "assignment":
            targets = child.children
            if targets:
                var_name = _node_text(targets[0], source)
                results.append(
                    {
                        "name": var_name,
                        "kind": "variable",
                        "line": child.start_point[0] + 1,
                        "end_line": child.end_point[0] + 1,
                    }
                )
    return results


def _body_changed(old_sym: dict, new_sym: dict, old_code: str, new_code: str) -> bool:
    """Check if the body of a symbol changed (heuristic: line count difference)."""
    old_span = old_sym.get("end_line", old_sym["line"]) - old_sym["line"]
    new_span = new_sym.get("end_line", new_sym["line"]) - new_sym["line"]
    return abs(old_span - new_span) > 0


def tree_sitter_available() -> bool:
    """Check if tree-sitter is installed AND the kill-switch is ON."""
    if not _kill_switch_enabled():
        return False
    parser = _get_parser(".py")
    return parser is not None
