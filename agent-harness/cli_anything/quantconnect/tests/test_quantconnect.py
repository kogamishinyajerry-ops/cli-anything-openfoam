"""
test_core.py - Unit tests for cli-anything-quantconnect

Tests QuantConnect Lean backend with synthetic data.
No real Lean installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  python -m pytest cli_anything/quantconnect/tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.quantconnect.utils import quantconnect_backend as qb


class TestCommandResult:
    def test_fields(self):
        r = qb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True

    def test_failure(self):
        r = qb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False


class TestVersion:
    def test_get_version_mock(self):
        v = qb.get_version()
        assert v["success"] is True
        assert "version" in v


class TestStatus:
    def test_get_status_mock(self):
        s = qb.get_status()
        assert s["success"] is True
        assert s["api_connected"] is True


class TestCreateProject:
    def test_create_project_mock(self):
        r = qb.create_project("test-algo", language="python")
        assert r.success is True
        assert "test-algo" in r.output


class TestListProjects:
    def test_list_projects_mock(self):
        r = qb.list_projects()
        assert r["success"] is True
        assert len(r["projects"]) >= 1


class TestBacktest:
    def test_backtest_missing_project(self):
        r = qb.run_backtest("/nonexistent/project")
        assert r.success is False

    def test_backtest_success_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "TestProject"
            proj.mkdir()
            (proj / "main.py").write_text("# algo")
            r = qb.run_backtest(str(proj))
            assert r.success is True
            assert "Backtest completed" in r.output


class TestReadResults:
    def test_read_results_missing_file(self):
        r = qb.read_backtest_results("/nonexistent/results.json")
        assert r["success"] is False

    def test_read_results_mock_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = Path(tmpdir) / "results.json"
            results.write_text('{"statistics": {"Return": "12.5%"}}')
            r = qb.read_backtest_results(str(results))
            assert r["success"] is True


class TestLive:
    def test_deploy_missing_project(self):
        r = qb.deploy_live("/nonexistent")
        assert r.success is False

    def test_deploy_success_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "TestProject"
            proj.mkdir()
            (proj / "main.py").write_text("# algo")
            r = qb.deploy_live(str(proj))
            assert r.success is True
            assert "Live deployment" in r.output


class TestOptimize:
    def test_optimize_missing_project(self):
        r = qb.optimize("/nonexistent")
        assert r.success is False

    def test_optimize_success_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "TestProject"
            proj.mkdir()
            (proj / "main.py").write_text("# algo")
            r = qb.optimize(str(proj))
            assert r.success is True
            assert "Optimization complete" in r.output


class TestFindLean:
    def test_find_lean_mock(self):
        p = qb.find_lean()
        assert p == Path("/usr/bin/true")


class TestMock:
    def test_mock_env_set(self):
        assert os.environ.get("QC_MOCK") == "1"
