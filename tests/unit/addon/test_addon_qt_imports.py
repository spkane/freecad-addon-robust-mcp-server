"""Regression tests for the PySide6 -> PySide2 import fallbacks.

The bundled bridge server and ``init_gui.py`` prefer PySide6 and fall back to
PySide2 for older FreeCAD builds. A partially initialized binding can raise
``NameError`` (not just ``ImportError``) during import, so both failures must
reach the fallback or produce a clear error.

These tests cover:

* ``_get_qt_core``: PySide6 is preferred, its failure falls back to PySide2,
  and both failures return ``None``.
* ``_start_queue_processor``: PySide6 failure falls back to the PySide2 Qt
  timer, while both failures make GUI startup fail closed.
* ``init_gui.py``: a PySide6 failure reaches the PySide2 fallback, and failure
  of both imports logs a clear warning through the outer ``except`` block.
"""

from __future__ import annotations

import ast
import importlib
import runpy
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

ADDON_DIR = Path(__file__).parent.parent.parent.parent / "freecad" / "RobustMCPBridge"
ADDON_INIT_PATH = ADDON_DIR / "__init__.py"
BRIDGE_UTILS_PATH = ADDON_DIR / "freecad_mcp_bridge" / "bridge_utils.py"
COMMANDS_PATH = ADDON_DIR / "commands.py"
INIT_GUI_PATH = ADDON_DIR / "init_gui.py"
PREFERENCES_PAGE_PATH = ADDON_DIR / "Qt" / "preferences_page.py"
QT_COMPAT_PATH = ADDON_DIR / "freecad_mcp_bridge" / "qt_compat.py"
STARTUP_BRIDGE_PATH = ADDON_DIR / "freecad_mcp_bridge" / "startup_bridge.py"
STATUS_WIDGET_PATH = ADDON_DIR / "Qt" / "status_widget.py"


class _NameErrorModule(types.ModuleType):
    """Module whose ``Qt*`` attributes raise ``NameError`` on access.

    This mimics a PySide shim that exists in ``sys.modules`` but has not yet
    finished binding its submodules.
    """

    def __getattr__(self, name: str) -> Any:
        """Raise on every attribute lookup.

        Args:
            name: The attribute that was looked up.

        Returns:
            Never returns; the method always raises.

        Raises:
            NameError: If ``name`` starts with ``Qt``, mimicking a PySide
                shim whose submodules are not bound yet.
            AttributeError: For any other attribute name.
        """
        if name.startswith("Qt"):
            raise NameError(f"name '{name}' is not defined")
        raise AttributeError(name)


def _pyside_module(name: str, qtcore: Any) -> types.ModuleType:
    """Build a fake PySide module exposing ``QtCore``."""
    module = types.ModuleType(name)
    module.QtCore = qtcore  # type: ignore[attr-defined]
    return module


def _binding_nameerror(name: str) -> types.ModuleType:
    """Build a fake binding whose ``QtCore`` access raises ``NameError``."""
    return _NameErrorModule(name)


def _binding_importerror() -> Any:
    """Make ``from PySide import ...`` raise ``ImportError``."""
    return None


