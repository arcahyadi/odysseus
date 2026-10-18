"""Tests pour AutoevalLoop."""

from unittest.mock import patch

from src.autoeval_loop import AutoevalLoop, EvalResult


def test_extract_pytest_pass_rate():
    loop = AutoevalLoop(".", "pytest tests/ -q", "pass_rate")
    output = "5 passed, 2 failed in 1.23s"
    score = loop._extract_metric(output, "pass_rate")
    assert abs(score - 5 / 7) < 0.01


def test_extract_json_metric():
    loop = AutoevalLoop(".", "python eval.py", "accuracy")
    output = '{"accuracy": 0.85, "loss": 0.3}'
    score = loop._extract_metric(output, "accuracy")
    assert score == 0.85


def test_improved_kept(tmp_path):
    loop = AutoevalLoop(str(tmp_path), "echo '10 passed'", "pass_rate")
    with patch.object(loop, "run_eval") as mock_eval:
        with patch.object(loop, "_get_git_hash", return_value="abc123"):
            mock_eval.return_value = EvalResult(score=0.9, raw_output="", success=True)
            run = loop.evaluate_last_change(score_baseline=0.7)
    assert run.action_taken == "kept"
    assert run.improved is True


def test_worse_reverted(tmp_path):
    loop = AutoevalLoop(str(tmp_path), "echo '3 passed, 7 failed'", "pass_rate")
    with patch.object(loop, "run_eval") as mock_eval:
        with patch.object(loop, "_get_git_hash", return_value="abc123"):
            with patch.object(loop, "_git_revert_to", return_value=True) as mock_revert:
                mock_eval.return_value = EvalResult(score=0.3, raw_output="", success=True)
                run = loop.evaluate_last_change(score_baseline=0.8)
    assert run.action_taken == "reverted"
    mock_revert.assert_called_once_with("abc123")
