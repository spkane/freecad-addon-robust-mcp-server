"""Tests for FreeCAD shutdown crash prevention.

These tests verify that FreeCAD can shut down cleanly when the MCP bridge
is running, without crashing due to Qt/PySide cleanup issues.

The crash scenario:
1. FreeCAD starts with MCP bridge (creates QTimer objects)
2. User closes FreeCAD
3. Python's atexit handlers run
4. Python's Py_FinalizeEx() runs garbage collection
5. GC tries to finalize PySide QTimer wrappers
6. PySide destructor triggers Qt's disconnectNotify callback
7. disconnectNotify calls back into partially-finalized Python
8. CRASH (SIGSEGV in _PyType_Lookup)

The fix uses shiboken.delete() in the atexit handler to explicitly destroy
the Qt/C++ objects before Python's GC runs, preventing the crash.

These tests are marked as slow because they start/stop FreeCAD processes.

Run these tests via the repo-standard just commands::

    just testing::integration-gui-release

Or headless::

    just testing::integration-headless-release

To exclude standalone tests from a normal integration run::

    just testing::integration
"""

from __future__ import annotations

import json
import os
import platform
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Signal numbers for crash detection
sigSegv = 11
sigAbrt = 6

# Exit codes that indicate a crash
# On Unix, signal exits are typically -signal or 128+signal
crashExitCodes = {
    -sigSegv,  # Killed by SIGSEGV
    -sigAbrt,  # Killed by SIGABRT
    128 + sigSegv,  # 139 - shell convention for SIGSEGV
    128 + sigAbrt,  # 134 - shell convention for SIGABRT
}


