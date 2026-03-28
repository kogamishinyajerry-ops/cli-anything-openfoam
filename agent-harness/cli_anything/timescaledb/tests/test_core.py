"""
test_core.py - Unit tests for cli-anything-timescaledb

Tests TimescaleDB backend with synthetic data.
No real TimescaleDB installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  TIMESCALEDB_MOCK=1 python -m pytest cli_anything/timescaledb/tests/test_core.py -v
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.timescaledb.utils import timescaledb_backend as tb


class TestCommandResult:
    def test_fields(self):
        r = tb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"

    def test_failure(self):
        r = tb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.error == "err"


class TestVersion:
    def test_get_version_mock(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        v = tb.get_version()
        assert v["success"] is True
        assert v["version"] == "2.14.2"


class TestHypertables:
    def test_list_hypertables_mock(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        info = tb.list_hypertables()
        assert info["success"] is True
        assert len(info["hypertables"]) == 2
        assert info["hypertables"][0]["Name"] == "conditions"

    def test_create_hypertable_mock(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        result = tb.create_hypertable("metrics", "time", chunk_interval="1 hour")
        assert result.success is True

    def test_create_hypertable_with_space_mock(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        result = tb.create_hypertable("metrics", "time", space_columns="device_id")
        assert result.success is True

    def test_hypertable_info_mock(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        info = tb.hypertable_info("metrics")
        assert info["success"] is True
        assert info["dimensions"] == 1


class TestAggregates:
    def test_create_continuous_aggregate_mock(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        result = tb.create_continuous_aggregate(
            "device_hourly", "metrics", "time", "1 hour"
        )
        assert result.success is True

    def test_list_continuous_aggregates_mock(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        info = tb.list_continuous_aggregates()
        assert info["success"] is True
        assert len(info["aggregates"]) == 1


class TestCompression:
    def test_enable_compression_mock(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        result = tb.enable_compression("metrics")
        assert result.success is True

    def test_compression_info_mock(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        info = tb.compression_info()
        assert info["success"] is True
        assert info["compression_ratio"] == 5.0


class TestData:
    def test_insert_from_csv_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        csv = tmp_path / "data.csv"
        csv.write_text("time,value\n2024-01-01,100\n2024-01-02,200\n")
        result = tb.insert_from_csv("metrics", str(csv))
        assert result.success is True
        assert "2 rows" in result.output

    def test_insert_from_csv_missing_file(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        result = tb.insert_from_csv("metrics", "/nonexistent/file.csv")
        assert result.success is False

    def test_query_mock(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        result = tb.query("SELECT * FROM metrics LIMIT 10")
        assert result.success is True


class TestRetention:
    def test_set_retention_policy_mock(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        result = tb.set_retention_policy("metrics", "30 days")
        assert result.success is True


class TestStats:
    def test_get_database_stats_mock(self, monkeypatch):
        monkeypatch.setenv("TIMESCALEDB_MOCK", "1")
        info = tb.get_database_stats()
        assert info["success"] is True
        assert info["hypertables"] == 3


class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.timescaledb import timescaledb_cli
        assert hasattr(timescaledb_cli, "cli")
        assert hasattr(timescaledb_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.timescaledb import utils
        assert hasattr(utils, "timescaledb_backend")
        b = utils.timescaledb_backend
        assert hasattr(b, "TIMESCALEDB_VERSION")
        assert hasattr(b, "create_hypertable")
        assert hasattr(b, "list_hypertables")
        assert hasattr(b, "create_continuous_aggregate")
        assert hasattr(b, "insert_from_csv")
        assert hasattr(b, "query")
