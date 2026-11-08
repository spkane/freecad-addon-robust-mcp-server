"""Tests for console capture and failure reporting."""

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult
from freecad_mcp.bridge.console import build_console_output_code
from freecad_mcp.bridge.embedded import EmbeddedBridge
from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge


def test_report_view_output_is_bounded(monkeypatch):
    """Read the visible report's most recent lines without clearing it."""
    report = SimpleNamespace(toPlainText=lambda: "first\nwarning\nerror\n")
    window = SimpleNamespace(findChild=lambda _type, _name: report)
    gui = ModuleType("FreeCADGui")
    monkeypatch.setattr(gui, "getMainWindow", lambda: window, raising=False)
    pyside = ModuleType("PySide")
    monkeypatch.setattr(pyside, "QtGui", SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        pyside, "QtWidgets", SimpleNamespace(QTextEdit=object), raising=False
    )
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    monkeypatch.setitem(sys.modules, "PySide", pyside)
    namespace = {"FreeCAD": SimpleNamespace(GuiUp=True, Console=SimpleNamespace())}

    exec(build_console_output_code(2), namespace)  # noqa: S102

    assert namespace["_result_"] == ["warning", "error"]


def test_report_view_uses_qtgui_fallback(monkeypatch):
    """Support a FreeCAD Qt wrapper exposing QTextEdit through QtGui only."""
    report = SimpleNamespace(toPlainText=lambda: "legacy report")
    text_edit = type("LegacyTextEdit", (), {})
    window = SimpleNamespace(
        findChild=lambda widget_type, name: (
            report if widget_type is text_edit and name == "Report view" else None
        )
    )
    gui = ModuleType("FreeCADGui")
    monkeypatch.setattr(gui, "getMainWindow", lambda: window, raising=False)
    pyside = ModuleType("PySide")
    monkeypatch.setattr(
        pyside, "QtGui", SimpleNamespace(QTextEdit=text_edit), raising=False
    )
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    monkeypatch.setitem(sys.modules, "PySide", pyside)
    namespace = {"FreeCAD": SimpleNamespace(GuiUp=True, Console=SimpleNamespace())}

    exec(build_console_output_code(10), namespace)  # noqa: S102

    assert namespace["_result_"] == ["legacy report"]


def test_missing_gui_window_falls_back_to_getlog(monkeypatch):
    """An absent main window still permits available console history."""
    gui = ModuleType("FreeCADGui")
    monkeypatch.setattr(gui, "getMainWindow", lambda: None, raising=False)
    pyside = ModuleType("PySide")
    monkeypatch.setattr(pyside, "QtGui", SimpleNamespace(), raising=False)
    monkeypatch.setattr(
        pyside, "QtWidgets", SimpleNamespace(QTextEdit=object), raising=False
    )
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    monkeypatch.setitem(sys.modules, "PySide", pyside)
    console = SimpleNamespace(GetLog=lambda: "available history")
    namespace = {"FreeCAD": SimpleNamespace(GuiUp=True, Console=console)}

    exec(build_console_output_code(10), namespace)  # noqa: S102

    assert namespace["_result_"] == ["available history"]


@pytest.mark.parametrize("where", ["window", "widget"])
def test_gui_lookup_failure_falls_back_to_getlog(monkeypatch, where):
    """Qt object lifetime failures do not prevent native history lookup."""

    def fail(*_args):
        raise RuntimeError("Qt object was deleted")

    gui = ModuleType("FreeCADGui")
    monkeypatch.setattr(
        gui,
        "getMainWindow",
        fail if where == "window" else lambda: SimpleNamespace(findChild=fail),
        raising=False,
    )
    pyside = ModuleType("PySide")
    monkeypatch.setattr(
        pyside, "QtWidgets", SimpleNamespace(QTextEdit=object), raising=False
    )
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    monkeypatch.setitem(sys.modules, "PySide", pyside)
    namespace = {
        "FreeCAD": SimpleNamespace(
            GuiUp=True, Console=SimpleNamespace(GetLog=lambda: "history")
        )
    }
    exec(build_console_output_code(10), namespace)  # noqa: S102
    assert namespace["_result_"] == ["history"]


