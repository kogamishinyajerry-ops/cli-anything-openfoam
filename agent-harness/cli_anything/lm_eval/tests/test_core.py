"""
test_core.py - Unit tests for cli-anything-lm-eval

Tests LM Eval backend and CLI with synthetic data.
No real lm-evaluation-harness required.

Run:
  cd cli-anything-openfoam/agent-harness
  LM_EVAL_MOCK=1 python -m pytest cli_anything/lm_eval/tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.lm_eval.utils import lm_eval_backend as lb


# -------------------------------------------------------------------
# Test: CommandResult dataclass
# -------------------------------------------------------------------

class TestCommandResult:
    def test_fields(self):
        r = lb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"
        assert r.returncode == 0

    def test_failure(self):
        r = lb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.returncode == 1
        assert r.error == "err"


# -------------------------------------------------------------------
# Test: Tasks
# -------------------------------------------------------------------

class TestTasks:
    def test_tasks_exist(self):
        expected = ["hellaswag", "mmlu", "truthful_qa", "gsm8k", "humaneval", "arc", "boolq"]
        for t in expected:
            assert t in lb.LM_EVAL_TASKS, f"Missing task: {t}"

    def test_task_structure(self):
        for name, info in lb.LM_EVAL_TASKS.items():
            assert "description" in info
            assert "type" in info


# -------------------------------------------------------------------
# Test: Mock evaluation
# -------------------------------------------------------------------

class TestEvaluateMock:
    def test_evaluate_mock_single_task(self, monkeypatch):
        monkeypatch.setenv("LM_EVAL_MOCK", "1")
        result = lb.evaluate(
            model="hf",
            model_args="pretrained=phi-2",
            tasks=["hellaswag"],
        )
        assert result["success"] is True
        assert "hellaswag" in result["scores"]
        assert 0.0 <= result["scores"]["hellaswag"]["acc"] <= 1.0

    def test_evaluate_mock_multiple_tasks(self, monkeypatch):
        monkeypatch.setenv("LM_EVAL_MOCK", "1")
        result = lb.evaluate(
            model="hf",
            tasks=["mmlu", "truthful_qa", "gsm8k"],
        )
        assert result["success"] is True
        assert "mmlu" in result["scores"]
        assert "truthful_qa" in result["scores"]
        assert "gsm8k" in result["scores"]

    def test_evaluate_mock_with_output(self, monkeypatch):
        monkeypatch.setenv("LM_EVAL_MOCK", "1")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name

        result = lb.evaluate(
            model="hf",
            tasks=["hellaswag"],
            output_path=out_path,
        )
        Path(out_path).unlink()

        assert result["success"] is True
        assert Path(out_path).exists() is False  # already deleted

    def test_evaluate_mock_code_task(self, monkeypatch):
        monkeypatch.setenv("LM_EVAL_MOCK", "1")
        result = lb.evaluate(
            model="hf",
            tasks=["humaneval"],
        )
        assert result["success"] is True
        assert "humaneval" in result["scores"]
        assert "pass@1" in result["scores"]["humaneval"]

    def test_evaluate_mock_math_task(self, monkeypatch):
        monkeypatch.setenv("LM_EVAL_MOCK", "1")
        result = lb.evaluate(
            model="hf",
            tasks=["gsm8k"],
        )
        assert result["success"] is True
        assert "gsm8k" in result["scores"]
        assert "exact_match" in result["scores"]["gsm8k"]


# -------------------------------------------------------------------
# Test: Task listing
# -------------------------------------------------------------------

class TestListTasks:
    def test_list_tasks_mock(self, monkeypatch):
        monkeypatch.setenv("LM_EVAL_MOCK", "1")
        result = lb.list_tasks()
        assert result["success"] is True
        assert "hellaswag" in result["tasks"]
        assert "mmlu" in result["tasks"]

    def test_get_task_info(self):
        result = lb.get_task_info("hellaswag")
        assert result["success"] is True
        assert result["task"] == "hellaswag"
        assert "description" in result

    def test_get_task_info_unknown(self):
        result = lb.get_task_info("nonexistent_task_xyz")
        assert result["success"] is False


# -------------------------------------------------------------------
# Test: Model configs
# -------------------------------------------------------------------

class TestModelConfigs:
    def test_model_configs_exist(self):
        assert "hf" in lb.MODEL_CONFIGS
        assert "openai" in lb.MODEL_CONFIGS
        assert "anthropic" in lb.MODEL_CONFIGS
        assert "vllm" in lb.MODEL_CONFIGS

    def test_model_config_structure(self):
        for name, cfg in lb.MODEL_CONFIGS.items():
            assert "name" in cfg
            assert "args" in cfg
            assert "required" in cfg


# -------------------------------------------------------------------
# Test: Result formatting
# -------------------------------------------------------------------

class TestFormatResults:
    def test_format_results_table(self, monkeypatch):
        monkeypatch.setenv("LM_EVAL_MOCK", "1")
        result = lb.evaluate(model="hf", tasks=["hellaswag", "mmlu"])
        table = lb.format_results_table(result)
        assert "hellaswag" in table
        assert "mmlu" in table
        assert "acc" in table


# -------------------------------------------------------------------
# Test: Parse output
# -------------------------------------------------------------------

class TestParseOutput:
    def test_parse_eval_output(self):
        output = """
        {
            'hellaswag': {'acc': 0.85, 'acc_stderr': 0.01},
            'mmlu': {'acc': 0.70, 'acc_stderr': 0.02}
        }
        """
        result = lb.parse_eval_output(output, "")
        assert "hellaswag" in result["results"]
        assert result["results"]["hellaswag"]["acc"] == 0.85

    def test_parse_empty_output(self):
        result = lb.parse_eval_output("", "")
        assert result["success"] is True
        assert result["results"] == {}


# -------------------------------------------------------------------
# Test: CLI module import
# -------------------------------------------------------------------

class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.lm_eval import lm_eval_cli
        assert hasattr(lm_eval_cli, "cli")
        assert hasattr(lm_eval_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.lm_eval import utils
        assert hasattr(utils, "lm_eval_backend")
        b = utils.lm_eval_backend
        assert hasattr(b, "LM_EVAL_VERSION")
        assert hasattr(b, "evaluate")
        assert hasattr(b, "list_tasks")
        assert hasattr(b, "LM_EVAL_TASKS")
