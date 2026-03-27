"""
test_core.py - Unit tests for cli-anything-xfoil

Tests XFoil backend and CLI with synthetic data.
No real XFoil installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  XFOIL_MOCK=1 python -m pytest cli_anything/xfoil/tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.xfoil.utils import xfoil_backend as xb


# -------------------------------------------------------------------
# Test: CommandResult dataclass
# -------------------------------------------------------------------

class TestCommandResult:
    def test_fields(self):
        r = xb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"

    def test_failure(self):
        r = xb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.returncode == 1


# -------------------------------------------------------------------
# Test: Presets
# -------------------------------------------------------------------

class TestPresets:
    def test_presets_exist(self):
        expected = ["naca0012", "naca2412", "naca4412", "naca4415", "naca6409"]
        for p in expected:
            assert p in xb.AIRFOIL_PRESETS, f"Missing preset: {p}"

    def test_preset_structure(self):
        for name, info in xb.AIRFOIL_PRESETS.items():
            assert "type" in info
            assert "series" in info
            assert "description" in info


# -------------------------------------------------------------------
# Test: Parse analyze output
# -------------------------------------------------------------------

class TestParseAnalyze:
    def test_parse_cl_cd_cm(self):
        output = """
  XFOIL   Version 6.99

   ALS   = 5.000   CL =   0.8123   CD =   0.01234   CDp =  0.00567
   CM   =  -0.0456   CD =   0.01234   CDp =  0.00567
   L/D  =  65.81
   CPmin =  -0.6789
   Top transition xtr = 0.1234
   Bot transition xtr = 0.5678
        """
        data = xb.parse_analyze_output(output)
        assert data["CL"] == 0.8123
        assert abs(data["CD"] - 0.01234) < 1e-6
        assert abs(data["CM"] - (-0.0456)) < 1e-6
        assert abs(data["L_D"] - 65.81) < 0.01
        assert abs(data["CP_min"] - (-0.6789)) < 1e-4

    def test_parse_empty(self):
        data = xb.parse_analyze_output("")
        assert data["CL"] is None
        assert data["CD"] is None

    def test_parse_transition(self):
        output = "Top transition xtr = 0.2345\nBot transition xtr = 0.6789\n"
        data = xb.parse_analyze_output(output)
        assert data["top_transition"] == 0.2345
        assert data["bot_transition"] == 0.6789


# -------------------------------------------------------------------
# Test: Parse polar output
# -------------------------------------------------------------------

class TestParsePolar:
    def test_parse_polar_data_lines(self):
        output = """
  XFOIL   Version 6.99

   ALS   =  0.000   CL =   0.5000   CD =   0.02000   CDp =  0.01000   CM =  -0.0300
   ALS   =  1.000   CL =   0.7000   CD =   0.02200   CDp =  0.01100   CM =  -0.0350
   ALS   =  2.000   CL =   0.9000   CD =   0.02400   CDp =  0.01200   CM =  -0.0400
        """
        data = xb.parse_polar_output(output)
        assert data["n_points"] == 3
        assert data["data"][0]["alpha"] == 0.0
        assert abs(data["data"][0]["CL"] - 0.5) < 1e-6
        assert data["data"][1]["alpha"] == 1.0
        assert data["data"][2]["alpha"] == 2.0

    def test_parse_empty_polar(self):
        data = xb.parse_polar_output("")
        assert data["n_points"] == 0
        assert data["success"] is False


# -------------------------------------------------------------------
# Test: Parse polar file
# -------------------------------------------------------------------

class TestParsePolarFile:
    def test_parse_polar_file(self):
        content = """#  NACA 4412   Re =  3.000E+06   M =  0.000   Iters =  100
  0.00000   0.50000   0.02000   0.01000  -0.0300   0.1234   0.5678
  1.00000   0.70000   0.02200   0.01100  -0.0350   0.2000   0.5000
  2.00000   0.90000   0.02400   0.01200  -0.0400   0.3000   0.4000
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
            f.write(content)
            f.flush()
            result = xb.parse_polar_file(Path(f.name))

        assert result["success"] is True
        assert result["n_points"] == 3
        assert result["data"][0]["CL"] == 0.5
        assert result["data"][0]["alpha"] == 0.0
        Path(f.name).unlink()

    def test_missing_polar_file(self):
        result = xb.parse_polar_file(Path("/nonexistent/polar.dat"))
        assert result["success"] is False
        assert "error" in result


# -------------------------------------------------------------------
# Test: CLI module import
# -------------------------------------------------------------------

class TestCLIModule:
    """Verify CLI module can be imported."""

    def test_cli_module_imports(self):
        """xfoil_cli module imports without error."""
        from cli_anything.xfoil import xfoil_cli
        assert hasattr(xfoil_cli, "cli")
        assert hasattr(xfoil_cli, "main")

    def test_backend_module_imports(self):
        """xfoil_backend module imports without error."""
        from cli_anything.xfoil import utils
        assert hasattr(utils, "xfoil_backend")
        b = utils.xfoil_backend
        assert hasattr(b, "AIRFOIL_PRESETS")
        assert hasattr(b, "parse_analyze_output")
        assert hasattr(b, "parse_polar_output")

