import pathlib
import re

from src import killswitch_registry as ksr


def test_unset_var_is_default_and_uses_code_default(monkeypatch):
    """An unset var falls back to the descriptor default.

    AUTOEVAL's descriptor default flipped to "on" with Palier 0, so an unset
    ODYSSEUS_AUTOEVAL now resolves to True. The OFF polarity is asserted
    through the dedicated ALLOW_RESET descriptor right below, which must stay
    "off" — that separation is the safety property, not a detail.
    """
    monkeypatch.delenv("ODYSSEUS_AUTOEVAL", raising=False)
    row = _find(ksr.read_states(), "ODYSSEUS_AUTOEVAL")
    assert row["is_default"] is True
    assert row["raw"] is None
    assert row["effective"] is True  # Palier 0 default


def test_destructive_revert_gate_stays_off_by_default(monkeypatch):
    """The cockpit must never present destructive auto-revert as available."""
    monkeypatch.delenv("ODYSSEUS_AUTOEVAL_ALLOW_RESET", raising=False)
    row = _find(ksr.read_states(), "ODYSSEUS_AUTOEVAL_ALLOW_RESET")
    assert row["is_default"] is True
    assert row["default"] == "off"
    assert row["effective"] is False


def test_all_p0_switches_are_registered():
    """Every Palier 0 switch must be visible in the registry.

    Six of them (OUTPUT_ROUTER, PREFERENCES, DATA_CLASSIFICATION,
    CONTENT_SECURITY, DURABLE_EXECUTION, PROVENANCE_MEMORY) were ON in
    .env.example but absent from the registry, so the cockpit could not
    reflect a state it did not even expose.
    """
    env_vars = {r["env_var"] for r in ksr.read_states()}
    p0 = [
        "PHASE_TRACKER", "MODEL_ROUTER", "PROGRESSIVE_DISCLOSURE", "MEMORY_IMPACT",
        "UNIFIED_TOKENS", "OUTPUT_ROUTER", "PREFERENCES", "DATA_CLASSIFICATION",
        "CONTENT_SECURITY", "DURABLE_EXECUTION", "PROVENANCE_MEMORY",
        "AUTOEVAL", "AUTOEVOLVE", "CHECKPOINT",
    ]
    missing = [f"ODYSSEUS_{s}" for s in p0 if f"ODYSSEUS_{s}" not in env_vars]
    assert missing == []


def test_p0_switches_default_to_on():
    """Palier 0 switches must be active by default in the shipped descriptors."""
    rows = {r["env_var"]: r for r in ksr.read_states()}
    p0 = [
        "PHASE_TRACKER", "MODEL_ROUTER", "PROGRESSIVE_DISCLOSURE", "MEMORY_IMPACT",
        "UNIFIED_TOKENS", "OUTPUT_ROUTER", "PREFERENCES", "DATA_CLASSIFICATION",
        "CONTENT_SECURITY", "DURABLE_EXECUTION", "PROVENANCE_MEMORY",
        "AUTOEVAL", "AUTOEVOLVE", "CHECKPOINT",
    ]
    wrong = [f"ODYSSEUS_{s}" for s in p0 if rows[f"ODYSSEUS_{s}"]["default"] != "on"]
    assert wrong == []


