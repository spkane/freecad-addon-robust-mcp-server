"""Exercise routing of model-selected file paths to local review."""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from freecad_mcp.bridge.base import ExecutionResult
from freecad_mcp.bridge.embedded import EmbeddedBridge
from freecad_mcp.bridge.file_review import file_review_target
from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge
from freecad_mcp.tools.documents import register_document_tools


class Tools:
    """Collect registered functions without running an MCP transport."""

    def __init__(self):
        self.functions = {}

    def tool(self, **_kwargs):
        def register(function):
            self.functions[function.__name__] = function
            return function

        return register


@pytest.mark.asyncio
@pytest.mark.parametrize("cancelled", [False, True])
async def test_failed_file_dispatch_releases_selected_document(
    monkeypatch: pytest.MonkeyPatch, cancelled: bool
) -> None:
    """Client-side failures and cancellation release the unclaimed reservation."""
    from freecad_mcp.tools.export import register_export_tools

    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=False),
    )
    bridge = SocketBridge()
    monkeypatch.setattr(
        bridge,
        "capture_review_document",
        AsyncMock(return_value={"name": "Model", "path": "", "token": "token"}),
    )
    release = AsyncMock()
    monkeypatch.setattr(bridge, "release_review_document", release)
    failure = asyncio.CancelledError() if cancelled else ValueError("failed")
    monkeypatch.setattr(bridge, "execute_python", AsyncMock(side_effect=failure))
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_export_tools(mcp, get_bridge)
    with pytest.raises(type(failure)):
        await mcp.functions["import_step"](file_path="/tmp/model.step")
    release.assert_awaited_once_with("token")


def _result(path: str) -> ExecutionResult:
    return ExecutionResult(
        success=True,
        result={"name": "Doc", "path": path},
        stdout="",
        stderr="",
        execution_time_ms=1,
    )


