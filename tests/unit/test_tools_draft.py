"""Unit tests for the draft tools module.

This module tests the Draft workbench tools, focusing on ShapeString
functionality for creating 3D text geometry. All tests use mocked FreeCAD
bridges to avoid requiring a running FreeCAD instance.
"""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from freecad_mcp.bridge.base import ExecutionResult

# Type aliases for fixtures
RegisteredTools = dict[str, Callable[..., Awaitable[Any]]]


class TestDraftTools:
    """Tests for Draft workbench tools (ShapeString)."""

    @pytest.fixture
    def mock_mcp(self) -> MagicMock:
        """Create a mock MCP server that captures tool registrations.

        Creates a MagicMock that simulates the FastMCP server's tool
        registration mechanism, storing registered tools in _registered_tools.

        Returns:
            MagicMock configured with a tool() decorator that captures
            registered tool functions by name.

        Raises:
            None.

        Example:
            def test_example(self, mock_mcp):
                # Access registered tools via mock_mcp._registered_tools
                assert "draft_shapestring" in mock_mcp._registered_tools
        """
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
    def mock_bridge(self) -> AsyncMock:
        """Create a mock FreeCAD bridge.

        Creates an AsyncMock that simulates the FreeCAD bridge's
        execute_python method for testing without a real FreeCAD instance.

        Returns:
            AsyncMock that can be configured with return values for
            execute_python calls.

        Raises:
            None.

        Example:
            def test_example(self, mock_bridge):
                mock_bridge.execute_python = AsyncMock(
                    return_value=ExecutionResult(success=True, result={})
                )
        """
        return AsyncMock()

    @pytest.fixture
    def register_tools(
        self, mock_mcp: MagicMock, mock_bridge: AsyncMock
    ) -> RegisteredTools:
        """Register draft tools and return the registered functions.

        Imports and calls register_draft_tools with the mock MCP and bridge,
        returning the dictionary of registered tool functions.

        Args:
            mock_mcp: The mock MCP server fixture.
            mock_bridge: The mock bridge fixture.

        Returns:
            Dictionary mapping tool names (str) to their async callable
            functions (e.g., draft_shapestring, draft_list_fonts).

        Raises:
            None.

        Example:
            async def test_shapestring(self, register_tools, mock_bridge):
                shapestring = register_tools["draft_shapestring"]
                result = await shapestring(text="Hello")
        """
        from freecad_mcp.tools.draft import register_draft_tools

        async def get_bridge() -> AsyncMock:
            return mock_bridge

        register_draft_tools(mock_mcp, get_bridge)
        return mock_mcp._registered_tools

    # =========================================================================
    # draft_shapestring tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_draft_shapestring_success(
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_shapestring creates 3D text geometry with default settings.

        Verifies that the draft_shapestring tool successfully creates a
        ShapeString object with the specified text and size.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Example:
            result = await shapestring(text="Hello", size=10.0)
            assert result["text"] == "Hello"
        """
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
    async def test_draft_shapestring_with_font(
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_shapestring uses custom font path.

        Verifies that the draft_shapestring tool accepts and uses a custom
        font file path when creating the ShapeString.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Example:
            result = await shapestring(text="Custom", font_path="/path/to/font.ttf")
            assert result["font"] == "/path/to/font.ttf"
        """
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
    async def test_draft_shapestring_with_position(
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_shapestring uses custom 3D position.

        Verifies that the draft_shapestring tool accepts and uses a custom
        position vector [x, y, z] when placing the ShapeString.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Example:
            result = await shapestring(text="Positioned", position=[10, 20, 5])
        """
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
    async def test_draft_shapestring_no_font(
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_shapestring fails when no font is available.

        Verifies that the draft_shapestring tool raises a ValueError when
        no font file is specified and no default font can be found on the system.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Raises:
            ValueError: When no font file is available.

        Example:
            with pytest.raises(ValueError, match="No font file specified"):
                await shapestring(text="NoFont")
        """
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
        self,
        register_tools: RegisteredTools,
        mock_bridge: AsyncMock,
        fonts_data: dict[str, Any],
        expected_count: int,
        expected_dirs: int,
    ) -> None:
        """Test draft_list_fonts returns available fonts or handles empty case.

        Verifies that the draft_list_fonts tool correctly returns font
        information when fonts are found and handles the case when no fonts
        are available on the system.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.
            fonts_data: Parametrized font data returned by the mock.
            expected_count: Expected number of fonts in the result.
            expected_dirs: Expected number of directories searched.

        Returns:
            None.

        Example:
            result = await list_fonts()
            assert result["count"] == 2
            assert len(result["fonts"]) == 2
        """
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
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_shapestring_to_sketch converts ShapeString to sketch.

        Verifies that the tool successfully converts a ShapeString object
        into a Sketcher::SketchObject containing the text outline geometry.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Example:
            result = await to_sketch(shapestring_name="ShapeString")
            assert result["type_id"] == "Sketcher::SketchObject"
        """
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
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_shapestring_to_sketch attaches sketch to PartDesign body.

        Verifies that the tool can convert a ShapeString to a sketch and
        attach it to an existing PartDesign body for parametric modeling.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Example:
            result = await to_sketch(shapestring_name="ShapeString", body_name="Body")
            assert result["type_id"] == "Sketcher::SketchObject"
        """
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
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_shapestring_to_sketch fails when source object not found.

        Verifies that the tool raises a ValueError when the specified
        ShapeString object does not exist in the active document.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Raises:
            ValueError: When the specified ShapeString object is not found.

        Example:
            with pytest.raises(ValueError, match="ShapeString not found"):
                await to_sketch(shapestring_name="BadName")
        """
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
    async def test_draft_shapestring_to_face_success(
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_shapestring_to_face converts ShapeString to face.

        Verifies that the tool successfully converts a ShapeString object
        into a Part::Feature containing face geometry suitable for boolean
        operations. Uses Part.makeFace with FaceMakerBullseye to preserve
        inner holes in letters like 'A', 'O', etc.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Example:
            result = await to_face(shapestring_name="ShapeString")
            assert result["type_id"] == "Part::Feature"
            assert result["face_count"] == 5
        """
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
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_shapestring_to_face fails when ShapeString has no wires.

        Verifies that the tool raises a ValueError when the ShapeString
        object has no wire geometry to convert into faces.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Raises:
            ValueError: When the ShapeString has no wires.

        Example:
            with pytest.raises(ValueError, match="ShapeString has no wires"):
                await to_face(shapestring_name="EmptyShape")
        """
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
    async def test_draft_text_on_surface_engrave(
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_text_on_surface engraves text into a surface.

        Verifies that the tool successfully creates engraved (cut into)
        text on a target object's face using a boolean cut operation.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Example:
            result = await text_on_surface(
                text="SAMPLE", target_face="Face6", target_object="Box",
                depth=1.5, operation="engrave"
            )
            assert result["operation"] == "engrave"
        """
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
    async def test_draft_text_on_surface_emboss(
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_text_on_surface embosses text on a surface.

        Verifies that the tool successfully creates embossed (raised)
        text on a target object's face using a boolean fuse operation.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Example:
            result = await text_on_surface(
                text="RAISED", target_face="Face6", target_object="Box",
                depth=2.0, operation="emboss"
            )
            assert result["operation"] == "emboss"
        """
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
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_text_on_surface rejects invalid operation type.

        Verifies that the tool raises a ValueError when an invalid operation
        type is specified (not 'emboss' or 'engrave').

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Raises:
            ValueError: When operation is not 'emboss' or 'engrave'.

        Example:
            with pytest.raises(ValueError, match="Invalid operation"):
                await text_on_surface(text="TEST", ..., operation="cut")
        """
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
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_text_on_surface fails when target face not found.

        Verifies that the tool raises a ValueError when the specified
        face does not exist on the target object.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Raises:
            ValueError: When the specified face is not found on the target object.

        Example:
            with pytest.raises(ValueError, match="Face not found"):
                await text_on_surface(text="TEST", target_face="Face99", ...)
        """
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
    async def test_draft_extrude_shapestring_success(
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_extrude_shapestring creates 3D solid text.

        Verifies that the tool successfully extrudes a ShapeString into
        a 3D solid Part::Feature with the specified height.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Example:
            result = await extrude(shapestring_name="ShapeString", height=5.0)
            assert result["type_id"] == "Part::Feature"
            assert result["volume"] == 1500.0
        """
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
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_extrude_shapestring uses custom extrusion direction.

        Verifies that the tool can extrude a ShapeString along a custom
        direction vector instead of the default Z direction.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Example:
            result = await extrude(
                shapestring_name="ShapeString", height=10.0,
                direction=[1.0, 0.0, 0.0]  # Extrude in X direction
            )
        """
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
        self, register_tools: RegisteredTools, mock_bridge: AsyncMock
    ) -> None:
        """Test draft_extrude_shapestring fails when no faces can be created.

        Verifies that the tool raises a ValueError when the ShapeString
        cannot be converted to faces for extrusion.

        Args:
            register_tools: Dictionary of registered draft tool functions.
            mock_bridge: Mock FreeCAD bridge for simulating execute_python calls.

        Returns:
            None.

        Raises:
            ValueError: When no faces can be created from the ShapeString.

        Example:
            with pytest.raises(ValueError, match="Could not create any faces"):
                await extrude(shapestring_name="BadShape", height=5.0)
        """
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

    def test_all_draft_tools_registered(self, register_tools: RegisteredTools) -> None:
        """Test that all expected draft tools are registered.

        Verifies that all required draft tools are properly registered
        with the MCP server when register_draft_tools is called.

        Args:
            register_tools: Dictionary of registered draft tool functions.

        Returns:
            None.

        Example:
            assert "draft_shapestring" in register_tools
            assert "draft_list_fonts" in register_tools
        """
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
