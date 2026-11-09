"""Tests for view and GUI tools module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult, ScreenshotResult, WorkbenchInfo


class TestViewTools:
    """Tests for view and GUI tools."""

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
        """Register view tools and return the registered functions."""
        from freecad_mcp.tools.view import register_view_tools

        async def get_bridge():
            return mock_bridge

        register_view_tools(mock_mcp, get_bridge)
        return mock_mcp._registered_tools

    @pytest.mark.asyncio
    async def test_get_screenshot_success(self, register_tools, mock_bridge):
        """get_screenshot should return base64 image data."""
        # get_screenshot calls bridge.get_screenshot which returns ScreenshotResult
        mock_bridge.get_screenshot = AsyncMock(
            return_value=ScreenshotResult(
                success=True,
                data="iVBORw0KGgo...",  # Base64 PNG data
                format="png",
                width=800,
                height=600,
                error=None,
            )
        )

        get_screenshot = register_tools["get_screenshot"]
        result = await get_screenshot(view_angle="Isometric")

        assert result["success"] is True
        assert "data" in result
        assert result["format"] == "png"
        mock_bridge.get_screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_screenshot_custom_size(self, register_tools, mock_bridge):
        """get_screenshot should accept width and height parameters."""
        mock_bridge.get_screenshot = AsyncMock(
            return_value=ScreenshotResult(
                success=True,
                data="...",
                format="png",
                width=1920,
                height=1080,
                error=None,
            )
        )

        get_screenshot = register_tools["get_screenshot"]
        result = await get_screenshot(width=1920, height=1080)

        assert result["width"] == 1920
        assert result["height"] == 1080

    @pytest.mark.asyncio
    async def test_get_screenshot_headless_error(self, register_tools, mock_bridge):
        """get_screenshot should return error in headless mode."""
        mock_bridge.get_screenshot = AsyncMock(
            return_value=ScreenshotResult(
                success=False,
                data=None,
                format="png",
                width=0,
                height=0,
                error="GUI not available - screenshot cannot be captured in headless mode",
            )
        )

        get_screenshot = register_tools["get_screenshot"]
        result = await get_screenshot()

        assert result["success"] is False
        assert "headless" in result["error"]

    @pytest.mark.asyncio
    async def test_get_screenshot_invalid_view_angle(self, register_tools, mock_bridge):
        """get_screenshot should return error for invalid view angle."""
        get_screenshot = register_tools["get_screenshot"]
        result = await get_screenshot(view_angle="InvalidAngle")

        assert result["success"] is False
        assert "Invalid view_angle" in result["error"]

    @pytest.mark.asyncio
    async def test_set_view_angle(self, register_tools, mock_bridge):
        """set_view_angle should set the camera view via bridge.set_view."""
        mock_bridge.set_view = AsyncMock(return_value=None)

        set_view_angle = register_tools["set_view_angle"]
        result = await set_view_angle(view_angle="Front")

        assert result["success"] is True
        mock_bridge.set_view.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_view_angle_invalid(self, register_tools, mock_bridge):
        """set_view_angle should return error for invalid view angle."""
        set_view_angle = register_tools["set_view_angle"]
        result = await set_view_angle(view_angle="InvalidAngle")

        assert result["success"] is False
        assert "Invalid view_angle" in result["error"]

    @pytest.mark.asyncio
    async def test_fit_all(self, register_tools, mock_bridge):
        """fit_all should zoom to fit all objects via bridge.set_view."""
        mock_bridge.set_view = AsyncMock(return_value=None)

        fit_all = register_tools["fit_all"]
        result = await fit_all()

        assert result["success"] is True
        mock_bridge.set_view.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_object_visibility(self, register_tools, mock_bridge):
        """set_object_visibility should show/hide objects via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={"success": True, "visible": False},
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        set_visibility = register_tools["set_object_visibility"]
        result = await set_visibility(object_name="Box", visible=False)

        assert result["success"] is True
        assert result["visible"] is False
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_object_visibility_headless(self, register_tools, mock_bridge):
        """set_object_visibility should return error in headless mode."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": False,
                    "error": "GUI not available - visibility cannot be set in headless mode",
                },
                stdout="",
                stderr="",
                execution_time_ms=5.0,
            )
        )

        set_visibility = register_tools["set_object_visibility"]
        result = await set_visibility(object_name="Box", visible=True)

        assert result["success"] is False
        assert "headless" in result["error"]

    @pytest.mark.asyncio
    async def test_set_display_mode(self, register_tools, mock_bridge):
        """set_display_mode should change display mode via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={"success": True, "mode": "Wireframe"},
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        set_mode = register_tools["set_display_mode"]
        result = await set_mode(object_name="Box", mode="Wireframe")

        assert result["success"] is True
        assert result["mode"] == "Wireframe"
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_object_color(self, register_tools, mock_bridge):
        """set_object_color should change object color via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={"success": True, "color": [1.0, 0.0, 0.0]},
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        set_color = register_tools["set_object_color"]
        result = await set_color(object_name="Box", color=[1.0, 0.0, 0.0])

        assert result["success"] is True
        assert result["color"] == [1.0, 0.0, 0.0]  # Red
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_object_color_invalid_color(self, register_tools, mock_bridge):
        """set_object_color should validate color array length."""
        set_color = register_tools["set_object_color"]
        result = await set_color(object_name="Box", color=[1.0, 0.0])  # Missing blue

        assert result["success"] is False
        assert "must be [r, g, b]" in result["error"]

    @pytest.mark.asyncio
    async def test_list_workbenches(self, register_tools, mock_bridge):
        """list_workbenches should return available workbenches."""
        mock_workbenches = [
            WorkbenchInfo(
                name="PartDesignWorkbench",
                label="Part Design",
                icon="",
                is_active=True,
            ),
            WorkbenchInfo(
                name="SketcherWorkbench",
                label="Sketcher",
                icon="",
                is_active=False,
            ),
        ]
        mock_bridge.get_workbenches = AsyncMock(return_value=mock_workbenches)

        list_workbenches = register_tools["list_workbenches"]
        result = await list_workbenches()

        assert len(result) == 2
        assert result[0]["name"] == "PartDesignWorkbench"
        assert result[0]["is_active"] is True

    @pytest.mark.asyncio
    async def test_activate_workbench(self, register_tools, mock_bridge):
        """activate_workbench should switch to a workbench."""
        mock_bridge.activate_workbench = AsyncMock(return_value=None)

        activate = register_tools["activate_workbench"]
        result = await activate(workbench_name="SketcherWorkbench")

        assert result["success"] is True
        mock_bridge.activate_workbench.assert_called_once_with("SketcherWorkbench")

    @pytest.mark.asyncio
    async def test_zoom_in(self, register_tools, mock_bridge):
        """zoom_in should increase zoom level via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={"success": True},
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        zoom_in = register_tools["zoom_in"]
        result = await zoom_in(factor=2.0)

        assert result["success"] is True
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_zoom_out(self, register_tools, mock_bridge):
        """zoom_out should decrease zoom level via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={"success": True},
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        zoom_out = register_tools["zoom_out"]
        result = await zoom_out(factor=2.0)

        assert result["success"] is True
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_camera_position(self, register_tools, mock_bridge):
        """set_camera_position should set camera location via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={"success": True},
                stdout="",
                stderr="",
                execution_time_ms=15.0,
            )
        )

        set_camera = register_tools["set_camera_position"]
        result = await set_camera(
            position=[100.0, 100.0, 100.0], look_at=[0.0, 0.0, 0.0]
        )

        assert result["success"] is True
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_undo(self, register_tools, mock_bridge):
        """undo should undo the last operation via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={"success": True, "can_undo": True},
                stdout="",
                stderr="",
                execution_time_ms=5.0,
            )
        )

        undo = register_tools["undo"]
        result = await undo()

        assert result["success"] is True
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_redo(self, register_tools, mock_bridge):
        """redo should redo an undone operation via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={"success": True, "can_redo": False},
                stdout="",
                stderr="",
                execution_time_ms=5.0,
            )
        )

        redo = register_tools["redo"]
        result = await redo()

        assert result["success"] is True
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_undo_redo_status(self, register_tools, mock_bridge):
        """get_undo_redo_status should return available operations via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "undo_count": 5,
                    "redo_count": 2,
                    "undo_names": ["Create Box", "Edit Box", "Create Fillet"],
                },
                stdout="",
                stderr="",
                execution_time_ms=5.0,
            )
        )

        get_status = register_tools["get_undo_redo_status"]
        result = await get_status()

        assert result["undo_count"] == 5
        assert result["redo_count"] == 2
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_parts_library(self, register_tools, mock_bridge):
        """list_parts_library should return available parts via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result=[
                    {
                        "name": "bolt_m6.FCStd",
                        "path": "/lib/bolt_m6.FCStd",
                        "category": "Fasteners",
                    },
                    {
                        "name": "nut_m6.FCStd",
                        "path": "/lib/nut_m6.FCStd",
                        "category": "Fasteners",
                    },
                ],
                stdout="",
                stderr="",
                execution_time_ms=50.0,
            )
        )

        list_parts = register_tools["list_parts_library"]
        result = await list_parts()

        assert len(result) == 2
        assert result[0]["name"] == "bolt_m6.FCStd"
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_parts_library_empty(self, register_tools, mock_bridge):
        """list_parts_library should return empty list when no parts found."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result=[],
                stdout="",
                stderr="",
                execution_time_ms=30.0,
            )
        )

        list_parts = register_tools["list_parts_library"]
        result = await list_parts()

        assert result == []

    @pytest.mark.asyncio
    async def test_insert_part_from_library(self, register_tools, mock_bridge):
        """insert_part_from_library should insert a part via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "Bolt",
                    "label": "Bolt",
                    "type_id": "Part::Feature",
                },
                stdout="",
                stderr="",
                execution_time_ms=100.0,
            )
        )

        insert_part = register_tools["insert_part_from_library"]
        result = await insert_part(
            part_path="/lib/bolt_m6.FCStd", position=[10.0, 20.0, 0.0]
        )

        assert result["name"] == "Bolt"
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_console_log(self, register_tools, mock_bridge):
        """get_console_log should return console messages."""
        mock_bridge.get_console_output = AsyncMock(
            return_value=[
                "Info: Started",
                "Info: Complete",
                "Warning: Deprecated feature",
            ]
        )

        get_log = register_tools["get_console_log"]
        result = await get_log(lines=50)

        assert len(result["messages"]) == 3
        assert len(result["warnings"]) == 1
        assert len(result["errors"]) == 0
        mock_bridge.get_console_output.assert_called_once_with(50)

    @pytest.mark.asyncio
    async def test_get_console_log_with_errors(self, register_tools, mock_bridge):
        """get_console_log should categorize error messages."""
        mock_bridge.get_console_output = AsyncMock(
            return_value=[
                "Info: Started",
                "Error: Failed to load module",
                "Warning: Deprecated API",
            ]
        )

        get_log = register_tools["get_console_log"]
        result = await get_log()

        assert len(result["messages"]) == 3
        assert len(result["errors"]) == 1
        assert "Failed to load module" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_recompute(self, register_tools, mock_bridge):
        """recompute should force document recomputation via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={"success": True, "touch_count": 3},
                stdout="",
                stderr="",
                execution_time_ms=20.0,
            )
        )

        recompute = register_tools["recompute"]
        result = await recompute()

        assert result["success"] is True
        assert result["touch_count"] == 3
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_recompute_no_document(self, register_tools, mock_bridge):
        """recompute should handle no document gracefully."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": False,
                    "error": "No document found",
                    "touch_count": 0,
                },
                stdout="",
                stderr="",
                execution_time_ms=5.0,
            )
        )

        recompute = register_tools["recompute"]
        result = await recompute()

        assert result["success"] is False
        assert "No document" in result["error"]
