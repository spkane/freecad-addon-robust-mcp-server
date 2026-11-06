"""Test stable workbench source and archive release guards."""

# ruff: noqa: S603, S607

import subprocess
import xml.etree.ElementTree as ET  # nosec B405 - local test metadata
import zipfile
from pathlib import Path

import pytest
from scripts.package_workbench import create_archives
from scripts.verify_released_workbench import verify_archive, verify_source

ROOT = Path(__file__).resolve().parents[2]


def test_release_branch_must_match_tagged_tree(tmp_path: Path) -> None:
    """Reject changed release-branch contents and accept identical trees."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "package.xml").write_text((ROOT / "package.xml").read_text())
    subprocess.run(["git", "add", "package.xml"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "first"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/released", "HEAD"],
        cwd=tmp_path,
        check=True,
    )
    verify_source(tmp_path)
    (tmp_path / "extra").write_text("different")
    subprocess.run(["git", "add", "extra"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "second"], cwd=tmp_path, check=True)
    with pytest.raises(ValueError, match="different trees"):
        verify_source(tmp_path)


def test_release_archive_must_match_packaged_source(tmp_path: Path) -> None:
    """Reject added or changed archive files even when the version matches."""
    manifest = ET.parse(ROOT / "package.xml").getroot()  # nosec B314  # noqa: S314
    version = manifest.findtext("{https://wiki.freecad.org/Package_Metadata}version")
    assert version
    create_archives(version, tmp_path, ROOT)
    verify_archive(version, tmp_path, ROOT)
    archive = tmp_path / f"freecad-mcp-workbench-{version}.zip"
    with zipfile.ZipFile(archive, "a") as output:
        output.writestr(f"freecad-mcp-workbench-{version}/extra", "unexpected")
    with pytest.raises(ValueError, match="differs"):
        verify_archive(version, tmp_path, ROOT)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('branch="released"', 'branch="main"', "repository"),
        (
            "https://raw.githubusercontent.com/spkane/",
            "https://example.com/spkane/",
            "README",
        ),
        ('<url type="readme">', '<url type="readme">', "README"),
    ],
)
def test_source_rejects_invalid_manifest_urls(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    """Reject incorrect branch, foreign README URLs, and duplicate entries."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    manifest = tmp_path / "package.xml"
    text = (ROOT / "package.xml").read_text()
    if old == new:
        line = next(line for line in text.splitlines() if old in line)
        text = text.replace(line, f"{line}\n{line}")
    else:
        assert old in text
        text = text.replace(old, new)
    manifest.write_text(text)
    subprocess.run(["git", "add", "package.xml"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "invalid metadata"], cwd=tmp_path, check=True
    )
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/released", "HEAD"],
        cwd=tmp_path,
        check=True,
    )
    with pytest.raises(ValueError, match=message):
        verify_source(tmp_path)


def test_archive_rejects_wrong_source_version(tmp_path: Path) -> None:
    """Do not accept an archive named for a different version."""
    with pytest.raises(ValueError, match="version"):
        verify_archive("99.0.0", tmp_path, ROOT)


def test_archive_rejects_duplicate_paths(tmp_path: Path) -> None:
    """A ZIP with duplicate entries cannot be accepted as matching source."""
    import warnings

    manifest = ET.parse(ROOT / "package.xml").getroot()  # nosec B314  # noqa: S314
    version = manifest.findtext("{https://wiki.freecad.org/Package_Metadata}version")
    assert version
    create_archives(version, tmp_path, ROOT)
    archive = tmp_path / f"freecad-mcp-workbench-{version}.zip"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(archive, "a") as output:
            output.writestr(f"freecad-mcp-workbench-{version}/README.md", "replacement")
    with pytest.raises(ValueError, match="duplicate"):
        verify_archive(version, tmp_path, ROOT)
