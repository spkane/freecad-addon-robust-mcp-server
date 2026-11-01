"""Exercise pinned independently released CAM components against candidates."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess  # nosec B404 - fixed tools and validated arguments
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = "spkane/freecad-addon-robust-mcp-server"


def _validate_entry(entry: Any, kind: str) -> tuple[str, str, str]:
    """Validate a pinned GitHub release identity and expected SHA-256."""
    if not isinstance(entry, dict) or set(entry) != {"tag", "asset", "sha256"}:
        raise ValueError(f"Invalid {kind} compatibility entry")
    tag, asset, digest = (entry[key] for key in ("tag", "asset", "sha256"))
    prefix = "robust-mcp-server-v" if kind == "server" else "robust-mcp-workbench-v"
    suffix = ".whl" if kind == "server" else ".zip"
    if (
        not isinstance(tag, str)
        or not tag.startswith(prefix)
        or not re.fullmatch(r"[A-Za-z0-9._-]+", tag)
        or not isinstance(asset, str)
        or not asset.endswith(suffix)
        or not re.fullmatch(r"[A-Za-z0-9._-]+", asset)
        or not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
    ):
        raise ValueError(f"Invalid {kind} release tag, asset or SHA-256")
    return tag, asset, digest


def _download(entry: Any, kind: str, directory: Path) -> Path:
    """Download a pinned artifact and reject any digest mismatch."""
    tag, name, expected = _validate_entry(entry, kind)
    directory.mkdir(parents=True, exist_ok=True)
    gh = shutil.which("gh")
    if gh is None:
        raise RuntimeError("GitHub CLI is required for compatibility tests")
    subprocess.run(  # nosec B603  # noqa: S603 - validated arguments
        [
            gh,
            "release",
            "download",
            tag,
            "--repo",
            REPO,
            "--pattern",
            name,
            "--dir",
            str(directory),
        ],
        check=True,
    )
    path = directory / name
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"SHA-256 mismatch for {tag}/{name}")
    return path


def main() -> None:
    """Run each declared server/workbench pairing with the opposite candidate."""
    with (ROOT / "cam-compatibility.toml").open("rb") as manifest_file:
        manifest = tomllib.load(manifest_file)
    if set(manifest) != {
        "compatible_servers",
        "compatible_workbenches",
        "retired_servers",
        "retired_workbenches",
    }:
        raise ValueError("Invalid CAM compatibility inventory")
    server_entries = manifest["compatible_servers"]
    workbench_entries = manifest["compatible_workbenches"]
    if not isinstance(server_entries, list) or not isinstance(workbench_entries, list):
        raise ValueError("CAM compatibility inventories must be lists")
    for kind, entries in (("server", server_entries), ("workbench", workbench_entries)):
        for entry in entries:
            _validate_entry(entry, kind)
    with tempfile.TemporaryDirectory(prefix="cam-compatibility-") as temporary:
        temp = Path(temporary)
        uv = shutil.which("uv")
        for index, entry in enumerate(server_entries):
            if uv is None:
                raise RuntimeError("uv is required for server compatibility tests")
            wheel = _download(entry, "server", temp / f"server-{index}")
            venv = temp / f"server-venv-{index}"
            subprocess.run(  # nosec B603  # noqa: S603
                [uv, "venv", "--python", "3.11", str(venv)],
                env=_without_github_tokens(),
                check=True,
            )
            python = venv / "bin/python"
            subprocess.run(  # nosec B603  # noqa: S603 - verified wheel
                [uv, "pip", "install", "--python", str(python), str(wheel)],
                env=_without_github_tokens(),
                check=True,
            )
            _run_test({"FREECAD_MCP_TEST_PYTHON": str(python)})
        for index, entry in enumerate(workbench_entries):
            archive = _download(entry, "workbench", temp / f"workbench-{index}")
            _run_test({"FREECAD_RELEASE_WORKBENCH_ARCHIVE": str(archive)})


def _without_github_tokens() -> dict[str, str]:
    """Keep the release token out of installed artifacts and test subprocesses."""
    return {
        key: value
        for key, value in os.environ.items()
        if key not in {"GH_TOKEN", "GITHUB_TOKEN"}
    }


def _run_test(overrides: dict[str, str]) -> None:
    """Run the real FreeCAD smoke test with the chosen release artifact."""
    env = {**_without_github_tokens(), **overrides, "FREECAD_CAM_RELEASE_GATE": "0"}
    subprocess.run(  # nosec B603 - current Python and fixed test selector
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration/test_authenticated_standalone.py::test_authenticated_transports_with_real_freecad",
            "-v",
            "--tb=short",
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
