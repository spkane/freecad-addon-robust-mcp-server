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
    wrapper_dir = tmp_path / "wrappers"
    wrapper_dir.mkdir()

    flock = command_dir / "flock"
    flock.write_text("#!/bin/sh\nexit 0\n")
    flock.chmod(0o755)

    uname = command_dir / "uname"
    uname.write_text("#!/bin/sh\nprintf 'unsupported-test-architecture\\n'\n")
    uname.chmod(0o755)

    environment = os.environ.copy()
    for variable in (
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "TRAVIS",
        "CIRCLECI",
        "JENKINS_URL",
        "BUILDKITE",
        "FREECAD_APPIMAGE_SHA256",
        "APPIMAGE_SHA256",
    ):
        environment.pop(variable, None)
    environment.update(
        {
            "APPIMAGE_DIR": str(appimage_dir),
            "FREECAD_BIN_DIR": str(wrapper_dir),
            "FREECAD_TAG": "test-release",
            "PATH": f"{command_dir}{os.pathsep}{environment['PATH']}",
        }
    )
    return appimage_dir, environment


def _write_command(path: Path, content: str) -> None:
    """Write an executable command stub."""
    path.write_text(content)
    path.chmod(0o755)


def _write_wrappers(environment: dict[str, str]) -> None:
    """Write executable FreeCAD wrapper placeholders for cache-hit tests."""
    wrapper_dir = Path(environment["FREECAD_BIN_DIR"])
    for name in ("freecad", "freecadcmd"):
        _write_command(wrapper_dir / name, "#!/bin/sh\nexit 0\n")


def _write_extracted_tree(appimage_dir: Path) -> None:
    """Write the minimum extracted AppImage directory required for a cache hit."""
    binary_dir = appimage_dir / "squashfs-root" / "usr" / "bin"
    binary_dir.mkdir(parents=True)
    for name in ("freecad", "freecadcmd"):
        _write_command(binary_dir / name, "#!/bin/sh\nexit 0\n")


def _configure_supported_cached_install(
    environment: dict[str, str], content: bytes
) -> None:
    """Configure a supported architecture, official URL, and fixture digest."""
    command_dir = Path(environment["PATH"].split(os.pathsep, maxsplit=1)[0])
    _write_command(command_dir / "uname", "#!/bin/sh\nprintf 'x86_64\\n'\n")
    environment.update(
        {
            "FREECAD_APPIMAGE_SHA256": hashlib.sha256(content).hexdigest(),
            "FREECAD_APPIMAGE_URL": (
                "https://github.com/FreeCAD/FreeCAD/releases/download/"
                "test-release/FreeCAD-Linux-x86_64.AppImage"
            ),
        }
    )


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
    _write_wrappers(environment)
    _write_extracted_tree(appimage_dir)
    environment["FREECAD_APPIMAGE_SHA256"] = hashlib.sha256(content).hexdigest()

    result = _run_setup(environment)

    assert result.returncode == 0
    assert "SHA256 checksum verified successfully" in result.stdout
    assert "already set up" in result.stdout
    assert appimage.exists()
    assert marker.exists()


def test_explicitly_empty_wrapper_directory_is_rejected(
    setup_environment: tuple[Path, dict[str, str]],
) -> None:
    """An explicit empty wrapper path must not fall back to the system path."""
    _, environment = setup_environment
    environment["FREECAD_BIN_DIR"] = ""

    result = _run_setup(environment)

    assert result.returncode != 0
    assert "FREECAD_BIN_DIR is empty" in result.stdout


