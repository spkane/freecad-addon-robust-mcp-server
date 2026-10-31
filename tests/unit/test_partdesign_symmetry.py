"""Executable compatibility tests for symmetric Part Design operations."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult


class _FakeFeature:
    """Model FreeCAD's dynamically exposed feature properties."""

    Name: str
    Label: str
    TypeId: str
    PropertiesList: list[str]
    assignments: dict[str, Any]
    initially_visible_symmetry_properties: dict[str, bool]
    ReferenceAxis: tuple[Any, list[str]]

    def __init__(
        self,
        type_id: str,
        name: str,
        symmetry_properties: list[str],
    ) -> None:
        object.__setattr__(self, "Name", name)
        object.__setattr__(self, "Label", name)
        object.__setattr__(self, "TypeId", type_id)
        object.__setattr__(self, "PropertiesList", symmetry_properties)
        object.__setattr__(self, "assignments", {})
        object.__setattr__(
            self,
            "initially_visible_symmetry_properties",
            {
                property_name: hasattr(self, property_name)
                for property_name in symmetry_properties
            },
        )

    def __setattr__(self, name: str, value: Any) -> None:
        """Record declared-property assignments while allowing dynamic attributes."""
        object.__setattr__(self, name, value)
        if name in self.PropertiesList:
            self.assignments[name] = value


class _FakeOrigin:
    """Provide role-addressable axes with auto-suffixed document names."""

    class _Feature:
        """Represent one FreeCAD origin feature."""

        def __init__(self, role: str, name: str) -> None:
            self.Role = role
            self.Name = name

    def __init__(self, axis_roles: list[str]) -> None:
        self.OriginFeatures = [self._Feature(role, f"{role}001") for role in axis_roles]


class _FakeBody:
    """Create one Part Design feature with configured dynamic properties."""

    TypeId = "PartDesign::Body"

    def __init__(
        self,
        sketch: object,
        symmetry_properties: list[str],
        axis_roles: list[str],
    ) -> None:
        self.Group = [sketch]
        self.Origin = _FakeOrigin(axis_roles)
        self._symmetry_properties = symmetry_properties
        self.feature: _FakeFeature | None = None

    def newObject(self, type_id: str, name: str) -> _FakeFeature:
        """Create and retain the feature targeted by generated code."""
        self.feature = _FakeFeature(type_id, name, self._symmetry_properties)
        return self.feature


class _FakeDocument:
    """Provide the document operations used by generated Part Design code."""

    def __init__(
        self,
        symmetry_properties: list[str],
        axis_roles: list[str] | None = None,
    ) -> None:
        self.sketch = object()
        self.body = _FakeBody(
            self.sketch,
            symmetry_properties,
            axis_roles if axis_roles is not None else ["X_Axis", "Y_Axis", "Z_Axis"],
        )
        self.Objects = [self.body]
        self.committed = False
        self.aborted = False

    def getObject(self, name: str) -> object | None:
        """Return the configured sketch by name."""
        return self.sketch if name == "Sketch" else None

    def openTransaction(self, _name: str) -> None:
        """Accept a transaction start."""

    def recompute(self) -> None:
        """Accept a document recompute."""

    def commitTransaction(self) -> None:
        """Record successful transaction completion."""
        self.committed = True

    def abortTransaction(self) -> None:
        """Record failed transaction rollback."""
        self.aborted = True


class _FakeFreeCAD:
    """Provide the FreeCAD module surface used by generated code."""

    def __init__(
        self,
        symmetry_properties: list[str],
        axis_roles: list[str] | None = None,
    ) -> None:
        self.ActiveDocument = _FakeDocument(symmetry_properties, axis_roles)

    def getDocument(self, _name: str) -> _FakeDocument:
        """Return the active fake document."""
        return self.ActiveDocument


