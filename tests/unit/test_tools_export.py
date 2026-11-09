"""Tests for export/import tools module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult


class TestExportTools:
    """Tests for export/import tools."""

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
        """Register export tools and return the registered functions."""
        from freecad_mcp.tools.export import register_export_tools

        async def get_bridge():
            return mock_bridge

        register_export_tools(mock_mcp, get_bridge)
        return mock_mcp._registered_tools

    @pytest.mark.asyncio
    async def test_export_step(self, register_tools, mock_bridge):
        """export_step should export to STEP format via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "path": "/tmp/output.step",
                    "object_count": 2,
                },
                stdout="",
                stderr="",
                execution_time_ms=50.0,
            )
        )

        export_step = register_tools["export_step"]
        result = await export_step(
            file_path="/tmp/output.step", object_names=["Box", "Cylinder"]
        )

        assert result["success"] is True
        assert result["path"] == "/tmp/output.step"
        assert result["object_count"] == 2
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_step_all_visible(self, register_tools, mock_bridge):
        """export_step should export all visible objects when no names given."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "path": "/tmp/output.step",
                    "object_count": 5,
                },
                stdout="",
                stderr="",
                execution_time_ms=75.0,
            )
        )

        export_step = register_tools["export_step"]
        result = await export_step(file_path="/tmp/output.step")

        assert result["success"] is True
        assert result["object_count"] == 5

    @pytest.mark.asyncio
    async def test_export_stl(self, register_tools, mock_bridge):
        """export_stl should export to STL format via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "path": "/tmp/output.stl",
                    "object_count": 1,
                },
                stdout="",
                stderr="",
                execution_time_ms=30.0,
            )
        )

        export_stl = register_tools["export_stl"]
        result = await export_stl(file_path="/tmp/output.stl", object_names=["Box"])

        assert result["success"] is True
        assert result["path"] == "/tmp/output.stl"
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_stl_with_tolerance(self, register_tools, mock_bridge):
        """export_stl should accept mesh tolerance parameter."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "path": "/tmp/fine.stl",
                    "object_count": 1,
                },
                stdout="",
                stderr="",
                execution_time_ms=45.0,
            )
        )

        export_stl = register_tools["export_stl"]
        result = await export_stl(file_path="/tmp/fine.stl", mesh_tolerance=0.01)

        assert result["success"] is True
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_3mf(self, register_tools, mock_bridge):
        """export_3mf should export to 3MF format via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "path": "/tmp/output.3mf",
                    "object_count": 1,
                },
                stdout="",
                stderr="",
                execution_time_ms=40.0,
            )
        )

        export_3mf = register_tools["export_3mf"]
        result = await export_3mf(file_path="/tmp/output.3mf")

        assert result["success"] is True
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_obj(self, register_tools, mock_bridge):
        """export_obj should export to OBJ format via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "path": "/tmp/output.obj",
                    "object_count": 1,
                },
                stdout="",
                stderr="",
                execution_time_ms=35.0,
            )
        )

        export_obj = register_tools["export_obj"]
        result = await export_obj(file_path="/tmp/output.obj")

        assert result["success"] is True
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_iges(self, register_tools, mock_bridge):
        """export_iges should export to IGES format via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "path": "/tmp/output.iges",
                    "object_count": 1,
                },
                stdout="",
                stderr="",
                execution_time_ms=55.0,
            )
        )

        export_iges = register_tools["export_iges"]
        result = await export_iges(file_path="/tmp/output.iges")

        assert result["success"] is True
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_step(self, register_tools, mock_bridge):
        """import_step should import STEP files via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "document": "Imported",
                    "objects": ["Part", "Assembly"],
                },
                stdout="",
                stderr="",
                execution_time_ms=100.0,
            )
        )

        import_step = register_tools["import_step"]
        result = await import_step(file_path="/tmp/input.step")

        assert result["success"] is True
        assert result["document"] == "Imported"
        assert len(result["objects"]) == 2
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_stl(self, register_tools, mock_bridge):
        """import_stl should import STL files via execute_python."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "document": "Mesh",
                    "object": "Mesh001",
                },
                stdout="",
                stderr="",
                execution_time_ms=80.0,
            )
        )

        import_stl = register_tools["import_stl"]
        result = await import_stl(file_path="/tmp/input.stl")

        assert result["success"] is True
        assert result["object"] == "Mesh001"
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_step_failure(self, register_tools, mock_bridge):
        """export_step should raise ValueError on failure."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="FileNotFoundError: Directory does not exist",
                execution_time_ms=5.0,
                error_type="FileNotFoundError",
                error_traceback="Traceback: FileNotFoundError: Directory does not exist",
            )
        )

        export_step = register_tools["export_step"]
        with pytest.raises(ValueError) as exc_info:
            await export_step(file_path="/nonexistent/output.step")

        assert "FileNotFoundError" in str(exc_info.value) or "Traceback" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_import_step_into_document(self, register_tools, mock_bridge):
        """import_step should import into specified document."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "document": "MyDoc",
                    "objects": ["ImportedPart"],
                },
                stdout="",
                stderr="",
                execution_time_ms=90.0,
            )
        )

        import_step = register_tools["import_step"]
        result = await import_step(file_path="/tmp/part.step", doc_name="MyDoc")

        assert result["success"] is True
        assert result["document"] == "MyDoc"