@pytest.mark.asyncio
async def test_open_document_reviews_its_exact_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit path uses the reviewed protocol rather than raw execution."""
    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=False),
    )
    bridge: Any = SocketBridge()
    bridge.execute_reviewed_file = AsyncMock(return_value=_result("/tmp/model.FCStd"))
    bridge._send_request = AsyncMock()
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    result = await mcp.functions["open_document"]("/tmp/model.FCStd")
    assert result["name"] == "Doc"
    args = bridge.execute_reviewed_file.await_args.args
    assert args[1:] == ("/tmp/model.FCStd", "read", "path")
    assert "FreeCAD.openDocument" in args[0]
    bridge._send_request.assert_not_awaited()
    assert file_review_target.get() is None


@pytest.mark.asyncio
async def test_existing_document_save_uses_reviewed_path() -> None:
    """Implicit saves bind the current path and document before approval."""
    bridge = SimpleNamespace(
        get_active_document=AsyncMock(
            return_value=SimpleNamespace(name="Model", path="/tmp/model.FCStd")
        ),
        save_document=AsyncMock(return_value="/tmp/model.FCStd"),
    )
    observed = []

    async def save(name, path):
        observed.append((name, path, file_review_target.get()))
        return path

    bridge.save_document.side_effect = save
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    await mcp.functions["save_document"]()
    assert observed == [
        ("Model", "/tmp/model.FCStd", ("/tmp/model.FCStd", "write", "path"))
    ]
    assert file_review_target.get() is None


@pytest.mark.asyncio
async def test_explicit_save_binds_active_document_before_review() -> None:
    """Changing the active document during review does not redirect the save."""
    observed = []

    async def active():
        assert file_review_target.get() is None
        return SimpleNamespace(name="Model")

    async def save(name, path):
        observed.append((name, path, file_review_target.get()))
        return path

    bridge = SimpleNamespace(get_active_document=active, save_document=save)
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    await mcp.functions["save_document"](path="/tmp/output.FCStd")
    assert observed == [
        ("Model", "/tmp/output.FCStd", ("/tmp/output.FCStd", "write", "path"))
    ]


@pytest.mark.asyncio
async def test_save_reviews_canonical_destination(tmp_path) -> None:
    """A request without the native suffix reviews the file FreeCAD will write."""
    requested = tmp_path / "model"
    destination = tmp_path / "model.FCStd"
    destination.write_text("existing")
    seen = []

    async def save(name, path):
        seen.append((name, path, file_review_target.get()))
        return path

    bridge = SimpleNamespace(save_document=save)
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    await mcp.functions["save_document"](doc_name="Model", path=str(requested))
    assert seen == [("Model", str(destination), (str(destination), "write", "path"))]


@pytest.mark.asyncio
async def test_macro_creation_uses_bound_reviewed_path(tmp_path) -> None:
    """A changed macro directory cannot redirect a reviewed write."""
    reviewed = tmp_path / "original" / "Demo.FCMacro"
    other = tmp_path / "new" / "Demo.FCMacro"
    other.parent.mkdir()
    bridge: Any = SocketBridge()

    async def execute(code):
        env = {
            "_robust_mcp_reviewed_file_path": str(reviewed),
            "FreeCAD": SimpleNamespace(
                getUserMacroDir=lambda _create: str(other.parent)
            ),
        }
        exec(code, env)  # noqa: S102 - run the bridge's generated code in a controlled directory
        return ExecutionResult(
            success=True,
            result=env["_result_"],
            stdout="",
            stderr="",
            execution_time_ms=1,
        )

    bridge.execute_python = AsyncMock(side_effect=execute)
    result = await bridge.create_macro("Demo", "print('example')")
    assert result.path == str(reviewed)
    assert reviewed.is_file()
    assert not other.exists()


@pytest.mark.asyncio
async def test_close_with_save_propagates_review_denial() -> None:
    """Denying a save does not silently close the document."""
    bridge = SimpleNamespace(
        get_active_document=AsyncMock(
            return_value=SimpleNamespace(name="Model", path="/tmp/model.FCStd")
        ),
        get_documents=AsyncMock(
            return_value=[SimpleNamespace(name="Model", path="/tmp/model.FCStd")]
        ),
        execute_python=AsyncMock(side_effect=ToolError("ReviewDenied")),
        close_document=AsyncMock(),
    )
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    with pytest.raises(ToolError, match="ReviewDenied"):
        await mcp.functions["close_document"](save_changes=True)
    bridge.close_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_with_save_keeps_original_active_document() -> None:
    """A switch of the active document during approval cannot close another one."""
    doc = SimpleNamespace(name="Model", path="/tmp/model.FCStd")
    bridge = SimpleNamespace(
        get_active_document=AsyncMock(return_value=doc),
        get_documents=AsyncMock(return_value=[doc]),
        execute_python=AsyncMock(
            return_value=SimpleNamespace(success=True, result=doc.path)
        ),
        close_document=AsyncMock(),
    )
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    await mcp.functions["close_document"](save_changes=True)
    bridge.execute_python.assert_awaited_once()
    bridge.close_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_automation_override_uses_existing_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only an explicit local server setting bypasses the review path."""
    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=True),
    )
    bridge: Any = SocketBridge()
    bridge._send_request = AsyncMock(
        return_value={"success": True, "result": {"name": "Doc"}}
    )
    bridge.execute_reviewed_file = AsyncMock()
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    await mcp.functions["open_document"]("/tmp/model.FCStd")
    bridge._send_request.assert_awaited_once()
    bridge.execute_reviewed_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_xmlrpc_has_no_unreviewed_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the local socket review protocol, file operations fail closed."""
    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=False),
    )
    bridge: Any = XmlRpcBridge()
    bridge._run_proxy_call = AsyncMock()
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    with pytest.raises(ToolError, match="ReviewUnavailable"):
        await mcp.functions["open_document"]("/tmp/model.FCStd")
    bridge._run_proxy_call.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type", ["ReviewDenied", "FileTargetChanged", "ReviewExecutionUnknown"]
)
async def test_review_failures_are_not_hidden_by_generic_tool_errors(
    monkeypatch: pytest.MonkeyPatch, error_type: str
) -> None:
    """Denial, target replacement, and unknown execution remain distinguishable."""
    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=False),
    )
    bridge: Any = SocketBridge()
    bridge.execute_reviewed_file = AsyncMock(
        return_value=ExecutionResult(
            success=False,
            result=None,
            stdout="",
            stderr="review stopped",
            execution_time_ms=0,
            error_type=error_type,
        )
    )
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    with pytest.raises(ToolError, match=error_type):
        await mcp.functions["open_document"]("/tmp/model.FCStd")


@pytest.mark.asyncio
async def test_concurrent_file_targets_do_not_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parallel requests retain separate task-local targets."""
    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=False),
    )
    bridge: Any = SocketBridge()
    seen = []

    async def review(_code, path, action, kind, timeout_ms=None):
        assert timeout_ms is None
        await asyncio.sleep(0)
        seen.append((path, action, kind, file_review_target.get()))
        return _result(path)

    bridge.execute_reviewed_file = AsyncMock(side_effect=review)
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    await asyncio.gather(
        mcp.functions["open_document"]("/tmp/a.FCStd"),
        mcp.functions["open_document"]("/tmp/b.FCStd"),
    )
    assert sorted(seen) == [
        ("/tmp/a.FCStd", "read", "path", ("/tmp/a.FCStd", "read", "path")),
        ("/tmp/b.FCStd", "read", "path", ("/tmp/b.FCStd", "read", "path")),
    ]


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("model", "model.FCStd"),
        ("model.fcstd", "model.fcstd.FCStd"),
        ("model.txt", "model.txt.FCStd"),
        ("model.", "model.FCStd"),
        ("model.FCStd", "model.FCStd"),
    ],
)
def test_save_path_is_canonical(requested: str, expected: str) -> None:
    """FreeCAD cannot silently add a different destination after review."""
    from freecad_mcp.tools.documents import _document_save_path

    assert _document_save_path(requested) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("doc_name", [None, ""])