@pytest.fixture(autouse=True)
def _hide_host_pyside(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default tests to an unknown host so PySide6-first fallback is exercised."""
    monkeypatch.setitem(sys.modules, "PySide", None)


# ---------------------------------------------------------------------------
# Bundled bridge server
# ---------------------------------------------------------------------------


@pytest.fixture
def server_mod(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Import the bundled bridge server module in isolation.

    The package is dropped from ``sys.modules`` before the import so that a
    cached copy from another test cannot be reused.  Any module the import
    adds is removed again on teardown, because ``monkeypatch`` only restores
    the entries it deleted itself.
    """
    monkeypatch.syspath_prepend(str(ADDON_DIR))
    for name in list(sys.modules):
        if name == "freecad_mcp_bridge" or name.startswith("freecad_mcp_bridge."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module("freecad_mcp_bridge.server")
    yield module
    for name in list(sys.modules):
        if name == "freecad_mcp_bridge" or name.startswith("freecad_mcp_bridge."):
            del sys.modules[name]


@pytest.fixture
def fake_freecad() -> Any:
    """Minimal stand-in for the ``FreeCAD`` module."""
    freecad = types.ModuleType("FreeCAD")
    freecad.GuiUp = True  # type: ignore[attr-defined]
    freecad.Console = MagicMock()  # type: ignore[attr-defined]
    return freecad


def _enable_gui(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch, fake_freecad: Any
) -> None:
    """Pretend we are running inside a FreeCAD GUI session."""
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", True, raising=False)
    monkeypatch.setattr(server_mod, "FreeCAD", fake_freecad, raising=False)


class TestGetQtCore:
    """Tests for the ``_get_qt_core`` import fallback."""

    def test_pyside6_is_preferred_when_both_are_available(
        self,
        server_mod: Any,
        monkeypatch: pytest.MonkeyPatch,
        fake_freecad: Any,
    ) -> None:
        """Modern FreeCAD builds should select PySide6 before PySide2."""
        _enable_gui(server_mod, monkeypatch, fake_freecad)
        pyside6_qtcore = MagicMock()
        pyside2_qtcore = MagicMock()
        monkeypatch.setitem(
            sys.modules, "PySide6", _pyside_module("PySide6", pyside6_qtcore)
        )
        monkeypatch.setitem(
            sys.modules, "PySide2", _pyside_module("PySide2", pyside2_qtcore)
        )

        assert server_mod._get_qt_core() is pyside6_qtcore

    def test_qt5_host_selects_pyside2_when_both_are_available(
        self,
        server_mod: Any,
        monkeypatch: pytest.MonkeyPatch,
        fake_freecad: Any,
    ) -> None:
        """A Qt5 FreeCAD process must never load the available PySide6 binding."""
        _enable_gui(server_mod, monkeypatch, fake_freecad)
        host_qtcore = MagicMock()
        host_qtcore.qVersion.return_value = "5.15.18"
        pyside6_qtcore = MagicMock()
        pyside2_qtcore = MagicMock()
        monkeypatch.setitem(
            sys.modules, "PySide", _pyside_module("PySide", host_qtcore)
        )
        monkeypatch.setitem(
            sys.modules, "PySide6", _pyside_module("PySide6", pyside6_qtcore)
        )
        monkeypatch.setitem(
            sys.modules, "PySide2", _pyside_module("PySide2", pyside2_qtcore)
        )

        assert server_mod._get_qt_core() is pyside2_qtcore

    def test_qt5_host_does_not_cross_fallback_to_pyside6(
        self,
        server_mod: Any,
        monkeypatch: pytest.MonkeyPatch,
        fake_freecad: Any,
    ) -> None:
        """A broken PySide2 host must fail closed instead of mixing in Qt6."""
        _enable_gui(server_mod, monkeypatch, fake_freecad)
        host_qtcore = MagicMock()
        host_qtcore.qVersion.return_value = "5.15.18"
        monkeypatch.setitem(
            sys.modules, "PySide", _pyside_module("PySide", host_qtcore)
        )
        monkeypatch.setitem(sys.modules, "PySide2", None)
        monkeypatch.setitem(
            sys.modules, "PySide6", _pyside_module("PySide6", MagicMock())
        )

        assert server_mod._get_qt_core() is None

    @pytest.mark.parametrize(
        "failed_binding",
        [lambda: _binding_nameerror("PySide6"), _binding_importerror],
        ids=["nameerror", "importerror"],
    )
    def test_pyside6_failure_falls_back_to_pyside2(
        self,
        server_mod: Any,
        monkeypatch: pytest.MonkeyPatch,
        fake_freecad: Any,
        failed_binding: Any,
    ) -> None:
        """Either supported PySide6 import failure should reach PySide2."""
        _enable_gui(server_mod, monkeypatch, fake_freecad)
        qtcore = MagicMock()
        monkeypatch.setitem(sys.modules, "PySide6", failed_binding())
        monkeypatch.setitem(sys.modules, "PySide2", _pyside_module("PySide2", qtcore))

        assert server_mod._get_qt_core() is qtcore

    def test_nameerror_on_both_returns_none(
        self,
        server_mod: Any,
        monkeypatch: pytest.MonkeyPatch,
        fake_freecad: Any,
    ) -> None:
        """If both bindings fail the helper should return ``None``."""
        _enable_gui(server_mod, monkeypatch, fake_freecad)
        monkeypatch.setitem(sys.modules, "PySide6", _binding_nameerror("PySide6"))
        monkeypatch.setitem(sys.modules, "PySide2", _binding_nameerror("PySide2"))

        assert server_mod._get_qt_core() is None

    def test_returns_none_without_gui(
        self,
        server_mod: Any,
        monkeypatch: pytest.MonkeyPatch,
        fake_freecad: Any,
    ) -> None:
        """Without a GUI there is nothing to import."""
        fake_freecad.GuiUp = False
        _enable_gui(server_mod, monkeypatch, fake_freecad)
        qtcore = MagicMock()
        monkeypatch.setitem(sys.modules, "PySide6", _pyside_module("PySide6", qtcore))

        assert server_mod._get_qt_core() is None


class TestStartQueueProcessor:
    """Tests for the ``_start_queue_processor`` import fallback."""

    @staticmethod
    def _plugin(server_mod: Any) -> Any:
        """Create a bare plugin instance without running ``__init__``."""
        plugin = object.__new__(server_mod.FreecadMCPPlugin)
        plugin._timer = None
        plugin._headless = False
        plugin._queue_thread = None
        return plugin

    @staticmethod
    def _fake_thread(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
        """Replace ``threading.Thread`` with a recording stub."""
        created: list[Any] = []

        class _FakeThread:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.args = args
                self.kwargs = kwargs
                self.started = False
                created.append(self)

            def start(self) -> None:
                self.started = True

        monkeypatch.setattr("threading.Thread", _FakeThread)
        return created

    @pytest.mark.parametrize(
        "failed_binding",
        [lambda: _binding_nameerror("PySide6"), _binding_importerror],
        ids=["nameerror", "importerror"],
    )
    def test_pyside6_failure_falls_back_to_pyside2_qt_timer(
        self,
        server_mod: Any,
        monkeypatch: pytest.MonkeyPatch,
        fake_freecad: Any,
        failed_binding: Any,
    ) -> None:
        """A PySide6 failure should still create the PySide2 timer."""
        _enable_gui(server_mod, monkeypatch, fake_freecad)
        timer = MagicMock()
        qtcore = MagicMock()
        qtcore.QTimer.return_value = timer
        monkeypatch.setitem(sys.modules, "PySide6", failed_binding())
        monkeypatch.setitem(sys.modules, "PySide2", _pyside_module("PySide2", qtcore))
        threads = self._fake_thread(monkeypatch)

        plugin = self._plugin(server_mod)
        plugin._start_queue_processor()

        assert plugin._timer is timer
        assert plugin._headless is False
        assert threads == []
        timer.start.assert_called_once_with(server_mod.QUEUE_POLL_INTERVAL_MS)
        timer.timeout.connect.assert_called_once_with(plugin._process_queue)

    @pytest.mark.parametrize(
        "failed_binding",
        [lambda: _binding_nameerror("PySide6"), _binding_importerror],
        ids=["nameerror", "importerror"],
    )
    def test_gui_mode_without_qt_fails_closed(
        self,
        server_mod: Any,
        monkeypatch: pytest.MonkeyPatch,
        fake_freecad: Any,
        failed_binding: Any,
    ) -> None:
        """GUI mode must not fall back to unsafe background processing."""
        _enable_gui(server_mod, monkeypatch, fake_freecad)
        monkeypatch.setitem(sys.modules, "PySide6", failed_binding())
        monkeypatch.setitem(sys.modules, "PySide2", _NameErrorModule("PySide2"))
        threads = self._fake_thread(monkeypatch)

        plugin = self._plugin(server_mod)
        with pytest.raises(RuntimeError, match="Refusing unsafe background"):
            plugin._start_queue_processor()

        assert plugin._timer is None
        assert plugin._headless is False
        assert plugin._queue_thread is None
        assert threads == []
        fake_freecad.Console.PrintError.assert_called_once()

    def test_start_rolls_back_running_state_when_gui_qt_is_unavailable(
        self,
        server_mod: Any,
        monkeypatch: pytest.MonkeyPatch,
        fake_freecad: Any,
    ) -> None:
        """A failed GUI queue setup must leave the plugin fully stopped."""
        _enable_gui(server_mod, monkeypatch, fake_freecad)
        monkeypatch.setitem(sys.modules, "PySide6", _NameErrorModule("PySide6"))
        monkeypatch.setitem(sys.modules, "PySide2", _NameErrorModule("PySide2"))

        plugin = server_mod.FreecadMCPPlugin(
            enable_xmlrpc=True, authenticator=MagicMock()
        )
        with pytest.raises(RuntimeError, match="Refusing unsafe background"):
            plugin.start()

        assert plugin.is_running is False
        assert plugin._timer is None
        assert plugin._queue_thread is None
        assert plugin._socket_thread is None
        assert plugin._xmlrpc_thread is None

    def test_status_setup_failure_stops_before_listeners(
        self, server_mod: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Status setup failure cannot leave a running bridge or listener."""
        plugin = server_mod.FreecadMCPPlugin(authenticator=MagicMock())
        monkeypatch.setattr(plugin, "_start_queue_processor", MagicMock())
        monkeypatch.setattr(
            plugin,
            "_start_status_updates",
            MagicMock(side_effect=RuntimeError("status")),
        )
        with pytest.raises(RuntimeError, match="status"):
            plugin.start()
        assert plugin.is_running is False
        assert plugin._socket_thread is None
        assert plugin._xmlrpc_thread is None

    def test_ambiguous_early_gui_fails_before_listener_creation(
        self,
        server_mod: Any,
        monkeypatch: pytest.MonkeyPatch,
        fake_freecad: Any,
    ) -> None:
        """An uninitialized GUI must never start background execution."""
        del fake_freecad.GuiUp
        _enable_gui(server_mod, monkeypatch, fake_freecad)
        monkeypatch.setattr(sys, "executable", "/opt/freecad/bin/freecad")
        monkeypatch.setattr(
            server_mod, "load_qt_core_widgets", MagicMock(side_effect=RuntimeError)
        )
        plugin = server_mod.FreecadMCPPlugin(
            enable_xmlrpc=True, authenticator=MagicMock()
        )
        with pytest.raises(RuntimeError, match="Cannot confirm headless"):
            plugin.start()
        assert plugin.is_running is False
        assert plugin._queue_thread is None
        assert plugin._socket_thread is None
        assert plugin._xmlrpc_thread is None

    def test_console_executable_with_gui_application_fails_closed(
        self,
        server_mod: Any,
        monkeypatch: pytest.MonkeyPatch,
        fake_freecad: Any,
    ) -> None:
        """A GUI application takes precedence over the executable name."""
        fake_freecad.GuiUp = False
        _enable_gui(server_mod, monkeypatch, fake_freecad)
        monkeypatch.setattr(sys, "executable", "/opt/freecad/bin/freecadcmd")

        class Application:
            pass

        qtcore = MagicMock()
        qtcore.QCoreApplication.instance.return_value = Application()
        qtwidgets = types.SimpleNamespace(QApplication=Application)
        monkeypatch.setattr(
            server_mod, "load_qt_core_widgets", lambda: (qtcore, qtwidgets)
        )
        plugin = server_mod.FreecadMCPPlugin(authenticator=MagicMock())
        with pytest.raises(RuntimeError, match="Cannot confirm headless"):
            plugin.start()
        assert plugin.is_running is False
        assert plugin._queue_thread is None
        assert plugin._socket_thread is None

    def test_headless_mode_uses_background_thread(
        self,
        server_mod: Any,
        monkeypatch: pytest.MonkeyPatch,
        fake_freecad: Any,
    ) -> None:
        """Headless sessions never create a Qt timer."""
        fake_freecad.GuiUp = False
        _enable_gui(server_mod, monkeypatch, fake_freecad)
        monkeypatch.setattr(sys, "executable", "/opt/freecad/bin/freecadcmd")
        monkeypatch.setitem(sys.modules, "PySide6", _NameErrorModule("PySide6"))
        monkeypatch.setitem(sys.modules, "PySide2", _NameErrorModule("PySide2"))
        threads = self._fake_thread(monkeypatch)

        plugin = self._plugin(server_mod)
        plugin._start_queue_processor()

        assert plugin._timer is None
        assert plugin._headless is True
        assert len(threads) == 1


# ---------------------------------------------------------------------------
# init_gui.py
# ---------------------------------------------------------------------------


def _install_init_gui_stubs(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Install the fake FreeCAD/Qt modules required by ``init_gui.py``."""
    monkeypatch.syspath_prepend(str(ADDON_DIR))
    freecad = types.ModuleType("FreeCAD")
    freecad.GuiUp = True  # type: ignore[attr-defined]
    freecad.Console = MagicMock()  # type: ignore[attr-defined]

    class _Workbench:
        """Stand-in for ``FreeCADGui.Workbench``."""

    freecad_gui = types.ModuleType("FreeCADGui")
    freecad_gui.Workbench = _Workbench  # type: ignore[attr-defined]
    freecad_gui.addWorkbench = MagicMock()  # type: ignore[attr-defined]
    freecad_gui.addIconPath = MagicMock()  # type: ignore[attr-defined]
    freecad_gui.addPreferencePage = MagicMock()  # type: ignore[attr-defined]

    path_utils = types.ModuleType("path_utils")
    path_utils.get_icons_dir = lambda: ""  # type: ignore[attr-defined]
    path_utils.get_workbench_icon = lambda: ""  # type: ignore[attr-defined]

    preferences = types.ModuleType("preferences")
    preferences.get_auto_start = lambda: False  # type: ignore[attr-defined]

    qt_package = types.ModuleType("Qt")
    qt_package.__path__ = []  # type: ignore[attr-defined]
    qt_preferences = types.ModuleType("Qt.preferences_page")
    qt_preferences.MCPBridgePreferencesPage = object  # type: ignore[attr-defined]
    qt_status = types.ModuleType("Qt.status_widget")
    qt_status.sync_status_with_bridge = lambda: None  # type: ignore[attr-defined]

    package = types.ModuleType("freecad.RobustMCPBridge")
    package.__path__ = [str(ADDON_DIR)]
    monkeypatch.setitem(sys.modules, "freecad.RobustMCPBridge", package)
    for name, module in (
        ("path_utils", path_utils),
        ("preferences", preferences),
        ("Qt", qt_package),
        ("Qt.preferences_page", qt_preferences),
        ("Qt.status_widget", qt_status),
    ):
        monkeypatch.setitem(sys.modules, f"freecad.RobustMCPBridge.{name}", module)
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)
    monkeypatch.setitem(sys.modules, "FreeCADGui", freecad_gui)
    monkeypatch.setitem(sys.modules, "path_utils", path_utils)
    monkeypatch.setitem(sys.modules, "preferences", preferences)
    monkeypatch.setitem(sys.modules, "Qt", qt_package)
    monkeypatch.setitem(sys.modules, "Qt.preferences_page", qt_preferences)
    monkeypatch.setitem(sys.modules, "Qt.status_widget", qt_status)
    return freecad


def _warnings(freecad: Any) -> list[str]:
    """Collect the warning messages logged to the FreeCAD console."""
    return [call.args[0] for call in freecad.Console.PrintWarning.call_args_list]


@pytest.mark.parametrize("missing_pairing", [True, False])
def test_deferred_gui_startup_reports_pairing_without_traceback(
    monkeypatch: pytest.MonkeyPatch, missing_pairing: bool
) -> None:
    """Only unexpected deferred GUI failures produce a traceback."""
    freecad = _install_init_gui_stubs(monkeypatch)
    preferences = sys.modules["freecad.RobustMCPBridge.preferences"]
    preferences.get_auto_start = lambda: True  # type: ignore[attr-defined]
    preferences.get_socket_port = lambda: 9876  # type: ignore[attr-defined]
    preferences.get_xmlrpc_port = lambda: 9875  # type: ignore[attr-defined]
    commands = types.ModuleType("commands")
    commands.is_bridge_running = lambda: False  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "freecad.RobustMCPBridge.commands", commands)
    qtcore = MagicMock()
    monkeypatch.setitem(sys.modules, "PySide6", _pyside_module("PySide6", qtcore))
    namespace = runpy.run_path(
        str(INIT_GUI_PATH), run_name="freecad.RobustMCPBridge.init_gui"
    )
    error = (
        namespace["PairingRequiredError"]("Run freecad-mcp --pair-bridge")
        if missing_pairing
        else RuntimeError("Unexpected startup failure")
    )
    server = types.ModuleType("server")
    plugin = MagicMock()
    plugin.start.side_effect = error
    server.FreecadMCPPlugin = MagicMock(return_value=plugin)  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules, "freecad.RobustMCPBridge.freecad_mcp_bridge.server", server
    )
    namespace["_auto_start_bridge"]()

    errors = "".join(call.args[0] for call in freecad.Console.PrintError.call_args_list)
    assert str(error) in errors
    assert ("Traceback" in errors) is not missing_pairing


class TestInitGuiQtFallback:
    """Tests for the PySide import fallback in ``init_gui.py``."""

    def test_pyside6_is_preferred_when_both_are_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Status-bar scheduling should prefer PySide6 when both exist."""
        freecad = _install_init_gui_stubs(monkeypatch)
        pyside6_qtcore = MagicMock()
        pyside2_qtcore = MagicMock()
        monkeypatch.setitem(
            sys.modules, "PySide6", _pyside_module("PySide6", pyside6_qtcore)
        )
        monkeypatch.setitem(
            sys.modules, "PySide2", _pyside_module("PySide2", pyside2_qtcore)
        )

        runpy.run_path(str(INIT_GUI_PATH), run_name="freecad.RobustMCPBridge.init_gui")

        assert pyside6_qtcore.QTimer.singleShot.call_count >= 1
        assert pyside2_qtcore.QTimer.singleShot.call_count == 0
        assert not any(
            "Could not schedule status bar sync" in msg for msg in _warnings(freecad)
        )

    @pytest.mark.parametrize(
        "failed_binding",
        [lambda: _binding_nameerror("PySide6"), _binding_importerror],
        ids=["nameerror", "importerror"],
    )
    def test_pyside6_failure_falls_back_to_pyside2(
        self, monkeypatch: pytest.MonkeyPatch, failed_binding: Any
    ) -> None:
        """Supported PySide6 failures should reach the PySide2 code path."""
        freecad = _install_init_gui_stubs(monkeypatch)
        qtcore = MagicMock()
        monkeypatch.setitem(sys.modules, "PySide6", failed_binding())
        monkeypatch.setitem(sys.modules, "PySide2", _pyside_module("PySide2", qtcore))

        runpy.run_path(str(INIT_GUI_PATH), run_name="freecad.RobustMCPBridge.init_gui")

        assert qtcore.QTimer.singleShot.call_count >= 1
        assert not any(
            "Could not schedule status bar sync" in msg for msg in _warnings(freecad)
        )

    def test_nameerror_on_both_logs_clear_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If both bindings fail, the warning should identify both bindings."""
        freecad = _install_init_gui_stubs(monkeypatch)
        monkeypatch.setitem(sys.modules, "PySide6", _NameErrorModule("PySide6"))
        monkeypatch.setitem(sys.modules, "PySide2", _NameErrorModule("PySide2"))

        runpy.run_path(str(INIT_GUI_PATH), run_name="freecad.RobustMCPBridge.init_gui")

        warnings = _warnings(freecad)
        assert any("Could not schedule status bar sync" in msg for msg in warnings)
        assert any("Neither PySide6 nor PySide2" in msg for msg in warnings)


@pytest.mark.parametrize("missing_pairing", [True, False])
def test_standalone_startup_only_traces_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch, missing_pairing: bool
) -> None:
    """Standalone startup keeps expected pairing errors readable."""
    import os
    import traceback

    class PairingRequiredError(RuntimeError):
        pass

    error = (
        PairingRequiredError("pair first")
        if missing_pairing
        else RuntimeError("unexpected")
    )
    bridge = types.ModuleType("bridge_utils")
    bridge.get_running_plugin = lambda: None  # type: ignore[attr-defined]
    server = types.ModuleType("server")
    plugin = MagicMock()
    plugin.start.side_effect = error
    server.FreecadMCPPlugin = MagicMock(return_value=plugin)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "bridge_utils", bridge)
    monkeypatch.setitem(sys.modules, "server", server)
    freecad = MagicMock()
    tree = ast.parse(STARTUP_BRIDGE_PATH.read_text())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_start_bridge"
    )
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace: dict[str, Any] = {
        "FreeCAD": freecad,
        "os": os,
        "traceback": traceback,
        "PairingRequiredError": PairingRequiredError,
    }
    exec(compile(module, str(STARTUP_BRIDGE_PATH), "exec"), namespace)  # noqa: S102
    namespace["_start_bridge"]()
    errors = "".join(call.args[0] for call in freecad.Console.PrintError.call_args_list)
    assert str(error) in errors
    assert ("Traceback" in errors) is not missing_pairing


