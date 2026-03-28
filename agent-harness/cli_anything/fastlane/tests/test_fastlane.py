"""
test_fastlane.py - Unit tests for cli-anything-fastlane
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.fastlane.utils import fastlane_backend as fb


class TestCommandResult:
    def test_fields(self):
        r = fb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True

    def test_failure(self):
        r = fb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False


class TestVersion:
    def test_get_version_mock(self):
        v = fb.get_version()
        assert v["success"] is True
        assert "version" in v


class TestDetectProject:
    def test_detect_project(self):
        r = fb.detect_project()
        assert r["success"] is True
        assert "project_type" in r


class TestRunLane:
    def test_run_test_mock(self):
        r = fb.run_test(platform="ios")
        assert r.success is True
        assert "test" in r.output.lower()

    def test_run_build_mock(self):
        r = fb.run_build(platform="android")
        assert r.success is True
        assert "BUILD" in r.output

    def test_run_beta_mock(self):
        r = fb.run_beta(platform="ios")
        assert r.success is True

    def test_run_release_mock(self):
        r = fb.run_release(platform="android")
        assert r.success is True


class TestMatchCertificates:
    def test_match_mock(self):
        r = fb.match_certificates("git@example.com:certs.git", platform="ios")
        assert r.success is True


class TestSigh:
    def test_sigh_renew_mock(self):
        r = fb.sigh_renew("com.example.app")
        assert r.success is True
        assert "com.example.app" in r.output


class TestScreenshots:
    def test_capture_screenshots_mock(self):
        r = fb.capture_screenshots(platform="ios")
        assert r.success is True
        assert "screenshots" in r.output.lower()


class TestMock:
    def test_mock_env_set(self):
        assert os.environ.get("FASTLANE_MOCK") == "1"
