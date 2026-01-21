"""Tests for FreeCAD Robust MCP prompts."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestFreecadPrompts:
    """Tests for FreeCAD Robust MCP prompts."""

    @pytest.fixture
    def mock_mcp(self) -> MagicMock:
        """Create a mock MCP server that captures prompt registrations."""
        mcp = MagicMock()
        mcp._registered_prompts = {}

        def prompt_decorator() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def wrapper(func: Callable[..., Any]) -> Callable[..., Any]:
                mcp._registered_prompts[func.__name__] = func
                return func

            return wrapper

        mcp.prompt = prompt_decorator
        return mcp

    @pytest.fixture
    def mock_bridge(self) -> AsyncMock:
        """Create a mock FreeCAD bridge."""
        return AsyncMock()

    @pytest.fixture
    def register_prompts(
        self, mock_mcp: MagicMock, mock_bridge: AsyncMock
    ) -> dict[str, Callable[..., Any]]:
        """Register prompts and return the registered functions."""
        from freecad_mcp.prompts.freecad import register_prompts

        async def get_bridge() -> AsyncMock:
            return mock_bridge

        register_prompts(mock_mcp, get_bridge)
        return mock_mcp._registered_prompts

    # =========================================================================
    # freecad_startup prompt tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_freecad_startup_returns_guidance(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_startup should return essential startup guidance."""
        prompt_startup = register_prompts["freecad_startup"]
        result = await prompt_startup()

        # Should be a non-empty string
        assert isinstance(result, str)
        assert len(result) > 100

        # Should contain key sections
        assert "Session Checklist" in result or "Session Initialized" in result
        assert "Critical Rules" in result
        assert "Quick Reference" in result

    @pytest.mark.asyncio
    async def test_freecad_startup_contains_validation_guidance(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_startup should mention validation tools."""
        prompt_startup = register_prompts["freecad_startup"]
        result = await prompt_startup()

        # Should mention validation
        assert "validate" in result.lower()
        assert "safe_execute" in result or "undo" in result

    @pytest.mark.asyncio
    async def test_freecad_startup_contains_partdesign_guidance(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_startup should contain PartDesign workflow guidance."""
        prompt_startup = register_prompts["freecad_startup"]
        result = await prompt_startup()

        # Should mention PartDesign workflow
        assert "Body" in result
        assert "create_sketch" in result or "sketch" in result.lower()
        assert "pad_sketch" in result or "pad" in result.lower()

    @pytest.mark.asyncio
    async def test_freecad_startup_mentions_gui_headless(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_startup should mention GUI vs headless modes."""
        prompt_startup = register_prompts["freecad_startup"]
        result = await prompt_startup()

        # Should mention GUI/headless considerations
        assert "GUI" in result or "gui" in result
        assert "headless" in result.lower() or "screenshot" in result.lower()

    # =========================================================================
    # freecad_guidance prompt tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_freecad_guidance_general(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_guidance with task_type='general' should return general guidance."""
        prompt_guidance = register_prompts["freecad_guidance"]
        result = await prompt_guidance(task_type="general")

        assert isinstance(result, str)
        assert len(result) > 100
        # Should have general guidance content
        assert "Before Starting" in result or "Key Principles" in result

    @pytest.mark.asyncio
    async def test_freecad_guidance_partdesign(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_guidance with task_type='partdesign' should return PartDesign guidance."""
        prompt_guidance = register_prompts["freecad_guidance"]
        result = await prompt_guidance(task_type="partdesign")

        assert isinstance(result, str)
        # Should have PartDesign-specific content
        assert "Body" in result
        assert "create_partdesign_body" in result or "PartDesign" in result

    @pytest.mark.asyncio
    async def test_freecad_guidance_sketching(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_guidance with task_type='sketching' should return sketch guidance."""
        prompt_guidance = register_prompts["freecad_guidance"]
        result = await prompt_guidance(task_type="sketching")

        assert isinstance(result, str)
        # Should have sketching-specific content
        assert "sketch" in result.lower()
        assert "rectangle" in result.lower() or "circle" in result.lower()

    @pytest.mark.asyncio
    async def test_freecad_guidance_boolean(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_guidance with task_type='boolean' should return boolean guidance."""
        prompt_guidance = register_prompts["freecad_guidance"]
        result = await prompt_guidance(task_type="boolean")

        assert isinstance(result, str)
        # Should have boolean-specific content
        assert "fuse" in result.lower() or "cut" in result.lower()
        assert "boolean" in result.lower()

    @pytest.mark.asyncio
    async def test_freecad_guidance_export(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_guidance with task_type='export' should return export guidance."""
        prompt_guidance = register_prompts["freecad_guidance"]
        result = await prompt_guidance(task_type="export")

        assert isinstance(result, str)
        # Should have export-specific content
        assert "STEP" in result or "STL" in result
        assert "export" in result.lower()

    @pytest.mark.asyncio
    async def test_freecad_guidance_debugging(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_guidance with task_type='debugging' should return debug guidance."""
        prompt_guidance = register_prompts["freecad_guidance"]
        result = await prompt_guidance(task_type="debugging")

        assert isinstance(result, str)
        # Should have debugging-specific content
        assert "console" in result.lower() or "error" in result.lower()
        assert "validate" in result.lower() or "inspect" in result.lower()

    @pytest.mark.asyncio
    async def test_freecad_guidance_validation(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_guidance with task_type='validation' should return validation guidance."""
        prompt_guidance = register_prompts["freecad_guidance"]
        result = await prompt_guidance(task_type="validation")

        assert isinstance(result, str)
        # Should have validation-specific content
        assert "validate_object" in result or "validate_document" in result
        assert "safe_execute" in result or "undo" in result.lower()

    @pytest.mark.asyncio
    async def test_freecad_guidance_unknown_type_falls_back_to_general(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_guidance with unknown task_type should fall back to general."""
        prompt_guidance = register_prompts["freecad_guidance"]
        result = await prompt_guidance(task_type="unknown_type")

        # Should return the general guidance as fallback
        general_result = await prompt_guidance(task_type="general")
        assert result == general_result

    @pytest.mark.asyncio
    async def test_freecad_guidance_default_is_general(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_guidance with no task_type should default to general."""
        prompt_guidance = register_prompts["freecad_guidance"]
        result = await prompt_guidance()

        general_result = await prompt_guidance(task_type="general")
        assert result == general_result

    # =========================================================================
    # Test that all expected prompts are registered
    # =========================================================================

    def test_startup_prompt_is_registered(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_startup prompt should be registered."""
        assert "freecad_startup" in register_prompts

    def test_guidance_prompt_is_registered(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """freecad_guidance prompt should be registered."""
        assert "freecad_guidance" in register_prompts

    def test_design_part_prompt_is_registered(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """design_part prompt should be registered."""
        assert "design_part" in register_prompts

    def test_create_sketch_guide_prompt_is_registered(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """create_sketch_guide prompt should be registered."""
        assert "create_sketch_guide" in register_prompts

    def test_boolean_operations_guide_prompt_is_registered(
        self, register_prompts: dict[str, Callable[..., Any]]
    ) -> None:
        """boolean_operations_guide prompt should be registered."""
        assert "boolean_operations_guide" in register_prompts
