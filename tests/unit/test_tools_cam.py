"""Unit tests for the CAM tools module.

The CAM tools load ``freecad_side/cam_runtime.py`` into FreeCAD once and then
send one function call per tool. These tests use a mocked bridge and check
the generated code: the runtime version is checked, it is loaded in pieces
small enough for the bridge, arguments travel as JSON, modifying tools run
inside an undo transaction, and every called runtime function exists.
"""

import ast
import asyncio
import hashlib
import json
import re
import sys
import xmlrpc.client
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult
from freecad_mcp.tools import cam
from freecad_mcp.tools.cam import (
    RUNTIME_MODULE,
    build_cam_code,
    build_runtime_load_code,
    register_cam_tools,
)

RegisteredTools = dict[str, Callable[..., Awaitable[Any]]]

MODIFYING_TOOLS = {
    "cam_create_job",
    "cam_set_stock",
    "cam_add_tool_controller",
    "cam_feeds_speeds",
    "cam_remove_tool_controller",
    "cam_add_operation",
    "cam_add_dressup",
    "cam_set_properties",
    "cam_set_operation_order",
    "cam_post_process",
    "cam_simulate",
    "cam_place_model",
}

READ_ONLY_TOOLS = {
    "cam_get_capabilities",
    "cam_list_tool_library",
    "cam_analyze_model",
    "cam_describe_type",
    "cam_get_properties",
    "cam_inspect_job",
    "cam_inspect_path",
    "cam_export_job_template",
    "cam_check_job",
    "cam_import_tool_library",
    "cam_export_tool_library",
}

# Minimal valid arguments for every tool
TOOL_ARGS: dict[str, dict[str, Any]] = {
    "cam_get_capabilities": {},
    "cam_check_job": {},
    "cam_simulate": {},
    "cam_place_model": {"rotate": {"axis": "x", "angle": 180}},
    "cam_import_tool_library": {"file_path": "/tmp/lib.fctl"},
    "cam_export_tool_library": {"library": "Default", "file_path": "/tmp/x.tbl"},
    "cam_list_tool_library": {},
    "cam_analyze_model": {"object_name": "Part"},
    "cam_create_job": {"model_objects": ["Part"]},
    "cam_set_stock": {},
    "cam_add_tool_controller": {"tool": {"shape": "endmill"}},
    "cam_feeds_speeds": {},
    "cam_remove_tool_controller": {"tool_controller": "TC"},
    "cam_add_operation": {"op_type": "Profile"},
    "cam_add_dressup": {"dressup_type": "Tags", "base_operation": "Profile"},
    "cam_describe_type": {"type_name": "Profile"},
    "cam_get_properties": {"object_name": "Profile"},
    "cam_set_properties": {"object_name": "Profile", "values": {"Side": "Inside"}},
    "cam_set_operation_order": {"order": ["Profile"]},
    "cam_inspect_job": {},
    "cam_inspect_path": {"object_name": "Profile"},
    "cam_post_process": {"post_processor": "linuxcnc"},
    "cam_export_job_template": {"file_path": "/tmp/job_test.json"},
}


def _runtime_functions() -> set[str]:
    tree = ast.parse(cam._runtime_source())
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


def _called_function(code: str) -> str:
    match = re.search(r"_result_ = _cam_runtime\.(\w+)\(_json\.loads\(", code)
    assert match, "generated code has no runtime call"
    return match.group(1)


def _payload(code: str) -> dict[str, Any]:
    match = re.search(r"_json\.loads\((.+)\)\)\n", code)
    assert match
    return json.loads(ast.literal_eval(match.group(1)))


class TestBuildCamCode:
    """Tests for the code generator shared by all CAM tools."""

    def test_checks_runtime_version_and_calls(self) -> None:
        code = build_cam_code("inspect_job", {"job_name": "Job"})
        sha = hashlib.sha256(cam._runtime_source().encode("utf-8")).hexdigest()
        assert repr(sha) in code
        assert "def inspect_job(" not in code
        assert _called_function(code) == "inspect_job"
        assert _payload(code) == {"job_name": "Job"}

    def test_generated_code_is_valid_python(self) -> None:
        code = build_cam_code("add_operation", {"op_type": "Profile"}, "Add Profile")
        compile(code, "<cam>", "exec")

    def test_values_cannot_inject_code(self) -> None:
        nasty = "x')); import os; os.system('echo pwned'); (('"
        code = build_cam_code("set_properties", {"object_name": nasty}, "Set")
        assert _payload(code) == {"object_name": nasty}
        assert "os.system('echo" not in code.replace(
            repr(json.dumps({"object_name": nasty})), ""
        )

    def test_transaction_wraps_modifying_call(self) -> None:
        code = build_cam_code("add_operation", {"doc_name": "D"}, "Add Profile")
        assert "openTransaction('Add Profile')" in code
        assert "abortTransaction()" in code
        assert "FreeCAD.getDocument('D')" in code

    def test_transaction_uses_active_document_without_doc_name(self) -> None:
        code = build_cam_code("add_operation", {}, "Add Profile")
        assert "_txn_doc = FreeCAD.ActiveDocument" in code

    def test_version_check_comes_before_transaction(self) -> None:
        code = build_cam_code("add_operation", {}, "Add Profile")
        assert code.index("raise RuntimeError") < code.index("openTransaction")

    def test_read_only_call_has_no_transaction(self) -> None:
        assert "openTransaction" not in build_cam_code("inspect_job", {})


