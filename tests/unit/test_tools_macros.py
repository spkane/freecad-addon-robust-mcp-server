"""Tests for macro tools module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult, MacroInfo


class TestMacroTools:
    """Tests for macro management tools."""

    @pytest.fixture
    def mock_mcp(self):
        """Create a mock MCP server that captures tool registrations."""
        mcp = MagicMock()
        mcp._registered_tools = {}

        def tool_decorator(**_kwargs):
            def wrapper(func):
                mcp._registered_tools[func.__name__] = func
                return func

            return wrapper

        mcp.tool = tool_decorator
        return mcp

    @pytest.fixture
    def mock_bridge(self):
        """Create a mock FreeCAD bridge."""
        return AsyncMock()

    @pytest.fixture
    def register_tools(self, mock_mcp, mock_bridge):
        """Register macro tools and return the registered functions."""
        from freecad_mcp.tools.macros import register_macro_tools

        async def get_bridge():
            return mock_bridge

        register_macro_tools(mock_mcp, get_bridge, allow_unsafe_code=True)
        return mock_mcp._registered_tools

    @pytest.mark.asyncio
    async def test_list_macros_empty(self, register_tools, mock_bridge):
        """list_macros should return empty list when no macros."""
        mock_bridge.get_macros = AsyncMock(return_value=[])

        list_macros = register_tools["list_macros"]
        result = await list_macros()

        assert result == []
        mock_bridge.get_macros.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_macros_with_macros(self, register_tools, mock_bridge):
        """list_macros should return macro info."""
        mock_macros = [
            MacroInfo(
                name="ExportSTL",
                path="/home/user/.FreeCAD/Macro/ExportSTL.FCMacro",
                description="Export objects to STL",
                is_system=False,
            ),
            MacroInfo(
                name="SystemMacro",
                path="/usr/share/freecad/Macro/SystemMacro.FCMacro",
                description="System macro",
                is_system=True,
            ),
        ]
        mock_bridge.get_macros = AsyncMock(return_value=mock_macros)

        list_macros = register_tools["list_macros"]
        result = await list_macros()

        assert len(result) == 2
        assert result[0]["name"] == "ExportSTL"
        assert result[0]["is_system"] is False
        assert result[1]["name"] == "SystemMacro"
        assert result[1]["is_system"] is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("args", [None, {"output_dir": "/tmp"}])
    async def test_run_macro_uses_only_reviewed_execution(
        self, register_tools, mock_bridge, args
    ):
        """Unavailable review never falls back to the unrestricted method."""
        mock_bridge.execute_reviewed_macro.return_value = ExecutionResult(
            success=False,
            result=None,
            stdout="",
            stderr="Review unavailable",
            execution_time_ms=0,
            error_type="ReviewUnavailable",
        )
        result = await register_tools["run_macro"]("ExportSTL", args)
        assert result["success"] is False
        assert result["error_type"] == "ReviewUnavailable"
        mock_bridge.execute_reviewed_macro.assert_awaited_once_with("ExportSTL", args)
        mock_bridge.run_macro.assert_not_awaited()
        mock_bridge.execute_python.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_macro(self, register_tools, mock_bridge):
        """create_macro should create a new macro file via bridge.create_macro."""
        # create_macro calls bridge.create_macro which returns MacroInfo
        mock_macro = MacroInfo(
            name="MyMacro",
            path="/home/user/.FreeCAD/Macro/MyMacro.FCMacro",
            description="My custom macro",
            is_system=False,
        )
        mock_bridge.create_macro = AsyncMock(return_value=mock_macro)

        create_macro = register_tools["create_macro"]
        result = await create_macro(
            name="MyMacro",
            code="FreeCAD.Console.PrintMessage('Hello')",
            description="My custom macro",
        )

        assert result["name"] == "MyMacro"
        assert result["path"] == "/home/user/.FreeCAD/Macro/MyMacro.FCMacro"
        assert result["description"] == "My custom macro"
        mock_bridge.create_macro.assert_called_once_with(
            "MyMacro", "FreeCAD.Console.PrintMessage('Hello')", "My custom macro"
        )

    @pytest.mark.asyncio
    async def test_read_macro(self, register_tools, mock_bridge):
        """read_macro should return macro source code via execute_python."""
        # read_macro uses execute_python to read file contents
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "MyMacro",
                    "code": "import FreeCAD\nFreeCAD.Console.PrintMessage('Hello')",
                    "path": "/home/user/.FreeCAD/Macro/MyMacro.FCMacro",
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        read_macro = register_tools["read_macro"]
        result = await read_macro(macro_name="MyMacro")

        assert result["name"] == "MyMacro"
        assert "FreeCAD" in result["code"]
        assert result["path"] == "/home/user/.FreeCAD/Macro/MyMacro.FCMacro"
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_macro_not_found(self, register_tools, mock_bridge):
        """read_macro should raise error when macro not found."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="FileNotFoundError: Macro not found: NonExistent",
                execution_time_ms=5.0,
                error_type="FileNotFoundError",
                error_traceback="Traceback...\nFileNotFoundError: Macro not found: NonExistent",
            )
        )

        read_macro = register_tools["read_macro"]
        with pytest.raises(ValueError) as exc_info:
            await read_macro(macro_name="NonExistent")

        assert "NonExistent" in str(exc_info.value) or "Traceback" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_delete_macro(self, register_tools, mock_bridge):
        """delete_macro should delete a user macro via execute_python."""
        # delete_macro uses execute_python to delete file
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "path": "/home/user/.FreeCAD/Macro/OldMacro.FCMacro",
                },
                stdout="",
                stderr="",
                execution_time_ms=8.0,
            )
        )

        delete_macro = register_tools["delete_macro"]
        result = await delete_macro(macro_name="OldMacro")

        assert result["success"] is True
        assert result["path"] == "/home/user/.FreeCAD/Macro/OldMacro.FCMacro"
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_macro_not_found(self, register_tools, mock_bridge):
        """delete_macro should raise error when macro not found."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="FileNotFoundError: User macro not found: NonExistent",
                execution_time_ms=5.0,
                error_type="FileNotFoundError",
                error_traceback="Traceback...\nFileNotFoundError: User macro not found: NonExistent",
            )
        )

        delete_macro = register_tools["delete_macro"]
        with pytest.raises(ValueError) as exc_info:
            await delete_macro(macro_name="NonExistent")

        assert "NonExistent" in str(exc_info.value) or "Traceback" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_create_macro_from_template_basic(self, register_tools, mock_bridge):
        """create_macro_from_template should create from basic template."""
        # Uses bridge.create_macro with template code
        mock_macro = MacroInfo(
            name="NewMacro",
            path="/home/user/.FreeCAD/Macro/NewMacro.FCMacro",
            description="",
            is_system=False,
        )
        mock_bridge.create_macro = AsyncMock(return_value=mock_macro)

        create_from_template = register_tools["create_macro_from_template"]
        result = await create_from_template(name="NewMacro", template="basic")

        assert result["name"] == "NewMacro"
        assert result["template"] == "basic"
        mock_bridge.create_macro.assert_called_once()
        # Verify basic template code was used
        call_args = mock_bridge.create_macro.call_args
        code_arg = call_args[0][1]  # Second positional arg is code
        assert "FreeCAD.ActiveDocument" in code_arg

    @pytest.mark.asyncio
    async def test_create_macro_from_template_part(self, register_tools, mock_bridge):
        """create_macro_from_template should create from part template."""
        mock_macro = MacroInfo(
            name="PartMacro",
            path="/home/user/.FreeCAD/Macro/PartMacro.FCMacro",
            description="Part operations",
            is_system=False,
        )
        mock_bridge.create_macro = AsyncMock(return_value=mock_macro)

        create_from_template = register_tools["create_macro_from_template"]
        result = await create_from_template(
            name="PartMacro", template="part", description="Part operations"
        )

        assert result["name"] == "PartMacro"
        assert result["template"] == "part"
        # Verify part template code was used
        call_args = mock_bridge.create_macro.call_args
        code_arg = call_args[0][1]
        assert "import Part" in code_arg

    @pytest.mark.asyncio
    async def test_create_macro_from_template_sketch(self, register_tools, mock_bridge):
        """create_macro_from_template should create from sketch template."""
        mock_macro = MacroInfo(
            name="SketchMacro",
            path="/home/user/.FreeCAD/Macro/SketchMacro.FCMacro",
            description="",
            is_system=False,
        )
        mock_bridge.create_macro = AsyncMock(return_value=mock_macro)

        create_from_template = register_tools["create_macro_from_template"]
        result = await create_from_template(name="SketchMacro", template="sketch")

        assert result["name"] == "SketchMacro"
        assert result["template"] == "sketch"
        # Verify sketch template code was used
        call_args = mock_bridge.create_macro.call_args
        code_arg = call_args[0][1]
        assert "Sketcher" in code_arg

    @pytest.mark.asyncio
    async def test_create_macro_from_template_gui(self, register_tools, mock_bridge):
        """create_macro_from_template should create from gui template."""
        mock_macro = MacroInfo(
            name="GuiMacro",
            path="/home/user/.FreeCAD/Macro/GuiMacro.FCMacro",
            description="",
            is_system=False,
        )
        mock_bridge.create_macro = AsyncMock(return_value=mock_macro)

        create_from_template = register_tools["create_macro_from_template"]
        result = await create_from_template(name="GuiMacro", template="gui")

        assert result["name"] == "GuiMacro"
        assert result["template"] == "gui"
        # Verify gui template code was used
        call_args = mock_bridge.create_macro.call_args
        code_arg = call_args[0][1]
        assert "freecad_mcp_bridge.qt_compat" in code_arg
        assert 'load_qt_modules("QtWidgets")' in code_arg

    @pytest.mark.asyncio
    async def test_create_macro_from_template_selection(
        self, register_tools, mock_bridge
    ):
        """create_macro_from_template should create from selection template."""
        mock_macro = MacroInfo(
            name="SelectionMacro",
            path="/home/user/.FreeCAD/Macro/SelectionMacro.FCMacro",
            description="",
            is_system=False,
        )
        mock_bridge.create_macro = AsyncMock(return_value=mock_macro)

        create_from_template = register_tools["create_macro_from_template"]
        result = await create_from_template(name="SelectionMacro", template="selection")

        assert result["name"] == "SelectionMacro"
        assert result["template"] == "selection"
        # Verify selection template code was used
        call_args = mock_bridge.create_macro.call_args
        code_arg = call_args[0][1]
        assert "Selection" in code_arg

    @pytest.mark.asyncio
    async def test_create_macro_from_template_invalid(
        self, register_tools, mock_bridge
    ):
        """create_macro_from_template should raise error for invalid template."""
        create_from_template = register_tools["create_macro_from_template"]

        with pytest.raises(ValueError) as exc_info:
            await create_from_template(name="BadMacro", template="invalid_template")

        assert "Unknown template" in str(exc_info.value)
        assert "invalid_template" in str(exc_info.value)


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        "../outside",
        "sub/file",
        r"sub\\file",
        r"C:\\outside",
        "C:outside",
        "bad\x00name",
        "bad\nname",
        "bad\rname",
    ],
)
@pytest.mark.parametrize(
    ("tool_name", "argument"),
    [
        ("read_macro", "macro_name"),
        ("delete_macro", "macro_name"),
        ("run_macro", "macro_name"),
        ("create_macro", "name"),
        ("create_macro_from_template", "name"),
    ],
)
@pytest.mark.asyncio
async def test_macro_tools_reject_paths_before_bridge_dispatch(
    name, tool_name, argument
):
    """Macro names cannot escape the macro directory through path components."""
    from freecad_mcp.tools.macros import register_macro_tools

    registered = {}
    mcp = MagicMock()

    def tool(**_kwargs):
        def register(func):
            registered[func.__name__] = func
            return func

        return register

    mcp.tool = tool
    get_bridge = AsyncMock()
    register_macro_tools(mcp, get_bridge, allow_unsafe_code=True)
    args = {argument: name}
    if tool_name == "create_macro":
        args["code"] = "pass"
    with pytest.raises(ValueError, match="single file name"):
        await registered[tool_name](**args)
    get_bridge.assert_not_awaited()