class TestSymmetricExtrudeExecution:
    """Execute every supported symmetric-extrusion compatibility path."""

    @staticmethod
    def _register_tools(
        bridge: AsyncMock,
    ) -> dict[str, Callable[..., Awaitable[dict[str, Any]]]]:
        """Register Part Design tools against a supplied bridge."""
        from freecad_mcp.tools.partdesign import register_partdesign_tools

        mcp = MagicMock()
        registered_tools: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {}

        def tool_decorator() -> Callable[
            [Callable[..., Awaitable[dict[str, Any]]]],
            Callable[..., Awaitable[dict[str, Any]]],
        ]:
            def wrapper(
                func: Callable[..., Awaitable[dict[str, Any]]],
            ) -> Callable[..., Awaitable[dict[str, Any]]]:
                registered_tools[func.__name__] = func
                return func

            return wrapper

        mcp.tool = tool_decorator

        async def get_bridge() -> AsyncMock:
            return bridge

        register_partdesign_tools(mcp, get_bridge)
        return registered_tools

    @staticmethod
    def _configure_executing_bridge(
        bridge: AsyncMock,
        freecad: _FakeFreeCAD,
    ) -> None:
        """Execute generated code against a controlled FreeCAD test double."""

        async def execute_python(code: str) -> ExecutionResult:
            namespace: dict[str, Any] = {"FreeCAD": freecad}
            try:
                exec(compile(code, "<generated>", "exec"), namespace)  # noqa: S102
            except Exception as exc:
                return ExecutionResult(
                    success=False,
                    result=None,
                    stdout="",
                    stderr="",
                    execution_time_ms=1.0,
                    error_type=type(exc).__name__,
                    error_traceback=str(exc),
                )
            return ExecutionResult(
                success=True,
                result=namespace["_result_"],
                stdout="",
                stderr="",
                execution_time_ms=1.0,
            )

        bridge.execute_python = AsyncMock(side_effect=execute_python)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("tool_name", "feature_variable", "feature_type", "operation_argument"),
        [
            ("pad_sketch", "pad", "PartDesign::Pad", {"length": 10.0}),
            ("pocket_sketch", "pocket", "PartDesign::Pocket", {"length": 10.0}),
            (
                "revolution_sketch",
                "rev",
                "PartDesign::Revolution",
                {"angle": 180.0},
            ),
            ("groove_sketch", "groove", "PartDesign::Groove", {"angle": 180.0}),
        ],
    )
    @pytest.mark.parametrize(
        ("property_name", "symmetry_properties"),
        [
            ("SideType", ["SideType"]),
            ("Midplane", ["Midplane"]),
            ("Symmetric", ["Symmetric"]),
            ("SideType", ["SideType", "Midplane"]),
            ("SideType", ["SideType", "Symmetric"]),
            ("Midplane", ["Midplane", "Symmetric"]),
            ("SideType", ["SideType", "Midplane", "Symmetric"]),
        ],
    )
    @pytest.mark.parametrize("symmetric", [True, False])
    async def test_executes_each_property_path(
        self,
        tool_name: str,
        feature_variable: str,
        feature_type: str,
        operation_argument: dict[str, float],
        property_name: str,
        symmetry_properties: list[str],
        symmetric: bool,
    ) -> None:
        """Set the declared property even when Python attribute probing fails."""
        freecad = _FakeFreeCAD(symmetry_properties)
        bridge = AsyncMock()
        self._configure_executing_bridge(bridge, freecad)
        tools = self._register_tools(bridge)

        result = await tools[tool_name](
            sketch_name="Sketch",
            symmetric=symmetric,
            **operation_argument,
        )

        feature = freecad.ActiveDocument.body.feature
        assert feature is not None
        assert feature.TypeId == feature_type
        assert set(feature.initially_visible_symmetry_properties) == set(
            symmetry_properties
        )
        assert not any(feature.initially_visible_symmetry_properties.values())
        if property_name == "SideType":
            expected_value: str | bool = "Symmetric" if symmetric else "One side"
        else:
            expected_value = symmetric
        assert feature.assignments == {property_name: expected_value}
        if tool_name not in ("pad_sketch", "pocket_sketch"):
            axis_object, subelements = feature.ReferenceAxis
            assert axis_object.Role == "X_Axis"
            assert axis_object.Name == "X_Axis001"
            assert subelements == [""]
        assert result["type_id"] == feature_type
        assert freecad.ActiveDocument.committed is True
        assert freecad.ActiveDocument.aborted is False

        code = bridge.execute_python.call_args.args[0]
        assert code.count("_symmetric =") == 1
        assert code.index(f'"SideType" in {feature_variable}.PropertiesList') < (
            code.index(f'"Midplane" in {feature_variable}.PropertiesList')
        )
        assert code.index(f'"Midplane" in {feature_variable}.PropertiesList') < (
            code.index(f'"Symmetric" in {feature_variable}.PropertiesList')
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("tool_name", "operation_argument", "feature_name"),
        [
            ("pad_sketch", {"length": 10.0}, "PartDesign::Pad"),
            ("pocket_sketch", {"length": 10.0}, "PartDesign::Pocket"),
            ("revolution_sketch", {"angle": 180.0}, "PartDesign::Revolution"),
            ("groove_sketch", {"angle": 180.0}, "PartDesign::Groove"),
        ],
    )
    async def test_rejects_feature_without_supported_property(
        self,
        tool_name: str,
        operation_argument: dict[str, float],
        feature_name: str,
    ) -> None:
        """Fail clearly and roll back when no compatibility property exists."""
        freecad = _FakeFreeCAD([])
        bridge = AsyncMock()
        self._configure_executing_bridge(bridge, freecad)
        tools = self._register_tools(bridge)

        with pytest.raises(ValueError, match=f"{feature_name} exposes no supported"):
            await tools[tool_name](
                sketch_name="Sketch",
                symmetric=True,
                **operation_argument,
            )

        assert freecad.ActiveDocument.committed is False
        assert freecad.ActiveDocument.aborted is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name", ["revolution_sketch", "groove_sketch"])
    async def test_rejects_missing_base_axis_and_rolls_back(
        self,
        tool_name: str,
    ) -> None:
        """Fail clearly when an origin does not expose the requested axis role."""
        freecad = _FakeFreeCAD(["Midplane"], axis_roles=[])
        bridge = AsyncMock()
        self._configure_executing_bridge(bridge, freecad)
        tools = self._register_tools(bridge)

        with pytest.raises(ValueError, match="no axis with role 'X_Axis'"):
            await tools[tool_name](
                sketch_name="Sketch",
                angle=180.0,
                symmetric=True,
            )

        assert freecad.ActiveDocument.committed is False
        assert freecad.ActiveDocument.aborted is True


