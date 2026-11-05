#!/usr/bin/env python3
"""Launch an isolated FreeCAD profile for manual Addon Manager testing."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # nosec B404 - launches the user-selected FreeCAD executable without a shell
import sys
import tempfile
from pathlib import Path

REPOSITORY = "https://github.com/spkane/freecad-addon-robust-mcp-server"
MARKER = "freecad-robust-mcp-manual-addon-test-v1"


def profile_path() -> Path:
    """Return this user's dedicated temporary test profile."""
    import hashlib

    user = (
        str(os.getuid())
        if hasattr(os, "getuid")
        else os.environ.get("USERNAME", "user")
    )
    suffix = hashlib.sha256(user.encode()).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"freecad-addon-manual-{suffix}"


def _running(pid: int) -> bool:
    """Check conservatively whether a recorded process is still alive."""
    if pid <= 0:
        raise ValueError("Invalid recorded process ID")
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, 0, pid)
        if not handle:
            return ctypes.get_last_error() != 87  # type: ignore[attr-defined]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_state(profile: Path) -> dict:
    if profile.is_symlink() or not profile.is_dir():
        raise ValueError(f"Not a safe test profile directory: {profile}")
    marker = profile / "state.json"
    if marker.is_symlink():
        raise ValueError("Test profile marker is a symlink")
    state = json.loads(marker.read_text(encoding="utf-8"))
    if state.get("marker") != MARKER:
        raise ValueError("Directory is not a recognized manual test profile")
    return state


def _binary() -> str:
    configured = os.environ.get("FREECAD_ADDON_GUI_COMMAND")
    if configured:
        return configured
    if sys.platform == "darwin":
        for app in (Path("/Applications"), Path.home() / "Applications"):
            binary = app / "FreeCAD.app/Contents/Resources/bin/freecad"
            if binary.is_file():
                return str(binary)
    for name in ("freecad", "FreeCAD", "FreeCAD.exe"):
        found = shutil.which(name)
        if found:
            return found
    raise ValueError(
        "FreeCAD not found; set FREECAD_ADDON_GUI_COMMAND to the GUI executable"
    )


def start(profile: Path, ref: str) -> int:
    """Create or reopen the isolated profile, then launch FreeCAD in the background."""
    if not ref or any(char.isspace() for char in ref):
        raise ValueError(
            "The repository ref must be a non-empty branch or tag without spaces"
        )
    binary = _binary()
    if profile.exists() or profile.is_symlink():
        state = _read_state(profile)
        if state.get("pid") and _running(state["pid"]):
            raise ValueError(
                "The test FreeCAD process is still running; close it first"
            )
    else:
        profile.mkdir(mode=0o700)
        state = {"marker": MARKER, "ref": ref}
        (profile / "state.json").write_text(json.dumps(state), encoding="utf-8")
    state["ref"] = ref
    data = profile / "data"
    temporary = profile / "temp"
    if data.is_symlink() or temporary.is_symlink():
        raise ValueError("Test profile directories must not be symlinks")
    data.mkdir(exist_ok=True)
    temporary.mkdir(exist_ok=True)
    (profile / "setup-ready").unlink(missing_ok=True)
    macro = profile / "setup.FCMacro"
    macro.write_text(
        "import FreeCAD\n"
        "from pathlib import Path\n"
        f"expected = Path({str(data)!r}).resolve()\n"
        "actual = Path(FreeCAD.getUserAppDataDir()).resolve()\n"
        "if not actual.is_relative_to(expected):\n"
        "    raise RuntimeError(f'Unsafe Addon Manager test profile: {actual} != {expected}')\n"
        "FreeCAD.ParamGet('User parameter:BaseApp/Preferences/Addons').SetString(\n"
        f"    'CustomRepositories', {f'{REPOSITORY} {ref}'!r})\n"
        f"Path({str(profile / 'setup-ready')!r}).write_text('ready', encoding='utf-8')\n"
        "FreeCAD.Console.PrintMessage('Manual Addon Manager test repository configured.\\n')\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        FREECAD_USER_HOME=str(data),
        FREECAD_USER_DATA=str(data),
        FREECAD_USER_TEMP=str(temporary),
    )
    print(f"Test profile: {profile}\nRepository: {REPOSITORY} ({ref})", flush=True)
    print(
        "\nManual test:\n"
        "1. Open Tools > Addon Manager, find FreeCAD Robust MCP Bridge, and install it.\n"
        "2. Close FreeCAD and rerun this command; confirm the workbench loads once.\n"
        "3. Test bridge start/stop and a paired MCP operation; check Report view.\n"
        "4. Test disable, enable, uninstall, reinstall, and upgrade with restarts.\n"
        "5. Close FreeCAD, then run just freecad::addon-test-clean.\n"
        "Pairing credentials belong to your OS account and are not isolated or removed.\n"
        "Use a disposable OS account if testing pairing or credential removal.\n",
        flush=True,
    )
    log_path = profile / "freecad.log"
    with log_path.open("a", encoding="utf-8") as output:
        process = subprocess.Popen(  # noqa: S603  # nosec B603 - explicit argument list, no shell
            [binary, "--user-cfg", str(data / "user.cfg"), str(macro)],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            if os.name == "nt"
            else 0,
        )
    try:
        state["pid"] = process.pid
        (profile / "state.json").write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        process.terminate()
        process.wait()
        raise
    print(f"FreeCAD launched (PID {process.pid}). Output: {log_path}", flush=True)
    return 0


def clean(profile: Path) -> None:
    """Remove only a recognized test profile whose FreeCAD process has stopped."""
    if not profile.exists() and not profile.is_symlink():
        print("No manual Addon Manager test profile exists.")
        return
    state = _read_state(profile)
    if state.get("pid") and _running(state["pid"]):
        raise ValueError("Close the test FreeCAD process before removing its profile")
    shutil.rmtree(profile)
    print(
        f"Removed test profile: {profile}. OS-account pairing credentials were not changed."
    )


def main() -> int:
    """Parse the command and report actionable errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "clean"))
    parser.add_argument("ref", nargs="?", default="main")
    args = parser.parse_args()
    try:
        if args.action == "start":
            return start(profile_path(), args.ref)
        clean(profile_path())
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Addon Manager test: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
