"""Tests for spreadsheet tools module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult


class TestSpreadsheetTools:
    """Tests for Spreadsheet workbench tools."""

    @pytest.fixture
    def mock_mcp(self):
        """Create a mock MCP server that captures tool registrations."""
        mcp = MagicMock()
        mcp._registered_tools = {}

        def tool_decorator():
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
        """Register spreadsheet tools and return the registered functions."""
        from freecad_mcp.tools.spreadsheet import register_spreadsheet_tools

        async def get_bridge():
            return mock_bridge

        register_spreadsheet_tools(mock_mcp, get_bridge)
        return mock_mcp._registered_tools

    # =========================================================================
    # spreadsheet_create tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_spreadsheet_create_success(self, register_tools, mock_bridge):
        """spreadsheet_create should create a spreadsheet object."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "Spreadsheet",
                    "label": "Spreadsheet",
                    "type_id": "Spreadsheet::Sheet",
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        spreadsheet_create = register_tools["spreadsheet_create"]
        result = await spreadsheet_create()

        assert result["name"] == "Spreadsheet"
        assert result["type_id"] == "Spreadsheet::Sheet"
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_spreadsheet_create_with_name(self, register_tools, mock_bridge):
        """spreadsheet_create should use provided name."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "Parameters",
                    "label": "Parameters",
                    "type_id": "Spreadsheet::Sheet",
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        spreadsheet_create = register_tools["spreadsheet_create"]
        result = await spreadsheet_create(name="Parameters")

        assert result["name"] == "Parameters"

    @pytest.mark.asyncio
    async def test_spreadsheet_create_failure(self, register_tools, mock_bridge):
        """spreadsheet_create should raise on failure."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=5.0,
                error_type="ValueError",
                error_traceback="Failed to create spreadsheet",
            )
        )

        spreadsheet_create = register_tools["spreadsheet_create"]
        with pytest.raises(ValueError, match="Failed to create spreadsheet"):
            await spreadsheet_create()

    # =========================================================================
    # spreadsheet_set_cell tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_spreadsheet_set_cell_number(self, register_tools, mock_bridge):
        """spreadsheet_set_cell should set numeric values."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "cell": "A1",
                    "value": 100,
                    "computed": 100,
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        set_cell = register_tools["spreadsheet_set_cell"]
        result = await set_cell(spreadsheet_name="Params", cell="A1", value=100)

        assert result["success"] is True
        assert result["cell"] == "A1"
        assert result["value"] == 100

    @pytest.mark.asyncio
    async def test_spreadsheet_set_cell_formula(self, register_tools, mock_bridge):
        """spreadsheet_set_cell should set formula values."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "cell": "A2",
                    "value": "=A1*2",
                    "computed": 200,
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        set_cell = register_tools["spreadsheet_set_cell"]
        result = await set_cell(spreadsheet_name="Params", cell="A2", value="=A1*2")

        assert result["success"] is True
        assert result["value"] == "=A1*2"
        assert result["computed"] == 200

    @pytest.mark.asyncio
    async def test_spreadsheet_set_cell_not_found(self, register_tools, mock_bridge):
        """spreadsheet_set_cell should raise when spreadsheet not found."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=5.0,
                error_type="ValueError",
                error_traceback="Spreadsheet not found: BadName",
            )
        )

        set_cell = register_tools["spreadsheet_set_cell"]
        with pytest.raises(ValueError, match="Spreadsheet not found"):
            await set_cell(spreadsheet_name="BadName", cell="A1", value=100)

    # =========================================================================
    # spreadsheet_get_cell tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_spreadsheet_get_cell_success(self, register_tools, mock_bridge):
        """spreadsheet_get_cell should return cell info."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "cell": "A1",
                    "value": "100",
                    "computed": 100,
                    "alias": "Length",
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        get_cell = register_tools["spreadsheet_get_cell"]
        result = await get_cell(spreadsheet_name="Params", cell="A1")

        assert result["cell"] == "A1"
        assert result["computed"] == 100
        assert result["alias"] == "Length"

    @pytest.mark.asyncio
    async def test_spreadsheet_get_cell_empty(self, register_tools, mock_bridge):
        """spreadsheet_get_cell should handle empty cells."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "cell": "Z99",
                    "value": None,
                    "computed": None,
                    "alias": None,
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        get_cell = register_tools["spreadsheet_get_cell"]
        result = await get_cell(spreadsheet_name="Params", cell="Z99")

        assert result["cell"] == "Z99"
        assert result["computed"] is None
        assert result["alias"] is None

    # =========================================================================
    # spreadsheet_set_alias tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_spreadsheet_set_alias_success(self, register_tools, mock_bridge):
        """spreadsheet_set_alias should set cell alias."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "cell": "A1",
                    "alias": "BoxLength",
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        set_alias = register_tools["spreadsheet_set_alias"]
        result = await set_alias(
            spreadsheet_name="Params", cell="A1", alias="BoxLength"
        )

        assert result["success"] is True
        assert result["alias"] == "BoxLength"

    @pytest.mark.asyncio
    async def test_spreadsheet_set_alias_invalid(self, register_tools, mock_bridge):
        """spreadsheet_set_alias should reject invalid aliases."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=5.0,
                error_type="ValueError",
                error_traceback="Invalid alias: '123bad'. Must be a valid Python identifier.",
            )
        )

        set_alias = register_tools["spreadsheet_set_alias"]
        with pytest.raises(ValueError, match="Invalid alias"):
            await set_alias(spreadsheet_name="Params", cell="A1", alias="123bad")

    # =========================================================================
    # spreadsheet_get_aliases tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_spreadsheet_get_aliases_success(self, register_tools, mock_bridge):
        """spreadsheet_get_aliases should return all aliases."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "spreadsheet": "Params",
                    "aliases": {"Length": "A1", "Width": "A2", "Height": "A3"},
                    "count": 3,
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        get_aliases = register_tools["spreadsheet_get_aliases"]
        result = await get_aliases(spreadsheet_name="Params")

        assert result["count"] == 3
        assert result["aliases"]["Length"] == "A1"
        assert result["aliases"]["Width"] == "A2"

    @pytest.mark.asyncio
    async def test_spreadsheet_get_aliases_empty(self, register_tools, mock_bridge):
        """spreadsheet_get_aliases should handle no aliases."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "spreadsheet": "Params",
                    "aliases": {},
                    "count": 0,
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        get_aliases = register_tools["spreadsheet_get_aliases"]
        result = await get_aliases(spreadsheet_name="Params")

        assert result["count"] == 0
        assert result["aliases"] == {}

    # =========================================================================
    # spreadsheet_clear_cell tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_spreadsheet_clear_cell_success(self, register_tools, mock_bridge):
        """spreadsheet_clear_cell should clear cell content and alias."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "cell": "A1",
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        clear_cell = register_tools["spreadsheet_clear_cell"]
        result = await clear_cell(spreadsheet_name="Params", cell="A1")

        assert result["success"] is True
        assert result["cell"] == "A1"

    # =========================================================================
    # spreadsheet_bind_property tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_spreadsheet_bind_property_success(self, register_tools, mock_bridge):
        """spreadsheet_bind_property should bind object property to cell."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "expression": "Params.BoxLength",
                    "target_object": "Box",
                    "target_property": "Length",
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        bind_property = register_tools["spreadsheet_bind_property"]
        result = await bind_property(
            spreadsheet_name="Params",
            alias="BoxLength",
            target_object="Box",
            target_property="Length",
        )

        assert result["success"] is True
        assert result["expression"] == "Params.BoxLength"
        assert result["target_object"] == "Box"

    @pytest.mark.asyncio
    async def test_spreadsheet_bind_property_alias_not_found(
        self, register_tools, mock_bridge
    ):
        """spreadsheet_bind_property should fail if alias doesn't exist."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=5.0,
                error_type="ValueError",
                error_traceback="Alias not found: 'NoSuchAlias'",
            )
        )

        bind_property = register_tools["spreadsheet_bind_property"]
        with pytest.raises(ValueError, match="Alias not found"):
            await bind_property(
                spreadsheet_name="Params",
                alias="NoSuchAlias",
                target_object="Box",
                target_property="Length",
            )

    # =========================================================================
    # spreadsheet_get_cell_range tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_spreadsheet_get_cell_range_success(
        self, register_tools, mock_bridge
    ):
        """spreadsheet_get_cell_range should return range values."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "spreadsheet": "Params",
                    "start": "A1",
                    "end": "B2",
                    "cells": {"A1": 10, "A2": 20, "B1": 30, "B2": 40},
                },
                stdout="",
                stderr="",
                execution_time_ms=10.0,
            )
        )

        get_range = register_tools["spreadsheet_get_cell_range"]
        result = await get_range(
            spreadsheet_name="Params", start_cell="A1", end_cell="B2"
        )

        assert result["start"] == "A1"
        assert result["end"] == "B2"
        assert result["cells"]["A1"] == 10
        assert result["cells"]["B2"] == 40

    # =========================================================================
    # spreadsheet_import_csv tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_spreadsheet_import_csv_success(self, register_tools, mock_bridge):
        """spreadsheet_import_csv should import CSV data."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "rows_imported": 10,
                    "cols_imported": 3,
                    "start_cell": "A1",
                },
                stdout="",
                stderr="",
                execution_time_ms=50.0,
            )
        )

        import_csv = register_tools["spreadsheet_import_csv"]
        result = await import_csv(spreadsheet_name="Data", file_path="/tmp/data.csv")

        assert result["success"] is True
        assert result["rows_imported"] == 10
        assert result["cols_imported"] == 3

    @pytest.mark.asyncio
    async def test_spreadsheet_import_csv_with_options(
        self, register_tools, mock_bridge
    ):
        """spreadsheet_import_csv should respect delimiter and start cell."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "rows_imported": 5,
                    "cols_imported": 2,
                    "start_cell": "C3",
                },
                stdout="",
                stderr="",
                execution_time_ms=30.0,
            )
        )

        import_csv = register_tools["spreadsheet_import_csv"]
        result = await import_csv(
            spreadsheet_name="Data",
            file_path="/tmp/data.tsv",
            delimiter="\t",
            start_cell="C3",
        )

        assert result["success"] is True
        assert result["start_cell"] == "C3"

    # =========================================================================
    # spreadsheet_export_csv tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_spreadsheet_export_csv_success(self, register_tools, mock_bridge):
        """spreadsheet_export_csv should export to CSV."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "file_path": "/tmp/output.csv",
                    "rows_exported": 15,
                },
                stdout="",
                stderr="",
                execution_time_ms=40.0,
            )
        )

        export_csv = register_tools["spreadsheet_export_csv"]
        result = await export_csv(spreadsheet_name="Data", file_path="/tmp/output.csv")

        assert result["success"] is True
        assert result["file_path"] == "/tmp/output.csv"
        assert result["rows_exported"] == 15

    @pytest.mark.asyncio
    async def test_spreadsheet_export_csv_empty(self, register_tools, mock_bridge):
        """spreadsheet_export_csv should handle empty spreadsheet."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": True,
                    "file_path": "/tmp/empty.csv",
                    "rows_exported": 0,
                },
                stdout="",
                stderr="",
                execution_time_ms=20.0,
            )
        )

        export_csv = register_tools["spreadsheet_export_csv"]
        result = await export_csv(spreadsheet_name="Empty", file_path="/tmp/empty.csv")

        assert result["success"] is True
        assert result["rows_exported"] == 0

    # =========================================================================
    # Test that all expected tools are registered
    # =========================================================================

    def test_all_spreadsheet_tools_registered(self, register_tools):
        """All spreadsheet tools should be registered."""
        expected_tools = [
            "spreadsheet_create",
            "spreadsheet_set_cell",
            "spreadsheet_get_cell",
            "spreadsheet_set_alias",
            "spreadsheet_get_aliases",
            "spreadsheet_clear_cell",
            "spreadsheet_bind_property",
            "spreadsheet_get_cell_range",
            "spreadsheet_import_csv",
            "spreadsheet_export_csv",
        ]

        for tool_name in expected_tools:
            assert tool_name in register_tools, f"Tool {tool_name} not registered"
