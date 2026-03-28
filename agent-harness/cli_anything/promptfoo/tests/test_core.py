"""
test_core.py - Unit tests for cli-anything-promptfoo

Tests Promptfoo backend with synthetic data.
No real Promptfoo installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  PROMPTFOO_MOCK=1 python -m pytest cli_anything/promptfoo/tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.promptfoo.utils import promptfoo_backend as pb


# -------------------------------------------------------------------
# Test: CommandResult dataclass
# -------------------------------------------------------------------

class TestCommandResult:
    def test_fields(self):
        r = pb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"
        assert r.returncode == 0

    def test_failure(self):
        r = pb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.returncode == 1
        assert r.error == "err"


# -------------------------------------------------------------------
# Test: find_promptfoo with mock
# -------------------------------------------------------------------

class TestFindPromptfoo:
    def test_find_promptfoo_mock(self, monkeypatch):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        path = pb.find_promptfoo()
        assert path == Path("/usr/bin/true")


# -------------------------------------------------------------------
# Test: Version
# -------------------------------------------------------------------

class TestVersion:
    def test_get_version_mock(self, monkeypatch):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        info = pb.get_version()
        assert info["success"] is True
        assert info["version"] == "0.80.0"


# -------------------------------------------------------------------
# Test: Config operations (mock)
# -------------------------------------------------------------------

class TestConfigMock:
    def test_init_config_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        config_path = str(tmp_path / "promptfoofile.yaml")
        result = pb.init_config(config_path)
        assert result.success is True
        assert Path(config_path).exists()

    def test_init_config_with_prompts(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        config_path = str(tmp_path / "promptfoofile.yaml")
        prompts = [{"id": "p1", "label": "Test Prompt", "prompt": "{{query}}"}]
        result = pb.init_config(config_path, prompts=prompts)
        assert result.success is True

    def test_read_config(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        config_path = str(tmp_path / "test.yaml")
        pb.init_config(config_path)
        info = pb.read_config(config_path)
        assert info["success"] is True
        assert "prompts" in info
        assert "providers" in info
        assert "tests" in info


# -------------------------------------------------------------------
# Test: Eval operations (mock)
# -------------------------------------------------------------------

class TestEvalMock:
    def test_run_eval_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        output_path = str(tmp_path / "output.json")
        result = pb.run_eval(output_path=output_path)
        assert result.success is True
        assert Path(output_path).exists()

    def test_run_eval_with_config_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        config_path = tmp_path / "pf.yaml"
        config_path.write_text("prompts:\n  - id: p1\nproviders:\n  - id: openai\ntests:\n  - vars:\n      q: test\n")
        output_path = str(tmp_path / "output.json")
        result = pb.run_eval(config_path=str(config_path), output_path=output_path)
        assert result.success is True

    def test_run_eval_with_filter_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        result = pb.run_eval(filter_pattern="test*")
        assert result.success is True

    def test_run_eval_with_temperature_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        result = pb.run_eval(temperature=0.7)
        assert result.success is True


# -------------------------------------------------------------------
# Test: Results parsing
# -------------------------------------------------------------------

class TestResults:
    def test_get_eval_results(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        output_path = str(tmp_path / "output.json")
        pb.run_eval(output_path=output_path)
        info = pb.get_eval_results(output_path)
        assert info["success"] is True
        assert "summary" in info
        assert info["summary"]["total"] == 1

    def test_get_eval_results_missing(self):
        info = pb.get_eval_results("/nonexistent/results.json")
        assert info["success"] is False

    def test_describe_result_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        output_path = str(tmp_path / "output.json")
        pb.run_eval(output_path=output_path)
        result = pb.describe_result(output_path)
        assert result.success is True
        assert "Total:" in result.output

    def test_get_metrics_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        output_path = str(tmp_path / "output.json")
        pb.run_eval(output_path=output_path)
        info = pb.get_metrics(output_path)
        assert info["success"] is True
        assert "summary" in info
        assert "assertion_stats" in info


# -------------------------------------------------------------------
# Test: Export
# -------------------------------------------------------------------

class TestExport:
    def test_export_results_json_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        output_path = str(tmp_path / "output.json")
        pb.run_eval(output_path=output_path)
        export_path = str(tmp_path / "export.json")
        result = pb.export_results(output_path, format="json", output_path=export_path)
        assert result.success is True
        assert Path(export_path).exists()

    def test_export_results_csv_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        output_path = str(tmp_path / "output.json")
        pb.run_eval(output_path=output_path)
        result = pb.export_results(output_path, format="csv")
        assert result.success is True
        assert "test,score,success" in result.output

    def test_export_results_table_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        output_path = str(tmp_path / "output.json")
        pb.run_eval(output_path=output_path)
        result = pb.export_results(output_path, format="table")
        assert result.success is True
        assert "Test" in result.output


# -------------------------------------------------------------------
# Test: Config modification
# -------------------------------------------------------------------

class TestConfigModification:
    def test_add_test_case_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        config_path = str(tmp_path / "pf.yaml")
        pb.init_config(config_path)
        result = pb.add_test_case(config_path, {"query": "What is 3+3?"})
        assert result.success is True

    def test_add_test_case_with_assertions_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        config_path = str(tmp_path / "pf.yaml")
        pb.init_config(config_path)
        assertions = [{"type": "contains", "value": "4"}]
        result = pb.add_test_case(config_path, {"query": "What is 2+2?"}, assertions=assertions)
        assert result.success is True

    def test_get_test_cases_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMPTFOO_MOCK", "1")
        config_path = str(tmp_path / "pf.yaml")
        pb.init_config(config_path)
        info = pb.get_test_cases(config_path)
        assert info["success"] is True
        assert info["count"] >= 0


# -------------------------------------------------------------------
# Test: CLI module import
# -------------------------------------------------------------------

class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.promptfoo import promptfoo_cli
        assert hasattr(promptfoo_cli, "cli")
        assert hasattr(promptfoo_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.promptfoo import utils
        assert hasattr(utils, "promptfoo_backend")
        b = utils.promptfoo_backend
        assert hasattr(b, "PROMPTFOO_VERSION")
        assert hasattr(b, "init_config")
        assert hasattr(b, "run_eval")
        assert hasattr(b, "get_eval_results")
        assert hasattr(b, "export_results")
        assert hasattr(b, "get_metrics")
