"""Behavioral tests for the screenshot operation shared by all bridges."""

import base64
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult
from freecad_mcp.bridge.embedded import EmbeddedBridge
from freecad_mcp.bridge.screenshot import build_screenshot_code
from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge


def _environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict, MagicMock, MagicMock]:
    """Provide GUI objects and isolate generated temporary files."""
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    view = MagicMock()
    view.getCamera.return_value = "original camera"
    view.isAnimationEnabled.return_value = True
    view.saveImage.side_effect = lambda path, *_args: Path(path).write_bytes(
        b"png data"
    )
    gui = MagicMock()
    gui.getDocument.return_value.activeView.return_value = view
    document = SimpleNamespace(Name="Target")
    freecad = SimpleNamespace(
        GuiUp=True,
        ActiveDocument=document,
        getDocument=MagicMock(return_value=document),
    )
    return {"FreeCAD": freecad, "FreeCADGui": gui}, view, gui


def test_capture_restores_camera_and_cleans_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Capture targets the requested document and restores the original camera."""
    environment, view, gui = _environment(tmp_path, monkeypatch)
    exec(build_screenshot_code("Target", "Front", 320, 240), environment)  # noqa: S102
    assert base64.b64decode(environment["_result_"]["data"]) == b"png data"
    gui.getDocument.assert_called_once_with("Target")
    view.viewFront.assert_called_once()
    view.fitAll.assert_called_once()
    view.setCamera.assert_called_once_with("original camera")
    assert [call.args[0] for call in view.setAnimationEnabled.call_args_list] == [
        False,
        True,
    ]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("failure", ["saveImage", "fitAll", "setCamera"])
def test_capture_cleans_up_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """A failed capture, fit, or restore must not leave a temporary file."""
    environment, view, _ = _environment(tmp_path, monkeypatch)
    getattr(view, failure).side_effect = RuntimeError(failure)
    with pytest.raises(RuntimeError, match=failure):
        exec(build_screenshot_code(None, "Front", 320, 240), environment)  # noqa: S102
    view.setCamera.assert_called_once_with("original camera")
    assert not list(tmp_path.iterdir())


def test_non_3d_view_fails_clearly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Views without the required camera and screenshot methods are rejected."""
    environment, _, gui = _environment(tmp_path, monkeypatch)
    gui.getDocument.return_value.activeView.return_value = SimpleNamespace()
    with pytest.raises(ValueError, match="supported 3D view"):
        exec(build_screenshot_code(None, "Front", 320, 240), environment)  # noqa: S102
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("bridge_class", [XmlRpcBridge, SocketBridge, EmbeddedBridge])
@pytest.mark.asyncio
async def test_all_bridges_execute_shared_capture(bridge_class: type) -> None:
    """All bridge modes execute the same capture operation."""
    bridge = bridge_class()
    bridge.is_gui_available = AsyncMock(return_value=True)
    bridge.execute_python = AsyncMock(
        return_value=ExecutionResult(
            success=True,
            stdout="",
            stderr="",
            execution_time_ms=0.0,
            result={"data": "cG5n", "format": "png", "width": 320, "height": 240},
        )
    )
    result = await bridge.get_screenshot(width=320, height=240, doc_name="Target")
    assert result.success
    assert bridge.execute_python.await_args.args[0] == build_screenshot_code(
        "Target", "Isometric", 320, 240
    )
