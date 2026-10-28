"""Exercise the actual workbench release builder and archive contents."""

import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NS = {"pkg": "https://wiki.freecad.org/Package_Metadata"}


def test_release_archives_contain_installable_workbench(tmp_path: Path) -> None:
    """Both published formats contain a complete, consistent package."""
    tree = ET.parse(ROOT / "package.xml")  # noqa: S314 - repository metadata
    version = tree.findtext(".//pkg:workbench/pkg:version", namespaces=NS)
    assert version
    subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [
            sys.executable,
            str(ROOT / "scripts/package_workbench.py"),
            "archives",
            version,
            str(tmp_path),
        ],
        check=True,
    )
    prefix = f"freecad-mcp-workbench-{version}"
    zip_path = tmp_path / f"{prefix}.zip"
    tar_path = tmp_path / f"{prefix}.tar.gz"
    with zipfile.ZipFile(zip_path) as archive:
        files = {name for name in archive.namelist() if not name.endswith("/")}
        manifest_bytes = archive.read(f"{prefix}/package.xml")
        for name in ("LICENSE-CODE", "LICENSE-MIT", "LICENSE-ICON", "NOTICE"):
            assert archive.read(f"{prefix}/{name}") == (ROOT / name).read_bytes()
    with tarfile.open(tar_path, "r:gz") as archive:
        tar_files = {member.name for member in archive.getmembers() if member.isfile()}
        assert tar_files == files
        for name in (
            "LICENSE-CODE",
            "LICENSE-MIT",
            "LICENSE-ICON",
            "NOTICE",
            "package.xml",
        ):
            extracted = archive.extractfile(f"{prefix}/{name}")
            assert extracted is not None
            assert extracted.read() == (
                manifest_bytes if name == "package.xml" else (ROOT / name).read_bytes()
            )
    manifest = ET.fromstring(manifest_bytes)  # noqa: S314 - archive built in this test
    assert manifest.findtext("pkg:version", namespaces=NS) == version
    for license_entry in manifest.findall("pkg:license", NS):
        assert f"{prefix}/{license_entry.attrib['file']}" in files
    subdirectory = manifest.findtext(".//pkg:workbench/pkg:subdirectory", namespaces=NS)
    assert subdirectory
    assert f"{prefix}/{subdirectory.removeprefix('./')}__init__.py" in files
    icon = manifest.findtext("pkg:icon", namespaces=NS)
    assert f"{prefix}/{icon}" in files
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in files)


def test_release_builder_rejects_wrong_version(tmp_path: Path) -> None:
    """Do not publish a package whose release and manifest versions disagree."""
    result = subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [
            sys.executable,
            str(ROOT / "scripts/package_workbench.py"),
            "archives",
            "99.99.99",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "does not match" in result.stderr
    assert not list(tmp_path.iterdir())


def test_source_package_builder_creates_complete_installation(tmp_path: Path) -> None:
    """The source installer uses the same complete package layout as releases."""
    destination = tmp_path / "installed-workbench"
    subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [
            sys.executable,
            str(ROOT / "scripts/package_workbench.py"),
            "install",
            str(destination),
        ],
        check=True,
    )
    manifest = ET.parse(destination / "package.xml")  # noqa: S314 - generated metadata
    for entry in manifest.findall("pkg:license", NS):
        name = entry.attrib["file"]
        assert (destination / name).read_bytes() == (ROOT / name).read_bytes()
    assert (destination / "NOTICE").read_bytes() == (ROOT / "NOTICE").read_bytes()
    assert (destination / "freecad/RobustMCPBridge/__init__.py").is_file()
