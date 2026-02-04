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


def _clear_bridge_cache() -> None:
    """Remove cached freecad_mcp_bridge imports so the module is re-imported fresh."""
    for mod_name in list(sys.modules.keys()):
        if "freecad_mcp_bridge" in mod_name:
            del sys.modules[mod_name]


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
        _clear_bridge_cache()

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()

        # Simulate having started (timers exist)
        mock_timer = MagicMock()
        plugin._timer = mock_timer  # type: ignore[assignment]
        plugin._status_timer = MagicMock()  # type: ignore[assignment]
        plugin._running = True

        # Reset the mock to clear any previous calls
        mock_qt_env["FreeCADGui"].reset_mock()

        plugin._cleanup_for_exit()

        # Verify that getMainWindow was NOT called
        mock_qt_env["FreeCADGui"].getMainWindow.assert_not_called()

    def test_cleanup_for_exit_does_not_call_set_status_bar(self, mock_qt_env):
        """_cleanup_for_exit should NOT call _set_status_bar().

        _set_status_bar accesses the main window's status bar, which crashes
        during Python finalization.
        """
        _clear_bridge_cache()

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()
        plugin._timer = MagicMock()  # type: ignore[assignment]
        plugin._status_timer = MagicMock()  # type: ignore[assignment]
        plugin._running = True

        # Spy on _set_status_bar
        plugin._set_status_bar = MagicMock()  # type: ignore[method-assign]

        plugin._cleanup_for_exit()

        # Verify _set_status_bar was NOT called
        plugin._set_status_bar.assert_not_called()

    def test_cleanup_for_exit_stops_timers(self, mock_qt_env):
        """_cleanup_for_exit should stop QTimer objects."""
        _clear_bridge_cache()

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()

        mock_queue_timer = MagicMock()
        mock_status_timer = MagicMock()
        plugin._timer = mock_queue_timer  # type: ignore[assignment]
        plugin._status_timer = mock_status_timer  # type: ignore[assignment]
        plugin._running = True

        plugin._cleanup_for_exit()

        # Verify timers were stopped
        mock_queue_timer.stop.assert_called_once()
        mock_status_timer.stop.assert_called_once()

        # Verify references are cleared
        assert plugin._timer is None
        assert plugin._status_timer is None

    def test_cleanup_for_exit_disconnects_timer_signals(self, mock_qt_env):
        """_cleanup_for_exit should disconnect timer signals."""
        _clear_bridge_cache()

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
        _clear_bridge_cache()

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
        _clear_bridge_cache()

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
        _clear_bridge_cache()

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()
        plugin._running = True

        plugin._cleanup_for_exit()

        assert plugin._running is False

    def test_cleanup_for_exit_safe_when_no_timers(self, mock_qt_env):
        """_cleanup_for_exit should be safe when no timers exist (headless mode)."""
        _clear_bridge_cache()

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()
        # Simulate headless mode: no timers were created
        plugin._timer = None
        plugin._status_timer = None
        plugin._running = True

        # Should not raise
        plugin._cleanup_for_exit()

        assert plugin._running is False

    def test_cleanup_for_exit_idempotent(self, mock_qt_env):
        """_cleanup_for_exit should be safe to call multiple times."""
        _clear_bridge_cache()

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()
        plugin._timer = MagicMock()  # type: ignore[assignment]
        plugin._status_timer = MagicMock()  # type: ignore[assignment]
        plugin._running = True

        # Call twice - should not raise
        plugin._cleanup_for_exit()
        plugin._cleanup_for_exit()

        assert plugin._running is False
        assert plugin._timer is None
        assert plugin._status_timer is None