async def test_file_tool_binds_active_cam_document_before_review(doc_name) -> None:
    """A later active-document switch cannot redirect a reviewed CAM operation."""
    from freecad_mcp.tools._registration import file_tool

    mcp = Tools()
    bridge = SimpleNamespace(
        get_active_document=AsyncMock(return_value=SimpleNamespace(name="Original"))
    )

    async def get_bridge():
        assert file_review_target.get() is None
        return bridge

    @file_tool(mcp, get_bridge=get_bridge)
    async def cam_post_process(output_file: str, doc_name: str | None = None):
        return doc_name, output_file, file_review_target.get()

    assert await mcp.functions["cam_post_process"]("/tmp/test.nc", doc_name) == (
        "Original",
        "/tmp/test.nc",
        ("/tmp/test.nc", "write", "path"),
    )
    assert file_review_target.get() is None


@pytest.mark.asyncio
async def test_file_tool_rejects_missing_active_cam_document() -> None:
    """Do not open a review whose destination document cannot be bound."""
    from freecad_mcp.tools._registration import file_tool

    mcp = Tools()
    bridge = SimpleNamespace(get_active_document=AsyncMock(return_value=None))
    called = False

    async def get_bridge():
        return bridge

    @file_tool(mcp, get_bridge=get_bridge)
    async def cam_post_process(output_file: str, doc_name: str | None = None):
        nonlocal called
        called = True
        return output_file, doc_name

    with pytest.raises(ValueError, match="No active document"):
        await mcp.functions["cam_post_process"]("/tmp/test.nc")
    assert not called
    assert file_review_target.get() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("has_previous", [False, True])
