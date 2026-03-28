"""
test_core.py - Unit tests for cli-anything-blender

Tests Blender backend with synthetic data.
No real Blender installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  BLENDER_MOCK=1 python -m pytest cli_anything/blender/tests/test_core.py -v
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.blender.utils import blender_backend as bb


class TestCommandResult:
    def test_fields(self):
        r = bb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"

    def test_failure(self):
        r = bb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.error == "err"


class TestFindBlender:
    def test_find_blender_mock(self, monkeypatch):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        path = bb.find_blender()
        assert path == Path("/usr/bin/true")


class TestVersion:
    def test_get_version_mock(self, monkeypatch):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        v = bb.get_version()
        assert v["success"] is True
        assert v["version"] == "4.2.0"


class TestRenderMock:
    def test_render_image_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        blend = tmp_path / "scene.blend"
        blend.write_text("dummy")
        output = str(tmp_path / "render.png")
        result = bb.render_image(str(blend), output)
        assert result.success is True

    def test_render_image_missing_blend(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        result = bb.render_image("/nonexistent.blend", "/tmp/out.png")
        assert result.success is False

    def test_render_animation_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        blend = tmp_path / "scene.blend"
        blend.write_text("dummy")
        result = bb.render_animation(str(blend), str(tmp_path / "output"), start_frame=1, end_frame=10)
        assert result.success is True


class TestImportExport:
    def test_import_model_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        model = tmp_path / "model.obj"
        model.write_text("dummy")
        result = bb.import_model(str(model))
        assert result.success is True

    def test_import_model_unknown_ext(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        result = bb.import_model("/unknown.xyz")
        assert result.success is False

    def test_export_model_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        result = bb.export_model(str(tmp_path / "in.blend"), str(tmp_path / "out.gltf"))
        assert result.success is True


class TestObject:
    def test_list_objects_mock(self, monkeypatch):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        info = bb.list_objects()
        assert info["success"] is True
        assert len(info["objects"]) == 3

    def test_get_object_info_mock(self, monkeypatch):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        info = bb.get_object_info("Cube")
        assert info["success"] is True
        assert info["type"] == "MESH"


class TestModifiers:
    def test_add_modifier_mock(self, monkeypatch):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        result = bb.add_modifier("Cube", "SUBSURF")
        assert result.success is True

    def test_add_modifier_unknown_type(self, monkeypatch):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        result = bb.add_modifier("Cube", "UNKNOWN_MOD")
        assert result.success is False


class TestScene:
    def test_get_scene_stats_mock(self, monkeypatch):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        info = bb.get_scene_stats()
        assert info["success"] is True
        assert info["objects"] == 42


class TestBatch:
    def test_batch_convert_mock(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BLENDER_MOCK", "1")
        indir = tmp_path / "input"
        indir.mkdir()
        outdir = tmp_path / "output"
        (indir / "a.obj").write_text("dummy")
        result = bb.batch_convert(str(indir), str(outdir), "obj", "gltf")
        assert result.success is True


class TestCLIModule:
    def test_cli_module_imports(self):
        from cli_anything.blender import blender_cli
        assert hasattr(blender_cli, "cli")
        assert hasattr(blender_cli, "main")

    def test_backend_module_imports(self):
        from cli_anything.blender import utils
        assert hasattr(utils, "blender_backend")
        b = utils.blender_backend
        assert hasattr(b, "BLENDER_VERSION")
        assert hasattr(b, "render_image")
        assert hasattr(b, "import_model")
        assert hasattr(b, "export_model")
