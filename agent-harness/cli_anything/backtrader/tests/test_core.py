"""
test_core.py - Unit tests for cli-anything-backtrader

Tests Backtrader backend with synthetic data.
No real Backtrader installation required for most tests (mock mode).

Run:
  cd cli-anything-openfoam/agent-harness
  BACKTRADER_MOCK=1 python -m pytest cli_anything/backtrader/tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.backtrader.utils import backtrader_backend as bb


class TestCommandResult:
    def test_fields(self):
        r = bb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"
        assert r.returncode == 0

    def test_failure(self):
        r = bb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.returncode == 1


class TestVersion:
    def test_get_version_mock(self, monkeypatch):
        monkeypatch.setenv("BACKTRADER_MOCK", "1")
        v = bb.get_version()
        assert v["success"] is True
        assert v["version"] == "1.9.78.123"


class TestStrategies:
    def test_list_strategies(self):
        result = bb.list_strategies()
        assert result["success"] is True
        assert "sma_crossover" in result["strategies"]
        assert "rsi" in result["strategies"]
        assert "macd" in result["strategies"]
        assert "mean_reversion" in result["strategies"]

    def test_get_strategy_info_valid(self):
        info = bb.get_strategy_info("sma_crossover")
        assert info["success"] is True
        assert info["strategy"] == "sma_crossover"
        assert "params" in info

    def test_get_strategy_info_invalid(self):
        info = bb.get_strategy_info("nonexistent")
        assert info["success"] is False

    def test_generate_strategy(self, tmp_path):
        out = str(tmp_path / "strategy.py")
        result = bb.generate_strategy("sma_crossover", output_path=out)
        assert result["success"] is True
        assert Path(out).exists()

    def test_generate_strategy_unknown(self):
        result = bb.generate_strategy("nonexistent")
        assert result["success"] is False


class TestBacktestMock:
    def test_run_backtest_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BACKTRADER_MOCK", "1")
        data_path = tmp_path / "data.csv"
        data_path.write_text("Date,Open,High,Low,Close,Volume\n2024-01-01,100,101,99,100,1000\n")
        output_path = str(tmp_path / "result.json")
        result = bb.run_backtest(
            str(data_path), strategy="sma_crossover",
            cash=10000.0, output_path=output_path
        )
        assert result.success is True
        assert Path(output_path).exists()
        data = json.loads(result.output)
        assert data["return_pct"] == 12.3

    def test_run_backtest_with_params_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BACKTRADER_MOCK", "1")
        data_path = tmp_path / "data.csv"
        data_path.write_text("Date,Open,High,Low,Close,Volume\n2024-01-01,100,101,99,100,1000\n")
        result = bb.run_backtest(
            str(data_path), strategy="rsi",
            cash=50000.0, rsi_period=7, rsi_upper=80, rsi_lower=20
        )
        assert result.success is True

    def test_run_backtest_missing_data(self, monkeypatch):
        monkeypatch.setenv("BACKTRADER_MOCK", "1")
        result = bb.run_backtest("/nonexistent/data.csv", strategy="sma_crossover")
        assert result.success is False

    def test_run_backtest_unknown_strategy(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BACKTRADER_MOCK", "1")
        data_path = tmp_path / "data.csv"
        data_path.write_text("Date,Open,High,Low,Close,Volume\n")
        result = bb.run_backtest(str(data_path), strategy="nonexistent")
        assert result.success is False

    def test_run_backtest_with_analyzers_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BACKTRADER_MOCK", "1")
        data_path = tmp_path / "data.csv"
        data_path.write_text("Date,Open,High,Low,Close,Volume\n2024-01-01,100,101,99,100,1000\n")
        result = bb.run_backtest_with_analyzers(str(data_path), strategy="sma_crossover")
        assert result.success is True
        data = json.loads(result.output)
        assert "sharpe_ratio" in data
        assert "max_drawdown_pct" in data


class TestData:
    def test_load_csv_data(self, tmp_path):
        data_path = tmp_path / "prices.csv"
        data_path.write_text("Date,Open,High,Low,Close,Volume\n2024-01-01,100,101,99,100,1000\n")
        info = bb.load_csv_data(str(data_path))
        assert info["success"] is True
        assert info["rows"] == 2

    def test_load_csv_data_missing(self):
        info = bb.load_csv_data("/nonexistent/file.csv")
        assert info["success"] is False

    def test_get_data_format_info(self):
        info = bb.get_data_format_info()
        assert info["success"] is True
        assert "columns" in info


class TestFetchData:
    def test_fetch_yahoo_data_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BACKTRADER_MOCK", "1")
        output_path = str(tmp_path / "aapl.csv")
        result = bb.fetch_yahoo_data("AAPL", "2024-01-01", "2024-12-31", output_path)
        assert result.success is True
        assert Path(output_path).exists()


class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.backtrader import backtrader_cli
        assert hasattr(backtrader_cli, "cli")
        assert hasattr(backtrader_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.backtrader import utils
        assert hasattr(utils, "backtrader_backend")
        b = utils.backtrader_backend
        assert hasattr(b, "BACKTRADER_VERSION")
        assert hasattr(b, "run_backtest")
        assert hasattr(b, "list_strategies")
        assert hasattr(b, "generate_strategy")
