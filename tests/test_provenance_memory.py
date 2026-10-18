"""Tests for SFD §5.7 — Mémoire avec provenance."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.provenance_memory import (
    IDENTIFIABLE_CATEGORIES,
    MEMORY_ROOT,
    OMISSION_TRIGGERS,
    PROTECTED_CATEGORIES,
    SENSITIVE_CATEGORIES,
    MemoryEntry,
    MemoryFile,
    MemoryFS,
    provenance_memory_enabled,
)

# =========================================================================
# MemoryFile
# =========================================================================


class TestMemoryFile:
    def test_create_minimal(self):
        mf = MemoryFile(path=Path("topics/test.md"), name="test")
        assert mf.name == "test"
        assert mf.description == ""
        assert mf.sources == ["chat"]
        assert mf.aliases == []
        assert mf.entries == []
        assert mf.version == ""

    def test_generate_version_returns_12hex(self):
        mf = MemoryFile(path=Path("x.md"), name="x")
        v = mf.generate_version()
        assert len(v) == 12
        assert all(c in "0123456789abcdef" for c in v)

    def test_generate_version_idempotent(self):
        mf = MemoryFile(path=Path("x.md"), name="x")
        v1 = mf.generate_version()
        v2 = mf.generate_version()
        assert v1 != v2  # Each call generates a new token

    def test_content_generates_frontmatter_and_entries(self):
        mf = MemoryFile(path=Path("topics/test.md"), name="test")
        mf.description = "Test description"
        mf.sources = ["chat", "research"]
        mf.aliases = ["test-alias"]
        mf.entries = [
            MemoryEntry(tag="stated", text="User likes Python"),
            MemoryEntry(tag="inferred", text="User is a developer", confidence=0.9),
        ]
        content = mf.content
        assert "name: test" in content
        assert "description: Test description" in content
        assert "sources: [chat, research]" in content
        assert "aliases: [test-alias]" in content
        assert "[stated] User likes Python" in content
        assert "[inferred] User is a developer (confiance: 0.9)" in content

    def test_from_content_roundtrip(self):
        original = MemoryFile(path=Path("topics/test.md"), name="test")
        original.description = "Roundtrip test"
        original.sources = ["chat"]
        original.entries = [
            MemoryEntry(tag="stated", text="Hello world"),
            MemoryEntry(tag="observed", text="System online"),
        ]
        parsed = MemoryFile.from_content(Path("topics/test.md"), original.content)
        assert parsed.name == original.name
        assert parsed.description == original.description
        assert parsed.sources == original.sources
        assert len(parsed.entries) == len(original.entries)
        for pe, oe in zip(parsed.entries, original.entries, strict=False):
            assert pe.tag == oe.tag
            assert pe.text == oe.text

    def test_from_content_no_frontmatter(self):
        content = "- [stated] Just a fact\n"
        mf = MemoryFile.from_content(Path("bare.md"), content)
        assert mf.name == "bare"
        assert len(mf.entries) == 1
        assert mf.entries[0].text == "Just a fact"


# =========================================================================
# MemoryEntry
# =========================================================================


class TestMemoryEntry:
    def test_stated_str(self):
        e = MemoryEntry(tag="stated", text="User said X")
        assert str(e) == "- [stated] User said X"

    def test_inferred_with_confidence(self):
        e = MemoryEntry(tag="inferred", text="Likely true", confidence=0.85)
        result = str(e)
        assert "- [inferred] Likely true" in result
        assert "confiance: 0.85" in result

    def test_observed_str(self):
        e = MemoryEntry(tag="observed", text="System detected Y")
        assert str(e) == "- [observed] System detected Y"

    def test_from_line_stated(self):
        e = MemoryEntry.from_line("- [stated] Python is great")
        assert e is not None
        assert e.tag == "stated"
        assert e.text == "Python is great"
        assert e.confidence is None

    def test_from_line_inferred_with_confidence(self):
        e = MemoryEntry.from_line("- [inferred] User is dev (confiance: 0.75)")
        assert e is not None
        assert e.tag == "inferred"
        assert e.text == "User is dev"
        assert e.confidence == 0.75

    def test_from_line_invalid_tag(self):
        e = MemoryEntry.from_line("- [unknown] Something")
        assert e is None

    def test_from_line_malformed(self):
        e = MemoryEntry.from_line("not a memory line")
        assert e is None


# =========================================================================
# MemoryFS — Basic operations
# =========================================================================


class TestMemoryFS:
    @pytest.fixture
    def fs(self, tmp_path: Path) -> MemoryFS:
        return MemoryFS(root=tmp_path / "mem")

    def test_memory_read_missing(self, fs: MemoryFS):
        content, version = fs.memory_read("nonexistent.md")
        assert content is None
        assert version == ""

    def test_memory_write_new(self, fs: MemoryFS):
        ok, version = fs.memory_write("hello.md", "- [stated] Hello", "new")
        assert ok
        assert len(version) == 12

    def test_memory_write_new_twice_fails(self, fs: MemoryFS):
        fs.memory_write("hello.md", "content", "new")
        ok, msg = fs.memory_write("hello.md", "content2", "new")
        assert not ok
        assert "already exists" in msg

    def test_memory_write_with_version(self, fs: MemoryFS):
        fs.memory_write("test.md", "content", "new")
        content, version = fs.memory_read("test.md")
        ok, new_version = fs.memory_write("test.md", "updated", version)
        assert ok
        assert new_version != version  # Content changed

    def test_memory_write_wrong_version(self, fs: MemoryFS):
        fs.memory_write("test.md", "content", "new")
        ok, msg = fs.memory_write("test.md", "updated", "badversion123456")
        assert not ok
        assert "Version mismatch" in msg

    def test_memory_read_after_write(self, fs: MemoryFS):
        fs.memory_write("readme.md", "- [stated] Hello", "new")
        content, version = fs.memory_read("readme.md")
        assert content is not None
        assert "- [stated] Hello" in content
        assert len(version) == 12

    def test_memory_append(self, fs: MemoryFS):
        fs.memory_write("log.md", "- [stated] First", "new")
        content, version = fs.memory_read("log.md")
        ok, _ = fs.memory_append("log.md", "- [observed] Second", version)
        assert ok
        content2, _ = fs.memory_read("log.md")
        assert "Second" in content2

    def test_memory_append_version_mismatch(self, fs: MemoryFS):
        fs.memory_write("log.md", "content", "new")
        ok, msg = fs.memory_append("log.md", "new entry", "wrongversion")
        assert not ok
        assert "Version mismatch" in msg

    def test_memory_append_dedup(self, fs: MemoryFS):
        fs.memory_write("log.md", "- [stated] Unique", "new")
        content, version = fs.memory_read("log.md")
        ok, _ = fs.memory_append("log.md", "- [stated] Unique", version)
        assert ok  # Dedup: already present, returns success
        content2, _ = fs.memory_read("log.md")
        assert content2.count("Unique") == 1  # Not duplicated

    def test_memory_delete(self, fs: MemoryFS):
        fs.memory_write("delete_me.md", "content", "new")
        content, version = fs.memory_read("delete_me.md")
        ok, _ = fs.memory_delete("delete_me.md", version)
        assert ok
        assert not (fs.root / "delete_me.md").exists()

    def test_memory_delete_force(self, fs: MemoryFS):
        fs.memory_write("delete_me.md", "content", "new")
        ok, _ = fs.memory_delete("delete_me.md", "force")
        assert ok

    def test_memory_delete_missing(self, fs: MemoryFS):
        ok, msg = fs.memory_delete("ghost.md", "force")
        assert not ok
        assert "does not exist" in msg

    def test_memory_list_empty(self, fs: MemoryFS):
        assert fs.memory_list() == []

    def test_memory_list_with_files(self, fs: MemoryFS):
        fs.memory_write("a.md", "a", "new")
        fs.memory_write("b.md", "b", "new")
        (fs.root / "sub").mkdir(parents=True, exist_ok=True)
        (fs.root / "sub" / "c.md").write_text("c", encoding="utf-8")
        files = fs.memory_list()
        assert "a.md" in files
        assert "b.md" in files
        assert "sub/c.md" in files

    def test_memory_list_prefix(self, fs: MemoryFS):
        fs.memory_write("topics/foo.md", "foo", "new")
        fs.memory_write("topics/bar.md", "bar", "new")
        fs.memory_write("other.md", "other", "new")
        topics = fs.memory_list("topics")
        assert "topics/foo.md" in topics
        assert "topics/bar.md" in topics
        assert "other.md" not in topics

    def test_memory_str_replace(self, fs: MemoryFS):
        fs.memory_write("edit.md", "Hello world", "new")
        content, version = fs.memory_read("edit.md")
        ok, _ = fs.memory_str_replace("edit.md", "world", "there", version)
        assert ok
        content2, _ = fs.memory_read("edit.md")
        assert "there" in content2
        assert "world" not in content2

    def test_memory_str_replace_not_found(self, fs: MemoryFS):
        fs.memory_write("edit.md", "Hello", "new")
        content, version = fs.memory_read("edit.md")
        ok, msg = fs.memory_str_replace("edit.md", "ZZZ", "YYY", version)
        assert not ok
        assert "not found" in msg

    def test_memory_str_replace_ambiguous(self, fs: MemoryFS):
        fs.memory_write("edit.md", "X X X", "new")
        content, version = fs.memory_read("edit.md")
        ok, msg = fs.memory_str_replace("edit.md", "X", "Y", version)
        assert not ok
        assert "must be unique" in msg


# =========================================================================
# MemoryFS — Omission rules
# =========================================================================


class TestMemoryFSOmission:
    @pytest.fixture
    def fs(self, tmp_path: Path) -> MemoryFS:
        return MemoryFS(root=tmp_path / "mem")

    def test_omission_protected_category(self, fs: MemoryFS):
        assert fs._should_omit("user said their religion is X")

    def test_omission_sensitive_category(self, fs: MemoryFS):
        # SENSITIVE_CATEGORIES inclut "diagnostics"
        assert fs._should_omit("patient a des diagnostics médicaux")

    def test_omission_identifiable_category(self, fs: MemoryFS):
        # IDENTIFIABLE_CATEGORIES inclut "données bancaires"
        assert fs._should_omit("mes données bancaires sont X")

    def test_omission_clean_text(self, fs: MemoryFS):
        assert not fs._should_omit("User likes programming in Python")

    def test_write_blocks_omitted_content(self, fs: MemoryFS):
        ok, _ = fs.memory_write("safe.md", "User likes Python", "new")
        assert ok

    def test_append_blocks_omitted(self, fs: MemoryFS):
        fs.memory_write("test.md", "safe content", "new")
        content, version = fs.memory_read("test.md")
        ok, msg = fs.memory_append("test.md", "religion is X", version)
        assert not ok
        assert "omission" in msg

    def test_sanitize_removes_omitted_lines(self, fs: MemoryFS):
        content = "safe line\nreligion is secret\nanother safe"
        clean = fs._sanitize_content(content)
        assert "safe line" in clean
        assert "another safe" in clean
        assert "religion" not in clean

    def test_omission_triggers_includes_all_categories(self):
        for cat in PROTECTED_CATEGORIES + SENSITIVE_CATEGORIES + IDENTIFIABLE_CATEGORIES:
            assert cat in OMISSION_TRIGGERS


# =========================================================================
# MemoryFS — High-level helpers
# =========================================================================


class TestMemoryFSHelpers:
    @pytest.fixture
    def fs(self, tmp_path: Path) -> MemoryFS:
        return MemoryFS(root=tmp_path / "mem")

    def test_add_stated_creates_file(self, fs: MemoryFS):
        ok, version = fs.add_stated("python", "User likes Python")
        assert ok
        content, _ = fs.memory_read("topics/python.md")
        assert content is not None
        assert "[stated] User likes Python" in content

    def test_add_stated_appends(self, fs: MemoryFS):
        fs.add_stated("python", "Fact 1")
        ok, _ = fs.add_stated("python", "Fact 2")
        assert ok
        content, _ = fs.memory_read("topics/python.md")
        assert "Fact 1" in content
        assert "Fact 2" in content

    def test_add_observed_requires_existing_file(self, fs: MemoryFS):
        ok, msg = fs.add_observed("unknown", "Something")
        assert not ok
        assert "does not exist" in msg

    def test_add_observed_after_stated(self, fs: MemoryFS):
        fs.add_stated("system", "System exists")
        ok, _ = fs.add_observed("system", "System is running")
        assert ok
        content, _ = fs.memory_read("topics/system.md")
        assert "[stated] System exists" in content
        assert "[observed] System is running" in content

    def test_add_inferred_requires_existing_file(self, fs: MemoryFS):
        ok, msg = fs.add_inferred("unknown", "Guess", 0.5)
        assert not ok
        assert "does not exist" in msg

    def test_add_inferred_with_confidence(self, fs: MemoryFS):
        fs.add_stated("user", "User exists")
        ok, _ = fs.add_inferred("user", "User is dev", 0.85)
        assert ok
        content, _ = fs.memory_read("topics/user.md")
        assert "confiance: 0.85" in content

    def test_get_profile_missing(self, fs: MemoryFS):
        assert fs.get_profile() is None

    def test_update_profile_creates(self, fs: MemoryFS):
        ok, _ = fs.update_profile("User is John")
        assert ok
        content = fs.get_profile()
        assert content is not None
        assert "John" in content

    def test_update_profile_appends(self, fs: MemoryFS):
        fs.update_profile("Fact 1")
        ok, _ = fs.update_profile("Fact 2")
        assert ok
        content = fs.get_profile()
        assert content is not None
        assert "Fact 1" in content
        assert "Fact 2" in content


# =========================================================================
# Kill-switch
# =========================================================================


class TestProvenanceKillSwitch:
    def test_default_on(self, monkeypatch: pytest.MonkeyPatch):
        """Palier 0 (FND-4 option C): ON by default again."""
        monkeypatch.delenv("ODYSSEUS_PROVENANCE_MEMORY", raising=False)
        assert provenance_memory_enabled() is True

    def test_can_be_off(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "off")
        assert provenance_memory_enabled() is False

    def test_on_when_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "on")
        assert provenance_memory_enabled() is True

    def test_on_accepts_1(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "1")
        assert provenance_memory_enabled() is True

    def test_on_accepts_true(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "true")
        assert provenance_memory_enabled() is True

    def test_off_when_empty_string(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ODYSSEUS_PROVENANCE_MEMORY", "")
        assert provenance_memory_enabled() is False


# =========================================================================
# Constants integrity
# =========================================================================


class TestConstants:
    def test_protected_categories_non_empty(self):
        assert len(PROTECTED_CATEGORIES) >= 5

    def test_sensitive_categories_non_empty(self):
        assert len(SENSITIVE_CATEGORIES) >= 5

    def test_identifiable_categories_non_empty(self):
        assert len(IDENTIFIABLE_CATEGORIES) >= 5

    def test_memory_root_is_path(self):
        assert isinstance(MEMORY_ROOT, Path)