def test_startup_script_prefers_pyside6_and_fails_closed() -> None:
    """The integration script should prefer Qt6 and fail closed without Qt."""
    startup_code = STARTUP_BRIDGE_PATH.read_text()

    assert "load_qt_core_widgets" in startup_code

    tree = ast.parse(startup_code)
    gui_up_branch = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and "getattr(FreeCAD, 'GuiUp', False)" in ast.unparse(node.test)
    )
    branch_code = "\n".join(ast.unparse(node) for node in gui_up_branch.body)

    assert "if QtCore is None or QtWidgets is None" in branch_code
    assert "Startup was stopped" in branch_code
    assert branch_code.count("_start_bridge()") == 1

    while gui_up_branch.orelse and isinstance(gui_up_branch.orelse[0], ast.If):
        gui_up_branch = gui_up_branch.orelse[0]
    fallback_code = "\n".join(ast.unparse(node) for node in gui_up_branch.orelse)

    assert "headless mode could not be confirmed" in fallback_code
    assert "_start_bridge()" not in fallback_code


@pytest.mark.parametrize(
    ("path", "loader"),
    [
        (ADDON_INIT_PATH, "load_qt_core_widgets"),
        (STARTUP_BRIDGE_PATH, "load_qt_core_widgets"),
        (BRIDGE_UTILS_PATH, "load_qt_core"),
        (INIT_GUI_PATH, "load_qt_core"),
        (STATUS_WIDGET_PATH, "load_qt_core_widgets"),
        (PREFERENCES_PAGE_PATH, "load_qt_core_widgets"),
        (COMMANDS_PATH, "load_qt_modules"),
    ],
)
def test_runtime_qt_probes_use_host_compatible_loader(path: Path, loader: str) -> None:
    """Every runtime Qt probe should use the host-compatible loader."""
    source = path.read_text()
    assert loader in source


def test_qt_compat_reports_clear_dual_binding_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown host should report both failed fallback bindings."""
    namespace = runpy.run_path(str(QT_COMPAT_PATH))
    monkeypatch.setitem(sys.modules, "PySide6", None)
    monkeypatch.setitem(sys.modules, "PySide2", None)

    with pytest.raises(RuntimeError, match="Neither PySide6 nor PySide2"):
        namespace["load_qt_modules"]("QtCore")
