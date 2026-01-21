"""Tests for draft tools module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult


class TestDraftTools:
    """Tests for Draft workbench tools (ShapeString)."""

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
        """Register draft tools and return the registered functions."""
        from freecad_mcp.tools.draft import register_draft_tools

        async def get_bridge():
            return mock_bridge

        register_draft_tools(mock_mcp, get_bridge)
        return mock_mcp._registered_tools

    # =========================================================================
    # draft_shapestring tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_draft_shapestring_success(self, register_tools, mock_bridge):
        """draft_shapestring should create 3D text geometry."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "ShapeString",
                    "label": "ShapeString",
                    "type_id": "Part::Part2DObjectPython",
                    "text": "Hello",
                    "size": 10.0,
                    "font": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                },
                stdout="",
                stderr="",
                execution_time_ms=100.0,
            )
        )

        shapestring = register_tools["draft_shapestring"]
        result = await shapestring(text="Hello", size=10.0)

        assert result["name"] == "ShapeString"
        assert result["text"] == "Hello"
        assert result["size"] == 10.0
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_draft_shapestring_with_font(self, register_tools, mock_bridge):
        """draft_shapestring should use custom font."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "ShapeString",
                    "label": "ShapeString",
                    "type_id": "Part::Part2DObjectPython",
                    "text": "Custom",
                    "size": 15.0,
                    "font": "/Library/Fonts/Arial.ttf",
                },
                stdout="",
                stderr="",
                execution_time_ms=100.0,
            )
        )

        shapestring = register_tools["draft_shapestring"]
        result = await shapestring(
            text="Custom",
            font_path="/Library/Fonts/Arial.ttf",
            size=15.0,
        )

        assert result["font"] == "/Library/Fonts/Arial.ttf"
        assert result["size"] == 15.0

    @pytest.mark.asyncio
    async def test_draft_shapestring_with_position(self, register_tools, mock_bridge):
        """draft_shapestring should use custom position."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "ShapeString",
                    "label": "ShapeString",
                    "type_id": "Part::Part2DObjectPython",
                    "text": "Positioned",
                    "size": 10.0,
                    "font": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                },
                stdout="",
                stderr="",
                execution_time_ms=100.0,
            )
        )

        shapestring = register_tools["draft_shapestring"]
        result = await shapestring(
            text="Positioned",
            position=[10.0, 20.0, 5.0],
        )

        assert result["text"] == "Positioned"

    @pytest.mark.asyncio
    async def test_draft_shapestring_no_font(self, register_tools, mock_bridge):
        """draft_shapestring should fail when no font available."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=50.0,
                error_type="ValueError",
                error_traceback="No font file specified and no default font found.",
            )
        )

        shapestring = register_tools["draft_shapestring"]
        with pytest.raises(ValueError, match="No font file specified"):
            await shapestring(text="NoFont")

    # =========================================================================
    # draft_list_fonts tests
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "fonts_data,expected_count,expected_dirs",
        [
            pytest.param(
                {
                    "fonts": [
                        {
                            "name": "DejaVuSans.ttf",
                            "path": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                            "type": "ttf",
                        },
                        {
                            "name": "Arial.ttf",
                            "path": "/Library/Fonts/Arial.ttf",
                            "type": "ttf",
                        },
                    ],
                    "count": 2,
                    "directories": ["/usr/share/fonts", "/Library/Fonts"],
                },
                2,
                2,
                id="fonts_found",
            ),
            pytest.param(
                {
                    "fonts": [],
                    "count": 0,
                    "directories": [],
                },
                0,
                0,
                id="no_fonts",
            ),
        ],
    )
    async def test_draft_list_fonts(
        self, register_tools, mock_bridge, fonts_data, expected_count, expected_dirs
    ):
        """draft_list_fonts should return available fonts or handle empty case."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result=fonts_data,
                stdout="",
                stderr="",
                execution_time_ms=150.0,
            )
        )

        list_fonts = register_tools["draft_list_fonts"]
        result = await list_fonts()

        assert result["count"] == expected_count
        assert len(result["fonts"]) == expected_count
        assert len(result["directories"]) == expected_dirs
        if expected_count > 0:
            assert result["fonts"][0]["name"] == "DejaVuSans.ttf"

    # =========================================================================
    # draft_shapestring_to_sketch tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_draft_shapestring_to_sketch_success(
        self, register_tools, mock_bridge
    ):
        """draft_shapestring_to_sketch should convert to sketch."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "TextSketch",
                    "label": "TextSketch",
                    "type_id": "Sketcher::SketchObject",
                    "wire_count": 15,
                    "source": "ShapeString",
                },
                stdout="",
                stderr="",
                execution_time_ms=150.0,
            )
        )

        to_sketch = register_tools["draft_shapestring_to_sketch"]
        result = await to_sketch(shapestring_name="ShapeString")

        assert result["name"] == "TextSketch"
        assert result["type_id"] == "Sketcher::SketchObject"
        assert result["wire_count"] == 15
        assert result["source"] == "ShapeString"

    @pytest.mark.asyncio
    async def test_draft_shapestring_to_sketch_with_body(
        self, register_tools, mock_bridge
    ):
        """draft_shapestring_to_sketch should attach to body."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "TextSketch",
                    "label": "TextSketch",
                    "type_id": "Sketcher::SketchObject",
                    "wire_count": 10,
                    "source": "ShapeString",
                },
                stdout="",
                stderr="",
                execution_time_ms=150.0,
            )
        )

        to_sketch = register_tools["draft_shapestring_to_sketch"]
        result = await to_sketch(
            shapestring_name="ShapeString",
            body_name="Body",
        )

        assert result["type_id"] == "Sketcher::SketchObject"

    @pytest.mark.asyncio
    async def test_draft_shapestring_to_sketch_not_found(
        self, register_tools, mock_bridge
    ):
        """draft_shapestring_to_sketch should fail if source not found."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=50.0,
                error_type="ValueError",
                error_traceback="ShapeString not found: 'BadName'",
            )
        )

        to_sketch = register_tools["draft_shapestring_to_sketch"]
        with pytest.raises(ValueError, match="ShapeString not found"):
            await to_sketch(shapestring_name="BadName")

    # =========================================================================
    # draft_shapestring_to_face tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_draft_shapestring_to_face_success(self, register_tools, mock_bridge):
        """draft_shapestring_to_face should convert to face."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "TextFace",
                    "label": "TextFace",
                    "type_id": "Part::Feature",
                    "face_count": 5,
                    "area": 250.0,
                    "source": "ShapeString",
                },
                stdout="",
                stderr="",
                execution_time_ms=120.0,
            )
        )

        to_face = register_tools["draft_shapestring_to_face"]
        result = await to_face(shapestring_name="ShapeString")

        assert result["name"] == "TextFace"
        assert result["type_id"] == "Part::Feature"
        assert result["face_count"] == 5
        assert result["area"] == 250.0

    @pytest.mark.asyncio
    async def test_draft_shapestring_to_face_no_wires(
        self, register_tools, mock_bridge
    ):
        """draft_shapestring_to_face should fail if no wires."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=50.0,
                error_type="ValueError",
                error_traceback="ShapeString has no wires",
            )
        )

        to_face = register_tools["draft_shapestring_to_face"]
        with pytest.raises(ValueError, match="ShapeString has no wires"):
            await to_face(shapestring_name="EmptyShape")

    # =========================================================================
    # draft_text_on_surface tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_draft_text_on_surface_engrave(self, register_tools, mock_bridge):
        """draft_text_on_surface should engrave text."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "Text_Box",
                    "label": "Text_Box",
                    "type_id": "Part::Feature",
                    "operation": "engrave",
                    "text": "SAMPLE",
                    "depth": 1.5,
                },
                stdout="",
                stderr="",
                execution_time_ms=300.0,
            )
        )

        text_on_surface = register_tools["draft_text_on_surface"]
        result = await text_on_surface(
            text="SAMPLE",
            target_face="Face6",
            target_object="Box",
            depth=1.5,
            operation="engrave",
        )

        assert result["operation"] == "engrave"
        assert result["text"] == "SAMPLE"
        assert result["depth"] == 1.5

    @pytest.mark.asyncio
    async def test_draft_text_on_surface_emboss(self, register_tools, mock_bridge):
        """draft_text_on_surface should emboss text."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "Text_Box",
                    "label": "Text_Box",
                    "type_id": "Part::Feature",
                    "operation": "emboss",
                    "text": "RAISED",
                    "depth": 2.0,
                },
                stdout="",
                stderr="",
                execution_time_ms=300.0,
            )
        )

        text_on_surface = register_tools["draft_text_on_surface"]
        result = await text_on_surface(
            text="RAISED",
            target_face="Face6",
            target_object="Box",
            depth=2.0,
            operation="emboss",
        )

        assert result["operation"] == "emboss"
        assert result["text"] == "RAISED"

    @pytest.mark.asyncio
    async def test_draft_text_on_surface_invalid_operation(
        self, register_tools, mock_bridge
    ):
        """draft_text_on_surface should reject invalid operation."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=50.0,
                error_type="ValueError",
                error_traceback="Invalid operation: 'cut'. Use 'emboss' or 'engrave'.",
            )
        )

        text_on_surface = register_tools["draft_text_on_surface"]
        with pytest.raises(ValueError, match="Invalid operation"):
            await text_on_surface(
                text="TEST",
                target_face="Face1",
                target_object="Box",
                operation="cut",
            )

    @pytest.mark.asyncio
    async def test_draft_text_on_surface_face_not_found(
        self, register_tools, mock_bridge
    ):
        """draft_text_on_surface should fail if face not found."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=50.0,
                error_type="ValueError",
                error_traceback="Face not found: Face99 on 'Box'",
            )
        )

        text_on_surface = register_tools["draft_text_on_surface"]
        with pytest.raises(ValueError, match="Face not found"):
            await text_on_surface(
                text="TEST",
                target_face="Face99",
                target_object="Box",
            )

    # =========================================================================
    # draft_extrude_shapestring tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_draft_extrude_shapestring_success(self, register_tools, mock_bridge):
        """draft_extrude_shapestring should create 3D solid text."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "ExtrudedText",
                    "label": "ExtrudedText",
                    "type_id": "Part::Feature",
                    "volume": 1500.0,
                    "height": 5.0,
                    "source": "ShapeString",
                },
                stdout="",
                stderr="",
                execution_time_ms=150.0,
            )
        )

        extrude = register_tools["draft_extrude_shapestring"]
        result = await extrude(shapestring_name="ShapeString", height=5.0)

        assert result["name"] == "ExtrudedText"
        assert result["type_id"] == "Part::Feature"
        assert result["volume"] == 1500.0
        assert result["height"] == 5.0
        assert result["source"] == "ShapeString"

    @pytest.mark.asyncio
    async def test_draft_extrude_shapestring_with_direction(
        self, register_tools, mock_bridge
    ):
        """draft_extrude_shapestring should use custom direction."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "name": "ExtrudedText",
                    "label": "ExtrudedText",
                    "type_id": "Part::Feature",
                    "volume": 1000.0,
                    "height": 10.0,
                    "source": "ShapeString",
                },
                stdout="",
                stderr="",
                execution_time_ms=150.0,
            )
        )

        extrude = register_tools["draft_extrude_shapestring"]
        result = await extrude(
            shapestring_name="ShapeString",
            height=10.0,
            direction=[1.0, 0.0, 0.0],  # Extrude in X direction
        )

        assert result["height"] == 10.0

    @pytest.mark.asyncio
    async def test_draft_extrude_shapestring_no_faces(
        self, register_tools, mock_bridge
    ):
        """draft_extrude_shapestring should fail if no faces created."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=50.0,
                error_type="ValueError",
                error_traceback="Could not create any faces from ShapeString",
            )
        )

        extrude = register_tools["draft_extrude_shapestring"]
        with pytest.raises(ValueError, match="Could not create any faces"):
            await extrude(shapestring_name="BadShape", height=5.0)

    # =========================================================================
    # Test that all expected tools are registered
    # =========================================================================

    def test_all_draft_tools_registered(self, register_tools):
        """All draft tools should be registered."""
        expected_tools = [
            "draft_shapestring",
            "draft_list_fonts",
            "draft_shapestring_to_sketch",
            "draft_shapestring_to_face",
            "draft_text_on_surface",
            "draft_extrude_shapestring",
        ]

        for tool_name in expected_tools:
            assert tool_name in register_tools, f"Tool {tool_name} not registered"
