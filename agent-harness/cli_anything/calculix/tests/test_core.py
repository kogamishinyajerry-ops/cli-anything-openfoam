"""
test_core.py - Unit tests for cli-anything-calculix

Tests Calculix backend with synthetic data.
No real Calculix installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  CALCULIX_MOCK=1 python -m pytest cli_anything/calculix/tests/test_core.py -v
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.calculix.utils import calculix_backend as cb


class TestCommandResult:
    def test_fields(self):
        r = cb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"

    def test_failure(self):
        r = cb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.error == "err"


class TestFindCCX:
    def test_find_ccx_mock(self, monkeypatch):
        monkeypatch.setenv("CALCULIX_MOCK", "1")
        path = cb.find_ccx()
        assert path == Path("/usr/bin/true")

    def test_find_cgx_mock(self, monkeypatch):
        monkeypatch.setenv("CALCULIX_MOCK", "1")
        path = cb.find_cgx()
        assert path == Path("/usr/bin/true")


class TestVersion:
    def test_get_version_mock(self, monkeypatch):
        monkeypatch.setenv("CALCULIX_MOCK", "1")
        v = cb.get_version()
        assert v["success"] is True
        assert v["version"] == "2.21"


class TestInputFile:
    def test_create_static_input(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CALCULIX_MOCK", "1")
        out = str(tmp_path / "test.inp")
        result = cb.create_static_input(out, title="Test Beam")
        assert result.success is True
        assert Path(out).exists()
        content = Path(out).read_text()
        assert "Test Beam" in content
        assert "*MATERIAL" in content
        assert "*STEP" in content

    def test_read_inp_info(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CALCULIX_MOCK", "1")
        inp = tmp_path / "beam.inp"
        inp.write_text("*HEADING\nTest Model\n*NODE\n1, 0, 0, 0\n2, 100, 0, 0\n")
        info = cb.read_inp_info(str(inp))
        assert info["success"] is True

    def test_read_inp_info_missing(self):
        info = cb.read_inp_info("/nonexistent.inp")
        assert info["success"] is False


class TestSolve:
    def test_solve_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CALCULIX_MOCK", "1")
        inp = tmp_path / "test.inp"
        inp.write_text("*HEADING\nTest\n")
        result = cb.solve(str(inp))
        assert result.success is True

    def test_solve_missing_file(self, monkeypatch):
        monkeypatch.setenv("CALCULIX_MOCK", "1")
        result = cb.solve("/nonexistent.inp")
        assert result.success is False

    def test_solve_modal_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CALCULIX_MOCK", "1")
        inp = tmp_path / "test.inp"
        inp.write_text("*HEADING\nTest\n")
        result = cb.solve_modal(str(inp), modes=5)
        assert result.success is True
        assert "12.50" in result.output  # Mock frequencies


class TestResults:
    def test_read_dat_file_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CALCULIX_MOCK", "1")
        # Create a mock DAT file with displacement data
        dat = tmp_path / "test.dat"
        dat.write_text("""
CALCULIX VERIFICATION OUTPUT

DISPLACEMENTS

      1  0.000000E+00  0.000000E+00  0.000000E+00
      2  1.234000E-01  0.000000E+00  0.000000E+00
""")
        info = cb.read_dat_file(str(dat))
        assert info["success"] is True
        assert len(info.get("displacements", [])) == 2

    def test_read_dat_file_missing(self):
        info = cb.read_dat_file("/nonexistent.dat")
        assert info["success"] is False

    def test_export_to_vtk_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CALCULIX_MOCK", "1")
        dat = tmp_path / "test.dat"
        dat.write_text("DISPLACEMENTS\n1 0 0 0\n")
        out = str(tmp_path / "test.vtk")
        result = cb.export_to_vtk(str(dat), out)
        assert result.success is True
        assert Path(out).exists()


class TestTemplates:
    def test_get_template_info(self):
        info = cb.get_template_info()
        assert info["success"] is True
        assert len(info["templates"]) == 3


class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.calculix import calculix_cli
        assert hasattr(calculix_cli, "cli")
        assert hasattr(calculix_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.calculix import utils
        assert hasattr(utils, "calculix_backend")
        b = utils.calculix_backend
        assert hasattr(b, "CALCULIX_VERSION")
        assert hasattr(b, "solve")
        assert hasattr(b, "solve_modal")
        assert hasattr(b, "read_dat_file")
        assert hasattr(b, "create_static_input")
