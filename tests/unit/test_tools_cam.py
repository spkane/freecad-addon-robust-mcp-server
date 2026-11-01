"""Unit tests for the CAM tools module.

The CAM tools call the versioned dispatcher installed with the bridge.
"""

import ast
import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult
from freecad_mcp.tools import cam
from freecad_mcp.tools.cam import (
    build_cam_code,
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
    tree = ast.parse(_runtime_source())
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


def _called_function(code: str) -> str:
    match = re.search(r"_robust_mcp_cam_dispatch\(1, '(\w+)', _json\.loads\(", code)
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
        assert "_robust_mcp_cam_dispatch(1," in code
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

    async def test_incompatible_bridge_exposes_only_safe_guidance(
        self, tools_and_bridge: tuple[RegisteredTools, AsyncMock]
    ) -> None:
        """CAM version errors are deliberately sent to the MCP client."""
        from mcp.server.mcpserver.exceptions import ToolError

        tools, bridge = tools_and_bridge
        bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=1.0,
                error_type="RuntimeError",
                error_traceback=(
                    "Traceback includes private local paths\n"
                    "RuntimeError: Incompatible CAM interface: bridge is older"
                ),
            )
        )
        with pytest.raises(ToolError, match="bridge is older") as exc:
            await tools["cam_get_capabilities"]()
        assert "private local paths" not in str(exc.value)

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
        assert "def _write_job_output(" in _runtime_source()

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
        assert "write_result_to_tc" in _runtime_source()

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


def _runtime_source() -> str:
    return (
        Path(__file__).resolve().parents[2]
        / "freecad/RobustMCPBridge/freecad_mcp_bridge/cam_runtime.py"
    ).read_text()


def test_old_bridge_reports_update_required() -> None:
    code = build_cam_code("capabilities", {})
    with pytest.raises(RuntimeError, match=r"update.*Bridge"):
        exec(code, {})  # noqa: S102