async def test_draft_text_binds_document_before_font_review(fail, has_previous) -> None:
    """Text is applied to the selected document even if active selection changes."""
    from freecad_mcp.tools.draft import register_draft_tools

    mcp = Tools()
    seen = []

    async def execute(code: str):
        seen.append((code, file_review_target.get()))
        return ExecutionResult(
            success=True,
            result={"name": "Text"},
            stdout="",
            stderr="",
            execution_time_ms=1,
        )

    bridge = SimpleNamespace(
        get_active_document=AsyncMock(return_value=SimpleNamespace(name="Original")),
        execute_python=execute,
    )

    async def get_bridge():
        return bridge

    register_draft_tools(mcp, get_bridge)
    await mcp.functions["draft_text_on_surface"](
        text="test", target_face="Face1", target_object="Box", font_path="/tmp/font.ttf"
    )
    assert "FreeCAD.getDocument('Original')" in seen[0][0]
    assert seen[0][1] == ("/tmp/font.ttf", "read", "path")
    import textwrap

    code = seen[0][0]
    start = code.index("    previous_doc = FreeCAD.ActiveDocument")
    end = code.index("    if shape_string is None:", start)
    fragment = textwrap.dedent(code[start:end])
    previous = SimpleNamespace(Name="Other") if has_previous else None
    selected = SimpleNamespace(Name="Original")
    active = {"value": previous}
    freecad = SimpleNamespace(ActiveDocument=previous)

    def set_active(name):
        active["value"] = selected if name == "Original" else previous
        if name:
            freecad.ActiveDocument = active["value"]

    def make_shapestring(*_args):
        assert active["value"] is selected
        if fail:
            raise ValueError("font failed")
        return object()

    context = {
        "FreeCAD": freecad,
        "Draft": SimpleNamespace(make_shapestring=make_shapestring),
        "doc": selected,
        "text": "test",
        "font_path": "/tmp/font.ttf",
        "size": 10,
    }
    freecad.setActiveDocument = set_active
    if fail:
        with pytest.raises(ValueError, match="font failed"):
            exec(fragment, context)  # noqa: S102 - exercise the generated code
    else:
        exec(fragment, context)  # noqa: S102 - exercise the generated code
    assert active["value"] is previous
    assert freecad.ActiveDocument is previous


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments", "action"),
    [
        ("export_step", {"file_path": "/tmp/model.step"}, "write"),
        (
            "spreadsheet_import_csv",
            {"spreadsheet_name": "Sheet", "file_path": "/tmp/data.csv"},
            "read",
        ),
        (
            "spreadsheet_export_csv",
            {"spreadsheet_name": "Sheet", "file_path": "/tmp/data.csv"},
            "write",
        ),
    ],
)
async def test_document_file_tools_bind_active_document(
    tool_name, arguments, action
) -> None:
    """File review cannot redirect export or spreadsheet work to another document."""
    from freecad_mcp.tools.export import register_export_tools
    from freecad_mcp.tools.spreadsheet import register_spreadsheet_tools

    mcp = Tools()
    seen = []

    async def execute(code: str):
        seen.append((code, file_review_target.get()))
        return ExecutionResult(
            success=True,
            result={"success": True},
            stdout="",
            stderr="",
            execution_time_ms=1,
        )

    bridge = SimpleNamespace(
        get_active_document=AsyncMock(return_value=SimpleNamespace(name="Original")),
        execute_python=execute,
    )

    async def get_bridge():
        return bridge

    register_export_tools(mcp, get_bridge)
    register_spreadsheet_tools(mcp, get_bridge)
    await mcp.functions[tool_name](**arguments)
    assert "FreeCAD.getDocument('Original')" in seen[0][0]
    assert seen[0][1] == (arguments["file_path"], action, "path")


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [None, "Original"])
@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("import_step", {"file_path": "/tmp/model.step"}),
        ("import_stl", {"file_path": "/tmp/model.stl"}),
        ("insert_part_from_library", {"part_path": "/tmp/model.step"}),
        ("draft_shapestring", {"text": "O", "font_path": "/tmp/font.ttf"}),
    ],
)
async def test_import_binds_existing_or_new_document(
    tool_name, arguments, active
) -> None:
    """An active-document switch during review cannot redirect an import."""
    from freecad_mcp.bridge.file_review import file_review_new_document
    from freecad_mcp.tools.draft import register_draft_tools
    from freecad_mcp.tools.export import register_export_tools
    from freecad_mcp.tools.view import register_view_tools

    mcp = Tools()
    seen = []

    async def execute(code: str):
        seen.append((code, file_review_target.get(), file_review_new_document.get()))
        return ExecutionResult(
            success=True,
            result={"success": True},
            stdout="",
            stderr="",
            execution_time_ms=1,
        )

    doc = SimpleNamespace(name=active) if active is not None else None
    bridge = SimpleNamespace(
        get_active_document=AsyncMock(return_value=doc), execute_python=execute
    )

    async def get_bridge():
        return bridge

    register_export_tools(mcp, get_bridge)
    register_view_tools(mcp, get_bridge)
    register_draft_tools(mcp, get_bridge)
    await mcp.functions[tool_name](**arguments)
    code, target, new_document = seen[0]
    path = (
        arguments.get("file_path")
        or arguments.get("part_path")
        or arguments["font_path"]
    )
    assert target == (path, "read", "path")
    assert new_document is (active is None)
    if active is None:
        assert "doc = None if True else" in code
    else:
        assert "FreeCAD.getDocument('Original')" in code
    bound_doc = object()
    later_active = object()
    freecad = SimpleNamespace(
        ActiveDocument=later_active,
        getDocument=lambda _name: bound_doc,
    )
    assignment = next(line for line in code.splitlines() if line.startswith("doc = "))
    env = {"FreeCAD": freecad}
    exec(assignment, env)  # noqa: S102 - exercise the generated document selection
    assert env["doc"] is (None if active is None else bound_doc)
    assert file_review_new_document.get() is False
    assert file_review_target.get() is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,module_name", [("import_step", "Part"), ("import_stl", "Mesh")]
)
async def test_import_without_initial_document_uses_new_document(
    tool_name, module_name, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """A later active document cannot become the destination of an import."""
    import sys
    from types import ModuleType

    from freecad_mcp.tools.export import register_export_tools

    source = tmp_path / "model.step"
    source.write_text("fixture")
    later = SimpleNamespace(Name="Later", Objects=[])
    created = SimpleNamespace(Name="Imported", Objects=[], recompute=lambda: None)
    freecad = SimpleNamespace(ActiveDocument=later, newDocument=lambda _: created)
    module = ModuleType(module_name)
    destinations = []

    def insert(_path, name):
        destinations.append(name)
        created.Objects.append(SimpleNamespace(Name="ImportedObject"))

    module.__dict__["insert"] = insert
    monkeypatch.setitem(sys.modules, module_name, module)
    mcp = Tools()

    async def execute(code):
        namespace = {"FreeCAD": freecad}
        exec(code, namespace)  # noqa: S102 - exercise the generated import
        return ExecutionResult(
            success=True,
            result=namespace["_result_"],
            stdout="",
            stderr="",
            execution_time_ms=1,
        )

    bridge = SimpleNamespace(
        get_active_document=AsyncMock(return_value=None), execute_python=execute
    )

    async def get_bridge():
        return bridge

    register_export_tools(mcp, get_bridge)
    result = await mcp.functions[tool_name](file_path=str(source))
    assert result["document"] == "Imported"
    assert destinations == ["Imported"]
    assert not later.Objects


@pytest.mark.asyncio
@pytest.mark.parametrize("has_later_selection", [False, True])
async def test_new_shapestring_preserves_active_document(
    has_later_selection: bool,
) -> None:
    """Restore a later selection or leave the new document active."""
    import textwrap

    from freecad_mcp.tools.draft import register_draft_tools

    mcp = Tools()
    captured = []

    async def execute(code: str):
        captured.append(code)
        return ExecutionResult(
            success=True,
            result={"name": "Text"},
            stdout="",
            stderr="",
            execution_time_ms=1,
        )

    bridge = SimpleNamespace(
        get_active_document=AsyncMock(return_value=None), execute_python=execute
    )

    async def get_bridge():
        return bridge

    register_draft_tools(mcp, get_bridge)
    await mcp.functions["draft_shapestring"](text="O", font_path="/tmp/font.ttf")
    code = captured[0]
    setup_start = code.index("previous_doc = FreeCAD.ActiveDocument")
    setup_end = code.index("# Wrap in transaction", setup_start)
    setup = code[setup_start:setup_end]
    create_start = code.index("    try:\n        FreeCAD.setActiveDocument(doc.Name)")
    create_end = code.index("    if shape_string is None:", create_start)
    create = textwrap.dedent(code[create_start:create_end])
    other = SimpleNamespace(Name="Other")
    created = SimpleNamespace(Name="Created")
    freecad = SimpleNamespace(ActiveDocument=other if has_later_selection else None)

    def new_document(_name):
        freecad.ActiveDocument = created
        return created

    def set_active(name):
        freecad.ActiveDocument = {"Other": other, "Created": created}[name]

    freecad.newDocument = new_document
    freecad.setActiveDocument = set_active
    draft = SimpleNamespace(make_shapestring=lambda *_args: object())
    env = {
        "FreeCAD": freecad,
        "Draft": draft,
        "text": "O",
        "font_path": "/tmp/font.ttf",
        "size": 10,
    }
    exec(setup, env)  # noqa: S102 - exercise generated document selection
    assert env["doc"] is created
    exec(create, env)  # noqa: S102 - exercise generated document restoration
    assert freecad.ActiveDocument is (other if has_later_selection else created)


@pytest.mark.asyncio
@pytest.mark.parametrize("bridge_type", [SocketBridge, XmlRpcBridge, EmbeddedBridge])
async def test_active_document_lookup_propagates_execution_errors(bridge_type) -> None:
    """A failed lookup must not be reported as an absent active document."""
    bridge = bridge_type.__new__(bridge_type)
    bridge.execute_python = AsyncMock(
        return_value=ExecutionResult(
            success=False,
            result=None,
            stdout="",
            stderr="bridge failed",
            execution_time_ms=1,
        )
    )
    with pytest.raises(RuntimeError, match="bridge failed"):
        await bridge.get_active_document()


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit_name", [None, "Model"])
async def test_save_document_reserves_selected_instance_before_review(
    explicit_name: str | None, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The token selected on the host follows the save into file review."""
    from freecad_mcp.bridge.file_review import (
        file_review_document,
        file_review_document_token,
    )

    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=False),
    )
    bridge = SocketBridge()
    selected = {
        "name": "Model",
        "path": str(tmp_path / "existing.FCStd"),
        "token": "unit-token",
    }
    capture = AsyncMock(return_value=selected)
    monkeypatch.setattr(bridge, "capture_review_document", capture)
    observed = []

    async def save(name, path):
        observed.append(
            (name, path, file_review_document.get(), file_review_document_token.get())
        )
        return path

    monkeypatch.setattr(bridge, "save_document", AsyncMock(side_effect=save))
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    target = str(tmp_path / "saved.FCStd")
    await mcp.functions["save_document"](doc_name=explicit_name, path=target)
    capture.assert_awaited_once_with(explicit_name, require_saved_path=False)
    assert observed == [("Model", target, "Model", "unit-token")]
    assert file_review_document.get() is None
    assert file_review_document_token.get() is None


@pytest.mark.asyncio
async def test_unsaved_document_save_can_retry_with_explicit_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """An unsaved path check does not prevent a later explicit save."""
    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=False),
    )
    bridge = SocketBridge()
    capture = AsyncMock(
        side_effect=[
            {"name": "Model", "path": "", "token": ""},
            {"name": "Model", "path": "", "token": "unit-token"},
        ]
    )
    monkeypatch.setattr(bridge, "capture_review_document", capture)
    target = str(tmp_path / "saved.FCStd")
    save = AsyncMock(return_value=target)
    monkeypatch.setattr(bridge, "save_document", save)
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    with pytest.raises(ValueError, match="No saved path"):
        await mcp.functions["save_document"]()
    save.assert_not_awaited()
    assert await mcp.functions["save_document"](path=target) == {
        "success": True,
        "path": target,
    }
    assert capture.await_args_list[0].kwargs["require_saved_path"] is True
    assert capture.await_args_list[1].kwargs["require_saved_path"] is False
    save.assert_awaited_once_with("Model", target)
