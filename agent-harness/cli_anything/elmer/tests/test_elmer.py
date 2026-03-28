"""
test_elmer.py - Unit tests for cli-anything-elmer
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.elmer.utils import elmer_backend as eb


class TestCommandResult:
    def test_fields(self):
        r = eb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True

    def test_failure(self):
        r = eb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False


class TestVersion:
    def test_get_version_mock(self):
        v = eb.get_version()
        assert v["success"] is True
        assert "version" in v


class TestFindSolver:
    def test_find_solver_mock(self):
        p = eb.find_elmer_solver()
        assert p == Path("/usr/bin/true")


class TestCreateSIF:
    def test_create_static_sif(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test.sif"
            r = eb.create_static_sif(str(out), title="Test Analysis")
            assert r.success is True
            assert out.exists()
            content = out.read_text()
            assert "ElmerSolver input file" in content
            assert "! Test Analysis" in content or "ElmerSolver" in content


class TestRunSimulation:
    def test_missing_sif(self):
        r = eb.run_simulation("/nonexistent.sif", "/tmp/mesh")
        assert r.success is False

    def test_missing_mesh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sif = Path(tmpdir) / "test.sif"
            sif.write_text("! Elmer input")
            r = eb.run_simulation(str(sif), "/nonexistent/mesh")
            assert r.success is False

    def test_success_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sif = Path(tmpdir) / "test.sif"
            sif.write_text("! Elmer input")
            mesh = Path(tmpdir) / "mesh"
            mesh.mkdir()
            r = eb.run_simulation(str(sif), str(mesh))
            assert r.success is True
            assert "ElmerSolver" in r.output


class TestMeshImport:
    def test_missing_input(self):
        r = eb.import_mesh("gmsh", "/nonexistent.msh", "/tmp/out")
        assert r.success is False

    def test_success_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = Path(tmpdir) / "model.msh"
            inp.write_text("MeshFormat")
            out = Path(tmpdir) / "output"
            out.mkdir()
            r = eb.import_mesh("gmsh", str(inp), str(out))
            assert r.success is True


class TestMeshInfo:
    def test_missing_mesh(self, monkeypatch):
        monkeypatch.delenv("ELMER_MOCK", raising=False)
        r = eb.mesh_info("/nonexistent/mesh")
        assert r["success"] is False

    def test_mock(self):
        r = eb.mesh_info("/fake/mesh")
        assert r["success"] is True
        assert "nodes" in r


class TestMock:
    def test_mock_env_set(self):
        assert os.environ.get("ELMER_MOCK") == "1"
