"""
test_core.py - Unit tests for cli-anything-visit

Tests VisIt backend and CLI with synthetic data.
No real VisIt installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  VISIT_MOCK=1 python -m pytest cli_anything/visit/tests/test_core.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.visit.utils import visit_backend as vb


# -------------------------------------------------------------------
# Test: CommandResult dataclass
# -------------------------------------------------------------------

class TestCommandResult:
    def test_fields(self):
        r = vb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"
        assert r.returncode == 0

    def test_failure(self):
        r = vb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.returncode == 1
        assert r.error == "err"


# -------------------------------------------------------------------
# Test: find_visit with mock
# -------------------------------------------------------------------

class TestFindVisit:
    def test_find_visit_mock(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        path = vb.find_visit()
        assert path == Path("/usr/bin/true")


# -------------------------------------------------------------------
# Test: database operations
# -------------------------------------------------------------------

class TestDatabase:
    def test_open_database(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.open_database("case.silo")
        assert result.success is True

    def test_open_database_timestep(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.open_database("case.silo", timestep=5)
        assert result.success is True


# -------------------------------------------------------------------
# Test: plot operations
# -------------------------------------------------------------------

class TestPlot:
    def test_add_plot_pseudocolor(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.add_plot("Pseudocolor", "Temperature")
        assert result.success is True

    def test_add_plot_volume(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.add_plot("Volume", "Density")
        assert result.success is True

    def test_add_plot_mesh(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.add_plot("Mesh", "mesh")
        assert result.success is True

    def test_draw_plots(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.draw_plots()
        assert result.success is True

    def test_delete_all_plots(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.delete_all_plots()
        assert result.success is True

    def test_set_plot_range(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.set_plot_range("Pressure", 0.0, 101325.0)
        assert result.success is True


# -------------------------------------------------------------------
# Test: operator operations
# -------------------------------------------------------------------

class TestOperator:
    def test_add_operator_slice(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.add_operator("Slice")
        assert result.success is True

    def test_add_operator_threshold(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.add_operator("Threshold")
        assert result.success is True

    def test_add_operator_volume(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.add_operator("Volume")
        assert result.success is True

    def test_set_slice_plane(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.set_slice_plane(axis="z", value=0.0)
        assert result.success is True


# -------------------------------------------------------------------
# Test: export operations
# -------------------------------------------------------------------

class TestExport:
    def test_save_window_png(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.save_window("output.png", width=1920, height=1080, format="png")
        assert result.success is True

    def test_save_window_eps(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.save_window("output.eps", format="eps")
        assert result.success is True

    def test_export_database(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.export_database("output_dir", format="Silo")
        assert result.success is True


# -------------------------------------------------------------------
# Test: query operations
# -------------------------------------------------------------------

class TestQuery:
    def test_query_minmax(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        data = vb.query_minmax("Temperature")
        assert data["success"] is True

    def test_query_volume(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        data = vb.query_volume()
        assert data["success"] is True

    def test_query_integral(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        data = vb.query_integral("Temperature")
        assert data["success"] is True

    def test_parse_query_output(self):
        output = """
Min: 0.000
Max: 100.000
"""
        data = vb.parse_query_output(output)
        assert len(data["values"]) >= 0


# -------------------------------------------------------------------
# Test: layout operations
# -------------------------------------------------------------------

class TestLayout:
    def test_set_window_layout_1(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.set_window_layout(1)
        assert result.success is True

    def test_set_window_layout_4(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.set_window_layout(4)
        assert result.success is True

    def test_create_subwindow(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.create_subwindow(2)
        assert result.success is True


# -------------------------------------------------------------------
# Test: animation
# -------------------------------------------------------------------

class TestAnimate:
    def test_set_time_slider(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.set_time_slider(0)
        assert result.success is True

    def test_get_time_slider_state(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.get_time_slider_state()
        assert result.success is True


# -------------------------------------------------------------------
# Test: annotation
# -------------------------------------------------------------------

class TestAnnotate:
    def test_set_title(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.set_title("My Simulation")
        assert result.success is True

    def test_hide_annotation(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.hide_annotation()
        assert result.success is True


# -------------------------------------------------------------------
# Test: macro
# -------------------------------------------------------------------

class TestMacro:
    def test_run_script(self, monkeypatch):
        monkeypatch.setenv("VISIT_MOCK", "1")
        result = vb.run_script("plot.py")
        assert result.success is True


# -------------------------------------------------------------------
# Test: CLI module import
# -------------------------------------------------------------------

class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.visit import visit_cli
        assert hasattr(visit_cli, "cli")
        assert hasattr(visit_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.visit import utils
        assert hasattr(utils, "visit_backend")
        b = utils.visit_backend
        assert hasattr(b, "VISIT_VERSION")
        assert hasattr(b, "open_database")
        assert hasattr(b, "add_plot")
        assert hasattr(b, "save_window")
