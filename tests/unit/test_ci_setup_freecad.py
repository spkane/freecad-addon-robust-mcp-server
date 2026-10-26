"""Behavioral tests for the FreeCAD AppImage setup script."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETUP_SCRIPT = PROJECT_ROOT / "tests" / "ci-test" / "setup-freecad.sh"


@pytest.fixture
def setup_environment(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Create cached setup paths and portable command stubs for the Linux script."""
    appimage_dir = tmp_path / "freecad-appimage"
    appimage_dir.mkdir()
    command_dir = tmp_path / "bin"
    command_dir.mkdir()

    flock = command_dir / "flock"
    flock.write_text("#!/bin/sh\nexit 0\n")
    flock.chmod(0o755)

    uname = command_dir / "uname"
    uname.write_text("#!/bin/sh\nprintf 'unsupported-test-architecture\\n'\n")
    uname.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "APPIMAGE_DIR": str(appimage_dir),
            "FREECAD_TAG": "test-release",
            "PATH": f"{command_dir}{os.pathsep}{environment['PATH']}",
        }
    )
    return appimage_dir, environment


def _write_cached_setup(appimage_dir: Path, content: bytes) -> tuple[Path, Path]:
    """Write a cached AppImage and matching release marker."""
    appimage = appimage_dir / "FreeCAD.AppImage"
    marker = appimage_dir / ".freecad_installed"
    appimage.write_bytes(content)
    marker.write_text("test-release\n")
    return appimage, marker


def _run_setup(environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the setup script with the supplied isolated environment."""
    return subprocess.run(  # noqa: S603
        ["/bin/bash", str(SETUP_SCRIPT)],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )


def test_matching_marker_verifies_cached_appimage_before_skipping(
    setup_environment: tuple[Path, dict[str, str]],
) -> None:
    """A matching marker may skip setup only after the supplied digest passes."""
    appimage_dir, environment = setup_environment
    content = b"verified FreeCAD AppImage fixture"
    appimage, marker = _write_cached_setup(appimage_dir, content)
    environment["FREECAD_APPIMAGE_SHA256"] = hashlib.sha256(content).hexdigest()

    result = _run_setup(environment)

    assert result.returncode == 0
    assert "SHA256 checksum verified successfully" in result.stdout
    assert "already set up" in result.stdout
    assert appimage.exists()
    assert marker.exists()


def test_digest_mismatch_removes_cached_setup_instead_of_skipping(
    setup_environment: tuple[Path, dict[str, str]],
) -> None:
    """A mismatched cached AppImage must be removed and setup must continue."""
    appimage_dir, environment = setup_environment
    appimage, marker = _write_cached_setup(appimage_dir, b"unexpected content")
    environment["FREECAD_APPIMAGE_SHA256"] = hashlib.sha256(
        b"expected content"
    ).hexdigest()

    result = _run_setup(environment)

    assert result.returncode != 0
    assert "SHA256 checksum mismatch" in result.stdout
    assert "will reinstall" in result.stdout
    assert "already set up" not in result.stdout
    assert not appimage.exists()
    assert not marker.exists()


def test_matching_marker_without_cached_appimage_reinstalls(
    setup_environment: tuple[Path, dict[str, str]],
) -> None:
    """A release marker alone must not be accepted as a complete cached setup."""
    appimage_dir, environment = setup_environment
    marker = appimage_dir / ".freecad_installed"
    marker.write_text("test-release\n")

    result = _run_setup(environment)

    assert result.returncode != 0
    assert "AppImage not found" in result.stdout
    assert "will reinstall" in result.stdout
    assert "already set up" not in result.stdout
    assert not marker.exists()