class TestPocketMidplaneTerminationGuard:
    """Reject symmetric cuts the Midplane fallback cannot honour.

    FreeCAD 1.0.x ``Pocket::buildExtrusion()`` ignores ``Midplane`` for the
    UpTo* termination modes (only ``Reversed`` is consulted there), so
    ``symmetric=True`` combined with ``type="UpToFirst"``/``"UpToFace"``/
    ``"UpToLast"`` would silently produce a one-sided cut. The guard lives
    only in the Midplane branch: FreeCAD 1.1+ ``SideType="Symmetric"`` mirrors
    the prism for every termination mode, and ``symmetric=False`` never needs
    Midplane at all.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("termination", ["UpToFirst", "UpToFace", "UpToLast"])
    async def test_rejects_symmetric_midplane_with_unsupported_termination(
        self,
        termination: str,
    ) -> None:
        """Refuse and roll back before writing any symmetry property."""
        freecad = _FakeFreeCAD(["Midplane"])
        bridge = AsyncMock()
        TestSymmetricExtrudeExecution._configure_executing_bridge(bridge, freecad)
        tools = TestSymmetricExtrudeExecution._register_tools(bridge)

        with pytest.raises(ValueError, match="is not supported with type="):
            await tools["pocket_sketch"](
                sketch_name="Sketch",
                length=10.0,
                type=termination,
                symmetric=True,
            )

        feature = freecad.ActiveDocument.body.feature
        assert feature is not None
        assert feature.assignments == {}
        assert freecad.ActiveDocument.committed is False
        assert freecad.ActiveDocument.aborted is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("symmetry_properties", "termination", "symmetric", "expected"),
        [
            (["Midplane"], "ThroughAll", True, ("Midplane", True)),
            (["Midplane"], "Length", True, ("Midplane", True)),
            (["Midplane"], "UpToFirst", False, ("Midplane", False)),
            (["SideType"], "UpToFirst", True, ("SideType", "Symmetric")),
        ],
    )
    async def test_accepts_supported_termination_combinations(
        self,
        symmetry_properties: list[str],
        termination: str,
        symmetric: bool,
        expected: tuple[str, Any],
    ) -> None:
        """Let every combination FreeCAD actually honours through."""
        freecad = _FakeFreeCAD(symmetry_properties)
        bridge = AsyncMock()
        TestSymmetricExtrudeExecution._configure_executing_bridge(bridge, freecad)
        tools = TestSymmetricExtrudeExecution._register_tools(bridge)

        result = await tools["pocket_sketch"](
            sketch_name="Sketch",
            length=10.0,
            type=termination,
            symmetric=symmetric,
        )

        assert result["type_id"] == "PartDesign::Pocket"
        feature = freecad.ActiveDocument.body.feature
        assert feature is not None
        assert feature.assignments == {expected[0]: expected[1]}
        assert freecad.ActiveDocument.committed is True
        assert freecad.ActiveDocument.aborted is False
