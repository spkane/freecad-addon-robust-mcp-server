"""Reconcile reviewed CAM release inventory with gated GitHub releases."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess  # nosec B404 - fixed GitHub CLI and validated arguments
import sys
import tomllib
from pathlib import Path
from typing import Any

from scripts.verify_cam_release_compatibility import _validate_entry

REPO = "spkane/freecad-addon-robust-mcp-server"
MARKER = "cam-gate-v1.json"
INVENTORY = "cam-compatibility.toml"
KINDS = {"server": "robust-mcp-server-v", "workbench": "robust-mcp-workbench-v"}
PLURAL = {"server": "servers", "workbench": "workbenches"}


def gh(*args: str) -> bytes:
    """Run GitHub CLI without exposing authentication credentials."""
    return subprocess.check_output(["gh", *args])  # nosec B603 B607  # noqa: S603, S607


def inventory(data: bytes) -> dict[str, Any]:
    """Read and validate the supported and explicitly retired releases."""
    result = tomllib.loads(data.decode())
    keys = {
        f"{status}_{PLURAL[kind]}"
        for status in ("compatible", "retired")
        for kind in KINDS
    }
    if set(result) != keys or any(not isinstance(result[key], list) for key in keys):
        raise ValueError("Invalid CAM compatibility inventory fields")
    for kind, prefix in KINDS.items():
        seen = set()
        for entry in result[f"compatible_{PLURAL[kind]}"]:
            tag, _, _ = _validate_entry(entry, kind)
            if tag in seen:
                raise ValueError(f"Duplicate CAM release: {tag}")
            seen.add(tag)
        for entry in result[f"retired_{PLURAL[kind]}"]:
            if (
                not isinstance(entry, dict)
                or set(entry) != {"tag", "reason"}
                or not isinstance(entry["tag"], str)
                or not entry["tag"].startswith(prefix)
                or not re.fullmatch(r"[A-Za-z0-9._-]+", entry["tag"])
                or not isinstance(entry["reason"], str)
                or not entry["reason"].strip()
                or entry["tag"] in seen
            ):
                raise ValueError(f"Invalid or duplicate retired {kind} release")
            seen.add(entry["tag"])
    return result


def published_releases() -> list[dict[str, Any]]:
    """Get all releases, including drafts, from the authoritative repository."""
    pages = gh("api", "--paginate", "--slurp", f"repos/{REPO}/releases?per_page=100")
    return [release for page in json.loads(pages) for release in page]


def source_has_cam(tag: str, kind: str) -> bool:
    """Check the released source for CAM when a release lacks a gate marker."""
    path = (
        "src/freecad_mcp/tools/cam.py"
        if kind == "server"
        else "freecad/RobustMCPBridge/freecad_mcp_bridge/cam_runtime.py"
    )
    executable = shutil.which("gh")
    if not executable:
        raise RuntimeError("GitHub CLI is required for CAM release reconciliation")
    result = subprocess.run(  # nosec B603  # noqa: S603
        [executable, "api", "--silent", f"repos/{REPO}/contents/{path}?ref={tag}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    if "HTTP 404" in result.stderr:
        return False
    raise RuntimeError(
        f"Could not inspect release source for {tag}: {result.stderr.strip()}"
    )


def discover(
    releases: list[dict[str, Any]], retired: set[str] | None = None
) -> dict[str, dict[str, dict[str, str]]]:
    """Identify gated releases and block unresolved staged publications."""
    found: dict[str, dict[str, dict[str, str]]] = {kind: {} for kind in KINDS}
    for release in releases:
        tag = release["tag_name"]
        kind = next(
            (key for key, prefix in KINDS.items() if tag.startswith(prefix)), None
        )
        if kind is None:
            continue
        if not re.fullmatch(r"[A-Za-z0-9._-]+", tag):
            raise ValueError(f"Invalid release tag: {tag}")
        assets = release["assets"]
        if not any(asset["name"] == MARKER for asset in assets):
            if (
                not release["draft"]
                and tag not in (retired or set())
                and source_has_cam(tag, kind)
            ):
                raise RuntimeError(
                    f"Published CAM-capable release {tag} has no gate receipt; investigate before publishing. See docs/development/release-recovery.md."
                )
            continue
        if release["draft"]:
            raise RuntimeError(
                f"Incomplete staged CAM release {tag}; finish or resolve it before "
                "publishing another component. See docs/development/release-recovery.md."
            )
        if tag in (retired or set()):
            continue
        suffix = ".whl" if kind == "server" else ".zip"
        matches = [a for a in assets if a["name"].endswith(suffix)]
        if len(matches) != 1:
            raise ValueError(f"Expected one {suffix} asset for gated release {tag}")
        asset = matches[0]
        digest = asset.get("digest") or ""
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ValueError(f"Missing SHA-256 for {tag}/{asset['name']}")
        entry = {"tag": tag, "asset": asset["name"], "sha256": digest[7:]}
        marker_asset = next(a for a in assets if a["name"] == MARKER)
        marker_bytes = gh(
            "api",
            "-H",
            "Accept: application/octet-stream",
            f"repos/{REPO}/releases/assets/{marker_asset['id']}",
        )
        receipt = json.loads(marker_bytes)
        if receipt != {"version": 1, **entry}:
            raise ValueError(f"CAM gate marker does not match the release asset: {tag}")
            _validate_entry(entry, kind)
        found[kind][tag] = entry
    return found


def reconcile(
    manifest: dict[str, Any], releases: dict[str, dict[str, dict[str, str]]]
) -> list[str]:
    """Return missing releases and reject changed or missing pinned assets."""
    missing: list[str] = []
    for kind in KINDS:
        recorded = {
            entry["tag"]: entry for entry in manifest[f"compatible_{PLURAL[kind]}"]
        }
        retired = {entry["tag"] for entry in manifest[f"retired_{PLURAL[kind]}"]}
        for tag, entry in recorded.items():
            if releases[kind].get(tag) != entry:
                raise ValueError(f"Pinned CAM release is missing or changed: {tag}")
        missing.extend(
            tag for tag in releases[kind] if tag not in recorded and tag not in retired
        )
    return sorted(missing)


def main_inventory() -> bytes:
    """Fetch the latest reviewed inventory from the default branch."""
    response = json.loads(gh("api", f"repos/{REPO}/contents/{INVENTORY}?ref=main"))
    return base64.b64decode(response["content"], validate=False)


def marker(tag: str, artifact: Path, output: Path) -> None:
    """Write a marker identifying the artifact that passed the CAM gate."""
    kind = next((key for key, prefix in KINDS.items() if tag.startswith(prefix)), None)
    if kind is None:
        raise ValueError("Invalid release tag")
    entry = {
        "tag": tag,
        "asset": artifact.name,
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    }
    _validate_entry(entry, kind)
    output.write_text(json.dumps({"version": 1, **entry}, sort_keys=True) + "\n")


def render(manifest: dict[str, Any]) -> str:
    """Produce a deterministic inventory while retaining explicit retirements."""
    result = [
        "# CAM releases covered by the release gate. Retire versions by reviewed PR."
    ]
    for status in ("compatible", "retired"):
        for kind in KINDS:
            key = f"{status}_{PLURAL[kind]}"
            entries = sorted(manifest[key], key=lambda entry: entry["tag"])
            if not entries:
                result.append(f"{key} = []")
                continue
            result.append(f"{key} = [")
            for entry in entries:
                fields = ", ".join(
                    f"{field} = {json.dumps(value, ensure_ascii=True)}"
                    for field, value in entry.items()
                )
                result.append(f"  {{ {fields} }},")
            result.append("]")
    return "\n".join(result) + "\n"


def main() -> None:
    """Prepare a gate marker or reconcile the release inventory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("marker", "check", "check-current", "update")
    )
    parser.add_argument("--tag")
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "marker":
        if not args.tag or not args.artifact or not args.output:
            parser.error("marker requires --tag, --artifact and --output")
        marker(args.tag, args.artifact, args.output)
        return
    reviewed = main_inventory()
    manifest = inventory(reviewed)
    if args.command == "check-current":
        if inventory(Path(INVENTORY).read_bytes()) != manifest:
            raise RuntimeError(
                "The reviewed CAM inventory changed during this release; resolve the staged release and rerun the gate from current main."
            )
        return
    retired = {
        entry["tag"] for kind in KINDS for entry in manifest[f"retired_{PLURAL[kind]}"]
    }
    releases = discover(published_releases(), retired)
    missing = reconcile(manifest, releases)
    if args.command == "check":
        if inventory(Path(INVENTORY).read_bytes()) != manifest:
            raise RuntimeError(
                "The tagged CAM inventory differs from main; merge the inventory update and create a new release tag from current main."
            )
        if missing:
            raise RuntimeError(
                "CAM inventory update required before publication: "
                + ", ".join(missing)
                + ". Merge the generated inventory PR (or see docs/development/release-recovery.md)."
            )
    else:
        if not args.tag or not any(args.tag in releases[kind] for kind in KINDS):
            raise RuntimeError(
                "Published gated release was not found; no inventory update was created"
            )
        for kind in KINDS:
            manifest[f"compatible_{PLURAL[kind]}"].extend(
                releases[kind][tag] for tag in missing if tag in releases[kind]
            )
        Path(INVENTORY).write_text(render(manifest))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"CAM release inventory: {exc}", file=sys.stderr)
        sys.exit(1)