def _literal(name: str) -> Any:
    """A module-level literal assignment of the runtime, e.g. a registry."""
    target: ast.expr
    for node in ast.parse(_runtime_source()).body:
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
        compile(_runtime_source(), "cam_runtime.py", "exec")

    def test_registries_reference_known_kinds(self) -> None:
        tree = ast.parse(_runtime_source())
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


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Load the installed runtime with a stand-in for the FreeCAD module."""
    import importlib.util
    import sys

    monkeypatch.setitem(sys.modules, "FreeCAD", MagicMock())
    path = (
        Path(__file__).resolve().parents[2]
        / "freecad/RobustMCPBridge/freecad_mcp_bridge/cam_runtime.py"
    )
    spec = importlib.util.spec_from_file_location("test_cam_runtime", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dispatch_rejects_incompatible_version_and_unknown_operation(
    runtime: Any,
) -> None:
    with pytest.raises(RuntimeError, match="Incompatible CAM interface"):
        runtime.dispatch(999, "capabilities", {})
    with pytest.raises(ValueError, match="Unknown CAM operation"):
        runtime.dispatch(1, "_write_output_file", {})


@pytest.mark.parametrize("server_api,direction", [(2, "older"), (0, "newer")])
def test_dispatch_reports_incompatible_bridge_direction(
    runtime: Any, server_api: int, direction: str
) -> None:
    """Mismatched components identify the older or newer bridge."""
    with pytest.raises(RuntimeError, match=direction):
        runtime.dispatch(server_api, "capabilities", {})


def test_split_output_collision_does_not_write(runtime: Any, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicate output"):
        runtime._write_output_file(
            tmp_path / "job.nc", [("same", "first"), ("same", "second")], True
        )
    assert not list(tmp_path.iterdir())


def test_output_requires_explicit_overwrite(runtime: Any, tmp_path: Path) -> None:
    output = tmp_path / "job.nc"
    output.write_text("existing")
    with pytest.raises(FileExistsError, match="already exists"):
        runtime._write_output_file(output, [("", "replacement")], False)
    assert output.read_text() == "existing"
    runtime._write_output_file(output, [("", "replacement")], False, overwrite=True)
    assert output.read_text() == "replacement"


def test_invalid_operation_is_not_post_processed(runtime: Any) -> None:
    op = MagicMock(Label="Broken", Active=True, State=["Invalid"])
    job = MagicMock()
    job.Operations.Group = [op]
    with pytest.raises(ValueError, match="failed recomputation"):
        runtime._validate_post_operations(job)


def test_empty_operation_is_not_post_processed(runtime: Any) -> None:
    op = MagicMock(
        Label="Empty", Active=True, State=[], PropertiesList=["ToolController"]
    )
    op.isValid.return_value = True
    op.Path.Commands = []
    job = MagicMock()
    job.Operations.Group = [op]
    with pytest.raises(ValueError, match="no toolpath"):
        runtime._validate_post_operations(job)


@pytest.mark.parametrize("resolution", [0, -1, float("inf"), float("nan"), 1e-9])
def test_simulation_rejects_invalid_or_excessive_resolution(
    runtime: Any, resolution: float
) -> None:
    with pytest.raises(ValueError, match="resolution"):
        runtime._simulation_resolution(resolution, 60, 40)


def test_simulation_accepts_default_resolution(runtime: Any) -> None:
    assert runtime._simulation_resolution(None, 60, 40) == 0.15


def test_job_output_collision_fails_before_writing(
    runtime: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys
    from types import ModuleType, SimpleNamespace

    path_module = ModuleType("Path")
    post_module = ModuleType("Path.Post")
    utils = ModuleType("Path.Post.Utils")

    class FilenameGenerator:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def generate_filenames(self) -> Any:
            while True:
                yield str(tmp_path / "same.nc")

        def set_subpartname(self, name: str) -> None:
            pass

    utils.FilenameGenerator = FilenameGenerator  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "Path", path_module)
    monkeypatch.setitem(sys.modules, "Path.Post", post_module)
    monkeypatch.setitem(sys.modules, "Path.Post.Utils", utils)
    job = SimpleNamespace(PostProcessorOutputFile="program.nc")
    with pytest.raises(ValueError, match="duplicate output"):
        runtime._write_job_output(job, [("first", "G1 X1"), ("second", "G1 X2")])
    assert not list(tmp_path.iterdir())


def test_output_rejects_symlinks(runtime: Any, tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("existing")
    link = tmp_path / "program.nc"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Creating symbolic links is unavailable on this account")
    with pytest.raises(ValueError, match="symbolic link"):
        runtime._write_output_file(link, [("", "G1")], False, overwrite=True)
    assert target.read_text() == "existing"


def test_embedded_cam_loads_without_importing_workbench(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from freecad_mcp.bridge.embedded import EmbeddedBridge

    workbench = tmp_path / "freecad/RobustMCPBridge"
    module_dir = workbench / "freecad_mcp_bridge"
    module_dir.mkdir(parents=True)
    (workbench / "__init__.py").write_text(
        "raise RuntimeError('unexpected auto-start')\n"
    )
    (module_dir / "cam_runtime.py").write_text(
        "def dispatch(version, operation, args):\n"
        "    return {'version': version, 'operation': operation, **args}\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    bridge = EmbeddedBridge()
    try:
        assert bridge._cam_dispatch(1, "capabilities", {"value": 2}) == {
            "version": 1,
            "operation": "capabilities",
            "value": 2,
        }
    finally:
        bridge._executor.shutdown(wait=True)


def test_post_process_requires_active_operations(runtime: Any) -> None:
    job = MagicMock()
    job.Operations.Group = []
    with pytest.raises(ValueError, match="no active operations"):
        runtime._validate_post_operations(job)


def test_embedded_cam_finds_workbench_in_active_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Find the workbench in the profile without importing its startup code."""
    from freecad_mcp.bridge.embedded import EmbeddedBridge

    workbench = tmp_path / "Mod/RobustMCPBridge/freecad/RobustMCPBridge"
    runtime_dir = workbench / "freecad_mcp_bridge"
    runtime_dir.mkdir(parents=True)
    (workbench / "__init__.py").write_text(
        "raise RuntimeError('unexpected auto-start')\n"
    )
    (runtime_dir / "cam_runtime.py").write_text(
        "def dispatch(version, operation, args):\n    return operation\n"
    )
    monkeypatch.setattr("sys.path", [])
    bridge = EmbeddedBridge()
    bridge._fc_module = MagicMock()
    bridge._fc_module.getUserAppDataDir.return_value = str(tmp_path)
    try:
        assert bridge._cam_dispatch(1, "capabilities", {}) == "capabilities"
    finally:
        bridge._executor.shutdown(wait=True)


