"""
test_core.py - Unit tests for cli-anything-assimp

Tests Assimp backend with synthetic data.
No real ASSIMP installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  python -m pytest cli_anything/assimp/tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.assimp.utils import assimp_backend as ab


class TestCommandResult:
    def test_fields(self):
        r = ab.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"

    def test_failure(self):
        r = ab.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.error == "err"


class TestVersion:
    def test_get_version(self):
        v = ab.get_version()
        assert v["success"] is True
        assert "version" in v

    def test_version_format(self):
        v = ab.get_version()
        assert "." in v["version"]


class TestFormats:
    def test_supported_formats_defined(self):
        assert len(ab.SUPPORTED_FORMATS) > 10
        assert "obj" in ab.SUPPORTED_FORMATS
        assert "fbx" in ab.SUPPORTED_FORMATS
        assert "stl" in ab.SUPPORTED_FORMATS
        assert "gltf" in ab.SUPPORTED_FORMATS


class TestModelInfo:
    def test_get_info_missing_file(self):
        # In mock mode (ASSIMP_MOCK=1 via conftest), missing files still return mock data
        # In real mode, would return error
        r = ab.get_model_info("/nonexistent/model.obj")
        # Mock returns success with synthetic data
        assert r["success"] is True
        assert r["filename"] == "model.obj"

    def test_get_info_mock(self):
        r = ab.get_model_info("/fake/model.stl")
        assert r["success"] is True
        assert r["format"] == "stl"
        assert "mesh_count" in r
        assert r["mesh_count"] == 3


class TestConvert:
    def test_convert_missing_input(self):
        r = ab.convert("/nonexistent/in.obj", "/tmp/out.fbx")
        assert r.success is False
        assert "not found" in r.error

    def test_convert_success_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = Path(tmpdir) / "model.stl"
            inp.write_text("solid model\nendsolid model\n")
            out = Path(tmpdir) / "model.obj"
            r = ab.convert(str(inp), str(out))
            assert r.success is True
            assert "Converted" in r.output


class TestConvertBatch:
    def test_batch_missing_input_dir(self):
        r = ab.convert_batch("/nonexistent", "/tmp/out", "stl", "obj")
        assert r.success is False
        assert "not found" in r.error

    def test_batch_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inp_dir = Path(tmpdir) / "input"
            out_dir = Path(tmpdir) / "output"
            inp_dir.mkdir()
            out_dir.mkdir()
            r = ab.convert_batch(str(inp_dir), str(out_dir), "stl", "obj")
            assert r.success is False
            assert "No" in r.error and "files found" in r.error


class TestValidate:
    def test_validate_missing_file(self):
        r = ab.validate("/nonexistent/model.obj")
        assert r["success"] is False

    def test_validate_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "model.stl"
            f.write_text("solid model\nendsolid model\n")
            r = ab.validate(str(f))
            assert r["success"] is True
            assert r["valid"] is True


class TestFindAssimp:
    def test_find_assimp_mock(self):
        p = ab.find_assimp()
        assert p == Path("/usr/bin/true")

    def test_mock_env_preserved(self):
        assert os.environ.get("ASSIMP_MOCK") == "1"
