// Per-backend × per-model install recipes for the Dependencies tab.
//
// Each entry says: when you're about to serve `model` on `backend`, here's
// the exact shell sequence to make the venv + install the right packages.
// Entries are matched first-hit; put the more specific patterns ABOVE the
// generic fallback for that backend.

// Recipes hold ONLY the install command(s). The renderer prepends a
// `source <venv>/bin/activate` line for context using the active server's
// configured envPath; the Run button reuses env_prefix to activate that
// same venv before executing, so the install lands in your existing
// environment rather than a fresh `.venv` in some random CWD.
const _RECIPES = [
  // ── vllm ──────────────────────────────────────────────────────────────
  // MiniMax M2/M2.7 — same generic vllm install for now; kept as its own
  // entry so future model-specific patches (FP8 quants, custom kernels)
  // land in one obvious place without touching the catch-all.
  {
    backend: 'vllm',
    label: 'MiniMax M2 / M2.7',
    match: (m) => /minimax[-_]?m\s?2(\.7)?/i.test(m || ''),
    commands: [
      'uv pip install -U vllm --torch-backend auto',
    ],
  },
  // Generic vllm fallback — auto-resolves the right torch backend (CUDA
  // 12.x / 12.4 / ROCm) at install time so users don't have to know.
  {
    backend: 'vllm',
    label: 'Any vLLM model',
    match: () => true,
    commands: [
      'uv pip install -U vllm --torch-backend auto',
    ],
  },

  // ── sglang ────────────────────────────────────────────────────────────
  {
    backend: 'sglang',
    label: 'Any SGLang model',
    match: () => true,
    commands: [
      'uv pip install -U "sglang[all]" --torch-backend auto',
    ],
  },

  // ── llama.cpp ─────────────────────────────────────────────────────────
  // The cookbook-side rebuild path covers this for users who already have
  // the engine compiled — but for a fresh box, surface a sane install.
  {
    backend: 'llama_cpp',
    label: 'Any GGUF model',
    match: () => true,
    commands: [
      'CMAKE_ARGS="-DGGML_CUDA=on" uv pip install -U "llama-cpp-python[server]"',
    ],
  },
];

// Backends we surface a recipe panel for. Other rows in the Dependencies
// list keep the existing flat Install/Reinstall button without an expand
// affordance.
export const RECIPE_BACKENDS = new Set(['vllm', 'sglang', 'llama_cpp']);

// All recipe entries for a given backend, in catalog order. The first one
// is the model-specific match (when present); the last is always the
// generic fallback.
export function recipesForBackend(backend) {
  return _RECIPES.filter((r) => r.backend === backend);
}

// Pick the best recipe for a backend + model id. Returns the catalog
// fallback when nothing more specific matches, or null if the backend
// isn't in the catalog at all.
export function pickRecipe(backend, modelId) {
  const candidates = recipesForBackend(backend);
  if (!candidates.length) return null;
  for (const r of candidates) {
    try { if (r.match(modelId)) return r; } catch (_) {}
  }
  return candidates[candidates.length - 1] || null;
}
