"""Tests for the FreeCAD Robust MCP workbench auto-start logic.

These tests verify that the auto-start logic in Init.py is correctly
implemented with proper diagnostic logging and all code paths covered.

This test suite was added after discovering a bug where auto-start wasn't
working because the code flow wasn't properly logging which path was taken,
making it difficult to debug.
"""

import ast
from pathlib import Path

import pytest

# Get the addon directory path
ADDON_DIR = (
    Path(__file__).parent.parent.parent.parent / "addon" / "FreecadRobustMCPBridge"
)


class TestAutoStartPreferences:
    """Tests for auto-start preference functions."""

    @pytest.fixture
    def preferences_code(self) -> str:
        """Load preferences.py content."""
        return (ADDON_DIR / "preferences.py").read_text()

    def test_get_auto_start_function_exists(self, preferences_code: str) -> None:
        """preferences.py should have get_auto_start function."""
        assert "def get_auto_start" in preferences_code

    def test_set_auto_start_function_exists(self, preferences_code: str) -> None:
        """preferences.py should have set_auto_start function."""
        assert "def set_auto_start" in preferences_code

    def test_auto_start_default_is_false(self, preferences_code: str) -> None:
        """Default auto-start should be False for safety."""
        assert "DEFAULT_AUTO_START = False" in preferences_code

    def test_auto_start_uses_param_path(self, preferences_code: str) -> None:
        """Auto-start should use FreeCAD parameter system."""
        assert "PARAM_PATH" in preferences_code
        assert "RobustMCPBridge" in preferences_code

    def test_get_auto_start_returns_bool(self, preferences_code: str) -> None:
        """get_auto_start should return a bool."""
        # Check for GetBool call
        assert "GetBool" in preferences_code
        # Use AST to verify return type annotation
        tree = ast.parse(preferences_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "get_auto_start":
                assert node.returns is not None, (
                    "get_auto_start should have return annotation"
                )
                # Check if return annotation is 'bool'
                if isinstance(node.returns, ast.Name):
                    assert node.returns.id == "bool", "Return type should be bool"
                elif isinstance(node.returns, ast.Constant):
                    # Python 3.9+ may use Constant for some annotations
                    assert node.returns.value == "bool", "Return type should be bool"
                else:
                    pytest.fail(
                        f"Unexpected return annotation type: {type(node.returns)}"
                    )
                return
        pytest.fail("get_auto_start function not found in preferences.py")


class TestAutoStartInitLogic:
    """Tests for auto-start logic in Init.py."""

    @pytest.fixture
    def init_code(self) -> str:
        """Load Init.py content."""
        return (ADDON_DIR / "Init.py").read_text()

    def test_imports_get_auto_start(self, init_code: str) -> None:
        """Init.py should import get_auto_start from preferences."""
        assert "from preferences import get_auto_start" in init_code

    def test_checks_auto_start_preference(self, init_code: str) -> None:
        """Init.py should check the auto_start preference value."""
        # Should call get_auto_start() and store/check the result
        assert "get_auto_start()" in init_code

    def test_logs_auto_start_preference_value(self, init_code: str) -> None:
        """Init.py should log whether auto-start is enabled.

        This diagnostic logging helps debug auto-start issues by showing
        what value was read from preferences.
        """
        # Should log the actual preference value
        assert "Auto-start preference" in init_code

    def test_logs_gui_state(self, init_code: str) -> None:
        """Init.py should log GuiUp, QtCore, and QApp availability.

        This diagnostic logging helps debug which code path is taken.
        """
        assert "GuiUp=" in init_code
        assert "QtCore=" in init_code
        assert "QApp=" in init_code

    def test_handles_gui_already_up_path(self, init_code: str) -> None:
        """Init.py should handle the case when GUI is already up."""
        # Should check FreeCAD.GuiUp and log accordingly
        assert "GUI already up" in init_code

    def test_handles_gui_not_ready_path(self, init_code: str) -> None:
        """Init.py should handle the case when GUI is not yet ready."""
        # Should use GuiWaiter when GUI is not ready but Qt is available
        assert "GUI not ready" in init_code
        assert "GuiWaiter" in init_code

    def test_handles_headless_path(self, init_code: str) -> None:
        """Init.py should handle true headless mode (QCoreApplication only)."""
        # Should detect and handle true headless mode
        assert "True headless mode" in init_code or "headless" in init_code.lower()
        # Should check QCoreApplication to detect true headless
        assert "QCoreApplication" in init_code
        # Should use isinstance to distinguish QCoreApplication from QApplication
        assert "isinstance" in init_code

    def test_imports_gui_waiter(self, init_code: str) -> None:
        """Init.py should import GuiWaiter for waiting on GUI."""
        assert "from freecad_mcp_bridge.bridge_utils import GuiWaiter" in init_code

    def test_uses_single_shot_timer_for_gui_up(self, init_code: str) -> None:
        """When GUI is up, should use single-shot timer for deferred start."""
        assert "setSingleShot(True)" in init_code

    def test_exception_handling_with_traceback(self, init_code: str) -> None:
        """Auto-start setup should catch exceptions and log traceback.

        Without traceback logging, failures are silent and hard to debug.
        """
        assert "except Exception" in init_code
        # Should log the traceback, not just the exception message
        assert "traceback" in init_code.lower()

    @pytest.mark.parametrize(
        "var_name",
        ["_auto_start_timer", "_gui_waiter"],
        ids=["timer_reference", "gui_waiter_reference"],
    )
    def test_global_references_prevent_gc(self, init_code: str, var_name: str) -> None:
        """Global references should be stored at module level to prevent GC.

        Both _auto_start_timer and _gui_waiter must be defined at module level
        (not indented) to prevent garbage collection of Qt timers and callbacks.
        """
        assert var_name in init_code, f"{var_name} should be present in Init.py"
        # Verify module-level definition (line starts with var name, not indented)
        lines = init_code.split("\n")
        for line in lines:
            if line.startswith(var_name):
                # Found module-level definition (not indented)
                return
        pytest.fail(f"{var_name} should be defined at module level (not indented)")


class TestAutoStartBridgeFunction:
    """Tests for the _auto_start_bridge function."""

    @pytest.fixture
    def init_code(self) -> str:
        """Load Init.py content."""
        return (ADDON_DIR / "Init.py").read_text()

    def test_auto_start_bridge_function_exists(self, init_code: str) -> None:
        """_auto_start_bridge function should exist."""
        assert "def _auto_start_bridge" in init_code

    def test_auto_start_bridge_checks_preference_again(self, init_code: str) -> None:
        """_auto_start_bridge should re-check preference before starting.

        This handles the case where preference changed between Init.py load
        and the deferred timer firing.
        """
        # Parse the function body
        tree = ast.parse(init_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_auto_start_bridge":
                # Convert function body back to source for analysis
                func_code = ast.unparse(node)
                assert "get_auto_start" in func_code
                return
        pytest.fail("_auto_start_bridge function not found")

    def test_auto_start_bridge_checks_if_already_running(self, init_code: str) -> None:
        """_auto_start_bridge should check if bridge is already running."""
        # Should check _mcp_plugin.is_running or similar
        assert "is_running" in init_code

    def test_auto_start_bridge_logs_start_message(self, init_code: str) -> None:
        """_auto_start_bridge should log when auto-starting."""
        assert "Auto-starting MCP Bridge" in init_code

    def test_auto_start_bridge_creates_plugin(self, init_code: str) -> None:
        """_auto_start_bridge should create a FreecadMCPPlugin instance."""
        assert "FreecadMCPPlugin" in init_code

    def test_auto_start_bridge_registers_plugin(self, init_code: str) -> None:
        """_auto_start_bridge should register plugin with commands module."""
        assert "register_mcp_plugin" in init_code

    def test_auto_start_bridge_handles_exceptions(self, init_code: str) -> None:
        """_auto_start_bridge should catch and log exceptions."""
        # Parse the function and check for try/except
        tree = ast.parse(init_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_auto_start_bridge":
                # Check if function has try/except
                for child in ast.walk(node):
                    if isinstance(child, ast.Try):
                        return  # Found try/except
        pytest.fail("_auto_start_bridge should have try/except for error handling")


class TestGuiWaiterUsage:
    """Tests for GuiWaiter class usage in auto-start."""

    @pytest.fixture
    def bridge_utils_code(self) -> str:
        """Load bridge_utils.py content."""
        return (ADDON_DIR / "freecad_mcp_bridge" / "bridge_utils.py").read_text()

    def test_gui_waiter_class_exists(self, bridge_utils_code: str) -> None:
        """GuiWaiter class should exist in bridge_utils.py."""
        assert "class GuiWaiter" in bridge_utils_code

    def test_gui_waiter_has_start_method(self, bridge_utils_code: str) -> None:
        """GuiWaiter should have a start method."""
        assert "def start(self)" in bridge_utils_code

    def test_gui_waiter_checks_gui_up(self, bridge_utils_code: str) -> None:
        """GuiWaiter should check FreeCAD.GuiUp."""
        assert "GuiUp" in bridge_utils_code

    def test_gui_waiter_uses_repeating_timer(self, bridge_utils_code: str) -> None:
        """GuiWaiter should use a repeating timer to poll GUI state."""
        # setSingleShot(False) means repeating
        assert "setSingleShot(False)" in bridge_utils_code

    def test_gui_waiter_has_timeout(self, bridge_utils_code: str) -> None:
        """GuiWaiter should have a timeout to prevent infinite waiting."""
        assert "max_retries" in bridge_utils_code or "timeout" in bridge_utils_code

    def test_gui_waiter_defers_callback(self, bridge_utils_code: str) -> None:
        """GuiWaiter should defer callback after GUI is ready.

        This prevents starting the bridge too early when FreeCAD is still
        initializing, which could cause race conditions.
        """
        # Check for specific defer-related patterns to avoid false positives
        # Look for the defer timer, defer_ms parameter, or deferring log message
        has_defer_timer = "_defer_timer" in bridge_utils_code
        has_defer_ms = "defer_ms" in bridge_utils_code
        has_deferring_message = "deferring" in bridge_utils_code.lower()
        assert any([has_defer_timer, has_defer_ms, has_deferring_message]), (
            "GuiWaiter should have defer functionality "
            "(expected _defer_timer, defer_ms, or 'deferring' in code)"
        )

    def test_gui_waiter_logs_waiting_message(self, bridge_utils_code: str) -> None:
        """GuiWaiter should log when it starts waiting."""
        assert "Waiting for GUI" in bridge_utils_code

    def test_gui_waiter_logs_ready_message(self, bridge_utils_code: str) -> None:
        """GuiWaiter should log when GUI becomes ready."""
        assert "GUI ready" in bridge_utils_code

    def test_gui_waiter_logs_timeout_error(self, bridge_utils_code: str) -> None:
        """GuiWaiter should log error on timeout."""
        assert "did not become ready" in bridge_utils_code


class TestInitGuiAutoStart:
    """Tests for auto-start logic in InitGui.py.

    InitGui.py is the primary entry point for auto-start at FreeCAD GUI startup.
    Init.py does NOT run at startup for workbench addons, so InitGui.py must
    handle auto-start using QTimer.singleShot() to defer the bridge start.
    """

    @pytest.fixture
    def initgui_code(self) -> str:
        """Load InitGui.py content."""
        return (ADDON_DIR / "InitGui.py").read_text()

    def test_uses_single_shot_timer_for_auto_start(self, initgui_code: str) -> None:
        """InitGui.py should use QTimer.singleShot for deferred auto-start."""
        # Should use singleShot with a delay
        assert "QTimer.singleShot" in initgui_code
        assert "_auto_start_bridge" in initgui_code

    def test_checks_auto_start_preference(self, initgui_code: str) -> None:
        """InitGui.py should check auto-start preference before scheduling."""
        assert "get_auto_start()" in initgui_code
        # Should only schedule timer if auto-start is enabled
        assert "if get_auto_start():" in initgui_code

    def test_auto_start_bridge_function_exists(self, initgui_code: str) -> None:
        """InitGui.py should have _auto_start_bridge callback function."""
        assert "def _auto_start_bridge" in initgui_code

    def test_auto_start_bridge_checks_if_running(self, initgui_code: str) -> None:
        """_auto_start_bridge should check if bridge is already running."""
        # Parse the function and check for is_bridge_running check
        tree = ast.parse(initgui_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_auto_start_bridge":
                func_code = ast.unparse(node)
                assert "is_bridge_running" in func_code
                return
        pytest.fail("_auto_start_bridge function not found")

    def test_auto_start_syncs_status_bar(self, initgui_code: str) -> None:
        """_auto_start_bridge should sync status bar after starting bridge."""
        # Parse the function and check for sync_status_with_bridge call
        tree = ast.parse(initgui_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_auto_start_bridge":
                func_code = ast.unparse(node)
                assert "sync_status_with_bridge" in func_code
                return
        pytest.fail("_auto_start_bridge function not found")

    def test_logs_auto_start_scheduled(self, initgui_code: str) -> None:
        """InitGui.py should log when auto-start is scheduled."""
        assert "Auto-start scheduled" in initgui_code

    def test_logs_auto_start_disabled(self, initgui_code: str) -> None:
        """InitGui.py should log when auto-start is disabled."""
        assert "Auto-start disabled" in initgui_code


class TestAutoStartCodePaths:
    """Tests to verify all auto-start code paths are properly handled."""

    @pytest.fixture
    def init_code(self) -> str:
        """Load Init.py content."""
        return (ADDON_DIR / "Init.py").read_text()

    def test_four_startup_scenarios_documented(self, init_code: str) -> None:
        """Init.py should document the four startup scenarios.

        1. GUI already up - use timer for deferred start
        2. True headless (QCoreApplication only) - start directly with background thread
        3. GUI not ready but Qt available - use GuiWaiter
        4. No Qt available - start directly (unusual state)
        """
        # Check for documentation of scenarios
        assert "GuiUp is True" in init_code or "GUI is already up" in init_code
        assert "QCoreApplication" in init_code  # True headless detection
        assert "GUI not ready" in init_code
        assert "No Qt available" in init_code or "headless" in init_code.lower()

    def test_all_paths_have_logging(self, init_code: str) -> None:
        """Each code path should have diagnostic logging."""
        # Count distinct log messages for different paths
        log_patterns = [
            "GUI already up",
            "True headless mode",
            "GUI not ready",
            "No Qt available",
        ]
        found = sum(1 for pattern in log_patterns if pattern in init_code)
        assert found >= 4, f"Expected 4 code paths with logging, found {found}"

    def test_pyside_fallback_from_2_to_6(self, init_code: str) -> None:
        """Should try PySide2 first, then fall back to PySide6."""
        # Check for both imports
        assert "PySide2" in init_code
        assert "PySide6" in init_code
        # PySide2 should be tried first (common pattern)
        pyside2_pos = init_code.find("PySide2")
        pyside6_pos = init_code.find("PySide6")
        assert pyside2_pos < pyside6_pos, "Should try PySide2 before PySide6"

    def test_true_headless_detection_via_isinstance(self, init_code: str) -> None:
        """Should use isinstance to detect true headless mode.

        True headless mode is when QCoreApplication exists but is NOT a
        QApplication. This happens with freecadcmd (headless FreeCAD).

        In GUI mode during early startup, there may be no application yet,
        or a QApplication that's being initialized. We need to wait for
        FreeCAD.GuiUp in those cases.
        """
        # Should check QCoreApplication.instance()
        assert "QCoreApplication.instance()" in init_code
        # Should use isinstance to check if it's a QApplication
        assert "isinstance" in init_code
        # Should have a variable tracking true headless state
        assert "_is_true_headless" in init_code
