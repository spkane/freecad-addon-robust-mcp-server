"""Install the workbench from a source checkout without shell-specific tools."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

if __package__:
    from .package_workbench import prepare_package
else:
    from package_workbench import prepare_package  # type: ignore[no-redef]


def select_mod_directory(base: Path) -> Path:
    """Choose the newest existing versioned profile, or the unversioned profile."""
    versions = []
    if base.is_dir():
        for child in base.iterdir():
            match = re.fullmatch(r"v(\d+)-(\d+)", child.name)
            if match and child.is_dir():
                versions.append(((int(match[1]), int(match[2])), child))
    profile = max(versions, key=lambda item: item[0])[1] if versions else base
    return profile / "Mod"


def default_mod_directory() -> Path:
    """Locate the FreeCAD profile directory for this operating system."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA is not set; specify --mod-dir explicitly")
        base = Path(appdata) / "FreeCAD"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "FreeCAD"
    elif sys.platform.startswith("linux"):
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
        base /= "FreeCAD"
    else:
        raise RuntimeError("Unsupported platform; specify --mod-dir explicitly")
    return select_mod_directory(base)


def install_workbench(mod_directory: Path) -> Path:
    """Build and install the package, restoring an existing installation on failure."""
    mod_directory.mkdir(parents=True, exist_ok=True)
    destination = mod_directory / "RobustMCPBridge"
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError(
            f"Installation target is not a regular directory: {destination}"
        )

    staging = Path(tempfile.mkdtemp(prefix=".robust-mcp-install-", dir=mod_directory))
    package = staging / "new"
    backup = staging / "previous"
    try:
        prepare_package(package)
        if destination.exists():
            destination.rename(backup)
        try:
            package.rename(destination)
        except OSError:
            if backup.exists():
                backup.rename(destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        # Preserve the backup if replacing or restoring the existing install fails.
        if not backup.exists():
            shutil.rmtree(staging)
    return destination


def main() -> None:
    """Install into the detected profile or an explicitly selected Mod directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod-dir", type=Path, help="FreeCAD Mod directory to use")
    args = parser.parse_args()
    destination = install_workbench(args.mod_dir or default_mod_directory())
    print(f"Installed workbench at: {destination}")
    print("Restart FreeCAD and select the Robust MCP Bridge workbench.")


if __name__ == "__main__":
    main()
