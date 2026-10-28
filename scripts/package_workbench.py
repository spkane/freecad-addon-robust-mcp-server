"""Build an installable FreeCAD workbench package and release archives."""

from __future__ import annotations

import argparse
import re
import shutil
import tarfile
import tempfile
import xml.etree.ElementTree as ET  # nosec B405 - parses repository metadata only
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = "https://wiki.freecad.org/Package_Metadata"
LICENSE_FILES = ("LICENSE-CODE", "LICENSE-MIT", "LICENSE-ICON", "NOTICE")


def prepare_package(destination: Path, root: Path = ROOT) -> str:
    """Create an installable workbench directory and return its version.

    Args:
        destination: New workbench directory to create.
        root: Repository root containing the workbench and metadata.

    Returns:
        The workbench version from the package metadata.

    Raises:
        ValueError: If required workbench metadata is absent or invalid.
        FileExistsError: If the destination already exists.
    """
    tree = ET.parse(root / "package.xml")  # nosec B314  # noqa: S314 - local metadata
    package = tree.getroot()
    namespace = {"pkg": NAMESPACE}
    workbench = package.find("pkg:content/pkg:workbench", namespace)
    if workbench is None:
        raise ValueError("package.xml does not describe a workbench")
    version = workbench.findtext("pkg:version", namespaces=namespace)
    if not version:
        raise ValueError("package.xml has no workbench version")
    for license_element in package.findall("pkg:license", namespace):
        filename = license_element.get("file")
        if filename not in LICENSE_FILES or not (root / filename).is_file():
            raise ValueError(f"Invalid license file in package.xml: {filename}")

    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(
        root / "freecad" / "RobustMCPBridge",
        destination / "freecad" / "RobustMCPBridge",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )
    for filename in LICENSE_FILES:
        shutil.copy2(root / filename, destination / filename)

    # FreeCAD expects standalone package version and its icon path at the root.
    version_element = ET.Element(f"{{{NAMESPACE}}}version")
    version_element.text = version
    package.insert(1, version_element)
    ET.register_namespace("", NAMESPACE)
    ET.indent(tree, space="    ")
    tree.write(destination / "package.xml", encoding="utf-8", xml_declaration=True)
    (destination / "README.md").write_text(
        f"# Robust MCP Bridge Workbench {version}\n\n"
        "Extract this directory into your FreeCAD Mod directory and restart FreeCAD. "
        "Select the Robust MCP Bridge workbench, then pair the MCP server and bridge.\n\n"
        "The workbench is not currently listed in the public Addon Manager catalog. "
        "See the [installation guide](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/getting-started/installation/).\n\n"
        "See LICENSE-CODE, LICENSE-MIT, LICENSE-ICON, and NOTICE for license and attribution details.\n",
        encoding="utf-8",
    )
    return version


def create_archives(version: str, output: Path, root: Path = ROOT) -> None:
    """Build tar.gz and zip release artifacts containing the installable package.

    Args:
        version: Version to match against the workbench manifest.
        output: Directory receiving the two release artifacts.
        root: Repository root containing the workbench and metadata.

    Raises:
        ValueError: If the requested version does not match the manifest.
    """
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.]+)?", version):
        raise ValueError("Invalid workbench release version")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="freecad-workbench-") as temp:
        package = Path(temp) / f"freecad-mcp-workbench-{version}"
        actual = prepare_package(package, root)
        if actual != version:
            raise ValueError(f"Workbench version {actual} does not match {version}")
        with tarfile.open(output / f"{package.name}.tar.gz", "w:gz") as archive:
            archive.add(package, arcname=package.name)
        with zipfile.ZipFile(
            output / f"{package.name}.zip", "w", zipfile.ZIP_DEFLATED
        ) as archive:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(package.parent))


def main() -> None:
    """Run the package directory or release archive builder."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    install = subparsers.add_parser("install", help="Create an installable directory")
    install.add_argument("destination", type=Path)
    archives = subparsers.add_parser("archives", help="Build release archives")
    archives.add_argument("version")
    archives.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "install":
        print(f"Packaged workbench {prepare_package(args.destination)}")
    else:
        create_archives(args.version, args.output)


if __name__ == "__main__":
    main()