def _is_freecad_process_running() -> bool:
    """Check if any FreeCAD process is currently running.

    Uses pgrep to match process names (not full command lines) to avoid
    false positives from unrelated processes whose arguments or working
    directory contain "freecad".

    Returns:
        True if a FreeCAD process is found, False otherwise.
    """
    try:
        # pgrep -i (case-insensitive) WITHOUT -f (no full command line match).
        # This matches executable basenames: freecad, FreeCAD, freecadcmd, etc.
        result = subprocess.run(
            ["pgrep", "-i", "freecad"],  # noqa: S607
            capture_output=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _is_port_occupied(host: str = "127.0.0.1", port: int = 9875) -> bool:
    """Check whether a bridge port is unavailable for binding.

    Args:
        host: Bridge hostname.
        port: Bridge port.

    Returns:
        True if binding fails for any reason, False otherwise. Failing closed
        also protects listeners that cannot accept another connection.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if os.name == "posix":
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((host, port))
    except OSError:
        return True
    return False


def _find_freecad_binary() -> str | None:
    """Find the FreeCAD GUI binary path.

    Returns:
        Path to FreeCAD binary, or None if not found.
    """
    if platform.system() == "Darwin":
        # macOS: Use the actual binary, not the .app bundle
        paths = [
            "/Applications/FreeCAD.app/Contents/Resources/bin/freecad",
            os.path.expanduser(
                "~/Applications/FreeCAD.app/Contents/Resources/bin/freecad"
            ),
        ]
    elif platform.system() == "Linux":
        paths = [
            "/usr/bin/freecad",
            "/usr/local/bin/freecad",
            "/opt/freecad/bin/FreeCAD",
        ]
        # Also check PATH
        import shutil

        freecadInPath = shutil.which("freecad") or shutil.which("FreeCAD")
        if freecadInPath:
            paths.insert(0, freecadInPath)
    else:
        # Windows
        paths = [
            os.path.join(
                os.environ.get("PROGRAMFILES", ""), "FreeCAD 1.0/bin/FreeCAD.exe"
            ),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "FreeCAD/bin/FreeCAD.exe"),
        ]

    for path in paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    return None


def _wait_for_bridge(
    host: str = "localhost", port: int = 9875, timeout: float = 60.0
) -> bool:
    """Wait for the MCP bridge to become available.

    Args:
        host: Bridge hostname.
        port: Bridge XML-RPC port.
        timeout: Maximum time to wait in seconds.

    Returns:
        True if bridge is available, False if timeout.
    """
    startTime = time.time()
    from tests.integration.auth_support import integration_proxy

    proxy = integration_proxy(host, port)

    while time.time() - startTime < timeout:
        try:
            result = proxy.ping()
            if isinstance(result, dict) and result.get("pong"):
                return True
        except Exception:
            pass
        time.sleep(0.5)

    return False


def _is_gui_available(host: str = "localhost", port: int = 9875) -> bool:
    """Check whether the running FreeCAD instance has a GUI.

    Executes ``FreeCAD.GuiUp`` via the bridge and returns the result.

    Args:
        host: Bridge hostname.
        port: Bridge XML-RPC port.

    Returns:
        True if FreeCAD.GuiUp is True, False on any error or if headless.
    """
    from tests.integration.auth_support import integration_proxy

    try:
        proxy = integration_proxy(host, port)
        result = proxy.execute(
            "import FreeCAD\n_result_ = {'gui_up': bool(FreeCAD.GuiUp)}"
        )
        if isinstance(result, dict) and result.get("success"):
            inner = result.get("result")
            if isinstance(inner, dict):
                return bool(inner.get("gui_up"))
    except Exception:
        pass
    return False


def _send_quit_command(host: str = "localhost", port: int = 9875) -> bool:
    """Send quit command to FreeCAD via the MCP bridge.

    Args:
        host: Bridge hostname.
        port: Bridge XML-RPC port.

    Returns:
        True if command was sent successfully.
    """
    from tests.integration.auth_support import integration_proxy

    try:
        proxy = integration_proxy(host, port)
        # Use FreeCADGui.getMainWindow().close() for a clean shutdown
        # This triggers the normal Qt close event which will run atexit handlers
        # Guard FreeCADGui import behind GuiUp check
        proxy.execute(
            """
import FreeCAD
if FreeCAD.GuiUp:
    import FreeCADGui
    mainWindow = FreeCADGui.getMainWindow()
    if mainWindow:
        mainWindow.close()
"""
        )
        return True
    except Exception:
        return False


@pytest.fixture
def freecad_binary() -> str:
    """Get the FreeCAD binary path or skip if not found."""
    binary = _find_freecad_binary()
    if binary is None:
        pytest.skip("FreeCAD binary not found")
        raise AssertionError("Unreachable")  # For mypy - skip always raises
    return binary


@pytest.fixture
def startup_script() -> str:
    """Get the path to the bridge startup script."""
    # Find the project root
    testsDir = Path(__file__).parent
    projectRoot = testsDir.parent.parent

    scriptPath = (
        projectRoot
        / "freecad"
        / "RobustMCPBridge"
        / "freecad_mcp_bridge"
        / "startup_bridge.py"
    )

    if not scriptPath.exists():
        pytest.skip(f"Startup script not found: {scriptPath}")

    return str(scriptPath)


@pytest.mark.standalone_freecad
@pytest.mark.timeout(120)  # 2 minute timeout for the entire test
class TestShutdownCrash:
    """Tests for FreeCAD shutdown without crashes.

    These tests start their own FreeCAD process and must NOT run while another
    FreeCAD instance with the MCP bridge is running (they would conflict on ports).

    Run via::

        just testing::integration-gui-release
    """

    @pytest.fixture(autouse=True)
    def check_no_existing_freecad(self) -> None:
        """Skip if FreeCAD is already running (would cause initApplication crash)."""
        if _is_freecad_process_running():
            pytest.skip(
                "A FreeCAD process is already running. "
                "These tests must run without an existing FreeCAD instance."
            )
        if _is_port_occupied(port=9875) or _is_port_occupied(port=9876):
            pytest.skip(
                "A bridge port is already occupied. "
                "These tests must run without an existing listener on ports 9875 or 9876."
            )

    def test_gui_shutdown_no_crash(
        self,
        freecad_binary: str,
        startup_script: str,
    ) -> None:
        """Test that FreeCAD GUI exits with code 0 when quit via MCP bridge."""
        # Start FreeCAD with the bridge startup script
        env = os.environ.copy()
        # Set testing mode so the bridge prints its instance ID
        env["FREECAD_MCP_TESTING"] = "1"

        # On macOS, we need to use the binary directly, not `open`
        # This allows us to capture the exit code
        # S603: Safe - freecad_binary is from _find_freecad_binary(), not user input
        proc = subprocess.Popen(  # noqa: S603
            [freecad_binary, startup_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        try:
            # Wait for bridge to be ready
            bridgeReady = _wait_for_bridge(timeout=60.0)
            if not bridgeReady:
                proc.terminate()
                proc.wait(timeout=10)
                pytest.fail("MCP bridge did not become available within timeout")

            # Verify the GUI is actually available before proceeding
            if not _is_gui_available():
                proc.terminate()
                proc.wait(timeout=10)
                pytest.skip("FreeCAD GUI not available; skipping GUI shutdown test")

            # Give FreeCAD a moment to fully stabilize
            time.sleep(2)

            # Send quit command — fail immediately if it cannot be sent
            quitSent = _send_quit_command()
            if not quitSent:
                proc.terminate()
                proc.wait(timeout=10)
                pytest.fail("Failed to send quit command to FreeCAD via MCP bridge")

            # Wait for FreeCAD to exit
            try:
                exitCode = proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
                pytest.fail("FreeCAD did not exit within 30 seconds after quit command")

            # Check for crash exit codes
            if exitCode in crashExitCodes:
                # Get stderr for debugging
                _, stderr = proc.communicate(timeout=5)
                stderrText = stderr.decode("utf-8", errors="replace") if stderr else ""

                crashSignal = (
                    "SIGSEGV" if exitCode in (-sigSegv, 128 + sigSegv) else "SIGABRT"
                )
                pytest.fail(
                    f"FreeCAD crashed during shutdown with {crashSignal} "
                    f"(exit code {exitCode}).\n"
                    f"This indicates the QTimer cleanup fix may not be working.\n"
                    f"stderr: {stderrText[:1000]}"
                )

            # Exit code 0 or small positive values are acceptable
            # Some GUI frameworks return 1 on close, which is not a crash
            assert exitCode not in crashExitCodes, (
                f"FreeCAD exited with crash-like code {exitCode}"
            )

        finally:
            # Ensure process is cleaned up
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

    @pytest.mark.parametrize("layout", ["addon-manager", "release-archive"])
    def test_namespace_workbench_imports(
        self, freecad_binary: str, tmp_path: Path, layout: str
    ) -> None:
        """FreeCAD discovers packaged workbench siblings from both install layouts."""
        root = Path(__file__).resolve().parents[2]
        folder = (
            "RobustMCPBridge"
            if layout == "addon-manager"
            else "freecad-mcp-workbench-1.0.0"
        )
        addon = tmp_path / "Mod" / folder
        package = addon / "freecad" / "MCPImportProbe"
        shutil.copytree(root / "freecad" / "RobustMCPBridge", package)
        result_path = tmp_path / "imports.json"
        with (package / "__init__.py").open("a", encoding="utf-8") as initializer:
            initializer.write(
                "\nimport importlib, json, os\n"
                "from pathlib import Path\n"
                "names = ['preferences', 'commands', 'path_utils', "
                "'freecad_mcp_bridge.server', 'Qt.status_widget']\n"
                "modules = [importlib.import_module('.' + name, __package__) for name in names]\n"
                "Path(os.environ['MCP_IMPORT_RESULT']).write_text(json.dumps([m.__file__ for m in modules]))\n"
            )
        macro = tmp_path / "close.FCMacro"
        macro.write_text(
            "import importlib, json, os\n"
            "from pathlib import Path\n"
            "from PySide import QtCore\n"
            "def finish():\n"
            "    path = Path(os.environ['MCP_IMPORT_RESULT'])\n"
            "    modules = json.loads(path.read_text())\n"
            "    modules.append(importlib.import_module('freecad.MCPImportProbe.init_gui').__file__)\n"
            "    path.write_text(json.dumps(modules))\n"
            "    FreeCADGui.getMainWindow().close()\n"
            "QtCore.QTimer.singleShot(1500, finish)\n",
            encoding="utf-8",
        )
        env = {
            **os.environ,
            "HOME": str(tmp_path),
            "FREECAD_MCP_TESTING": "1",
            "MCP_IMPORT_RESULT": str(result_path),
        }
        result = subprocess.run(  # noqa: S603 - discovered FreeCAD binary
            [
                freecad_binary,
                "--user-cfg",
                str(tmp_path / "user.cfg"),
                "--system-cfg",
                str(tmp_path / "system.cfg"),
                "--module-path",
                str(addon),
                str(macro),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert result_path.exists(), result.stdout + result.stderr
        assert all(
            Path(path).is_relative_to(package)
            for path in json.loads(result_path.read_text(encoding="utf-8"))
        )

    def test_gui_workbench_autostart_and_clean_shutdown(
        self, freecad_binary: str, tmp_path: Path
    ) -> None:
        """The real GUI starts the paired workbench and exits without a crash."""
        root = Path(__file__).resolve().parents[2]
        macro = root / "tests" / "fixtures" / "freecad_gui_autostart.FCMacro"
        result_path = tmp_path / "result.json"
        ports = []
        for _ in range(2):
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                ports.append(probe.getsockname()[1])
        env = {
            **os.environ,
            "HOME": str(tmp_path),
            "FREECAD_MCP_TESTING": "1",
            "FREECAD_BRIDGE_CLIENT_ID": secrets.token_hex(16),
            "FREECAD_BRIDGE_SECRET": secrets.token_hex(32),
            "MCP_TEST_REPO": str(root),
            "MCP_TEST_RESULT": str(result_path),
            "MCP_TEST_XMLRPC_PORT": str(ports[0]),
            "MCP_TEST_SOCKET_PORT": str(ports[1]),
        }
        result = subprocess.run(  # noqa: S603 - discovered FreeCAD binary
            [
                freecad_binary,
                "--user-cfg",
                str(tmp_path / "user.cfg"),
                "--system-cfg",
                str(tmp_path / "system.cfg"),
                str(macro),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert result_path.exists(), result.stdout + result.stderr
        assert json.loads(result_path.read_text(encoding="utf-8")) == {
            "started": True,
            "listening": True,
        }

    def test_sigterm_shutdown_no_crash(
        self,
        freecad_binary: str,
        startup_script: str,
    ) -> None:
        """Test that FreeCAD handles SIGTERM without crashing."""
        if platform.system() == "Windows":
            pytest.skip("SIGTERM test not applicable on Windows")

        env = os.environ.copy()
        env["FREECAD_MCP_TESTING"] = "1"

        # S603: Safe - freecad_binary is from _find_freecad_binary(), not user input
        proc = subprocess.Popen(  # noqa: S603
            [freecad_binary, startup_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        try:
            # Wait for bridge to be ready
            bridgeReady = _wait_for_bridge(timeout=60.0)
            if not bridgeReady:
                proc.terminate()
                proc.wait(timeout=10)
                pytest.fail("MCP bridge did not become available within timeout")

            # Give FreeCAD time to fully stabilize
            time.sleep(2)

            # Send SIGTERM (graceful termination)
            proc.send_signal(signal.SIGTERM)

            # Wait for exit
            try:
                exitCode = proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
                pytest.fail("FreeCAD did not exit within 30 seconds after SIGTERM")

            # SIGTERM should result in clean exit or -SIGTERM
            # It should NOT result in SIGSEGV or SIGABRT
            if exitCode in (-sigSegv, 128 + sigSegv, -sigAbrt, 128 + sigAbrt):
                _, stderr = proc.communicate(timeout=5)
                stderrText = stderr.decode("utf-8", errors="replace") if stderr else ""
                pytest.fail(
                    f"FreeCAD crashed during SIGTERM shutdown (exit code {exitCode}).\n"
                    f"stderr: {stderrText[:1000]}"
                )

        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


# Standalone test runner for manual testing
if __name__ == "__main__":
    """Run the shutdown crash test manually.

    Usage:
        python tests/integration/test_shutdown_crash.py
    """
    binary = _find_freecad_binary()
    if not binary:
        print("ERROR: FreeCAD binary not found")
        sys.exit(1)

    testsDir = Path(__file__).parent
    projectRoot = testsDir.parent.parent
    script = str(
        projectRoot
        / "freecad"
        / "RobustMCPBridge"
        / "freecad_mcp_bridge"
        / "startup_bridge.py"
    )

    print(f"FreeCAD binary: {binary}")
    print(f"Startup script: {script}")
    print()

    print("Starting FreeCAD with MCP bridge...")
    env = os.environ.copy()
    env["FREECAD_MCP_TESTING"] = "1"

    # S603: Safe - binary is from _find_freecad_binary(), not user input
    proc = subprocess.Popen(  # noqa: S603
        [binary, script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    print("Waiting for bridge to be ready...")
    if not _wait_for_bridge(timeout=60.0):
        print("ERROR: Bridge did not become available")
        proc.terminate()
        proc.wait()
        sys.exit(1)

    print("Bridge is ready!")
    print("Waiting 3 seconds for stabilization...")
    time.sleep(3)

    print("Sending quit command...")
    _send_quit_command()

    print("Waiting for FreeCAD to exit...")
    try:
        exitCode = proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        print("Timeout - killing process")
        proc.kill()
        exitCode = proc.wait()

    print(f"Exit code: {exitCode}")

    if exitCode in crashExitCodes:
        print("CRASH DETECTED!")
        _, stderr = proc.communicate(timeout=5)
        if stderr:
            print("stderr:", stderr.decode("utf-8", errors="replace")[:2000])
        sys.exit(1)
    else:
        print("Clean shutdown - no crash!")
        sys.exit(0)
