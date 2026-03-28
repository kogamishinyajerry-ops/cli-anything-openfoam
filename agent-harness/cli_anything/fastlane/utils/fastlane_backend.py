"""
fastlane_backend.py - Fastlane CI/CD CLI wrapper

Fastlane provides automation tools for mobile app deployment.

Key commands:
  - fastlane test                 Run tests
  - fastlane build               Build app
  - fastlane beta                Deploy to beta
  - fastlane release             Deploy to production
  - fastlane match               Manage certificates/provisioning
  - fastlane sigh                Provisioning profiles
  - fastlane cert                Certificates

Install:
  - gem install fastlane
  - brew install fastlane

Principles:
  - MUST call real fastlane commands, not reimplement
  - Fastlane is a Ruby gem, invoked as `fastlane` command
  - Requires Appfile for project configuration
  - iOS/Android project structure required
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# -------------------------------------------------------------------
# Version
# -------------------------------------------------------------------

FASTLANE_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

def find_fastlane() -> Path:
    """Locate fastlane binary."""
    if os.environ.get("FASTLANE_MOCK"):
        return Path("/usr/bin/true")

    path = os.environ.get("FASTLANE_PATH")
    if path:
        p = Path(path)
        if p.exists():
            return p

    try:
        result = subprocess.run(
            ["which", "fastlane"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["bundle", "exec", "fastlane", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return Path("bundle")
    except Exception:
        pass

    raise RuntimeError(
        "Fastlane not found.\n"
        "Install: gem install fastlane\n"
        "Or: brew install fastlane\n"
        "Set FASTLANE_MOCK=1 for testing."
    )


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a Fastlane command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run(args: list, lane_path: Optional[str] = None, timeout: int = 600, check: bool = True) -> CommandResult:
    """Run Fastlane command."""
    fastlane = find_fastlane()
    cmd = [str(fastlane)] + args

    # If using bundle, adjust command
    if str(fastlane) == "bundle":
        cmd = ["bundle", "exec"] + cmd

    cwd = Path(lane_path).parent if lane_path else Path.cwd()
    start = time.time()

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        duration = time.time() - start

        if check and proc.returncode != 0:
            return CommandResult(
                success=False,
                output=proc.stdout,
                error=proc.stderr,
                returncode=proc.returncode,
                duration_seconds=duration,
            )

        return CommandResult(
            success=proc.returncode == 0,
            output=proc.stdout,
            error=proc.stderr,
            returncode=proc.returncode,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            success=False,
            output="",
            error="Command timed out after {}s".format(timeout),
            returncode=-1,
            duration_seconds=timeout,
        )
    except Exception as e:
        return CommandResult(
            success=False,
            output="",
            error=str(e),
            returncode=-99,
            duration_seconds=time.time() - start,
        )


# -------------------------------------------------------------------
# Version / Info
# -------------------------------------------------------------------

def get_version() -> dict:
    """Get Fastlane version."""
    if os.environ.get("FASTLANE_MOCK"):
        return {"success": True, "version": "2.216.0", "platform": "iOS Android"}

    result = _run(["--version"], timeout=15, check=False)
    if result.success:
        match = re.search(r"(\d+\.\d+\.\d+)", result.output)
        version = match.group(1) if match else "unknown"
        return {"success": True, "version": version}
    return {"success": False, "error": result.error}


def detect_project() -> dict:
    """
    Detect if current directory is an iOS/Android project.

    Returns dict with project type and paths.
    """
    cwd = Path.cwd()

    indicators = {
        "ios": [],
        "android": [],
    }

    ios_indicators = ["*.xcworkspace", "*.xcodeproj", "Podfile", "Fastlane.swift", "Appfile"]
    android_indicators = ["build.gradle", "settings.gradle", "gradlew", "AndroidManifest.xml", "Gemfile"]

    for pattern in ios_indicators:
        if "*" in pattern:
            from pathlib import Path as P
            for p in cwd.glob(pattern):
                indicators["ios"].append(str(p))
        elif (cwd / pattern).exists():
            indicators["ios"].append(pattern)

    for pattern in android_indicators:
        if "*" in pattern:
            from pathlib import Path as P
            for p in cwd.glob(pattern):
                indicators["android"].append(str(p))
        elif (cwd / pattern).exists():
            indicators["android"].append(pattern)

    project_type = None
    if indicators["ios"]:
        project_type = "ios"
    elif indicators["android"]:
        project_type = "android"

    return {
        "success": True,
        "project_type": project_type,
        "cwd": str(cwd),
        "indicators": indicators,
    }


# -------------------------------------------------------------------
# Lanes
# -------------------------------------------------------------------

def run_lane(
    lane: str,
    platform: str = "ios",
    lane_path: Optional[str] = None,
    extra_args: Optional[list] = None,
) -> CommandResult:
    """
    Run a Fastlane lane.

    Args:
        lane: Lane name (e.g. 'beta', 'release', 'test')
        platform: 'ios' or 'android'
        lane_path: Path to Fastfile
        extra_args: Additional fastlane arguments

    Returns:
        CommandResult
    """
    if os.environ.get("FASTLANE_MOCK"):
        return CommandResult(
            success=True,
            output="Fastlane {} [{}] lane completed\n"
                    "  Build: BUILD SUCCEEDED\n"
                    "  Tests: 42 passed, 0 failed".format(platform, lane),
            returncode=0,
        )

    args = [platform, lane]
    if extra_args:
        args.extend(extra_args)

    return _run(args, lane_path=lane_path, timeout=1800, check=False)


def run_test(
    platform: str = "ios",
    lane_path: Optional[str] = None,
) -> CommandResult:
    """Run tests via Fastlane."""
    return run_lane("test", platform=platform, lane_path=lane_path)


def run_build(
    platform: str = "ios",
    lane_path: Optional[str] = None,
) -> CommandResult:
    """Build app via Fastlane."""
    return run_lane("build", platform=platform, lane_path=lane_path)


def run_beta(
    platform: str = "ios",
    lane_path: Optional[str] = None,
) -> CommandResult:
    """Deploy to beta via Fastlane."""
    return run_lane("beta", platform=platform, lane_path=lane_path)


def run_release(
    platform: str = "ios",
    lane_path: Optional[str] = None,
) -> CommandResult:
    """Deploy to production via Fastlane."""
    return run_lane("release", platform=platform, lane_path=lane_path)


# -------------------------------------------------------------------
# Match / Certificates
# -------------------------------------------------------------------

def match_certificates(
    git_url: str,
    platform: str = "ios",
    readonly: bool = True,
) -> CommandResult:
    """
    Fetch certificates and provisioning profiles via Fastlane Match.

    Args:
        git_url: Private git URL storing certificates
        platform: 'ios' or 'android'
        readonly: Only fetch, don't create

    Returns:
        CommandResult
    """
    if os.environ.get("FASTLANE_MOCK"):
        return CommandResult(
            success=True,
            output="Successfully fetched certificates from git",
            returncode=0,
        )

    args = ["match", platform, "--git_url", git_url]
    if readonly:
        args.append("--readonly")

    return _run(args, timeout=120, check=False)


# -------------------------------------------------------------------
# Sigh (Provisioning)
# -------------------------------------------------------------------

def sigh_renew(
    app_identifier: str,
    development: bool = False,
) -> CommandResult:
    """
    Renew provisioning profile via Fastlane Sigh.

    Args:
        app_identifier: App bundle ID
        development: Use development profile

    Returns:
        CommandResult
    """
    if os.environ.get("FASTLANE_MOCK"):
        return CommandResult(
            success=True,
            output="Provisioning profile renewed: {} {}".format(
                app_identifier,
                "(Development)" if development else "(Distribution)"
            ),
            returncode=0,
        )

    args = ["sigh", "renew", "--app_identifier", app_identifier]
    if development:
        args.append("--development")

    return _run(args, timeout=120, check=False)


# -------------------------------------------------------------------
# Frameworks (screenshots)
# -------------------------------------------------------------------

def capture_screenshots(
    platform: str = "ios",
    lane_path: Optional[str] = None,
) -> CommandResult:
    """Capture screenshots via Fastlane Snapshot."""
    if os.environ.get("FASTLANE_MOCK"):
        return CommandResult(
            success=True,
            output="Screenshots captured: 24 screenshots in 4 languages",
            returncode=0,
        )

    args = ["capture_screenshots", "--platform", platform]
    return _run(args, lane_path=lane_path, timeout=600, check=False)