def test_unavailable_qt_wrapper_falls_back_to_getlog(monkeypatch):
    """An unavailable Qt wrapper does not hide available console history."""
    gui = ModuleType("FreeCADGui")
    monkeypatch.setattr(gui, "getMainWindow", object, raising=False)
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui)
    monkeypatch.setitem(sys.modules, "PySide", ModuleType("PySide"))
    console = SimpleNamespace(GetLog=lambda: "available history")
    namespace = {"FreeCAD": SimpleNamespace(GuiUp=True, Console=console)}

    exec(build_console_output_code(10), namespace)  # noqa: S102

    assert namespace["_result_"] == ["available history"]


def test_headless_console_history_falls_back_to_getlog():
    """Use the native history API when it is available without the GUI."""
    console = SimpleNamespace(GetLog=lambda: "first\nlast\n")
    namespace = {"FreeCAD": SimpleNamespace(GuiUp=False, Console=console)}

    exec(build_console_output_code(1), namespace)  # noqa: S102

    assert namespace["_result_"] == ["last"]


def test_unavailable_history_is_not_reported_as_empty():
    """No accessible console history is distinguishable from an empty report."""
    namespace = {"FreeCAD": SimpleNamespace(GuiUp=False, Console=SimpleNamespace())}
    exec(build_console_output_code(10), namespace)  # noqa: S102
    assert namespace["_result_"] is None


@pytest.mark.parametrize("lines", [0, -1, 1001, True])
def test_console_output_rejects_invalid_line_limits(lines):
    """Reject unbounded or ambiguous line counts."""
    with pytest.raises(ValueError, match="lines"):
        build_console_output_code(lines)


@pytest.mark.asyncio
async def test_embedded_console_checks_limits_before_unavailable_error():
    """Embedded mode uses the same line-limit contract as network transports."""
    bridge = EmbeddedBridge()
    with pytest.raises(ValueError, match="lines"):
        await bridge.get_console_output(0)
    with pytest.raises(RuntimeError, match="unavailable"):
        await bridge.get_console_output(1)


@pytest.mark.asyncio
@pytest.mark.parametrize("bridge_type", [XmlRpcBridge, SocketBridge])
async def test_console_bridge_distinguishes_empty_and_failed_capture(bridge_type):
    """Both transports return empty captured history but raise on failure."""
    bridge = bridge_type()
    bridge.execute_python = AsyncMock(return_value=ExecutionResult(True, [], "", "", 0))
    assert await bridge.get_console_output() == []

    bridge.execute_python.return_value = ExecutionResult(True, None, "", "", 0)
    with pytest.raises(RuntimeError, match="unavailable"):
        await bridge.get_console_output()


@pytest.mark.asyncio
@pytest.mark.parametrize("bridge_type", [XmlRpcBridge, SocketBridge])
@pytest.mark.parametrize(
    ("error_type", "exception"),
    [
        ("TimeoutError", TimeoutError),
        ("RequestNotSentError", TimeoutError),
        ("ConnectionError", ConnectionError),
        ("ConnectionRefusedError", ConnectionError),
        ("ConnectionResetError", ConnectionError),
        ("ConnectionAbortedError", ConnectionError),
        ("BrokenPipeError", ConnectionError),
        ("RemoteDisconnected", ConnectionError),
    ],
)
async def test_console_bridge_preserves_transport_failures(
    bridge_type, error_type, exception
):
    """A transport failure is not misreported as unavailable console history."""
    bridge = bridge_type()
    bridge.execute_python = AsyncMock(
        return_value=ExecutionResult(
            False, None, "", "transport failed", 0, error_type=error_type
        )
    )
    with pytest.raises(exception, match="transport failed"):
        await bridge.get_console_output()