class TestCamTools:
    """Tests for the registered CAM tools with a mocked bridge."""

    @pytest.fixture
    def tools_and_bridge(self) -> tuple[RegisteredTools, AsyncMock]:
        registered: RegisteredTools = {}
        mcp = MagicMock()

        def tool_decorator() -> Callable[
            [Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]
        ]:
            def wrapper(
                func: Callable[..., Awaitable[Any]],
            ) -> Callable[..., Awaitable[Any]]:
                registered[func.__name__] = func
                return func

            return wrapper

        mcp.tool = tool_decorator
        bridge = AsyncMock()
        bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={"ok": True},
                stdout="",
                stderr="",
                execution_time_ms=1.0,
            )
        )

        async def get_bridge() -> AsyncMock:
            return bridge

        register_cam_tools(mcp, get_bridge)
        return registered, bridge

    def test_registers_all_tools(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        tools, _ = tools_and_bridge
        assert set(tools) == MODIFYING_TOOLS | READ_ONLY_TOOLS
        assert set(TOOL_ARGS) == set(tools)

    @pytest.mark.parametrize("tool_name", sorted(TOOL_ARGS))
    async def test_tool_calls_existing_runtime_function(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock], tool_name: str
    ) -> None:
        tools, bridge = tools_and_bridge
        assert await tools[tool_name](**TOOL_ARGS[tool_name]) == {"ok": True}
        code = bridge.execute_python.call_args.args[0]
        assert _called_function(code) in _runtime_functions()
        has_txn = "openTransaction" in code
        assert has_txn == (tool_name in MODIFYING_TOOLS)

    async def test_long_timeout_for_cam_calls(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        tools, bridge = tools_and_bridge
        await tools["cam_add_operation"](op_type="Surface")
        timeout = bridge.execute_python.call_args.kwargs["timeout_ms"]
        assert timeout == cam.CAM_TIMEOUT_MS

    async def test_none_arguments_are_dropped(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        tools, bridge = tools_and_bridge
        await tools["cam_add_operation"](
            op_type="Profile",
            base=[{"object": "Part", "subelements": ["Face1"]}],
            properties={"Side": "Outside"},
        )
        payload = _payload(bridge.execute_python.call_args.args[0])
        assert payload == {
            "op_type": "Profile",
            "base": [{"object": "Part", "subelements": ["Face1"]}],
            "properties": {"Side": "Outside"},
        }

    async def test_empty_base_is_kept(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        tools, bridge = tools_and_bridge
        await tools["cam_add_operation"](op_type="Profile", base=[])
        assert _payload(bridge.execute_python.call_args.args[0])["base"] == []

    async def test_failure_raises_with_last_traceback_line(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        tools, bridge = tools_and_bridge
        bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=1.0,
                error_type="ValueError",
                error_traceback="Traceback ...\nValueError: Profile.Side: 'X' not in ['Outside', 'Inside']",
            )
        )
        with pytest.raises(ValueError, match=r"^ValueError: Profile\.Side"):
            await tools["cam_set_properties"](
                object_name="Profile", values={"Side": "X"}
            )

    async def test_describe_type_passes_type_as_type(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        tools, bridge = tools_and_bridge
        await tools["cam_describe_type"](type_name="Tags", kind="dressup")
        payload = _payload(bridge.execute_python.call_args.args[0])
        assert payload["type"] == "Tags"
        assert payload["kind"] == "dressup"

    async def test_post_process_passes_use_job_output(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        tools, bridge = tools_and_bridge
        await tools["cam_post_process"](use_job_output=True)
        code = bridge.execute_python.call_args.args[0]
        assert _payload(code)["use_job_output"] is True
        assert _called_function(code) == "post_process"
        assert "def _write_job_output(" in cam._runtime_source()

    async def test_add_operation_passes_source_operations(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        tools, bridge = tools_and_bridge
        await tools["cam_add_operation"](
            op_type="Array", source_operations=["Profile", "Pocket"]
        )
        payload = _payload(bridge.execute_python.call_args.args[0])
        assert payload["source_operations"] == ["Profile", "Pocket"]
        assert "base" not in payload

    async def test_set_stock_material_only_sends_no_kind(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        tools, bridge = tools_and_bridge
        await tools["cam_set_stock"](material="Steel-Generic")
        payload = _payload(bridge.execute_python.call_args.args[0])
        assert payload == {"material": "Steel-Generic"}

    async def test_add_tool_controller_uses_presets_by_default(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        tools, bridge = tools_and_bridge
        await tools["cam_add_tool_controller"](
            tool={"library_bit": "endmill_6mm"}, op_type="profile"
        )
        payload = _payload(bridge.execute_python.call_args.args[0])
        assert payload["feeds_speeds"] == "preset"
        assert payload["op_type"] == "profile"

    async def test_feeds_speeds_passes_apply(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        tools, bridge = tools_and_bridge
        await tools["cam_feeds_speeds"](tool_controllers=["TC_17"], apply=True)
        code = bridge.execute_python.call_args.args[0]
        payload = _payload(code)
        assert payload["apply"] is True
        assert payload["tool_controllers"] == ["TC_17"]
        assert _called_function(code) == "feeds_speeds"
        assert "write_result_to_tc" in cam._runtime_source()

    async def test_simulate_runs_in_a_transaction(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        tools, bridge = tools_and_bridge
        await tools["cam_simulate"](show_result=True, resolution=0.2)
        code = bridge.execute_python.call_args.args[0]
        assert _payload(code) == {
            "compare_with_model": True,
            "show_result": True,
            "resolution": 0.2,
        }
        assert "openTransaction" in code


def _run_like_bridge(code: str) -> None:
    """Run generated code the way the bridge does (fresh namespace)."""
    exec(compile(code, "<cam>", "exec"), {})  # noqa: S102


def _missing_runtime() -> ExecutionResult:
    return ExecutionResult(
        success=False,
        result=None,
        stdout="",
        stderr="",
        execution_time_ms=1.0,
        error_type="RuntimeError",
        error_traceback="Traceback ...\nRuntimeError: robust-mcp CAM runtime not loaded",
    )


def _ok(result: Any) -> ExecutionResult:
    return ExecutionResult(
        success=True, result=result, stdout="", stderr="", execution_time_ms=1.0
    )


class TestRuntimeLoading:
    """The runtime is loaded in pieces when FreeCAD doesn't have it (yet)."""

    def test_requests_fit_the_bridge_limit(self) -> None:
        for code in build_runtime_load_code():
            request = xmlrpc.client.dumps((code,), "execute").encode("utf-8")
            assert len(request) < 60 * 1024

    def test_load_code_creates_the_module(self) -> None:
        source = "VALUE = 41\n\ndef answer(args):\n    return VALUE + args['n']\n"
        try:
            for code in build_runtime_load_code(source):
                _run_like_bridge(code)
            module = sys.modules[RUNTIME_MODULE]
            assert module.answer({"n": 1}) == 42
            assert (
                hashlib.sha256(source.encode("utf-8")).hexdigest()
                == module._SOURCE_SHA256
            )
            assert RUNTIME_MODULE + "_upload" not in sys.modules
        finally:
            sys.modules.pop(RUNTIME_MODULE, None)

    def test_incomplete_upload_is_rejected(self) -> None:
        codes = build_runtime_load_code("A = 1\n" * 5000)
        assert len(codes) > 2
        try:
            _run_like_bridge(codes[0])
            with pytest.raises(RuntimeError, match="incomplete"):
                _run_like_bridge(codes[-1])
            assert RUNTIME_MODULE not in sys.modules
        finally:
            sys.modules.pop(RUNTIME_MODULE + "_upload", None)
            sys.modules.pop(RUNTIME_MODULE, None)

    def test_broken_runtime_is_not_registered(self) -> None:
        try:
            for code in build_runtime_load_code("raise ValueError('boom')\n")[:-1]:
                _run_like_bridge(code)
            with pytest.raises(ValueError, match="boom"):
                _run_like_bridge(
                    build_runtime_load_code("raise ValueError('boom')\n")[-1]
                )
            assert RUNTIME_MODULE not in sys.modules
        finally:
            sys.modules.pop(RUNTIME_MODULE, None)

    async def test_missing_runtime_is_loaded_and_call_retried(self) -> None:
        loads = build_runtime_load_code()
        bridge = AsyncMock()
        bridge.execute_python = AsyncMock(
            # first call, re-check under the lock, pieces, retried call
            side_effect=[_missing_runtime(), _missing_runtime()]
            + [_ok(True)] * len(loads)
            + [_ok({"ok": True})]
        )
        tools: RegisteredTools = {}
        mcp = MagicMock()
        mcp.tool = lambda: lambda func: tools.setdefault(func.__name__, func)

        async def get_bridge() -> AsyncMock:
            return bridge

        register_cam_tools(mcp, get_bridge)
        assert await tools["cam_inspect_job"]() == {"ok": True}
        sent = [c.args[0] for c in bridge.execute_python.call_args_list]
        assert sent[2:-1] == loads
        assert sent[0] == sent[1] == sent[-1]

    async def test_concurrent_calls_load_the_runtime_once(self) -> None:
        loads = build_runtime_load_code()
        loaded = False
        load_requests: list[str] = []

        async def execute_python(code: str, timeout_ms: int = 0) -> ExecutionResult:  # noqa: ARG001
            nonlocal loaded
            await asyncio.sleep(0)  # let the other call run in between
            if code in loads:
                load_requests.append(code)
                if code == loads[-1]:
                    loaded = True
                return _ok(True)
            return _ok({"ok": True}) if loaded else _missing_runtime()

        bridge = AsyncMock()
        bridge.execute_python = execute_python
        tools: RegisteredTools = {}
        mcp = MagicMock()
        mcp.tool = lambda: lambda func: tools.setdefault(func.__name__, func)

        async def get_bridge() -> AsyncMock:
            return bridge

        register_cam_tools(mcp, get_bridge)
        results = await asyncio.gather(
            tools["cam_inspect_job"](), tools["cam_get_capabilities"]()
        )
        assert results == [{"ok": True}, {"ok": True}]
        assert load_requests == loads  # one upload, pieces in order

    async def test_failed_load_raises(self) -> None:
        bridge = AsyncMock()
        bridge.execute_python = AsyncMock(
            side_effect=[
                _missing_runtime(),
                _missing_runtime(),
                ExecutionResult(
                    success=False,
                    result=None,
                    stdout="",
                    stderr="<ProtocolError: 413 Request too large>",
                    execution_time_ms=1.0,
                ),
            ]
        )
        tools: RegisteredTools = {}
        mcp = MagicMock()
        mcp.tool = lambda: lambda func: tools.setdefault(func.__name__, func)

        async def get_bridge() -> AsyncMock:
            return bridge

        register_cam_tools(mcp, get_bridge)
        with pytest.raises(ValueError, match="413 Request too large"):
            await tools["cam_inspect_job"]()


def _literal(name: str) -> Any:
    """A module-level literal assignment of the runtime, e.g. a registry."""
    target: ast.expr
    for node in ast.parse(cam._runtime_source()).body:
        if isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        else:
            continue
        if isinstance(target, ast.Name) and target.id == name:
            return ast.literal_eval(value)
    raise KeyError(name)


class TestRuntimeSource:
    """Static checks of the FreeCAD-side runtime (FreeCAD isn't importable here)."""

    def test_runtime_compiles(self) -> None:
        compile(cam._runtime_source(), "cam_runtime.py", "exec")

    def test_registries_reference_known_kinds(self) -> None:
        tree = ast.parse(cam._runtime_source())
        names = {
            t.id
            for n in tree.body
            if isinstance(n, ast.AnnAssign | ast.Assign)
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
            if isinstance(t, ast.Name)
        }
        assert {"OPERATIONS", "DRESSUPS", "FREECAD_BUGS"} <= names

    def test_special_operations_are_consistent(self) -> None:
        special = _literal("SPECIAL_OPERATIONS")
        assert set(special) == {"Comment", "Stop", "Copy", "Array", "SimpleCopy"}
        assert not set(special) & set(_literal("OPERATIONS"))
        for name, spec in special.items():
            assert spec["sources"] in {"none", "one", "many"}, name
            assert spec["gui"].startswith("Path.Op.Gui."), name
            # all but SimpleCopy (a Custom op) are built from a GUI-module class
            assert ("cls" in spec and "vp" in spec) or name == "SimpleCopy", name

    def test_gui_only_dressups_are_recipes(self) -> None:
        dressups = _literal("DRESSUPS")
        for name in ("Boundary2", "Mirror", "PlungeMilling"):
            assert dressups[name]["kind"] == "recipe"
            assert dressups[name]["gui"] == f"Path.Dressup.Gui.{name}"
