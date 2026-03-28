"""
fastlane_cli.py - Fastlane CI/CD CLI harness

Usage:
  fastlane test [platform]           Run tests
  fastlane build [platform]          Build app
  fastlane beta [platform]            Deploy to beta
  fastlane release [platform]        Deploy to production
  fastlane match <platform> --git_url <url>  Manage certs
  fastlane sigh <app_id>             Renew provisioning
  fastlane screenshots [platform]    Capture screenshots
  fastlane detect                    Detect project type
  fastlane version                  Show version
"""

from __future__ import annotations

import click
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli_anything.fastlane.utils import fastlane_backend as fb


@click.group()
@click.version_option(version=fb.FASTLANE_VERSION, prog_name="fastlane")
def cli():
    """Fastlane mobile CI/CD automation CLI."""
    pass


@cli.command("test")
@click.argument("platform", default="ios", type=click.Choice(["ios", "android"]))
@click.option("--path", "lane_path", help="Path to Fastfile")
def test_cmd(platform: str, lane_path: str | None):
    """Run tests."""
    result = fb.run_test(platform=platform, lane_path=lane_path)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("build")
@click.argument("platform", default="ios", type=click.Choice(["ios", "android"]))
@click.option("--path", "lane_path", help="Path to Fastfile")
def build_cmd(platform: str, lane_path: str | None):
    """Build app."""
    result = fb.run_build(platform=platform, lane_path=lane_path)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("beta")
@click.argument("platform", default="ios", type=click.Choice(["ios", "android"]))
@click.option("--path", "lane_path", help="Path to Fastfile")
def beta_cmd(platform: str, lane_path: str | None):
    """Deploy to beta."""
    result = fb.run_beta(platform=platform, lane_path=lane_path)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("release")
@click.argument("platform", default="ios", type=click.Choice(["ios", "android"]))
@click.option("--path", "lane_path", help="Path to Fastfile")
def release_cmd(platform: str, lane_path: str | None):
    """Deploy to production."""
    result = fb.run_release(platform=platform, lane_path=lane_path)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("match")
@click.argument("platform", default="ios", type=click.Choice(["ios", "android"]))
@click.option("--git-url", "git_url", required=True, help="Git URL for certificate storage")
@click.option("--readonly/--no-readonly", default=True, help="Read-only mode")
def match_cmd(platform: str, git_url: str, readonly: bool):
    """Fetch certificates and provisioning profiles."""
    result = fb.match_certificates(git_url=git_url, platform=platform, readonly=readonly)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("sigh")
@click.argument("app_identifier")
@click.option("--development", is_flag=True, help="Development profile")
def sigh_cmd(app_identifier: str, development: bool):
    """Renew provisioning profile."""
    result = fb.sigh_renew(app_identifier=app_identifier, development=development)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("screenshots")
@click.argument("platform", default="ios", type=click.Choice(["ios", "android"]))
@click.option("--path", "lane_path", help="Path to Fastfile")
def screenshots_cmd(platform: str, lane_path: str | None):
    """Capture screenshots."""
    result = fb.capture_screenshots(platform=platform, lane_path=lane_path)
    if result.success:
        click.echo(result.output)
    else:
        click.echo("Error: " + result.error, err=True)
        sys.exit(1)


@cli.command("detect")
def detect_cmd():
    """Detect project type (iOS/Android)."""
    info = fb.detect_project()
    if info.get("success"):
        ptype = info.get("project_type") or "unknown"
        click.echo("Detected project type: {}".format(ptype.upper()))
        if info.get("indicators", {}).get("ios"):
            click.echo("  iOS indicators: {}".format(", ".join(info["indicators"]["ios"])))
        if info.get("indicators", {}).get("android"):
            click.echo("  Android indicators: {}".format(", ".join(info["indicators"]["android"])))
    else:
        click.echo("Error: " + info.get("error", "Unknown error"), err=True)
        sys.exit(1)


@cli.command("version")
def version_cmd():
    """Show Fastlane version."""
    info = fb.get_version()
    if info.get("success"):
        click.echo("Fastlane version: {}".format(info.get("version")))
    else:
        click.echo("Fastlane: not found", err=True)
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
