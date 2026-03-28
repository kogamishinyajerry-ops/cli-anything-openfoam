"""
test_core.py - Unit tests for cli-anything-slurm

Tests Slurm/PBS backend with synthetic data.
No real scheduler installation required.

Run:
  cd cli-anything-openfoam/agent-harness
  python -m pytest cli_anything/slurm/tests/test_core.py -v
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cli_anything.slurm.utils import slurm_backend as sb


class TestCommandResult:
    def test_fields(self):
        r = sb.CommandResult(success=True, output="test", returncode=0)
        assert r.success is True
        assert r.output == "test"

    def test_failure(self):
        r = sb.CommandResult(success=False, error="err", returncode=1)
        assert r.success is False
        assert r.error == "err"


class TestSchedulerDetection:
    def test_detect_mock(self):
        detected = sb.detect_scheduler()
        assert detected == "mock"


class TestVersion:
    def test_get_version_mock(self):
        v = sb.get_version()
        assert v["success"] is True
        assert "version" in v


class TestSlurmSubmit:
    def test_submit_missing_script(self):
        r = sb.slurm_submit("/nonexistent/script.sh")
        assert r.success is False
        assert "not found" in r.error

    def test_submit_success_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script = Path(tmpdir) / "job.sh"
            script.write_text("#!/bin/bash\necho hello")
            r = sb.slurm_submit(str(script))
            assert r.success is True
            assert "12345" in r.output


class TestSlurmListJobs:
    def test_list_jobs_mock(self):
        r = sb.slurm_list_jobs()
        assert r.success is True
        assert "JOBID" in r.output or "12345" in r.output

    def test_list_jobs_with_user(self):
        r = sb.slurm_list_jobs(user="testuser")
        assert r.success is True


class TestSlurmCancel:
    def test_cancel_job_mock(self):
        r = sb.slurm_cancel("12345")
        assert r.success is True
        assert "12345" in r.output


class TestSlurmNodeInfo:
    def test_node_info_mock(self):
        r = sb.slurm_node_info()
        assert r.success is True
        assert "node" in r.output.lower()


class TestSlurmJobInfo:
    def test_job_info_mock(self):
        info = sb.slurm_job_info("12345")
        assert info["success"] is True
        assert info["job_id"] == "12345"


class TestGenericWrappers:
    def test_submit_job_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script = Path(tmpdir) / "job.sh"
            script.write_text("#!/bin/bash\necho hello")
            r = sb.submit_job(str(script))
            assert r.success is True

    def test_list_jobs_mock(self):
        r = sb.list_jobs()
        assert r.success is True

    def test_cancel_job_mock(self):
        r = sb.cancel_job("12345")
        assert r.success is True


class TestEnvVars:
    def test_mock_env_set(self):
        assert os.environ.get("SLURM_MOCK") == "1"
