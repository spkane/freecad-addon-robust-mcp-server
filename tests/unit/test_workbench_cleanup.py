"""Tests for workbench bridge cleanup during Python exit.

These tests verify that the MCP bridge plugin properly cleans up during
Python finalization (atexit handlers) without accessing destroyed GUI elements.

The key issue: During Python's Py_FinalizeEx(), the garbage collector tries to
finalize PySide QTimer wrapper objects. This triggers Qt's disconnectNotify
callback which tries to do Python operations on a partially-finalized interpreter,
causing a SIGSEGV crash.

The fix uses shiboken.delete() to explicitly destroy the C++ QTimer objects
BEFORE Python's GC runs, which marks the PySide wrappers as invalid so the
GC won't try to destroy them again.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestCleanupForExit:
    """Tests for _cleanup_for_exit method."""

    @pytest.fixture
    def mock_freecad_env(self):
        """Set up mocked FreeCAD environment for testing plugin code."""
        # Create mock modules
        mock_freecad = MagicMock()
        mock_freecad.GuiUp = True
        mock_freecad.Console = MagicMock()

        mock_freecadgui = MagicMock()

        # Patch the imports before importing the plugin module
        with patch.dict(
            sys.modules,
            {
                "FreeCAD": mock_freecad,
                "FreeCADGui": mock_freecadgui,
            },
        ):
            yield {
                "FreeCAD": mock_freecad,
                "FreeCADGui": mock_freecadgui,
            }

    @pytest.fixture
    def mock_qt_env(self, mock_freecad_env):
        """Set up mocked Qt environment with shiboken."""
        mock_qtcore = MagicMock()
        mock_timer = MagicMock()
        mock_qtcore.QTimer.return_value = mock_timer

        # Mock shiboken delete function
        mock_shiboken_delete = MagicMock()
        mock_shiboken6 = MagicMock()
        mock_shiboken6.delete = mock_shiboken_delete

        with patch.dict(
            sys.modules,
            {
                "PySide2": MagicMock(),
                "PySide2.QtCore": mock_qtcore,
                "PySide6": MagicMock(),
                "PySide6.QtCore": mock_qtcore,
                "shiboken6": mock_shiboken6,
            },
        ):
            yield {
                **mock_freecad_env,
                "QtCore": mock_qtcore,
                "timer": mock_timer,
                "shiboken_delete": mock_shiboken_delete,
            }

    def test_cleanup_for_exit_does_not_access_main_window(self, mock_qt_env):
        """_cleanup_for_exit should NOT call FreeCADGui.getMainWindow().

        This is critical because during Python finalization, the main window
        may already be destroyed by Qt, causing a crash.
        """
        # Import after mocking to get mocked FreeCAD
        # We need to reload or import fresh

        # Remove any cached imports
        for mod_name in list(sys.modules.keys()):
            if "freecad_mcp_bridge" in mod_name:
                del sys.modules[mod_name]

        # Now import the plugin module
        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        # Create a plugin instance
        plugin = server.FreecadMCPPlugin()

        # Simulate having started (timers exist)
        mock_timer = MagicMock()
        plugin._timer = mock_timer  # type: ignore[assignment]
        plugin._status_timer = MagicMock()  # type: ignore[assignment]
        plugin._running = True

        # Reset the mock to clear any previous calls
        mock_qt_env["FreeCADGui"].reset_mock()

        # Call the cleanup method
        plugin._cleanup_for_exit()

        # Verify that getMainWindow was NOT called
        mock_qt_env["FreeCADGui"].getMainWindow.assert_not_called()

    def test_cleanup_for_exit_does_not_call_set_status_bar(self, mock_qt_env):
        """_cleanup_for_exit should NOT call _set_status_bar().

        _set_status_bar accesses the main window's status bar, which crashes
        during Python finalization.
        """

        # Remove any cached imports
        for mod_name in list(sys.modules.keys()):
            if "freecad_mcp_bridge" in mod_name:
                del sys.modules[mod_name]

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()
        plugin._timer = MagicMock()  # type: ignore[assignment]
        plugin._status_timer = MagicMock()  # type: ignore[assignment]
        plugin._running = True

        # Spy on _set_status_bar
        plugin._set_status_bar = MagicMock()  # type: ignore[method-assign]

        # Call cleanup
        plugin._cleanup_for_exit()

        # Verify _set_status_bar was NOT called
        plugin._set_status_bar.assert_not_called()

    def test_cleanup_for_exit_stops_timers(self, mock_qt_env):
        """_cleanup_for_exit should stop QTimer objects."""

        for mod_name in list(sys.modules.keys()):
            if "freecad_mcp_bridge" in mod_name:
                del sys.modules[mod_name]

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()

        # Create mock timers
        mock_queue_timer = MagicMock()
        mock_status_timer = MagicMock()
        plugin._timer = mock_queue_timer  # type: ignore[assignment]
        plugin._status_timer = mock_status_timer  # type: ignore[assignment]
        plugin._running = True

        # Call cleanup
        plugin._cleanup_for_exit()

        # Verify timers were stopped
        mock_queue_timer.stop.assert_called_once()
        mock_status_timer.stop.assert_called_once()

        # Verify references are cleared
        assert plugin._timer is None
        assert plugin._status_timer is None

    def test_cleanup_for_exit_disconnects_timer_signals(self, mock_qt_env):
        """_cleanup_for_exit should disconnect timer signals."""

        for mod_name in list(sys.modules.keys()):
            if "freecad_mcp_bridge" in mod_name:
                del sys.modules[mod_name]

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()

        mock_queue_timer = MagicMock()
        mock_status_timer = MagicMock()
        plugin._timer = mock_queue_timer  # type: ignore[assignment]
        plugin._status_timer = mock_status_timer  # type: ignore[assignment]
        plugin._running = True

        plugin._cleanup_for_exit()

        # Verify signals were disconnected
        mock_queue_timer.timeout.disconnect.assert_called_once()
        mock_status_timer.timeout.disconnect.assert_called_once()

    def test_cleanup_for_exit_uses_shiboken_delete(self, mock_qt_env):
        """_cleanup_for_exit should use shiboken.delete() to destroy Qt objects.

        This is CRITICAL: deleteLater() doesn't work during shutdown because
        it schedules deletion for the next event loop iteration, which never
        happens. Python's GC then tries to finalize the PySide wrapper, which
        triggers Qt's disconnectNotify callback into partially-finalized Python.

        Using shiboken.delete() explicitly destroys the C++ object immediately,
        marking the PySide wrapper as invalid so Python's GC won't try to
        destroy it again.
        """

        for mod_name in list(sys.modules.keys()):
            if "freecad_mcp_bridge" in mod_name:
                del sys.modules[mod_name]

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()

        mock_queue_timer = MagicMock()
        mock_status_timer = MagicMock()
        plugin._timer = mock_queue_timer  # type: ignore[assignment]
        plugin._status_timer = mock_status_timer  # type: ignore[assignment]
        plugin._running = True

        # Reset the mock to track calls during cleanup
        mock_qt_env["shiboken_delete"].reset_mock()

        plugin._cleanup_for_exit()

        # Verify shiboken.delete() was called for both timers
        assert mock_qt_env["shiboken_delete"].call_count == 2
        calls = [call[0][0] for call in mock_qt_env["shiboken_delete"].call_args_list]
        assert mock_queue_timer in calls
        assert mock_status_timer in calls

    def test_cleanup_for_exit_does_not_use_delete_later(self, mock_qt_env):
        """_cleanup_for_exit should NOT use deleteLater().

        deleteLater() is the source of the crash because it schedules
        deletion for the next event loop iteration, but the event loop
        isn't running during atexit.
        """

        for mod_name in list(sys.modules.keys()):
            if "freecad_mcp_bridge" in mod_name:
                del sys.modules[mod_name]

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()

        mock_queue_timer = MagicMock()
        mock_status_timer = MagicMock()
        plugin._timer = mock_queue_timer  # type: ignore[assignment]
        plugin._status_timer = mock_status_timer  # type: ignore[assignment]
        plugin._running = True

        plugin._cleanup_for_exit()

        # Verify deleteLater was NOT called
        mock_queue_timer.deleteLater.assert_not_called()
        mock_status_timer.deleteLater.assert_not_called()

    def test_cleanup_for_exit_sets_running_false(self, mock_qt_env):
        """_cleanup_for_exit should set _running to False."""

        for mod_name in list(sys.modules.keys()):
            if "freecad_mcp_bridge" in mod_name:
                del sys.modules[mod_name]

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()
        plugin._running = True

        plugin._cleanup_for_exit()

        assert plugin._running is False


class TestAtexitHandler:
    """Tests for the atexit cleanup handler."""

    @pytest.fixture
    def mock_freecad_env(self):
        """Set up mocked FreeCAD environment."""
        mock_freecad = MagicMock()
        mock_freecad.GuiUp = True
        mock_freecad.Console = MagicMock()

        mock_freecadgui = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "FreeCAD": mock_freecad,
                "FreeCADGui": mock_freecadgui,
                "PySide2": MagicMock(),
                "PySide2.QtCore": MagicMock(),
                "PySide6": MagicMock(),
                "PySide6.QtCore": MagicMock(),
                "shiboken6": MagicMock(),
            },
        ):
            yield {
                "FreeCAD": mock_freecad,
                "FreeCADGui": mock_freecadgui,
            }

    def test_cleanup_all_servers_calls_cleanup_for_exit(self, mock_freecad_env):
        """_cleanup_all_servers should call _cleanup_for_exit, not stop()."""
        for mod_name in list(sys.modules.keys()):
            if "freecad_mcp_bridge" in mod_name:
                del sys.modules[mod_name]

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        # Create a plugin and add it to the active servers set
        plugin = server.FreecadMCPPlugin()
        plugin._running = True

        # Spy on the methods
        plugin._cleanup_for_exit = MagicMock()  # type: ignore[method-assign]
        plugin.stop = MagicMock()  # type: ignore[method-assign]

        # Add to active servers
        server._active_servers.add(plugin)

        try:
            # Call the cleanup function
            server._cleanup_all_servers()

            # Verify _cleanup_for_exit was called, not stop()
            plugin._cleanup_for_exit.assert_called_once()
            plugin.stop.assert_not_called()
        finally:
            # Clean up
            server._active_servers.discard(plugin)

    def test_cleanup_all_servers_handles_exceptions(self, mock_freecad_env):
        """_cleanup_all_servers should continue even if one server raises."""
        for mod_name in list(sys.modules.keys()):
            if "freecad_mcp_bridge" in mod_name:
                del sys.modules[mod_name]

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        # Create two plugins
        plugin1 = server.FreecadMCPPlugin()
        plugin1._running = True
        plugin1._cleanup_for_exit = MagicMock(  # type: ignore[method-assign]
            side_effect=Exception("Test error")
        )

        plugin2 = server.FreecadMCPPlugin()
        plugin2._running = True
        plugin2._cleanup_for_exit = MagicMock()  # type: ignore[method-assign]

        server._active_servers.add(plugin1)
        server._active_servers.add(plugin2)

        try:
            # Should not raise even though plugin1 raises
            server._cleanup_all_servers()

            # Both should have been attempted
            plugin1._cleanup_for_exit.assert_called_once()
            plugin2._cleanup_for_exit.assert_called_once()
        finally:
            server._active_servers.discard(plugin1)
            server._active_servers.discard(plugin2)
