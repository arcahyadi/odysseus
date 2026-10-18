"""SFD §5.27 — P19: Memory Impact Verification.

Before storing a memory fact, compare the agent's response with and without
the fact. Facts that don't change the response ("earn their place") are
flagged as low-impact and may be discarded to keep the memory store lean.

Gated behind ODYSSEUS_MEMORY_IMPACT kill-switch (default OFF).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass

# `provenance_memory` does not import this module, so a top-level import is
# acyclic here. Kept at module level (rather than inside the function) so the
# store contract is resolved once, at import, like every other dependency.
from src.provenance_memory import get_memory_fs
from src.app_context import app_context


logger = logging.getLogger(__name__)

# ─── Kill-switch ────────────────────────────────────────────────────────


def memory_impact_enabled() -> bool:
    val = os.getenv("ODYSSEUS_MEMORY_IMPACT", "on").strip().lower()
    return val in {"on", "1", "true", "yes"}


# ─── Constants ──────────────────────────────────────────────────────────

DEFAULT_IMPACT_THRESHOLD = 0.15

# Représente « sans ce fait, l'agent n'aurait rien dit de tel ». Non vide par
# construction : `evaluate_impact` renvoie 0.0 sur un comparatif vide
# (`memory_impact.py:51-52`), ce qui confondrait « le fait a tout changé » et
# « le fait n'a rien changé ».
EMPTY_ANSWER_SENTINEL = "(sans ce fait, la réponse serait vide)"

# Taille des n-grammes utilisés pour comparer deux réponses. Partagée avec
# `_is_measurable` : en dessous de ce nombre de mots, la comparaison n'est pas
# une mesure et ne doit pas être lue comme un score.
NGRAM = 3


@dataclass
class ImpactResult:
    fact: str
    impact_score: float
    threshold: float
    should_store: bool
    reason: str = ""


class MemoryImpactVerifier:
    def __init__(self, threshold: float = DEFAULT_IMPACT_THRESHOLD):
        self.threshold = threshold

    def evaluate_impact(
        self,
        fact: str,
        current_response: str,
        hypothetical_response: str,
    ) -> float:
        if not current_response or not hypothetical_response:
            return 0.0

        current_norm = _normalize(current_response)
        hypo_norm = _normalize(hypothetical_response)

        if current_norm == hypo_norm:
            return 0.0

        current_hash = _token_set_hash(current_norm)
        hypo_hash = _token_set_hash(hypo_norm)

        if not current_hash or not hypo_hash:
            # A response too short to yield a single 3-gram is not a measured
            # zero, it is an unmeasurable comparison. Returning 0.0 here makes
            # "we could not tell" indistinguishable from "this fact changed
            # nothing", and the caller then discards the fact on a guess.
            logger.debug("[p19] response too short to compare (%d/%d tokens)", len(current_norm.split()), len(hypo_norm.split()))
            return 0.0

        intersection = current_hash & hypo_hash
        union = current_hash | hypo_hash
        if not union:
            return 0.0

        similarity = len(intersection) / len(union)
        impact = 1.0 - similarity
        return round(impact, 4)

    def should_store(self, fact: str, impact_score: float) -> bool:
        return impact_score > self.threshold

    def verify(
        self,
        fact: str,
        current_response: str,
        hypothetical_response: str,
    ) -> ImpactResult:
        impact = self.evaluate_impact(fact, current_response, hypothetical_response)
        store = self.should_store(fact, impact)

        reason = ""
        if not _is_measurable(current_response, hypothetical_response):
            # "Cannot compare" must never read as "no impact". A response too
            # short to yield a single 3-gram tells us nothing about the fact, so
            # it is kept by default: losing a memory is recoverable, silently
            # dropping a user's own words because the metric could not run is
            # not. The reason string says which of the two happened.
            store = True
            reason = "not_measurable (responses too short to compare) — kept by default"
        elif not store:
            if impact == 0.0:
                reason = "no_impact"
            else:
                reason = f"below_threshold ({impact:.4f} <= {self.threshold})"
        else:
            reason = f"above_threshold ({impact:.4f} > {self.threshold})"

        result = ImpactResult(
            fact=fact,
            impact_score=impact,
            threshold=self.threshold,
            should_store=store,
            reason=reason,
        )

        if store:
            logger.debug("[p19] memory impact: storing fact (impact=%.4f, %s)", impact, reason)
        else:
            logger.debug("[p19] memory impact: discarding fact (impact=%.4f, %s)", impact, reason)

        return result


def _is_measurable(current_response: str, hypothetical_response: str) -> bool:
    """Le comparatif a-t-il produit assez de matière pour être une mesure ?

    `_token_set_hash` renvoie None en dessous de NGRAM mots : ce n'est pas un
    score de zéro, c'est l'absence de mesure. Confondre les deux ferait
    jeter un fait sur une conjecture.
    """
    if not current_response or not hypothetical_response:
        return False
    return (
        len(_normalize(current_response).split()) >= NGRAM and len(_normalize(hypothetical_response).split()) >= NGRAM
    )


def build_hypothetical_response(fact: str, response: str) -> str:
    """Construit le comparatif « et sans ce fait ? ».

    L'ancien appelait `verify(..., hypothetical_response="")`, ce qui
    court-circuitait `evaluate_impact` à 0.0 (`memory_impact.py:51-52`) :
    `should_store` valait **toujours** False, et le principe ne pouvait rien
    retenir. Sans LLM nominal (cf. `OPENCODE_API_KEY` absente de `.env`), la
    seule réponse hypothétique honnête et déterministe est **la réponse dont on
    retire le fait** : si l'agent a utilisé le fait, la réponse change quand on
    le retire, et le score est > 0. Sinon elle ne change pas, et le score est
    nul. C'est exactement la question de P19 : « ce fait a-t-il changé la
    réponse ? ».
    """
    if not response:
        return ""

    fact_tokens = {t for t in re.findall(r"\w+", fact.lower()) if len(t) > 3}
    if not fact_tokens:
        return response

    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", response):
        sent_tokens = {t for t in re.findall(r"\w+", sentence.lower()) if len(t) > 3}
        if not sent_tokens:
            kept.append(sentence)
            continue
        # Drop a sentence only when the fact DOMINATES it. A single shared word
        # is not enough: "PostgreSQL" appearing once would otherwise delete a
        # whole unrelated sentence and inflate every score.
        if len(sent_tokens & fact_tokens) / len(sent_tokens) >= 0.5:
            continue
        kept.append(sentence)

    remainder = " ".join(kept).strip()
    if not remainder:
        # Every sentence was fact-driven: without the fact the agent would have
        # said nothing of the sort. That is MAXIMUM impact, so the hypothetical
        # must be a non-empty string that differs from the response — returning
        # `response` here (the obvious fallback) silently reported zero impact
        # for the very turns where the fact mattered most.
        return EMPTY_ANSWER_SENTINEL
    return remainder


def store_impacted_fact(
    fact: str,
    tag: str = "observed",
    confidence: float | None = None,
) -> tuple[bool, str]:
    """Donne un consommateur réel à `should_store`.

    Tant que le verdict n'était que loggé, P19 calculait un score que personne
    ne lisait. Le fait retenu part maintenant dans le store de provenance (P16),
    taggé, pour que la décision soit consultable et non perdu.
    """
    fs = get_memory_fs()
    domain = "agent-impact"
    # add_observed / add_inferred refuse d'ecrire si le fichier de domaine
    # n'existe pas encore (`provenance_memory.py:344-346`, `:356-358`). Sans ce
    # premier poste, `should_store=True` n'ecrirait rien et le principe
    # resterait sans effet — le meme no-op que P16, traite a l'item 6.
    seed, _ = fs.add_stated(domain, f"Faits retenus par verification d'impact ({domain})")
    if not seed and not (fs.root / f"topics/{domain}.md").exists():
        return False, f"could not create memory domain {domain}"

    if tag == "inferred":
        return fs.add_inferred(domain, fact, confidence if confidence is not None else 0.0)
    if tag == "stated":
        return fs.add_stated(domain, fact)
    return fs.add_observed(domain, fact)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _token_set_hash(text: str, n: int = NGRAM) -> set[int] | None:
    tokens = text.split()
    if len(tokens) < n:
        return None
    result: set[int] = set()
    for i in range(len(tokens) - n + 1):
        ngram = " ".join(tokens[i : i + n])
        h = int(hashlib.sha256(ngram.encode()).hexdigest()[:16], 16)
        result.add(h)
    return result


app_context.caches.verifier: MemoryImpactVerifier | None = None


def get_memory_impact_verifier(threshold: float = DEFAULT_IMPACT_THRESHOLD) -> MemoryImpactVerifier:
    if app_context.caches.verifier is None:
        app_context.caches.verifier = MemoryImpactVerifier(threshold=threshold)
    return app_context.caches.verifier
