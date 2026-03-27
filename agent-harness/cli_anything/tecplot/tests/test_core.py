"""
test_core.py - Unit tests for cli-anything-tecplot

Tests Tecplot backend and CLI with synthetic data.
No real Tecplot installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  TECPLOT_MOCK=1 python -m pytest cli_anything/tecplot/tests/test_core.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.tecplot.utils import tecplot_backend as tb


# -------------------------------------------------------------------
# Test: CommandResult dataclass
# -------------------------------------------------------------------

class TestCommandResult:
    def test_fields(self):
        r = tb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"
        assert r.returncode == 0

    def test_failure(self):
        r = tb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.returncode == 1
        assert r.error == "err"


# -------------------------------------------------------------------
# Test: find_tecplot with mock
# -------------------------------------------------------------------

class TestFindTecplot:
    def test_find_tecplot_mock(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        path = tb.find_tecplot()
        assert path == Path("/usr/bin/true")


# -------------------------------------------------------------------
# Test: load operations
# -------------------------------------------------------------------

class TestLoadData:
    def test_load_data(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.load_data("case.dat")
        assert result.success is True

    def test_load_layout(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.load_layout("mylayout.lay")
        assert result.success is True


# -------------------------------------------------------------------
# Test: plot operations
# -------------------------------------------------------------------

class TestPlot:
    def test_set_plot_type_cartesian(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.set_plot_type("cartesian")
        assert result.success is True

    def test_set_plot_type_polar(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.set_plot_type("polar")
        assert result.success is True

    def test_set_plot_type_xyline(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.set_plot_type("XYLine")
        assert result.success is True

    def test_contour_levels(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        levels = [0.0, 0.1, 0.2, 0.3, 0.4]
        result = tb.contour_levels("Pressure", levels=levels)
        assert result.success is True

    def test_contour_levels_auto(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.contour_levels("Temperature")
        assert result.success is True

    def test_set_variable_range(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.set_variable_range("Velocity", 0.0, 100.0)
        assert result.success is True


# -------------------------------------------------------------------
# Test: slice operations
# -------------------------------------------------------------------

class TestSlice:
    def test_create_slice_plane(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.create_slice_plane("zone slices")
        assert result.success is True

    def test_create_slice_plane_i(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.create_slice_plane("i-slice")
        assert result.success is True

    def test_create_iso_surface(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.create_iso_surface("Pressure", 101325.0)
        assert result.success is True

    def test_create_streamtrace(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.create_streamtrace()
        assert result.success is True


# -------------------------------------------------------------------
# Test: export operations
# -------------------------------------------------------------------

class TestExport:
    def test_export_image(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.export_image("output.png", width=1920, height=1080)
        assert result.success is True

    def test_export_data(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.export_data("output.dat")
        assert result.success is True

    def test_export_data_zone(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.export_data("output.dat", zone_name="fluid")
        assert result.success is True


# -------------------------------------------------------------------
# Test: macro operations
# -------------------------------------------------------------------

class TestMacro:
    def test_run_macro(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.run_macro("plot.mac")
        assert result.success is True

    def test_run_python_script(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.run_python_script("plot.py")
        assert result.success is True


# -------------------------------------------------------------------
# Test: layout operations
# -------------------------------------------------------------------

class TestLayout:
    def test_new_layout(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.new_layout("mylayout")
        assert result.success is True

    def test_save_layout(self, monkeypatch):
        monkeypatch.setenv("TECPLOT_MOCK", "1")
        result = tb.save_layout("mylayout.lay")
        assert result.success is True


# -------------------------------------------------------------------
# Test: CLI module import
# -------------------------------------------------------------------

class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.tecplot import tecplot_cli
        assert hasattr(tecplot_cli, "cli")
        assert hasattr(tecplot_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.tecplot import utils
        assert hasattr(utils, "tecplot_backend")
        b = utils.tecplot_backend
        assert hasattr(b, "TECPLOT_VERSION")
        assert hasattr(b, "load_data")
        assert hasattr(b, "export_image")
        assert hasattr(b, "create_slice_plane")
