"""Validate the exact workbench archives before publication."""

from __future__ import annotations

import argparse
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def verify_archives(version: str, directory: Path) -> None:
    """Check archive paths, contents, manifests, and release version."""
    prefix = f"freecad-mcp-workbench-{version}"

    def unsafe(name: str) -> bool:
        path = PurePosixPath(name)
        return (
            "\\" in name
            or path.is_absolute()
            or ".." in path.parts
            or (name.rstrip("/") != prefix and not name.startswith(f"{prefix}/"))
        )

    with zipfile.ZipFile(directory / f"{prefix}.zip") as archive:
        if any(unsafe(item.filename) for item in archive.infolist()):
            raise ValueError("Archive contains an unsafe path")
        zipped = {
            item.filename: archive.read(item)
            for item in archive.infolist()
            if not item.is_dir()
        }
    with tarfile.open(directory / f"{prefix}.tar.gz", "r:gz") as tar_archive:
        members = tar_archive.getmembers()
        if any(unsafe(item.name) for item in members):
            raise ValueError("Archive contains an unsafe path")
        if any(not item.isfile() and not item.isdir() for item in members):
            raise ValueError("Archive contains a non-regular entry")
        packed = {}
        for item in members:
            if item.isfile():
                file = tar_archive.extractfile(item)
                if file is None:
                    raise ValueError("Archive entry cannot be read")
                packed[item.name] = file.read()
    if zipped != packed:
        raise ValueError("Archive formats have different contents")
    required = {
        f"{prefix}/{path}"
        for path in (
            "package.xml",
            "LICENSE-CODE",
            "LICENSE-MIT",
            "LICENSE-ICON",
            "NOTICE",
            "freecad/RobustMCPBridge/__init__.py",
            "freecad/RobustMCPBridge/freecad_mcp_bridge/cam_runtime.py",
        )
    }
    if not required.issubset(zipped):
        raise ValueError("Archive is missing required package files")
    manifest = zipped[f"{prefix}/package.xml"].decode("utf-8")
    match = re.search(r"<version>\s*([^<]+?)\s*</version>", manifest)
    actual = match.group(1) if match else None
    if actual != version:
        raise ValueError(f"Archive version {actual!r} does not match {version!r}")


def main() -> None:
    """Validate release archives in a directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    verify_archives(args.version, args.directory)


if __name__ == "__main__":
    main()