def test_set_on_is_effective_true(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_AUTOEVAL", "on")
    row = _find(ksr.read_states(), "ODYSSEUS_AUTOEVAL")
    assert row["is_default"] is False
    assert row["raw"] == "on"
    assert row["effective"] is True


def test_set_off_is_effective_false(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_LIVE_ORCHESTRATION", "off")
    row = _find(ksr.read_states(), "ODYSSEUS_LIVE_ORCHESTRATION")
    assert row["effective"] is False
    assert row["is_default"] is False


def test_destructive_gate_defaults_on(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_DESTRUCTIVE_GATE", raising=False)
    row = _find(ksr.read_states(), "ODYSSEUS_DESTRUCTIVE_GATE")
    assert row["is_default"] is True
    assert row["effective"] is True  # default "on"


def test_every_descriptor_has_required_keys():
    required = {"name", "env_var", "default", "category", "timing", "desc", "source"}
    for row in ksr.read_states():
        assert required.issubset(row.keys()), row
        assert row["source"], f"empty source for {row['env_var']}"
        assert row["timing"] in ("startup", "runtime")


def test_categories_cover_all_switches():
    cats = set(ksr.categories())
    for row in ksr.read_states():
        assert row["category"] in cats


def _find(rows, env_var):
    for r in rows:
        if r["env_var"] == env_var:
            return r
    raise AssertionError(f"{env_var} not in registry")


# ── the registry must not be able to lie ─────────────────────────────────
#
# Palier 0 exposed a real problem: 16 descriptors declared `default: "on"`
# while their reader fell back to `off`, and 9 more declared `on` with no
# reader anywhere. The dashboard therefore showed switches as ACTIVE that
# were, respectively, OFF or entirely unimplemented. "The cockpit reflects
# the state" is a Palier 0 precondition, so the registry is now policed by
# this test instead of by good intentions.

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SOURCE_DIRS = ("src", "core", "routes", "archive", "services", "mcp_servers")
_READER_RE = re.compile(
    r'(?:os\.environ\.get|os\.getenv)\(\s*(?:"(ODYSSEUS_[A-Z0-9_]+)"|([A-Z_][A-Z0-9_]*))\s*,\s*"([^"]*)"'
)

# Une lecture SANS defaut litteral — `os.getenv("ODYSSEUS_X")` — etait invisible
# ici, alors que c'est une lecture au meme titre. Six variables en profitaient,
# dont deux inscrites au registre (LETTA, MEM0) et une deja presente avant
# (`ZEN_FROM_ENDPOINT`) : leurs entrées ne pouvaient donc pas etre verifiees, ni
# leur defaut concorde avec quoi que ce soit de lisible.
#
# On les capte donc, avec le defaut vide — ce que `_normalise` lit deja comme
# « eteint ». Un interrupteur lu sans defaut explicite n'est pas pour autant un
# interrupteur inexistant, et c'est justement ce qu'on ne voulait pas voir
# disparaitre du controle.
_READER_SANS_DEFAUT_RE = re.compile(
    r'(?:os\.environ\.get|os\.getenv)\(\s*"(ODYSSEUS_[A-Z0-9_]+)"\s*\)'
)

# Un module peut nommer la variable dans une CONSTANTE et la lire par cette
# constante : `os.getenv(REMOTE_SSH_ENV, "off")`. C'est la bonne pratique — une
# seule orthographe, code et tableau d'accord — mais c'était un angle mort de
# plus : le verificateur ne voyait que les litteraux, donc une lecture par
# constante Passait pour une lecture inexistante, et le registre exigeait
# `wired=False` pour une porte qui gouvernait reellement quelque chose.
#
# On resout donc les constantes de module avant de scanner. C'est du support d'une
# bonne pratique, pas un assouplissement : la constante doit etre une chaine
# `ODYSSEUS_*` directement au niveau du module, pas un calcul.
_CONSTANTE_RE = re.compile(r'^([A-Z_][A-Z0-9_]*)\s*(?::[^=]+)?=\s*"(ODYSSEUS_[A-Z0-9_]+)"', re.M)


def _constantes_env(texte: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in _CONSTANTE_RE.finditer(texte)}

# Descriptors whose reader resolves the env var name at call time, so no
# literal `os.getenv("ODYSSEUS_...")` exists to match. Each one is bound to
# the module that reads it, and to the default that module applies.
_DYNAMIC_READERS = {
    "src/orchestrator/agent_dispatcher.py": "off",
}


def _real_readers() -> dict[str, set[str]]:
    """Map every env var name to the set of defaults its real readers use."""
    return _reader_sites_defaults()


def _reader_sites() -> dict[str, list[str]]:
    """Map every env var name to the files+lines that actually read it.

    Location, not just existence: `wired` proves a reader exists, but nothing
    proved the *cited* file was it. It was not — 33 of 54 descriptors pointed
    at two unrelated files (`checkpoint_tracker.py`, `memory_impact.py`),
    copy-pasted. The cockpit renders `source` as "Lecteur", so a wrong value
    there is a false statement about where the switch is honoured.
    """
    sites: dict[str, list[str]] = {}
    for d in _SOURCE_DIRS:
        root = _REPO_ROOT / d
        if not root.is_dir():
            continue
        for f in sorted(root.rglob("*.py")):
            try:
                lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            # Les constantes se resolvent par FICHIER, pas par ligne : une
            # constante est definie une fois en haut du module et lue cent lignes
            # plus bas.
            consts = _constantes_env("\n".join(lines))
            for i, line in enumerate(lines, 1):
                trouve = False
                for m in _READER_RE.finditer(line):
                    nom = m.group(1) or consts.get(m.group(2), "")
                    if nom:
                        sites.setdefault(nom, []).append(f"{f.relative_to(_REPO_ROOT)}:{i}")
                    trouve = True
                if not trouve:
                    for m in _READER_SANS_DEFAUT_RE.finditer(line):
                        sites.setdefault(m.group(1), []).append(f"{f.relative_to(_REPO_ROOT)}:{i}")
    return sites


def _reader_sites_defaults() -> dict[str, set[str]]:
    """env var name -> the defaults its real readers apply."""
    found: dict[str, set[str]] = {}
    for d in _SOURCE_DIRS:
        root = _REPO_ROOT / d
        if not root.is_dir():
            continue
        for f in root.rglob("*.py"):
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            consts = _constantes_env(txt)
            for m in _READER_RE.finditer(txt):
                nom = m.group(1) or consts.get(m.group(2), "")
                if nom:
                    found.setdefault(nom, set()).add(m.group(3))
            for m in _READER_SANS_DEFAUT_RE.finditer(txt):
                found.setdefault(m.group(1), set()).add("")
    return found


def _normalise(default: str) -> str:
    """A reader falling back to "" is an OFF switch; say so plainly."""
    return "off" if default == "" else default


def test_every_wired_descriptor_has_a_real_reader():
    """`wired=True` must mean some code really reads the variable."""
    readers = _real_readers()
    for row in ksr.read_states():
        if not row["wired"]:
            continue
        if row["env_var"] in readers:
            continue
        dynamic = {src: d for src, d in _DYNAMIC_READERS.items() if src == row["source"]}
        assert dynamic, (
            f"{row['env_var']} is declared wired but nothing in the codebase reads it "
            f"(source: {row['source']}) — either wire it or flag wired=False"
        )


def test_unwired_descriptors_really_have_no_reader():
    """Conversely: `wired=False` must stay true, so the flag can't rot either."""
    readers = _real_readers()
    for row in ksr.read_states():
        if row["wired"]:
            continue
        assert row["env_var"] not in readers, (
            f"{row['env_var']} now has a real reader ({sorted(readers[row['env_var']])}) "
            f"— drop wired=False and set its default from the code"
        )


def test_descriptor_default_matches_the_real_reader():
    """The dashboard's headline number must be the one the code will use."""
    readers = _real_readers()
    lying = []
    for row in ksr.read_states():
        if not row["wired"] or row["env_var"] not in readers:
            continue
        declared = _normalise(row["default"])
        actual = {_normalise(d) for d in readers[row["env_var"]]}
        if declared not in actual:
            lying.append(f"{row['env_var']}: registre={declared} code={sorted(actual)}")
    assert lying == []


def test_no_switch_presents_itself_active_while_unwired():
    """The cockpit must not offer a switch that provably cannot do anything."""
    for row in ksr.read_states():
        if row["wired"]:
            continue
        assert row["effective"] is False, (
            f"{row['env_var']} is unwired yet reports effective=True — "
            f"the dashboard would be advertising an unreachable switch"
        )


def test_wired_source_points_at_a_file_that_really_reads_the_var():
    """`source` is rendered as "Lecteur" — it must not be a guess.

    33 of 54 descriptors cited `checkpoint_tracker.py:39` or
    `memory_impact.py:23` regardless of the switch they described. Nothing
    policed the field, so the cockpit could name a file that has nothing to do
    with the switch. `wired` proves a reader exists; this proves the cited one
    is it.
    """
    sites = _reader_sites()
    dynamic = set(_DYNAMIC_READERS)
    wrong = []
    for row in ksr.read_states():
        if not row["wired"]:
            continue
        cited = row["source"].split(":")[0]
        if cited in dynamic:
            continue  # read via _is_enabled(env_var), no literal getenv site
        if row["env_var"] in sites and any(s.startswith(cited) for s in sites[row["env_var"]]):
            continue
        wrong.append(
            f"{row['env_var']}: source={row['source']!r} "
            f"lecteurs réels={sites.get(row['env_var'], [])}"
        )
    assert wrong == []


def test_unwired_source_declares_the_absence_of_a_reader():
    """A descriptor with no reader must not cite a file as if it had one."""
    wrong = [
        f"{row['env_var']}: source={row['source']!r}"
        for row in ksr.read_states()
        if not row["wired"] and "aucun lecteur" not in row["source"]
    ]
    assert wrong == []
