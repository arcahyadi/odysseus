"""
IntentGate : classifie l'intention d'une requête avant routing.
Catégories : quick / deep / utility / vision / code / creative

Utilisé par ModelRouter pour sélectionner le bon tier de modèle.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Dictionnaire de mots-clés par catégorie
# Chaque liste contient des patterns (sous-chaînes insensibles à la casse).
# ---------------------------------------------------------------------------

INTENT_KEYWORDS: dict[str, list[str]] = {
    "code": [
        "implémente",
        "implemente",
        "implement",
        "code",
        "function",
        "classe",
        "class",
        "bug",
        "fix",
        "refactor",
        "test",
        "debug",
        "lint",
        "script",
        "module",
        "api",
        "endpoint",
        "migration",
        "schema",
        "algorithm",
        "algorithme",
        "programme",
        "program",
    ],
    "deep": [
        "analyse",
        "analyze",
        "recherche",
        "research",
        "explique en détail",
        "explique en detail",
        "explain in detail",
        "architecture",
        "pourquoi",
        "why",
        "compare",
        "comparison",
        "stratégie",
        "strategy",
        "deep dive",
        "comprehensive",
        "exhaustif",
        "exhaustive",
        "distributed",
        "distribué",
        "consensus",
        "benchmark",
    ],
    "vision": [
        "image",
        "screenshot",
        "photo",
        "visuel",
        "visual",
        "picture",
        "regarde",
        "look at",
        "voir",
        "see",
        "diagram",
        "diagramme",
        "capture",
        "écran",
        "screen",
    ],
    "creative": [
        "génère",
        "genere",
        "generate",
        "invente",
        "invent",
        "crée un design",
        "create a design",
        "brainstorm",
        "idée",
        "idea",
        "imagine",
        "propose",
        "suggest",
        "novel",
        "original",
        "story",
        "histoire",
        "poem",
        "poème",
        "narrative",
    ],
    "quick": [
        "résume",
        "resume",
        "summarize",
        "liste",
        "list",
        "court",
        "short",
        "rapide",
        "quick",
        "simple",
        "brief",
        "définition",
        "definition",
        "define",
        "qu'est-ce",
        "what is",
        "donne-moi",
        "give me",
        "show me",
    ],
}

# Signaux forts pour "deep" issus du heuristique existant dans model-routing.json
_STRONG_SIGNALS: list[str] = [
    "implement",
    "architect",
    "design system",
    "security",
    "performance",
    "implémenter",
    "architecturer",
    "concevoir",
    "analyse profonde",
    "migration",
]

# Signaux faibles → quick
_WEAK_SIGNALS: list[str] = [
    "hello",
    "bonjour",
    "hi",
    "merci",
    "thanks",
    "ok",
    "oui",
    "non",
    "capital",
    "what is",
    "qu'est",
]

# Seuils de longueur (en mots)
_WORD_COUNT_THRESHOLDS = {
    "weak_max": 8,
    "strong_min": 40,
}

# Score de confiance minimum pour retourner une catégorie non-utility
_SCORE_THRESHOLD = 0.25


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


def classify_intent(prompt: str) -> str:
    """
    Classifie l'intent d'un prompt.
    Retourne une catégorie parmi : quick / deep / utility / vision / code / creative.

    Logique :
      1. Vérifie les signaux forts/faibles
      2. Compte les correspondances par catégorie
      3. Si aucune correspondance → heuristique longueur
    """
    if not prompt or not prompt.strip():
        return "utility"

    prompt_lower = prompt.lower()

    # Signaux forts → deep
    for signal in _STRONG_SIGNALS:
        if signal in prompt_lower:
            return "deep"

    # Signaux faibles → quick
    for signal in _WEAK_SIGNALS:
        if signal in prompt_lower:
            words = _word_count(prompt)
            if words <= _WORD_COUNT_THRESHOLDS["weak_max"]:
                return "quick"

    # Comptage de correspondances par catégorie
    scores: dict[str, int] = {}
    for category, keywords in INTENT_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in prompt_lower)
        if count > 0:
            scores[category] = count

    if scores:
        best_cat = max(scores, key=lambda c: scores[c])
        # Normalisation grossière : si le meilleur score est suffisant
        total_words = max(_word_count(prompt), 1)
        normalized = scores[best_cat] / total_words
        if normalized >= _SCORE_THRESHOLD or scores[best_cat] >= 2:
            return best_cat

    # Aucune correspondance claire → heuristique longueur
    return classify_by_word_count(prompt)


def classify_by_word_count(prompt: str) -> str:
    """
    Heuristique de fallback basée sur la longueur du prompt.

    - ≤ weak_max mots  → quick
    - ≥ strong_min mots → deep
    - entre les deux   → utility
    """
    words = _word_count(prompt)
    if words <= _WORD_COUNT_THRESHOLDS["weak_max"]:
        return "quick"
    if words >= _WORD_COUNT_THRESHOLDS["strong_min"]:
        return "deep"
    return "utility"


def classify_intent_with_stage(prompt: str, stage: str | None = None) -> tuple[str, str | None]:
    """
    Retourne (intent_category, stage) prêt pour ModelRouter.complete().

    Si un stage est passé, il prend la priorité pour le routing mais
    la catégorie d'intent est quand même calculée (pour logging/analytics).
    """
    intent = classify_intent(prompt)
    return intent, stage


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _word_count(text: str) -> int:
    """Nombre de mots dans un texte (split naïf sur espaces/ponctuation)."""
    return len(re.findall(r"\b\w+\b", text))
