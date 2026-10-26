"""Regression: /api/cookbook/hf-latest must go through hwfit's fit engine
instead of the old crude VRAM regex. The ranker gives the trending tab the
same architecture bonus, quant penalty, backend-support and VRAM/RAM fit
rules as the What-Fits view.
"""
from pathlib import Path


ROUTES = Path(__file__).resolve().parents[1] / "routes" / "cookbook_routes.py"
JS = Path(__file__).resolve().parents[1] / "static" / "js" / "cookbook.js"


def _routes_src() -> str:
    return ROUTES.read_text(encoding="utf-8")


def _js_src() -> str:
    return JS.read_text(encoding="utf-8")


def test_hf_latest_imports_the_hwfit_ranker_helpers():
    src = _routes_src()
    # Handler must pull analyze_model and the repo-name parsers from hwfit.
    assert "from services.hwfit.fit import analyze_model" in src
    assert "_infer_quant" in src
    assert "_parse_params_from_name" in src
    assert "_infer_context" in src


def test_hf_latest_drops_the_old_crude_vram_regex():
    src = _routes_src()
    # The regex-based estimator and its hand-rolled 30% headroom must be gone.
    assert "def _est_vram_fp16" not in src
    assert "est_fp16 * quant_mult" not in src
    assert "needed_vram = (est_vram * 1.3)" not in src


def test_hf_latest_uses_analyze_model_and_fit_level():
    src = _routes_src()
    assert "analyze_model(model, system)" in src
    assert 'result.get("fit_level")' in src
    # too_tight rows must be filtered when the caller supplied a vram budget.
    assert 'if vram_gb > 0 and fit_level == "too_tight"' in src


def test_hf_latest_accepts_host_and_forwards_hw_params():
    src = _routes_src()
    assert "host: str = \"\"" in src
    assert "ssh_port: str = \"\"" in src
    assert "platform: str = \"\"" in src
    assert "detect_system" in src


def test_hf_latest_frontend_forwards_server_params():
    src = _js_src()
    # Frontend must set host/ssh_port/platform on the querystring, not just vram_gb.
    assert "qp.set('host', hwInfo.host)" in src
    assert "qp.set('ssh_port', hwInfo.sshPort)" in src
    assert "qp.set('platform', hwInfo.platform)" in src


def test_hf_latest_response_contract_preserved():
    src = _routes_src()
    # Existing frontend expects these keys — keep them alongside the new
    # fit_level / score fields so the card renderer is unaffected.
    for key in ('"repo_id"', '"downloads"', '"likes"', '"createdAt"',
                '"tags"', '"pipeline_tag"', '"est_vram_gb"', '"needed_vram_gb"'):
        assert key in src