class TestAtexitHandler:
    """Tests for the atexit cleanup handler (_cleanup_all_servers)."""

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

    @pytest.fixture
    def fresh_server_module(self, mock_freecad_env):
        """Import a fresh server module and yield it, cleaning up _activeServers after."""
        _clear_bridge_cache()

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        yield server

        # Clean up any servers we added during the test
        server._activeServers.clear()

    def test_cleanup_all_servers_calls_cleanup_for_exit(self, fresh_server_module):
        """_cleanup_all_servers should call _cleanup_for_exit, not stop()."""
        server = fresh_server_module

        plugin = server.FreecadMCPPlugin()
        plugin._running = True
        plugin._cleanup_for_exit = MagicMock()  # type: ignore[method-assign]
        plugin.stop = MagicMock()  # type: ignore[method-assign]

        server._activeServers.add(plugin)

        server._cleanup_all_servers()

        plugin._cleanup_for_exit.assert_called_once()
        plugin.stop.assert_not_called()

    def test_cleanup_all_servers_handles_exceptions(self, fresh_server_module):
        """_cleanup_all_servers should continue even if one server raises."""
        server = fresh_server_module

        plugin1 = server.FreecadMCPPlugin()
        plugin1._running = True
        plugin1._cleanup_for_exit = MagicMock(  # type: ignore[method-assign]
            side_effect=Exception("Test error")
        )

        plugin2 = server.FreecadMCPPlugin()
        plugin2._running = True
        plugin2._cleanup_for_exit = MagicMock()  # type: ignore[method-assign]

        server._activeServers.add(plugin1)
        server._activeServers.add(plugin2)

        # Should not raise even though plugin1 raises
        server._cleanup_all_servers()

        # Both should have been attempted
        plugin1._cleanup_for_exit.assert_called_once()
        plugin2._cleanup_for_exit.assert_called_once()

    def test_cleanup_all_servers_calls_non_running_servers(self, fresh_server_module):
        """_cleanup_all_servers should call _cleanup_for_exit even when _running is False.

        A server may have timers allocated from a failed startup that still
        need explicit shiboken.delete() to avoid GC crashes.
        """
        server = fresh_server_module

        plugin = server.FreecadMCPPlugin()
        plugin._running = False  # Simulate failed startup
        plugin._cleanup_for_exit = MagicMock()  # type: ignore[method-assign]

        server._activeServers.add(plugin)

        server._cleanup_all_servers()

        # _cleanup_for_exit should still be called
        plugin._cleanup_for_exit.assert_called_once()

    def test_cleanup_all_servers_empty_set(self, fresh_server_module):
        """_cleanup_all_servers should be safe with no active servers."""
        server = fresh_server_module
        server._activeServers.clear()

        # Should not raise
        server._cleanup_all_servers()

    def test_cleanup_all_servers_iterates_safely_during_modification(
        self, fresh_server_module
    ):
        """_cleanup_all_servers should iterate a snapshot, not the live set.

        The function calls list(_activeServers) to snapshot before iterating,
        so modifications to _activeServers during cleanup don't cause errors.
        """
        server = fresh_server_module

        plugin1 = server.FreecadMCPPlugin()
        plugin1._running = True
        plugin2 = server.FreecadMCPPlugin()
        plugin2._running = True

        # Make plugin1's cleanup remove plugin2 from _activeServers
        def remove_plugin2() -> None:
            server._activeServers.discard(plugin2)

        plugin1._cleanup_for_exit = MagicMock(  # type: ignore[method-assign]
            side_effect=remove_plugin2
        )
        plugin2._cleanup_for_exit = MagicMock()  # type: ignore[method-assign]

        server._activeServers.add(plugin1)
        server._activeServers.add(plugin2)

        # Should not raise RuntimeError: Set changed size during iteration
        server._cleanup_all_servers()

        # Both should have been attempted (snapshot was taken before iteration)
        plugin1._cleanup_for_exit.assert_called_once()
        plugin2._cleanup_for_exit.assert_called_once()

    def test_cleanup_all_servers_multiple_exception_sources(self, fresh_server_module):
        """_cleanup_all_servers should handle ALL servers raising exceptions."""
        server = fresh_server_module

        plugin1 = server.FreecadMCPPlugin()
        plugin1._running = True
        plugin1._cleanup_for_exit = MagicMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("Error 1")
        )

        plugin2 = server.FreecadMCPPlugin()
        plugin2._running = True
        plugin2._cleanup_for_exit = MagicMock(  # type: ignore[method-assign]
            side_effect=TypeError("Error 2")
        )

        server._activeServers.add(plugin1)
        server._activeServers.add(plugin2)

        # Should not raise even when every server raises
        server._cleanup_all_servers()

        plugin1._cleanup_for_exit.assert_called_once()
        plugin2._cleanup_for_exit.assert_called_once()


class TestAtexitRegistration:
    """Tests for atexit handler registration during FreecadMCPPlugin.__init__."""

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
            yield

    def test_plugin_added_to_active_servers(self, mock_freecad_env):
        """Creating a plugin should register it in _activeServers."""
        _clear_bridge_cache()

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        initial_count = len(server._activeServers)
        plugin = server.FreecadMCPPlugin()

        assert plugin in server._activeServers
        assert len(server._activeServers) >= initial_count + 1

        server._activeServers.discard(plugin)

    def test_atexit_registered_once(self, mock_freecad_env):
        """atexit.register should be called at most once across multiple plugins."""
        _clear_bridge_cache()

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        # Reset the flag to test fresh registration
        server._atexitRegistered = False

        with patch("atexit.register") as mock_register:
            _ = server.FreecadMCPPlugin()
            _ = server.FreecadMCPPlugin()

            # Should only register once
            mock_register.assert_called_once_with(server._cleanup_all_servers)

        server._activeServers.clear()

    def test_weak_reference_allows_gc(self, mock_freecad_env):
        """_activeServers uses WeakSet, so unreferenced plugins can be GC'd."""
        _clear_bridge_cache()

        from freecad.RobustMCPBridge.freecad_mcp_bridge import server

        plugin = server.FreecadMCPPlugin()
        assert plugin in server._activeServers

        # Remove the only strong reference—WeakSet should let it be collected
        plugin_id = id(plugin)
        del plugin

        # The plugin should no longer be in the set (may need GC nudge)
        import gc

        gc.collect()

        remaining_ids = [id(s) for s in server._activeServers]
        assert plugin_id not in remaining_ids
