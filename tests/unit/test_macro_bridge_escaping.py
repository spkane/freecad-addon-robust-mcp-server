"""Verify macro names cannot escape generated bridge code."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult
from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge


@pytest.mark.asyncio
@pytest.mark.parametrize("bridge_class", [SocketBridge, XmlRpcBridge])
@pytest.mark.parametrize(
    "name", ["'''; marker.append('executed'); #", "name\nmarker.append('executed')"]
)
async def test_macro_name_is_data_in_generated_code(
    tmp_path: Path, bridge_class: type, name: str
) -> None:
    """A quote-bearing name must not execute when the macro is created."""
    marker: list[str] = []

    async def execute(code: str) -> ExecutionResult:
        namespace = {
            "FreeCAD": SimpleNamespace(getUserMacroDir=lambda _create: str(tmp_path)),
            "marker": marker,
        }
        exec(code, namespace)  # noqa: S102
        return ExecutionResult(
            success=True,
            result=namespace["_result_"],
            stdout="",
            stderr="",
            execution_time_ms=0,
        )

    bridge = bridge_class()
    bridge.execute_python = AsyncMock(side_effect=execute)
    created = await bridge.create_macro(
        name, "_result_ = 42", "note\nmarker.append('executed')"
    )
    assert marker == []
    assert created.name == name
    contents = await asyncio.to_thread(Path(created.path).read_text)
    assert all(
        not line or line.startswith("#")
        for line in contents.split("import FreeCAD")[0].splitlines()
    )
    assert contents.endswith("_result_ = 42")
