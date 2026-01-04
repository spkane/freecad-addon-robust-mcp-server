"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def sample_python_code():
    """Sample Python code for execution tests."""
    return """
x = 1 + 1
_result_ = {"value": x, "type": type(x).__name__}
"""


@pytest.fixture
def sample_freecad_code():
    """Sample FreeCAD Python code."""
    return """
import Part
box = Part.makeBox(10, 20, 30)
_result_ = {
    "volume": box.Volume,
    "area": box.Area,
    "is_valid": box.isValid(),
}
"""


@pytest.fixture
def mock_execution_result():
    """Mock execution result for testing."""
    from freecad_mcp.bridge.base import ExecutionResult

    return ExecutionResult(
        success=True,
        result={"value": 42},
        stdout="",
        stderr="",
        execution_time_ms=10.5,
    )


@pytest.fixture
def mock_document_info():
    """Mock document info for testing."""
    from freecad_mcp.bridge.base import DocumentInfo

    return DocumentInfo(
        name="TestDoc",
        path="/tmp/test.FCStd",
        objects=["Box", "Cylinder"],
        is_modified=False,
        label="Test Document",
    )


@pytest.fixture
def mock_object_info():
    """Mock object info for testing."""
    from freecad_mcp.bridge.base import ObjectInfo

    return ObjectInfo(
        name="Box",
        label="My Box",
        type_id="Part::Box",
        properties={"Length": 10.0, "Width": 20.0, "Height": 30.0},
        shape_info={
            "type": "Solid",
            "volume": 6000.0,
            "area": 2200.0,
            "is_valid": True,
        },
        children=[],
    )
