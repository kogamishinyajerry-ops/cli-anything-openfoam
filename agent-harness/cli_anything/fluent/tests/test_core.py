"""
test_core.py - Unit tests for cli-anything-fluent

Tests Fluent backend and CLI with synthetic data.
No real Fluent installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  FLUENT_MOCK=1 python -m pytest cli_anything/fluent/tests/test_core.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.fluent.utils import fluent_backend as fb


# -------------------------------------------------------------------
# Test: CommandResult dataclass
# -------------------------------------------------------------------

class TestCommandResult:
    def test_fields(self):
        r = fb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"
        assert r.returncode == 0

    def test_failure(self):
        r = fb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.returncode == 1
        assert r.error == "err"


# -------------------------------------------------------------------
# Test: find_fluent with mock
# -------------------------------------------------------------------

class TestFindFluent:
    def test_find_fluent_mock(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        # Should not raise
        path = fb.find_fluent()
        assert path == Path("/usr/bin/true")


# -------------------------------------------------------------------
# Test: case_new
# -------------------------------------------------------------------

class TestCaseNew:
    def test_case_new_dim3(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.case_new("test.cas", dimension=3)
        assert result.success is True

    def test_case_new_dim2(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.case_new("test2d.cas", dimension=2)
        assert result.success is True


# -------------------------------------------------------------------
# Test: case_open / case_save
# -------------------------------------------------------------------

class TestCaseOperations:
    def test_case_open_missing_file(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        # Should still "succeed" because mock just returns /usr/bin/true
        result = fb.case_open("/nonexistent/test.cas")
        assert result.success is True

    def test_case_save(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.case_save("save.cas")
        assert result.success is True

    def test_case_save_no_file(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.case_save()
        assert result.success is True


# -------------------------------------------------------------------
# Test: mesh_read
# -------------------------------------------------------------------

class TestMesh:
    def test_mesh_read(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.mesh_read("mesh.msh")
        assert result.success is True


# -------------------------------------------------------------------
# Test: setup functions
# -------------------------------------------------------------------

class TestSetup:
    def test_setup_solver_pressure(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.setup_solver("pressure-based")
        assert result.success is True

    def test_setup_solver_density(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.setup_solver("density-based")
        assert result.success is True

    def test_setup_models(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.setup_models(energy=True, viscous="k-epsilon")
        assert result.success is True

    def test_setup_models_sst(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.setup_models(energy=False, viscous="SST")
        assert result.success is True

    def test_setup_materials(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.setup_materials("water")
        assert result.success is True


# -------------------------------------------------------------------
# Test: boundary conditions
# -------------------------------------------------------------------

class TestBoundaryConditions:
    def test_bc_velocity_inlet(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.bc_set("inlet", "velocity-inlet", {"velocity": 10.0, "temperature": 300})
        assert result.success is True

    def test_bc_pressure_outlet(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.bc_set("outlet", "pressure-outlet", {"pressure": 0})
        assert result.success is True

    def test_bc_wall(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.bc_set("wall1", "wall")
        assert result.success is True

    def test_bc_symmetry(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.bc_set("sym1", "symmetry")
        assert result.success is True

    def test_bc_unknown_type(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.bc_set("zone1", "unknown-type")
        assert result.success is False
        assert "Unknown boundary condition" in result.error


# -------------------------------------------------------------------
# Test: solve functions
# -------------------------------------------------------------------

class TestSolve:
    def test_solve_init(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.solve_init()
        assert result.success is True

    def test_solve_iterate(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.solve_iterate(n_iter=100)
        assert result.success is True

    def test_solve_monitors(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.solve_monitors(residual_enable=True, residual_plot=True)
        assert result.success is True


# -------------------------------------------------------------------
# Test: report parsing
# -------------------------------------------------------------------

class TestReport:
    def test_parse_report_output(self):
        output = """
Flux Report
  inlet: 1.2345
  outlet: -1.2340
"""
        data = fb.parse_report_output(output, "velocity-magnitude")
        assert len(data["values"]) == 2
        assert data["values"][0]["name"] == "inlet"
        assert abs(data["values"][0]["value"] - 1.2345) < 1e-4

    def test_parse_empty_output(self):
        data = fb.parse_report_output("", "temperature")
        assert data["values"] == []


# -------------------------------------------------------------------
# Test: export
# -------------------------------------------------------------------

class TestExport:
    def test_export_results(self, monkeypatch):
        monkeypatch.setenv("FLUENT_MOCK", "1")
        result = fb.export_results("output.dat", surface="inlet")
        assert result.success is True


# -------------------------------------------------------------------
# Test: CLI module import
# -------------------------------------------------------------------

class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.fluent import fluent_cli
        assert hasattr(fluent_cli, "cli")
        assert hasattr(fluent_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.fluent import utils
        assert hasattr(utils, "fluent_backend")
        b = utils.fluent_backend
        assert hasattr(b, "FLUENT_VERSION")
        assert hasattr(b, "case_new")
        assert hasattr(b, "solve_iterate")
