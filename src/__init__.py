# src/__init__.py
# Expose IntentGate (classifier) + hash-edit validator.
# NOTE: llm_router.ModelRouter was removed (M3.1) — graded REDUNDANT vs the native
# model/provider resolver (resolve_endpoint). See .planning/intel/INDEX.md §2.
from src.hash_edit_validator import compute_file_hash, validate_and_edit
from src.intent_gate import classify_by_word_count, classify_intent

__all__ = [
    "classify_intent",
    "classify_by_word_count",
    "compute_file_hash",
    "validate_and_edit",
]