def test_embedded_cam_rejects_ambiguous_profile_installations(tmp_path: Path) -> None:
    """Reject multiple profile installations instead of guessing which to load."""
    from freecad_mcp.bridge.embedded import EmbeddedBridge

    for name in ("first", "second"):
        runtime = (
            tmp_path
            / f"Mod/{name}/freecad/RobustMCPBridge/freecad_mcp_bridge/cam_runtime.py"
        )
        runtime.parent.mkdir(parents=True)
        runtime.write_text("# installed runtime\n")
    bridge = EmbeddedBridge()
    bridge._fc_module = MagicMock()
    bridge._fc_module.getUserAppDataDir.return_value = str(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="Multiple Robust MCP Bridge"):
            bridge._find_profile_cam_runtime()
    finally:
        bridge._executor.shutdown(wait=True)


def test_split_output_preparation_failure_leaves_no_files(
    runtime: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Clean staged files when preparing a later output fails."""
    original = runtime._stage_output_file
    calls = 0

    def fail_second(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk full")
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime, "_stage_output_file", fail_second)
    with pytest.raises(OSError, match="disk full"):
        runtime._write_output_file(
            tmp_path / "job.nc", [("first", "G1"), ("second", "G2")], True
        )
    assert not list(tmp_path.iterdir())


def test_split_output_publication_failure_reports_published_files(
    runtime: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Report earlier outputs without deleting files that may have changed."""
    original = runtime.os.link
    calls = 0

    def fail_second(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise FileExistsError("publication failed")
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime.os, "link", fail_second)
    with pytest.raises(RuntimeError, match=r"job_first\.nc"):
        runtime._write_output_file(
            tmp_path / "job.nc", [("first", "G1"), ("second", "G2")], True
        )
    assert (tmp_path / "job_first.nc").read_text() == "G1"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["job_first.nc"]


def test_output_falls_back_when_hard_links_are_unsupported(
    runtime: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exclusive creation supports filesystems that cannot create hard links."""

    def unsupported(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("hard links unsupported")

    monkeypatch.setattr(runtime.os, "link", unsupported)
    path = tmp_path / "job.nc"
    runtime._write_output_file(path, [("", "G1 X1")], False)
    assert path.read_text() == "G1 X1"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["job.nc"]


def test_output_overwrite_preserves_existing_permissions(
    runtime: Any, tmp_path: Path
) -> None:
    """Replacing a program preserves its existing access permissions."""
    import os
    import stat

    if os.name == "nt":
        pytest.skip("POSIX permission bits are unavailable on Windows")
    path = tmp_path / "job.nc"
    path.write_text("old")
    path.chmod(0o640)
    runtime._write_output_file(path, [("", "new")], False, overwrite=True)
    assert stat.S_IMODE(path.stat().st_mode) == 0o640
    assert path.read_text() == "new"


def test_new_output_matches_normal_file_permissions(
    runtime: Any, tmp_path: Path
) -> None:
    """New programs use the same umask-adjusted mode as ordinary files."""
    import os
    import stat

    if os.name == "nt":
        pytest.skip("POSIX permission bits are unavailable on Windows")
    baseline = tmp_path / "baseline"
    baseline.write_text("baseline")
    output = tmp_path / "job.nc"
    runtime._write_output_file(output, [("", "G1")], False)
    assert stat.S_IMODE(output.stat().st_mode) == stat.S_IMODE(baseline.stat().st_mode)


def test_atomic_rename_refuses_existing_destination(
    runtime: Any, tmp_path: Path
) -> None:
    """Atomic fallback never replaces a file created by another process."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.write_text("new")
    destination.write_text("existing")
    with pytest.raises(FileExistsError):
        runtime._rename_no_replace(source, destination)
    assert source.read_text() == "new"
    assert destination.read_text() == "existing"


def test_unsupported_atomic_publication_leaves_no_output(
    runtime: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If atomic publication is unavailable no partial program is exposed."""
    import errno

    def unsupported(*_args: Any, **_kwargs: Any) -> None:
        raise OSError(errno.ENOTSUP, "unsupported")

    monkeypatch.setattr(runtime.os, "link", unsupported)
    monkeypatch.setattr(runtime, "_rename_no_replace", unsupported)
    with pytest.raises(OSError, match="cannot publish G-code atomically"):
        runtime._write_output_file(tmp_path / "job.nc", [("", "G1")], False)
    assert not list(tmp_path.iterdir())


def test_new_output_is_not_world_writable_under_permissive_umask(
    runtime: Any, tmp_path: Path
) -> None:
    """A permissive umask cannot make newly exported programs world-writable."""
    import os
    import stat

    if os.name == "nt":
        pytest.skip("POSIX permission bits are unavailable on Windows")
    old_umask = os.umask(0)
    try:
        output = tmp_path / "job.nc"
        runtime._write_output_file(output, [("", "G1")], False)
    finally:
        os.umask(old_umask)
    assert stat.S_IMODE(output.stat().st_mode) & 0o002 == 0


def test_publication_failure_does_not_delete_replaced_output(
    runtime: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file replaced by another process survives a later output failure."""
    original = runtime._publish_no_replace
    calls = 0

    def replace_then_fail(source: Any, destination: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            first = tmp_path / "job_first.nc"
            first.unlink()
            first.write_text("replacement from another process")
            raise FileExistsError("collision")
        original(source, destination)

    monkeypatch.setattr(runtime, "_publish_no_replace", replace_then_fail)
    with pytest.raises(RuntimeError, match=r"job_first\.nc"):
        runtime._write_output_file(
            tmp_path / "job.nc", [("first", "G1"), ("second", "G2")], True
        )
    assert (tmp_path / "job_first.nc").read_text() == "replacement from another process"


def test_rejects_unsafe_shared_output_directory(runtime: Any, tmp_path: Path) -> None:
    """Prevent other users from replacing staged files in shared directories."""
    import os

    if os.name == "nt":
        pytest.skip("POSIX directory permission bits are unavailable on Windows")
    tmp_path.chmod(0o777)
    try:
        with pytest.raises(PermissionError, match="not protected"):
            runtime._write_output_file(tmp_path / "job.nc", [("", "G1")], False)
    finally:
        tmp_path.chmod(0o700)
    assert not list(tmp_path.iterdir())


def test_sticky_directory_with_untrusted_owner_is_rejected(runtime: Any) -> None:
    """A sticky directory owner can replace files even when other users cannot."""
    import os
    from types import SimpleNamespace

    if os.name == "nt":
        pytest.skip("POSIX ownership is unavailable on Windows")
    directory = MagicMock()
    resolved = directory.resolve.return_value
    resolved.parents = ()
    resolved.stat.return_value = SimpleNamespace(st_mode=0o1777, st_uid=123456789)
    with pytest.raises(PermissionError, match="not protected"):
        runtime._validate_output_directory(directory)


def test_rejects_untrusted_ancestor_directory(runtime: Any, tmp_path: Path) -> None:
    """A writable ancestor can replace even a private output directory."""
    import os

    if os.name == "nt":
        pytest.skip("POSIX directory permission bits are unavailable on Windows")
    shared = tmp_path / "shared"
    output_dir = shared / "private"
    output_dir.mkdir(parents=True)
    shared.chmod(0o777)
    try:
        with pytest.raises(PermissionError, match="not protected"):
            runtime._write_output_file(output_dir / "job.nc", [("", "G1")], False)
    finally:
        shared.chmod(0o700)
    assert not list(output_dir.iterdir())
