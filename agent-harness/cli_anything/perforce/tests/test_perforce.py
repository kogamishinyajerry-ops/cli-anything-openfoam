"""
test_perforce.py - Unit tests for cli-anything-perforce
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.perforce.utils import perforce_backend as pb


class TestCommandResult:
    def test_fields(self):
        r = pb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True

    def test_failure(self):
        r = pb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False


class TestVersion:
    def test_get_version_mock(self):
        v = pb.get_version()
        assert v["success"] is True
        assert "version" in v


class TestInfo:
    def test_get_info_mock(self):
        i = pb.get_info()
        assert i["success"] is True
        assert "server" in i


class TestListFiles:
    def test_list_files_mock(self):
        r = pb.list_files("//depot/main/...")
        assert r["success"] is True
        assert len(r["files"]) >= 1
        assert "depotFile" in r["files"][0]


class TestListChanges:
    def test_list_changes_mock(self):
        r = pb.list_changes()
        assert r["success"] is True
        assert len(r["changes"]) >= 1
        assert "change" in r["changes"][0]


class TestDescribeChange:
    def test_describe_change_mock(self):
        r = pb.describe_change("12345")
        assert r["success"] is True
        assert r["change"] == "12345"


class TestSubmit:
    def test_submit_mock(self):
        r = pb.submit("Test change description")
        assert r["success"] is True
        assert "submitted" in r
        assert r["submitted"] is True


class TestStatus:
    def test_status_mock(self):
        r = pb.status()
        assert r["success"] is True
        assert "opened_files" in r or "raw" in r


class TestSync:
    def test_sync_mock(self):
        r = pb.sync("//depot/main")
        assert r.success is True
        assert "Sync" in r.output


class TestFindP4:
    def test_find_p4_mock(self):
        p = pb.find_p4()
        assert p == Path("/usr/bin/true")


class TestMock:
    def test_mock_env_set(self):
        assert os.environ.get("P4_MOCK") == "1"
