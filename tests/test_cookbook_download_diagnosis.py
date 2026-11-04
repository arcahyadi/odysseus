"""Regression tests for the download-side diagnosis helper (added 2026-10-03).

`_diagnose_serve_output` already existed but download failures surfaced only
as raw output tail text — this covers the four ROADMAP-named categories that
now produce a structured `{message, suggestions}` payload.
"""
from routes.cookbook_helpers import _diagnose_download_output


def test_diagnose_disk_full():
    out = "OSError: [Errno 28] No space left on device: '/models/Qwen2.5-7B-Q4_K_M.gguf.incomplete'"
    d = _diagnose_download_output(out)
    assert d and "out of space" in d["message"]
    assert any(s["op"] == "settings" for s in d["suggestions"])


def test_diagnose_gated_repo():
    out = (
        "huggingface_hub.errors.RepositoryNotFoundError: "
        "403 Forbidden: Access to model meta-llama/Llama-3.1-70B is restricted."
    )
    d = _diagnose_download_output(out)
    assert d and "gated" in d["message"]
    labels = [s["label"] for s in d["suggestions"]]
    assert any("license" in lbl for lbl in labels)
    assert any("HF token" in lbl for lbl in labels)


def test_diagnose_missing_quant_tag():
    out = (
        "Entry not found: Does not appear to have a file named "
        "qwen2.5-coder-32b-instruct-Q9_XX.gguf"
    )
    d = _diagnose_download_output(out)
    assert d and "doesn't exist" in d["message"]


def test_diagnose_transient_network_or_hf_transfer():
    out = (
        "requests.exceptions.ConnectionError: "
        "('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))\n"
        "hf_transfer: error while streaming"
    )
    d = _diagnose_download_output(out)
    assert d and "network" in d["message"]
    labels = [s["label"] for s in d["suggestions"]]
    assert any("hf_transfer" in lbl for lbl in labels)


def test_diagnose_download_traceback_fallback():
    out = "Traceback (most recent call last):\n  File 'hf.py'..."
    d = _diagnose_download_output(out)
    assert d and "traceback" in d["message"].lower()


def test_diagnose_download_no_noise_returns_none():
    assert _diagnose_download_output("") is None
    assert _diagnose_download_output("Download complete") is None
