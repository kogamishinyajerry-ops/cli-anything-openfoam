"""
test_core.py - Unit tests for cli-anything-vectorbt

Tests VectorBT backend with synthetic data.
No real VectorBT installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  python -m pytest cli_anything/vectorbt/tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.vectorbt.utils import vectorbt_backend as vb


class TestCommandResult:
    def test_fields(self):
        r = vb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True

    def test_failure(self):
        r = vb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False


class TestVersion:
    def test_get_version_mock(self):
        v = vb.get_version()
        assert v["success"] is True
        assert "version" in v


class TestStrategies:
    def test_list_strategies(self):
        r = vb.list_strategies()
        assert r["success"] is True
        assert "sma_cross" in r["strategies"]
        assert "rsi" in r["strategies"]

    def test_strategies_have_descriptions(self):
        r = vb.list_strategies()
        assert "descriptions" in r
        assert len(r["descriptions"]) > 0


class TestRunBacktest:
    def test_run_missing_data(self):
        r = vb.run_backtest("/nonexistent/data.csv")
        assert r.success is False
        assert "not found" in r.error

    def test_run_unknown_strategy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = Path(tmpdir) / "data.csv"
            data.write_text("open,high,low,close,volume\n100,101,99,100,1000\n")
            r = vb.run_backtest(str(data), strategy="nonexistent")
            assert r.success is False
            assert "Unknown" in r.error

    def test_run_success_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = Path(tmpdir) / "data.csv"
            data.write_text("open,high,low,close,volume\n100,101,99,100,1000\n")
            r = vb.run_backtest(str(data))
            assert r.success is True
            result = json.loads(r.output)
            assert result["strategy"] == "sma_cross"
            assert result["return_pct"] > 0


class TestGenerateReport:
    def test_report_missing_results(self):
        r = vb.generate_report("/nonexistent/results.json", "/tmp/report.html")
        assert r.success is False

    def test_report_success_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = Path(tmpdir) / "results.json"
            results.write_text('{"success": true, "strategy": "sma_cross"}')
            out = Path(tmpdir) / "report.html"
            r = vb.generate_report(str(results), str(out))
            assert r.success is True
            assert out.exists()


class TestPython:
    def test_find_python(self):
        p = vb.find_python()
        assert p.exists()
        assert "python" in str(p)
