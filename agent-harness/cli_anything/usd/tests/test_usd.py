"""
test_usd.py - Unit tests for cli-anything-usd

Tests USD backend with synthetic data.
No real USD installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  python -m pytest cli_anything/usd/tests/test_usd.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.usd.utils import usd_backend as ub


class TestCommandResult:
    """Test CommandResult dataclass."""

    def test_fields(self):
        """Test CommandResult fields."""
        r = ub.CommandResult(success=True, output="test output", returncode=0)
        assert r.success is True
        assert r.output == "test output"
        assert r.returncode == 0
        assert r.error == ""

    def test_failure(self):
        """Test CommandResult failure case."""
        r = ub.CommandResult(success=False, error="file not found", returncode=1)
        assert r.success is False
        assert r.error == "file not found"
        assert r.returncode == 1

    def test_with_duration(self):
        """Test CommandResult with duration."""
        r = ub.CommandResult(success=True, output="ok", returncode=0, duration_seconds=1.5)
        assert r.duration_seconds == 1.5


class TestVersion:
    """Test version detection."""

    def test_get_version_mock(self):
        """Test get_version in mock mode."""
        v = ub.get_version()
        assert v["success"] is True
        assert "version" in v
        assert "USD" in v["version"]


class TestFindUsdcat:
    """Test usdcat binary finder."""

    def test_find_usdcat_mock(self):
        """Test find_usdcat returns /usr/bin/true in mock mode."""
        p = ub.find_usdcat()
        assert p == Path("/usr/bin/true")


class TestFindUsdchecker:
    """Test usdchecker binary finder."""

    def test_find_usdchecker_mock(self):
        """Test find_usdchecker returns /usr/bin/true in mock mode."""
        p = ub.find_usdchecker()
        assert p == Path("/usr/bin/true")


class TestValidate:
    """Test USD validation."""

    def test_validate_missing_file(self):
        """Test validate with missing file returns error in non-mock mode."""
        # In mock mode, validation returns success for all paths
        # This test verifies the non-mocked behavior
        import subprocess
        original_mock = os.environ.pop("USD_MOCK", None)
        try:
            r = ub.validate_usd("/nonexistent/file.usda")
            assert r.success is False
            assert "not found" in r.error.lower()
        finally:
            if original_mock:
                os.environ["USD_MOCK"] = original_mock

    def test_validate_mock_success(self):
        """Test validate in mock mode returns success."""
        r = ub.validate_usd("/fake/file.usda")
        assert r.success is True
        assert r.returncode == 0


class TestUsdInfo:
    """Test USD stage info."""

    def test_usd_info_missing_file(self):
        """Test usd_info with missing file returns error in non-mock mode."""
        import subprocess
        original_mock = os.environ.pop("USD_MOCK", None)
        try:
            r = ub.usd_info("/nonexistent/file.usda")
            assert r["success"] is False
            assert "not found" in r["error"].lower()
        finally:
            if original_mock:
                os.environ["USD_MOCK"] = original_mock

    def test_usd_info_mock(self):
        """Test usd_info in mock mode returns synthetic info."""
        r = ub.usd_info("/fake/file.usda")
        assert r["success"] is True
        assert r["filename"] == "file.usda"
        assert "prims" in r
        assert "layers" in r
        assert r["mock"] is True


class TestConvert:
    """Test USD conversion."""

    def test_convert_missing_input(self):
        """Test convert with missing input returns error in non-mock mode."""
        original_mock = os.environ.pop("USD_MOCK", None)
        try:
            r = ub.convert_usd("/nonexistent/in.usda", "/tmp/out.usdc", "usdc")
            assert r.success is False
            assert "not found" in r.error.lower()
        finally:
            if original_mock:
                os.environ["USD_MOCK"] = original_mock

    def test_convert_mock_success(self):
        """Test convert in mock mode returns success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = Path(tmpdir) / "model.usda"
            inp.write_text("#usda 1.0\n")
            out = Path(tmpdir) / "model.usdc"
            r = ub.convert_usd(str(inp), str(out), "usdc")
            assert r.success is True
            assert "Converted" in r.output


class TestListLayers:
    """Test layer listing."""

    def test_list_layers_missing_file(self):
        """Test list_layers with missing file returns error in non-mock mode."""
        original_mock = os.environ.pop("USD_MOCK", None)
        try:
            r = ub.list_layers("/nonexistent/file.usda")
            assert r["success"] is False
            assert "not found" in r["error"].lower()
        finally:
            if original_mock:
                os.environ["USD_MOCK"] = original_mock

    def test_list_layers_mock(self):
        """Test list_layers in mock mode returns synthetic layers."""
        r = ub.list_layers("/fake/file.usda")
        assert r["success"] is True
        assert r["filename"] == "file.usda"
        assert "layers" in r
        assert r["layer_count"] == 2
        assert r["mock"] is True


class TestMock:
    """Test mock environment."""

    def test_mock_env_set(self):
        """Test USD_MOCK environment is set."""
        assert os.environ.get("USD_MOCK") == "1"
