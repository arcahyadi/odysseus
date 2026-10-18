#!/usr/bin/env python3
"""Génère les tables de kill-switch des docs de traçabilité depuis le registre.

Problème résolu : les documents alignaient à la main les défauts de kill-switch,
et sont donc devenus faux au moment où le Palier 0 a basculé 14 défauts à `on`.
Un document faux est pire qu'un document absent : il affirme une activation qui
n'existe pas.

Ici, la **cartographie** (module SFD → switch) est maintenue à la main, mais les
**valeurs** sont lues à chaque exécution depuis `src/killswitch_registry.py`.
Une valeur ne peut donc plus périmer : soit elle est générée, soit elle ment.

Usage :
    python tools/gen_killswitch_tables.py            # réécrit les docs
    python tools/gen_killswitch_tables.py --check    # exit 1 si périmé (CI)

Écrit :
    docs/traceability/01-SFD-TRACEABILITY.md   (§1 colonne kill-switch, §2 table complète)
    docs/traceability/TRACEABILITY.md          (§1 tableau d'inventaire, ligne kill-switches)
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# monte au niveau module : sys.path est deja pose ci-dessus, et cet import
# echouerait tot plutot que de faire echouer la generation de documentation.
from src.killswitch_registry import read_states  # noqa: E402

P0_PALIER_0 = {
    "ODYSSEUS_PHASE_TRACKER",
    "ODYSSEUS_MODEL_ROUTER",
    "ODYSSEUS_PROGRESSIVE_DISCLOSURE",
    "ODYSSEUS_MEMORY_IMPACT",
    "ODYSSEUS_UNIFIED_TOKENS",
    "ODYSSEUS_OUTPUT_ROUTER",
    "ODYSSEUS_PREFERENCES",
    "ODYSSEUS_DATA_CLASSIFICATION",
    "ODYSSEUS_CONTENT_SECURITY",
    "ODYSSEUS_DURABLE_EXECUTION",
    "ODYSSEUS_PROVENANCE_MEMORY",
    "ODYSSEUS_AUTOEVAL",
    "ODYSSEUS_AUTOEVOLVE",
    "ODYSSEUS_CHECKPOINT",
}

# Module SFD -> env vars. Noms **corrigés** (les anciennes divergences de nommage
# ODYSSEUS_DURABLE_EXEC / MEMORY_PROVENANCE / VISUAL_OUTPUT ont été nettoyées le 2026-09-25).
MODULE_SWITCHES: dict[str, list[str]] = {
    "§5.1 Décision multi-agent & orchestration": [
        "ODYSSEUS_LIVE_ORCHESTRATION",
        "ODYSSEUS_PHASE_TRACKER",
        "ODYSSEUS_AGENT_CATALOG",
    ],
    "§5.2 Ingénierie du contexte": [],
    "§5.3 Planification intelligente": ["ODYSSEUS_PLANNING_ENGINE"],
    "§5.4 Exécution contrôlée/sécurisée": ["ODYSSEUS_DESTRUCTIVE_GATE"],
    "§5.5 Exécution durable": ["ODYSSEUS_DURABLE_EXECUTION", "ODYSSEUS_CHECKPOINT"],
    "§5.6 Routage modèles": ["ODYSSEUS_MODEL_ROUTER", "ODYSSEUS_ZEN_FROM_ENDPOINT"],
    "§5.7 Mémoire boucle fermée": ["ODYSSEUS_PROVENANCE_MEMORY", "ODYSSEUS_OBSIDIAN_MCP", "ODYSSEUS_MEMORY_IMPACT"],
    "§5.8 Communication multi-canal": [
        "ODYSSEUS_INPROCESS_DISCORD",
        "ODYSSEUS_INPROCESS_TELEGRAM",
        "ODYSSEUS_CHANNEL_AGENT_REPLY",
    ],
    "§5.9 Gouvernance & budgets": ["ODYSSEUS_GOVERNANCE_ANCESTRY"],
    "§5.10 Auto-évaluation & qualité": ["ODYSSEUS_AUTOEVAL", "ODYSSEUS_AUTOEVOLVE", "ODYSSEUS_DEEPEVAL"],
    "§5.11 Observabilité": ["ODYSSEUS_LANGFUSE", "ODYSSEUS_CODEBURN", "ODYSSEUS_UNIFIED_TOKENS"],
    "§5.12 Workspaces & worktrees": [],
    "§5.13 Extensibilité & MCP": [
        "ODYSSEUS_DISABLE_MCP",
        "ODYSSEUS_CBM",
        "ODYSSEUS_GRAPHIFY",
        "ODYSSEUS_SERENA_MCP",
    ],
    "§5.14 Config intégrale versionnée": [],
    "§5.15 Préférences utilisateur": ["ODYSSEUS_PREFERENCES"],
    "§5.16 Recherche conversations": [],
    "§5.17 Système de skills": [],
    "§5.18 Sortie visuelle": ["ODYSSEUS_OUTPUT_ROUTER"],
    "§5.19 Classification & rétention": ["ODYSSEUS_DATA_CLASSIFICATION"],
    "§5.20 Sécurité des contenus": ["ODYSSEUS_CONTENT_SECURITY", "ODYSSEUS_PROGRESSIVE_DISCLOSURE"],
}

BEGIN = "<!-- gen:killswitchs:begin -->"
END = "<!-- gen:killswitchs:end -->"


def load_states() -> dict[str, dict]:
    return {s["env_var"]: s for s in read_states()}


def render_switch_cell(env_vars: list[str], states: dict[str, dict]) -> str:
    if not env_vars:
        return "—"
    parts = []
    for ev in env_vars:
        st = states.get(ev)
        if st is None:
            # absent du registre : on le dit, on ne l'invente pas
            parts.append(f"`{ev}`=*(absent du registre)*")
            continue
        flag = ""
        if not st["wired"]:
            flag = " ⚠️non câblé"
        elif ev in P0_PALIER_0:
            flag = " 🔒P0"
        parts.append(f"`{ev}`={st['default']}{flag}")
    return ", ".join(parts)


def render_full_table(states: dict[str, dict]) -> str:
    order = sorted(states.values(), key=lambda s: (s["category"], s["name"]))
    lines = [
        BEGIN,
        "| Catégorie | Env var | Défaut code | Effectif | Câblé | Lecteur |",
        "|---|---|---|---|---|---|",
    ]
    for st in order:
        wired = "oui" if st["wired"] else "**NON**"
        eff = "`on`" if st["effective"] else "`off`"
        src = f"`{st['source']}`" if st["source"] else "—"
        lines.append(f"| {st['category']} | `{st['env_var']}` | `{st['default']}` | {eff} | {wired} | {src} |")
    total = len(order)
    on = sum(1 for s in order if s["effective"])
    p0 = sum(1 for s in order if s["env_var"] in P0_PALIER_0 and s["default"] == "on")
    unwired = sum(1 for s in order if not s["wired"])
    lines += [
        "",
        f"**{total} descripteurs · {on} ON par défaut · {unwired} non câblés · {p0}/{len(P0_PALIER_0)} P0 à `on`.**",
        "",
        f"- 🔒P0 = bascule à `on` par le **Palier 0** (2026-09-26), sur les {len(P0_PALIER_0)} principes cœur.",
        "- ⚠️non câblé = aucun lecteur dans le code. Le registre l'affiche `off` et `wired=False` : "
        "il ne peut **pas** se présenter comme actif. Ces 9 descripteurs étaient présentés comme `on` avant le 2026-09-26.",
        "- « Effectif » = valeur lue après application de `.env` (`is_default=False` ⇒ surcharge).",
        END,
    ]
    return "\n".join(lines)


def render_inventory_row(states: dict[str, dict]) -> str:
    total = len(states)
    on = sum(1 for s in states.values() if s["effective"])
    unwired = sum(1 for s in states.values() if not s["wired"])
    p0 = sum(1 for s in states.values() if s["env_var"] in P0_PALIER_0 and s["default"] == "on")
    return (
        f"| Kill-switches curatés | {total} (**{on} ON**, dont **{p0}/14 P0** ; "
        f"{unwired} non câblés) — *généré par* `tools/gen_killswitch_tables.py` |"
    )


def substitute(text: str, pattern: str, replacement: str | object) -> str:
    # `replacement` peut être une chaîne littérale (échappée par un lambda)
    # ou déjà une fonction, pour les cellules calculées.
    repl = replacement if callable(replacement) else (lambda _m, r=replacement: r)
    new, n = re.subn(pattern, repl, text, count=1, flags=re.M)
    if n != 1:
        raise SystemExit(f"motif introuvable ou ambigu : {pattern}")
    return new


SENTINELLE = "(aucun lecteur dans le code)"


def verifie_sources(states: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Verifie la colonne `source` du registre. Rend `(cassees, sans_ligne)`.

    `--check` ne verifiait que les TABLEaux. La colonne `source` — 33 references
    `fichier:ligne` sur 54 switches — n'etait verifiee par rien, donc une derive y
    restait invisible jusqu'a ce qu'un oeil la remarque. C'est le meme defaut que
    les citations de documentation, sur une autre colonne.

    Trois formes sont acceptees, et la troisieme est signalee sans faire echouer
    le controle, parce qu'elle n'est pas fausse :
      * `chemin/fichier.py:42` — verifie : le fichier existe, la ligne existe ;
      * `chemin/fichier.py`    — le fichier existe, mais aucune ligne n'est
                                 designee, donc l'affirmation est plus faible.
                                 Signalee, non bloquee.
      * `(aucun lecteur dans le code)` — sentinelle explicite d'un switch non
                                 cable. Ce n'est pas une source, c'est un aveu.
    """
    cassees: list[str] = []
    sans_ligne: list[str] = []
    for env, st in states.items():
        src = (st.get("source") or "").strip()
        if not src or src == SENTINELLE:
            continue
        m = re.fullmatch(r"([\w./-]+\.py):(\d+)", src)
        if m:
            rel, num = m.group(1), int(m.group(2))
        elif re.fullmatch(r"[\w./-]+\.py", src):
            rel, num = src, None
            sans_ligne.append(f"{env}: {src}")
        else:
            cassees.append(f"{env}: forme non reconnue pour source={src!r}")
            continue
        chemin = REPO / rel
        if not chemin.is_file():
            cassees.append(f"{env}: {rel} n'existe pas")
            continue
        if num is not None:
            total = sum(1 for _ in chemin.open(encoding="utf-8", errors="replace"))
            if not 1 <= num <= total:
                cassees.append(f"{env}: {rel} a {total} lignes, la source en designe {num}")
    return cassees, sans_ligne



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 si un doc est périmé")
    args = ap.parse_args()

    states = load_states()
    targets: list[tuple[pathlib.Path, str]] = []

    # ---- 01-SFD-TRACEABILITY.md -------------------------------------------
    p01 = REPO / "docs/traceability/01-SFD-TRACEABILITY.md"
    d01 = p01.read_text(encoding="utf-8")
    for module, env_vars in MODULE_SWITCHES.items():
        esc = re.escape(module)
        # la cellule générée est entourée d'espaces : le motif les consomme,
        # et une cellule Markdown sans espace adjacent ne s'affiche plus.
        cell = render_switch_cell(env_vars, states)
        d01 = substitute(
            d01,
            rf"^(\| {esc} \|[^|]*\|)[^|]*(\|[^|]*\|)$",
            lambda m, c=cell: m.group(1) + " " + c + " " + m.group(2),
        )
    d01 = re.sub(
        re.escape(BEGIN) + r".*?" + re.escape(END),
        lambda _m: render_full_table(states),
        d01,
        flags=re.S,
    )
    # La section §2 est réécrite ENTIEREMENT, pas seulement entre marqueurs : sinon
    # la table écrite à la main survit à côté de la table générée, et c'est
    # précisément elle qui affichait `ODYSSEUS_PHASE_TRACKER=off` alors que le
    # code lit `on`. Un document qui affiche deux versions du même registre ment deux fois.
    d01 = re.sub(
        r"^## 2\. Kill-switches.*\Z",
        lambda _m: "## 2. Kill-switches (registre vérifiable)\n\n"
        + render_full_table(states)
        + "\n\n> La table ci-dessus est la **source unique** de l'état des kill-switchs. "
        "Elle est régénérée depuis `src/killswitch_registry.py` : toute valeur écrite "
        "à la main ici serait périmée au prochain changement de registre.\n",
        d01,
        flags=re.S | re.M,
    )
    # Tolérant aux deux formes (avant / après génération) pour rester idempotent.
    d01 = substitute(
        d01,
        r"^\*(Généré:|Table de kill-switchs).*$",
        "*Table de kill-switchs **générée** par `tools/gen_killswitch_tables.py` — "
        "rejouer `python tools/gen_killswitch_tables.py` après toute modification du registre.*",
    )
    targets.append((p01, d01))

    # ---- TRACEABILITY.md ---------------------------------------------------
    ptr = REPO / "docs/traceability/TRACEABILITY.md"
    dtr = ptr.read_text(encoding="utf-8")
    dtr = substitute(
        dtr,
        r"^\| Kill-switches curatés \|.*\|$",
        lambda _m: render_inventory_row(states),
    )
    targets.append((ptr, dtr))

    cassees, sans_ligne = verifie_sources(states)
    if sans_ligne:
        print(
            f"\n  {len(sans_ligne)} source(s) sans numero de ligne — "
            "affirmation plus faible, signalee et non bloquante :"
        )
        for s_ in sans_ligne:
            print(f"    {s_}")
    if cassees:
        print("\nSOURCES PERIMEES :")
        for s_ in cassees:
            print(f"  {s_}")
        return 1

    stale = []
    for path, new in targets:
        old = path.read_text(encoding="utf-8")
        if old == new:
            print(f"  à jour   {path.relative_to(REPO)}")
        elif args.check:
            stale.append(path.relative_to(REPO))
        else:
            path.write_text(new, encoding="utf-8")
            print(f"  écrit    {path.relative_to(REPO)}")

    if stale:
        print("\nPERIMES — lancez : python tools/gen_killswitch_tables.py")
        for s in stale:
            print(f"  {s}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
