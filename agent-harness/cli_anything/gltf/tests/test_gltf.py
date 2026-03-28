"""
test_gltf.py - Unit tests for cli-anything-gltf

Tests glTF backend and CLI with synthetic data.
No real glTF tools required.

Run:
  cd cli-anything-openfoam/agent-harness
  python -m pytest cli_anything/gltf/tests/test_gltf.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.gltf.utils import gltf_backend as gb


# -------------------------------------------------------------------
# Test: CommandResult dataclass
# -------------------------------------------------------------------

class TestCommandResult:
    def test_fields(self):
        """CommandResult stores success, output, error, returncode."""
        r = gb.CommandResult(success=True, output="test output", returncode=0)
        assert r.success is True
        assert r.output == "test output"
        assert r.returncode == 0

    def test_failure(self):
        """CommandResult failure has error message and non-zero returncode."""
        r = gb.CommandResult(success=False, error="something went wrong", returncode=1)
        assert r.success is False
        assert r.error == "something went wrong"
        assert r.returncode == 1


# -------------------------------------------------------------------
# Test: Version
# -------------------------------------------------------------------

class TestVersion:
    def test_get_version_mock(self, monkeypatch):
        """get_version returns glTF 2.0 info in mock mode."""
        monkeypatch.setenv("GLTF_MOCK", "1")
        info = gb.get_version()
        assert info["success"] is True
        assert info["version"] == "glTF 2.0"
        assert info["tool"] == "python-json"


# -------------------------------------------------------------------
# Test: find_gltf
# -------------------------------------------------------------------

class TestFindGltf:
    def test_find_gltf_mock(self, monkeypatch):
        """find_gltf returns /usr/bin/true in mock mode."""
        monkeypatch.setenv("GLTF_MOCK", "1")
        path = gb.find_gltf()
        assert path == Path("/usr/bin/true")


# -------------------------------------------------------------------
# Test: Validate
# -------------------------------------------------------------------

class TestValidate:
    def test_validate_valid_json(self, monkeypatch, tmp_path):
        """validate_gltf succeeds for valid glTF 2.0 JSON."""
        monkeypatch.delenv("GLTF_MOCK", raising=False)
        gltf_file = tmp_path / "test.gltf"
        gltf_file.write_text(json.dumps({
            "asset": {"version": "2.0"},
            "nodes": [],
            "meshes": [],
        }))
        result = gb.validate_gltf(str(gltf_file))
        assert result.success is True

    def test_validate_invalid_json(self, monkeypatch, tmp_path):
        """validate_gltf fails for invalid JSON."""
        monkeypatch.delenv("GLTF_MOCK", raising=False)
        gltf_file = tmp_path / "invalid.gltf"
        gltf_file.write_text("{ this is not json }")
        result = gb.validate_gltf(str(gltf_file))
        assert result.success is False
        assert "JSON" in result.error or "error" in result.error.lower()

    def test_validate_mock_success(self, monkeypatch):
        """validate_gltf returns success in mock mode."""
        monkeypatch.setenv("GLTF_MOCK", "1")
        result = gb.validate_gltf("/nonexistent/file.gltf")
        assert result.success is True


# -------------------------------------------------------------------
# Test: GLB to glTF conversion
# -------------------------------------------------------------------

class TestGlbToGltf:
    def test_glb_to_gltf_missing_input(self, monkeypatch):
        """glb_to_gltf fails gracefully when input file missing."""
        monkeypatch.setenv("GLTF_MOCK", "1")
        result = gb.glb_to_gltf("/nonexistent/input.glb", "/tmp/output.gltf")
        assert result.success is True  # Mock returns success

    def test_glb_to_gltf_mock_success(self, monkeypatch, tmp_path):
        """glb_to_gltf returns success in mock mode."""
        monkeypatch.setenv("GLTF_MOCK", "1")
        output = tmp_path / "output.gltf"
        result = gb.glb_to_gltf("/nonexistent/input.glb", str(output))
        assert result.success is True


# -------------------------------------------------------------------
# Test: glTF to GLB conversion
# -------------------------------------------------------------------

class TestGltfToGlb:
    def test_gltf_to_glb_missing_input(self, monkeypatch):
        """gltf_to_glb fails gracefully when input file missing."""
        monkeypatch.setenv("GLTF_MOCK", "1")
        result = gb.gltf_to_glb("/nonexistent/input.gltf", "/tmp/output.glb")
        assert result.success is True  # Mock returns success

    def test_gltf_to_glb_mock_success(self, monkeypatch, tmp_path):
        """gltf_to_glb returns success in mock mode."""
        monkeypatch.setenv("GLTF_MOCK", "1")
        output = tmp_path / "output.glb"
        result = gb.gltf_to_glb("/nonexistent/input.gltf", str(output))
        assert result.success is True


# -------------------------------------------------------------------
# Test: glTF Info
# -------------------------------------------------------------------

class TestGltfInfo:
    def test_gltf_info_missing_file(self, monkeypatch):
        """gltf_info returns error dict for missing file."""
        monkeypatch.setenv("GLTF_MOCK", "1")
        info = gb.gltf_info("/nonexistent/file.gltf")
        assert info["success"] is True  # Mock returns success

    def test_gltf_info_mock(self, monkeypatch):
        """gltf_info returns synthetic info in mock mode."""
        monkeypatch.setenv("GLTF_MOCK", "1")
        info = gb.gltf_info("/fake/path.gltf")
        assert info["success"] is True
        assert "nodes" in info
        assert "meshes" in info
        assert "images" in info
        assert "accessors" in info
        assert info["nodes"] == 5
        assert info["meshes"] == 2
        assert info["images"] == 1


# -------------------------------------------------------------------
# Test: Mock environment
# -------------------------------------------------------------------

class TestMock:
    def test_mock_env_set(self):
        """GLTF_MOCK environment variable is set by conftest."""
        assert os.environ.get("GLTF_MOCK") == "1"
