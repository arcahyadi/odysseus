"""Le validateur de citations doit échouer quand une citation est fausse.

Un validateur qui n'a jamais échoué ne prouve rien. Ce fichier fait donc échouer
`tools/check_citations.py` sur plusieurs classes d'erreurs, ce qui est le seul
moyen de savoir qu'il détecte quelque chose.

Périmètre honnête : ces tests prouvent que le Checker détecte un **fichier inexistant**
et un **numéro de ligne hors fichier**. Ils ne prétendent PAS qu'il détecte une citation
décalée de quelques lignes dans un fichier de 4700 lignes — il ne le peut pas, et le
Checker le dit explicitement dans son docstring. Les trois dérives de citations trouvées
par le projet (245 lignes d'écart compris) étaient toutes dans les bornes.
"""

import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
TOOL = REPO / "tools" / "check_citations.py"


def _run(*args):
    # `check=False` volontaire : ces tests **inspectent** le code de retour du Checker
    # (0 attendu, mais 1 est une information utile), on ne veut pas que subprocess lève.
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=300,
        check=False,
    )


# ─── L'auto-test interne du Checker ────────────────────────────────────────


def test_the_checker_proves_it_detects():
    """`--self-test` doit passer : il vérifie que le détecteur détecte."""
    r = _run("--self-test")
    assert r.returncode == 0, f"l'auto-test du Checker a échoué :\n{r.stdout}\n{r.stderr}"
    assert "auto-test OK" in r.stdout


# ─── Le Checker doit échouer sur une citation fausse ───────────────────────


def test_an_unresolvable_filename_is_reported(tmp_path):
    """PREUVE : un nom de fichier qui n'existe pas doit être signalé comme non résolu.

    Ici la citation est dans les bornes, donc aucune erreur de bornes n'est attendue :
    ce qui doit être signalé, c'est l'impossibilité de résoudre le nom.
    """
    from tools.check_citations import build_index, check  # noqa: PLC0415 — test du Checker lui-même

    doc = tmp_path / "doc.md"
    doc.write_text("preuve : `fichier_inexistant_98765.py:12`\n", encoding="utf-8")

    index = build_index()
    total, problems, unresolved = check([doc], index)

    assert total == 1
    assert not problems, "la citation est dans les bornes, il ne doit pas y avoir de probleme de bornes"
    assert "fichier_inexistant_98765.py" in unresolved, "le nom invente doit etre signale comme non resolu"


def test_a_line_beyond_end_of_file_is_reported(tmp_path):
    """PREUVE : un numéro de ligne au-delà de la fin du fichier doit être signalé.

    On vise un vrai fichier du dépôt pour que seul le numéro soit fautif — c'est
    exactement la faute la plus facile à commettre quand on édite une doc.
    """
    from tools.check_citations import build_index, check  # noqa: PLC0415

    index = build_index()
    biggest = max(
        (len(p.read_text(encoding="utf-8", errors="replace").splitlines()), p)
        for paths in index.values()
        for p in paths[:1]
    )
    n_lines, path = biggest
    doc = tmp_path / "doc.md"
    doc.write_text(f"preuve : `{path.name}:{n_lines + 5000}`\n", encoding="utf-8")

    _, problems, _ = check([doc], index)
    assert problems, f"une citation a {n_lines + 5000} lignes dans un fichier de {n_lines} doit etre signalee"
    assert str(n_lines + 5000) in problems[0][2]


# ─── La resolution doit preferer le corps reel, pas la shim ───────────────


def test_agent_loop_resolves_to_the_archived_body_not_the_shim():
    """`agent_loop.py` doit résoudre sur `archive/legacy/`, pas sur la shim de 27 lignes.

    C'est le piège que ce Checker a réellement rencontré : en ignorant `archive/`, le
    résolveur partait sur `src/agent_loop.py` et déclarait **toutes** les citations de la
    boucle hors fichier — un faux positif de 43 citations. La préférence doit donc être
    testée, pas seulement commentée.
    """
    from tools.check_citations import build_index, resolve  # noqa: PLC0415

    index = build_index()
    target = resolve("agent_loop.py", index)

    assert target is not None, "agent_loop.py doit resoudre"
    rel = target.relative_to(REPO).as_posix()
    assert rel == "archive/legacy/agent_loop.py", f"resolution vers {rel}, attendu archive/legacy/agent_loop.py"
    n_lines = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
    assert n_lines > 1000, f"le fichier resolu a {n_lines} lignes : c'est la shim, pas le corps"


def test_the_real_docs_pass_the_checker():
    """Contre-épreuve : les docs du dépôt passent, et le Checker sort 0.

    Sans ce test, on pourrait rendre le Checker tolérant en le rendant tolérant.
    """
    r = _run()
    assert r.returncode == 0, f"les docs doivent passer le Checker :\n{r.stdout}\n{r.stderr}"
    assert "hors fichier         : 0" in r.stdout
    assert "noms non resolus     : 0" in r.stdout
