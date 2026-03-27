"""
test_core.py - Unit tests for cli-anything-ragas

Tests RAGAS backend and CLI with synthetic data.
No real RAGAS/OpenAI API required.

Run:
  cd cli-anything-openfoam/agent-harness
  RAGAS_MOCK=1 python -m pytest cli_anything/ragas/tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.ragas.utils import ragas_backend as rb


# -------------------------------------------------------------------
# Test: CommandResult dataclass
# -------------------------------------------------------------------

class TestCommandResult:
    def test_fields(self):
        r = rb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"
        assert r.returncode == 0

    def test_failure(self):
        r = rb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.returncode == 1
        assert r.error == "err"


# -------------------------------------------------------------------
# Test: Metrics
# -------------------------------------------------------------------

class TestMetrics:
    def test_metrics_exist(self):
        expected = [
            "faithfulness",
            "answer_relevancy",
            "context_relevancy",
            "context_precision",
            "context_recall",
            "answer_correctness",
            "answer_similarity",
        ]
        for m in expected:
            assert m in rb.RAGAS_METRICS, f"Missing metric: {m}"

    def test_metric_structure(self):
        for name, info in rb.RAGAS_METRICS.items():
            assert "description" in info
            assert "llm_required" in info
            assert isinstance(info["llm_required"], bool)


# -------------------------------------------------------------------
# Test: Dataset loading
# -------------------------------------------------------------------

class TestDatasetLoading:
    def test_load_json(self):
        content = [
            {"user_input": "What is X?", "retrieved_contexts": ["X is Y"], "response": "X is Y"},
            {"user_input": "What is Z?", "retrieved_contexts": ["Z is W"], "response": "Z is W"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(content, f)
            f.flush()
            samples = rb.load_dataset_from_json(f.name)
            Path(f.name).unlink()

        assert len(samples) == 2
        assert samples[0]["user_input"] == "What is X?"

    def test_load_json_missing_file(self):
        with pytest.raises(FileNotFoundError):
            rb.load_dataset_from_json("/nonexistent/file.json")

    def test_load_csv(self):
        content = "user_input,response,reference\nWhat is X?,X is Y,Correct"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(content)
            f.flush()
            samples = rb.load_dataset_from_csv(f.name)
            Path(f.name).unlink()

        assert len(samples) == 1
        assert samples[0]["user_input"] == "What is X?"


# -------------------------------------------------------------------
# Test: Evaluation (mock mode)
# -------------------------------------------------------------------

class TestEvaluateMock:
    def test_evaluate_dataset_mock(self, monkeypatch):
        monkeypatch.setenv("RAGAS_MOCK", "1")
        samples = [
            {"user_input": "Q1", "retrieved_contexts": ["C1"], "response": "A1"},
            {"user_input": "Q2", "retrieved_contexts": ["C2"], "response": "A2"},
        ]
        result = rb.evaluate_dataset(
            samples=samples,
            metrics=["faithfulness", "answer_relevancy"],
        )
        assert result["success"] is True
        assert result["n_samples"] == 2
        assert "faithfulness" in result["scores"]
        assert "answer_relevancy" in result["scores"]
        assert 0.0 <= result["scores"]["faithfulness"]["mean"] <= 1.0

    def test_evaluate_from_json_mock(self, monkeypatch):
        monkeypatch.setenv("RAGAS_MOCK", "1")
        content = [
            {"user_input": "Q1", "retrieved_contexts": ["C1"], "response": "A1"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(content, f)
            f.flush()
            result = rb.evaluate_from_json(
                json_file=f.name,
                metrics=["context_relevancy"],
            )
            Path(f.name).unlink()

        assert result["success"] is True
        assert "context_relevancy" in result["scores"]

    def test_evaluate_from_csv_mock(self, monkeypatch):
        monkeypatch.setenv("RAGAS_MOCK", "1")
        content = "user_input,response\nWhat is X?,X is Y"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(content)
            f.flush()
            result = rb.evaluate_from_csv(
                csv_file=f.name,
                metrics=["faithfulness"],
            )
            Path(f.name).unlink()

        assert result["success"] is True

    def test_evaluate_output_file_mock(self, monkeypatch):
        monkeypatch.setenv("RAGAS_MOCK", "1")
        samples = [{"user_input": "Q", "retrieved_contexts": ["C"], "response": "A"}]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name
        result = rb.evaluate_dataset(
            samples=samples,
            metrics=["answer_relevancy"],
            output_file=out_path,
        )
        Path(out_path).unlink()
        assert result["success"] is True

    def test_evaluate_unknown_metric_mock(self, monkeypatch):
        monkeypatch.setenv("RAGAS_MOCK", "1")
        samples = [{"user_input": "Q", "retrieved_contexts": ["C"], "response": "A"}]
        # Mock mode skips unknown metrics (no error, just ignores them)
        result = rb.evaluate_dataset(
            samples=samples,
            metrics=["unknown_metric"],
        )
        assert result["success"] is True
        assert "unknown_metric" not in result["scores"]


# -------------------------------------------------------------------
# Test: Export CSV
# -------------------------------------------------------------------

class TestExport:
    def test_export_results_csv(self, monkeypatch):
        monkeypatch.setenv("RAGAS_MOCK", "1")
        results = {
            "success": True,
            "n_samples": 2,
            "scores": {
                "faithfulness": {
                    "mean": 0.85,
                    "scores": [0.8, 0.9],
                },
                "answer_relevancy": {
                    "mean": 0.75,
                    "scores": [0.7, 0.8],
                },
            },
        }
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            out_path = f.name

        result = rb.export_results_csv(results, out_path)
        Path(out_path).unlink()

        assert result.success is True
        assert "Exported" in result.output

    def test_export_empty_scores(self):
        results = {"success": True, "scores": {}}
        result = rb.export_results_csv(results, "/tmp/test.csv")
        assert result.success is False


# -------------------------------------------------------------------
# Test: CLI module import
# -------------------------------------------------------------------

class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.ragas import ragas_cli
        assert hasattr(ragas_cli, "cli")
        assert hasattr(ragas_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.ragas import utils
        assert hasattr(utils, "ragas_backend")
        b = utils.ragas_backend
        assert hasattr(b, "RAGAS_VERSION")
        assert hasattr(b, "evaluate_dataset")
        assert hasattr(b, "RAGAS_METRICS")
        assert hasattr(b, "load_dataset_from_json")