def test_valid_cache_without_wrappers_continues_setup(
    setup_environment: tuple[Path, dict[str, str]],
) -> None:
    """A valid AppImage alone must not be accepted as a complete installation."""
    appimage_dir, environment = setup_environment
    content = b"verified FreeCAD AppImage without wrappers"
    _, marker = _write_cached_setup(appimage_dir, content)
    _write_extracted_tree(appimage_dir)
    _configure_supported_cached_install(environment, content)

    result = _run_setup(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "SHA256 checksum verified successfully" in result.stdout
    assert "installation is incomplete, will repair" in result.stdout
    assert "already set up" not in result.stdout
    assert marker.read_text() == "test-release\n"
    assert (Path(environment["FREECAD_BIN_DIR"]) / "freecadcmd").is_file()


def test_valid_cache_without_extracted_tree_continues_setup(
    setup_environment: tuple[Path, dict[str, str]],
) -> None:
    """A valid image and wrappers still require the extracted application tree."""
    appimage_dir, environment = setup_environment
    content = b"""#!/bin/sh
if [ "${1:-}" = "--appimage-extract" ]; then
    mkdir -p squashfs-root/usr/bin
    printf '#!/bin/sh\\nexit 0\\n' > squashfs-root/usr/bin/freecadcmd
    printf '#!/bin/sh\\nexit 0\\n' > squashfs-root/usr/bin/freecad
    chmod +x squashfs-root/usr/bin/freecadcmd squashfs-root/usr/bin/freecad
fi
"""
    _, marker = _write_cached_setup(appimage_dir, content)
    _write_wrappers(environment)
    _configure_supported_cached_install(environment, content)

    result = _run_setup(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "SHA256 checksum verified successfully" in result.stdout
    assert "installation is incomplete, will repair" in result.stdout
    assert "already set up" not in result.stdout
    assert (appimage_dir / "squashfs-root" / "usr" / "bin").is_dir()
    assert marker.read_text() == "test-release\n"


def test_local_cache_without_digest_continues_to_release_resolution(
    setup_environment: tuple[Path, dict[str, str]],
) -> None:
    """A local cache must not exit successfully before resolving its digest."""
    appimage_dir, environment = setup_environment
    _write_cached_setup(appimage_dir, b"unverified local cache")
    _write_wrappers(environment)
    _write_extracted_tree(appimage_dir)

    result = _run_setup(environment)

    assert result.returncode != 0
    assert "has no digest, will resolve and verify" in result.stdout
    assert "already set up" not in result.stdout


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


def test_ci_rejects_digestless_cached_appimage(
    setup_environment: tuple[Path, dict[str, str]],
) -> None:
    """CI must reject a cached AppImage when no expected digest is supplied."""
    appimage_dir, environment = setup_environment
    _write_cached_setup(appimage_dir, b"unverified content")
    environment["CI"] = "true"

    result = _run_setup(environment)

    assert result.returncode != 0
    assert "A SHA256 digest is required in CI environments" in result.stdout
    assert "already set up" not in result.stdout


def test_digest_mismatch_reinstalls_and_marks_complete_setup(
    setup_environment: tuple[Path, dict[str, str]],
) -> None:
    """A bad cache must be replaced, verified, extracted, and marked complete."""
    appimage_dir, environment = setup_environment
    _write_cached_setup(appimage_dir, b"unexpected cached content")
    command_dir = Path(environment["PATH"].split(os.pathsep, maxsplit=1)[0])
    _write_command(command_dir / "uname", "#!/bin/sh\nprintf 'x86_64\\n'\n")

    fake_appimage = appimage_dir.parent / "verified-source.AppImage"
    _write_command(
        fake_appimage,
        """#!/bin/sh
if [ "${1:-}" = "--appimage-extract" ]; then
    mkdir -p squashfs-root/usr/bin
    printf '#!/bin/sh\\nexit 0\\n' > squashfs-root/usr/bin/freecadcmd
    printf '#!/bin/sh\\nexit 0\\n' > squashfs-root/usr/bin/freecad
    chmod +x squashfs-root/usr/bin/freecadcmd squashfs-root/usr/bin/freecad
fi
""",
    )
    _write_command(
        command_dir / "curl",
        """#!/bin/sh
destination=''
while [ "$#" -gt 0 ]; do
    if [ "$1" = "-o" ]; then
        shift
        destination="$1"
    fi
    shift
done
cp "$FAKE_APPIMAGE_SOURCE" "$destination"
""",
    )
    environment.update(
        {
            "CI": "true",
            "FAKE_APPIMAGE_SOURCE": str(fake_appimage),
            "FREECAD_APPIMAGE_SHA256": hashlib.sha256(
                fake_appimage.read_bytes()
            ).hexdigest(),
            "FREECAD_APPIMAGE_URL": (
                "https://github.com/FreeCAD/FreeCAD/releases/download/"
                "test-release/FreeCAD-Linux-x86_64.AppImage"
            ),
        }
    )

    result = _run_setup(environment)

    marker = appimage_dir / ".freecad_installed"
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Cached FreeCAD AppImage failed verification" in result.stdout
    assert "SHA256 checksum verified successfully" in result.stdout
    assert marker.read_text() == "test-release\n"
    assert (Path(environment["FREECAD_BIN_DIR"]) / "freecadcmd").is_file()
