"""Regression tests for untrusted strings in generated FreeCAD code."""

import ast
import builtins
import importlib
from unittest.mock import AsyncMock

import pytest

from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge


class CaptureCode(Exception):
    """Stop a tool immediately after capturing the generated source."""


class CaptureTools:
    """Collect registered tool functions without starting an MCP server."""

    def __init__(self):
        self.functions = {}

    def tool(self, **_kwargs):
        def register(function):
            self.functions[function.__name__] = function
            return function

        return register


PAYLOAD = 'name" + str(__import__("builtins").injected()) + "'


def assert_no_injected_call(code: str) -> None:
    """Check the hostile expression remains data in valid generated Python."""
    tree = ast.parse(code)
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "__import__"
        for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.Constant) and node.value == PAYLOAD
        for node in ast.walk(tree)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("bridge_class", [SocketBridge, XmlRpcBridge])
async def test_open_document_path_is_never_executable(bridge_class, monkeypatch):
    """A path containing Python expressions cannot alter generated code."""
    bridge = bridge_class()
    bridge.execute_python = AsyncMock(side_effect=CaptureCode)
    with pytest.raises(CaptureCode):
        await bridge.open_document(PAYLOAD)
    code = bridge.execute_python.await_args.args[0]
    assert_no_injected_call(code)
    invoked = []
    monkeypatch.setattr(
        builtins, "injected", lambda: invoked.append(True), raising=False
    )
    with pytest.raises(FileNotFoundError, match="File not found"):
        exec(code, {})  # noqa: S102
    assert invoked == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module", "register", "tool", "arguments"),
    [
        ("export", "register_export_tools", "import_step", {"file_path": PAYLOAD}),
        (
            "partdesign",
            "register_partdesign_tools",
            "create_sketch",
            {"body_name": PAYLOAD},
        ),
        (
            "objects",
            "register_object_tools",
            "scale_object",
            {"object_name": PAYLOAD, "scale": 1.0},
        ),
        (
            "spreadsheet",
            "register_spreadsheet_tools",
            "spreadsheet_set_cell",
            {"spreadsheet_name": PAYLOAD, "cell": "A1", "value": "1"},
        ),
        (
            "draft",
            "register_draft_tools",
            "draft_shapestring_to_face",
            {"shapestring_name": PAYLOAD},
        ),
        (
            "view",
            "register_view_tools",
            "set_object_visibility",
            {"object_name": PAYLOAD, "visible": True},
        ),
    ],
)
async def test_tool_string_inputs_are_never_executable(
    module, register, tool, arguments
):
    """Model-selected strings remain literals even in error-message branches."""
    mcp = CaptureTools()
    bridge = AsyncMock()
    bridge.execute_python.side_effect = CaptureCode

    async def get_bridge():
        return bridge

    getattr(importlib.import_module(f"freecad_mcp.tools.{module}"), register)(
        mcp, get_bridge
    )
    with pytest.raises(CaptureCode):
        await mcp.functions[tool](**arguments)
    assert_no_injected_call(bridge.execute_python.await_args.args[0])
