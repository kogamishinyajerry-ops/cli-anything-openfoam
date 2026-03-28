import os
import subprocess

import pytest

os.environ.setdefault('OPENFOAM_MOCK', '1')


def docker_available():
    """Check if Docker daemon is accessible."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def pytest_collection_modifyitems(items):
    """Skip TestTrueBackend tests if Docker is not available."""
    if docker_available():
        return
    skip_docker = pytest.mark.skip(reason="Docker not available")
    for item in items:
        if "TestTrueBackend" in item.nodeid or "test_full_e2e" in item.nodeid:
            item.add_marker(skip_docker)
