"""Verify stable workbench releases match the Addon Manager release branch."""

from __future__ import annotations

import argparse
import subprocess  # nosec B404 - invokes git with fixed arguments
import tempfile
import xml.etree.ElementTree as ET  # nosec B405 - local project metadata
import zipfile
from pathlib import Path

from scripts.package_workbench import NAMESPACE, prepare_package


def verify_source(root: Path) -> None:
    """Require the checked-out release and fetched release branch to match."""

    def tree(ref: str) -> str:
        return subprocess.check_output(  # nosec B603, B607  # noqa: S603
            ["git", "rev-parse", "--verify", f"{ref}^{{tree}}"],  # noqa: S607
            cwd=root,
            text=True,
        ).strip()

    if tree("HEAD") != tree("refs/remotes/origin/released"):
        raise ValueError("Tagged source and released branch have different trees")
    manifest = ET.parse(root / "package.xml").getroot()  # nosec B314  # noqa: S314
    urls = manifest.findall(f"{{{NAMESPACE}}}url")
    repositories = [url for url in urls if url.get("type") == "repository"]
    readmes = [url for url in urls if url.get("type") == "readme"]
    if len(repositories) != 1 or repositories[0].get("branch") != "released":
        raise ValueError("Manifest repository must track the released branch")
    if len(readmes) != 1 or not (readmes[0].text or "").endswith("/released/README.md"):
        raise ValueError("Manifest README must track the released branch")


def verify_archive(version: str, directory: Path, root: Path) -> None:
    """Compare every archive file against a package rebuilt from release source."""
    prefix = f"freecad-mcp-workbench-{version}"
    with tempfile.TemporaryDirectory() as temporary:
        package = Path(temporary) / prefix
        if prepare_package(package, root) != version:
            raise ValueError("Release source version does not match archive")
        expected = {
            str(path.relative_to(package.parent)): path.read_bytes()
            for path in package.rglob("*")
            if path.is_file()
        }
        with zipfile.ZipFile(directory / f"{prefix}.zip") as archive:
            files = [item for item in archive.infolist() if not item.is_dir()]
            if len({item.filename for item in files}) != len(files):
                raise ValueError("Release archive contains duplicate paths")
            actual = {item.filename: archive.read(item) for item in files}
        if actual != expected:
            raise ValueError("Release archive differs from the release source package")


def main() -> None:
    """Validate the source branch or built archive for a stable release."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=("source", "archive"))
    parser.add_argument("version", nargs="?")
    parser.add_argument("directory", nargs="?", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    if args.check == "source":
        verify_source(root)
    elif args.version and args.directory:
        verify_archive(args.version, args.directory, root)
    else:
        parser.error("archive requires version and directory")


if __name__ == "__main__":
    main()
