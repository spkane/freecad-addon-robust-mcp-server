"""Behavioral tests for FreeCAD object inspection and serialization."""

import json
import xmlrpc.client
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult
from freecad_mcp.bridge.embedded import EmbeddedBridge
from freecad_mcp.bridge.object_inspection import build_object_inspection_code
from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge


class LinkedObject:
    """Represent a FreeCAD document object with a misleading class module."""

    Name = "Box"
    Label = "A box"
    TypeId = "Part::Box"
    Document = SimpleNamespace(Name="Doc")

    def isDerivedFrom(self, type_id: str) -> bool:
        """Identify this object as a FreeCAD document object."""
        return type_id == "App::DocumentObject"


def _execute_inspection(obj: object, **options: bool) -> dict[str, Any]:
    """Execute the exact generated code using a minimal FreeCAD document."""
    doc = SimpleNamespace(getObject=lambda _name: obj)
    freecad = SimpleNamespace(ActiveDocument=doc, getDocument=lambda _name: doc)
    namespace: dict[str, Any] = {"FreeCAD": freecad}
    code = build_object_inspection_code("Object", "Doc", **options)
    exec(compile(code, "<inspection>", "exec"), namespace)  # noqa: S102
    return namespace["_result_"]


def _object(**properties: object) -> SimpleNamespace:
    """Build an object with the supplied FreeCAD-style properties."""
    return SimpleNamespace(
        Name="Object",
        Label="Object",
        TypeId="Part::Feature",
        PropertiesList=list(properties),
        OutList=[],
        InList=[],
        **properties,
    )


def test_serializes_nested_links_and_xmlrpc_unsafe_values() -> None:
    """Both wire formats accept the output and preserve link identity."""
    link = LinkedObject()
    obj = _object(
        Link=link,
        Nested=[link, (link, ("Edge1", "Edge2"))],
        Large=2**40,
        Nonfinite=float("nan"),
        Text="invalid\x00\ud800",
    )
    obj.Label = "invalid\x00label"
    result = _execute_inspection(obj, include_shape=False)
    expected_link = {
        "name": "Box",
        "label": "A box",
        "type_id": "Part::Box",
        "document": "Doc",
    }
    assert result["properties"]["Link"] == expected_link
    assert result["properties"]["Nested"] == [
        expected_link,
        [expected_link, ["Edge1", "Edge2"]],
    ]
    assert result["properties"]["Large"] == str(2**40)
    assert result["properties"]["Nonfinite"] == "nan"
    assert result["properties"]["Text"] == "invalid\ufffd\ufffd"
    assert result["label"] == "invalid\ufffdlabel"
    xmlrpc.client.loads(xmlrpc.client.dumps((result,), allow_none=True))
    json.dumps(result, allow_nan=False).encode("utf-8")


def test_limits_cycles_depth_and_collection_size() -> None:
    """Large and cyclic properties produce explicit, bounded results."""
    cyclic: list = []
    cyclic.append(cyclic)
    deep: object = "end"
    for _ in range(12):
        deep = [deep]
    result = _execute_inspection(
        _object(Cycle=cyclic, Deep=deep, Many=list(range(150)), Text="x" * 900),
        include_shape=False,
    )
    props = result["properties"]
    assert props["Cycle"] == ["<cycle>"]
    nested = props["Deep"]
    for _ in range(8):
        nested = nested[0]
    assert nested == "<max depth>"
    assert len(props["Many"]) == 101
    assert props["Many"][-1] == "<truncated>"
    assert props["Text"].endswith("<truncated>")
    assert len(props["Text"]) < 600
    xmlrpc.client.dumps((result,), allow_none=True)


def test_global_budget_limits_nested_output_and_marks_colliding_keys() -> None:
    """Shared limits cap output and converted mapping keys do not overwrite."""
    result = _execute_inspection(
        _object(
            Mapping={1: "first", "1": "second"},
            Long=["\U0001f600" * 512 for _ in range(100)],
        ),
        include_shape=False,
    )
    assert result["properties"]["Mapping"] == {"1": "first", "<truncated>": True}
    assert result["properties"]["Long"][-1] == "<truncated>"
    assert len(json.dumps(result).encode("utf-8")) < 64 * 1024
    xmlrpc.client.dumps((result,), allow_none=True)


def test_disabled_properties_and_shape_are_not_read() -> None:
    """Disabled sections must not access their corresponding FreeCAD data."""

    class ObjectWithoutReadableDetails:
        """Object whose optional data cannot be accessed."""

        Name = Label = "Object"
        TypeId = "Part::Feature"

        @property
        def PropertiesList(self) -> list[str]:
            """Fail if properties are read."""
            raise AssertionError("Properties were read")

        @property
        def Shape(self) -> object:
            """Fail if the shape is read."""
            raise AssertionError("Shape was read")

    result = _execute_inspection(
        ObjectWithoutReadableDetails(), include_properties=False, include_shape=False
    )
    assert result["properties"] == {}
    assert result["shape_info"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("bridge_class", [XmlRpcBridge, SocketBridge, EmbeddedBridge])
async def test_bridge_inspection_uses_common_program_and_propagates_errors(
    bridge_class: type,
) -> None:
    """Every bridge executes the common inspection code and preserves errors."""
    bridge = bridge_class()
    bridge.execute_python = AsyncMock(
        return_value=ExecutionResult(
            success=False,
            result=None,
            stdout="",
            stderr="transport failed",
            execution_time_ms=0,
        )
    )
    try:
        with pytest.raises(ValueError, match="transport failed"):
            await bridge.get_object(
                "Object", "Doc", include_properties=False, include_shape=False
            )
        code = bridge.execute_python.call_args.args[0]
        assert code == build_object_inspection_code(
            "Object", "Doc", include_properties=False, include_shape=False
        )
    finally:
        await bridge.disconnect()
