"""Integration tests for the MultiExport macro.

These tests verify the MultiExporter class functionality including:
- Exporting to STL format
- Exporting to STEP format
- Exporting to multiple formats simultaneously
- Handling mesh tolerance settings

Note: These tests require a running FreeCAD Robust MCP Bridge.
      Start it with: just freecad::run-gui or just freecad::run-headless

To run these tests:
    pytest tests/integration/test_multi_export.py -v
"""

from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    import xmlrpc.client

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


def execute_code(proxy: xmlrpc.client.ServerProxy, code: str) -> dict[str, Any]:
    """Execute Python code via the MCP bridge and return the result."""
    result = proxy.execute(code)  # type: ignore[union-attr]
    assert isinstance(result, dict), f"Unexpected result type: {type(result)}"
    assert result.get("success"), f"Execution failed: {result.get('error_traceback')}"
    return result


# The MultiExporter class code embedded for testing
MULTI_EXPORTER_CODE = '''
import os
import FreeCAD as App
import Part
import Mesh


class MultiExporter:
    """Handles exporting objects to multiple formats."""

    def __init__(self, objects, params):
        """Initialize the exporter."""
        self.objects = objects
        self.params = params
        self.exported_files = []
        self.errors = []

    def export_all(self):
        """Export objects to all selected formats."""
        formats = self.params["formats"]

        if not formats:
            return [], ["No formats selected"]

        for fmt in formats:
            try:
                filepath = self._export_format(fmt)
                self.exported_files.append(filepath)
            except Exception as e:
                self.errors.append(f"Failed to export {fmt.upper()}: {str(e)}")

        return self.exported_files, self.errors

    def _export_format(self, extension):
        """Export to a specific format."""
        directory = self.params["directory"]
        base_name = self.params["base_filename"]
        filepath = os.path.join(directory, f"{base_name}.{extension}")

        shapes = []
        for obj in self.objects:
            if hasattr(obj, "Shape"):
                shapes.append(obj.Shape)

        if not shapes:
            raise ValueError("No exportable shapes found")

        if len(shapes) == 1:
            combined_shape = shapes[0]
        else:
            combined_shape = Part.makeCompound(shapes)

        if extension == "stl":
            self._export_mesh(combined_shape, filepath)
        elif extension == "step":
            combined_shape.exportStep(filepath)
        elif extension == "brep":
            combined_shape.exportBrep(filepath)
        else:
            raise ValueError(f"Unsupported format: {extension}")

        return filepath

    def _export_mesh(self, shape, filepath):
        """Export shape as mesh format."""
        tolerance = self.params.get("mesh_tolerance", 0.1)
        mesh = Mesh.Mesh()
        vertices, facets = shape.tessellate(tolerance)
        mesh_data = []
        for facet in facets:
            triangle = [vertices[facet[0]], vertices[facet[1]], vertices[facet[2]]]
            mesh_data.append(triangle)
        mesh.addFacets(mesh_data)
        mesh.write(filepath)
'''


@pytest.fixture
def temp_export_dir():
    """Create a temporary directory for export tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestMultiExporter:
    """Tests for the MultiExporter functionality."""

    def test_export_stl(self, xmlrpc_proxy, temp_export_dir):
        """Test exporting a simple box to STL format."""
        code = f"""
{MULTI_EXPORTER_CODE}

# Create a new document and simple box
doc = App.newDocument("TestExportSTL")
box = doc.addObject("Part::Box", "TestBox")
box.Length = 20
box.Width = 20
box.Height = 10
doc.recompute()

# Set up export parameters
params = {{
    "directory": "{temp_export_dir}",
    "base_filename": "test_box",
    "formats": ["stl"],
    "mesh_tolerance": 0.1,
}}

# Create exporter and export
exporter = MultiExporter([box], params)
exported_files, errors = exporter.export_all()

# Clean up
App.closeDocument("TestExportSTL")

_result_ = {{
    "exported_files": exported_files,
    "errors": errors,
    "file_exists": os.path.exists(exported_files[0]) if exported_files else False,
}}
"""
        result = execute_code(xmlrpc_proxy, code)
        data = result.get("result", {})

        assert len(data["exported_files"]) == 1
        assert len(data["errors"]) == 0
        assert data["file_exists"] is True
        assert data["exported_files"][0].endswith(".stl")

    def test_export_step(self, xmlrpc_proxy, temp_export_dir):
        """Test exporting a simple cylinder to STEP format."""
        code = f"""
{MULTI_EXPORTER_CODE}

# Create a new document and simple cylinder
doc = App.newDocument("TestExportSTEP")
cylinder = doc.addObject("Part::Cylinder", "TestCylinder")
cylinder.Radius = 10
cylinder.Height = 30
doc.recompute()

# Set up export parameters
params = {{
    "directory": "{temp_export_dir}",
    "base_filename": "test_cylinder",
    "formats": ["step"],
    "mesh_tolerance": 0.1,
}}

# Create exporter and export
exporter = MultiExporter([cylinder], params)
exported_files, errors = exporter.export_all()

# Clean up
App.closeDocument("TestExportSTEP")

_result_ = {{
    "exported_files": exported_files,
    "errors": errors,
    "file_exists": os.path.exists(exported_files[0]) if exported_files else False,
}}
"""
        result = execute_code(xmlrpc_proxy, code)
        data = result.get("result", {})

        assert len(data["exported_files"]) == 1
        assert len(data["errors"]) == 0
        assert data["file_exists"] is True
        assert data["exported_files"][0].endswith(".step")

    def test_export_multiple_formats(self, xmlrpc_proxy, temp_export_dir):
        """Test exporting to multiple formats simultaneously."""
        code = f"""
{MULTI_EXPORTER_CODE}

# Create a new document and simple sphere
doc = App.newDocument("TestExportMulti")
sphere = doc.addObject("Part::Sphere", "TestSphere")
sphere.Radius = 15
doc.recompute()

# Set up export parameters for multiple formats
params = {{
    "directory": "{temp_export_dir}",
    "base_filename": "test_sphere",
    "formats": ["stl", "step", "brep"],
    "mesh_tolerance": 0.1,
}}

# Create exporter and export
exporter = MultiExporter([sphere], params)
exported_files, errors = exporter.export_all()

# Check which files exist
files_exist = [os.path.exists(f) for f in exported_files]

# Clean up
App.closeDocument("TestExportMulti")

_result_ = {{
    "exported_files": exported_files,
    "errors": errors,
    "files_exist": files_exist,
    "count": len(exported_files),
}}
"""
        result = execute_code(xmlrpc_proxy, code)
        data = result.get("result", {})

        assert data["count"] == 3
        assert len(data["errors"]) == 0
        assert all(data["files_exist"])
        # Verify each format is present
        extensions = [os.path.splitext(f)[1] for f in data["exported_files"]]
        assert ".stl" in extensions
        assert ".step" in extensions
        assert ".brep" in extensions

    def test_export_multiple_objects(self, xmlrpc_proxy, temp_export_dir):
        """Test exporting multiple objects as a compound."""
        code = f"""
{MULTI_EXPORTER_CODE}

# Create a new document with multiple objects
doc = App.newDocument("TestExportMultiObj")
box = doc.addObject("Part::Box", "Box1")
box.Length = 10
box.Width = 10
box.Height = 10

cylinder = doc.addObject("Part::Cylinder", "Cyl1")
cylinder.Radius = 5
cylinder.Height = 20
cylinder.Placement.Base = App.Vector(20, 0, 0)

doc.recompute()

# Set up export parameters
params = {{
    "directory": "{temp_export_dir}",
    "base_filename": "test_compound",
    "formats": ["stl"],
    "mesh_tolerance": 0.1,
}}

# Create exporter with multiple objects
exporter = MultiExporter([box, cylinder], params)
exported_files, errors = exporter.export_all()

# Check file size (compound should be larger than single object)
file_size = os.path.getsize(exported_files[0]) if exported_files else 0

# Clean up
App.closeDocument("TestExportMultiObj")

_result_ = {{
    "exported_files": exported_files,
    "errors": errors,
    "file_exists": os.path.exists(exported_files[0]) if exported_files else False,
    "file_size": file_size,
}}
"""
        result = execute_code(xmlrpc_proxy, code)
        data = result.get("result", {})

        assert len(data["exported_files"]) == 1
        assert len(data["errors"]) == 0
        assert data["file_exists"] is True
        # Compound file should have some reasonable size
        assert data["file_size"] > 100

    def test_export_with_custom_tolerance(self, xmlrpc_proxy, temp_export_dir):
        """Test that mesh tolerance affects output file size.

        Note: FreeCAD's tessellate function has internal limits, so we need
        to use a very fine tolerance (0.01) to actually see more triangles
        compared to the default tessellation.
        """
        code = f"""
{MULTI_EXPORTER_CODE}

# Create a sphere (curved surface shows tolerance effect best)
doc = App.newDocument("TestTolerance")
sphere = doc.addObject("Part::Sphere", "TestSphere")
sphere.Radius = 20
doc.recompute()

# Export with coarse tolerance (uses default tessellation)
params_coarse = {{
    "directory": "{temp_export_dir}",
    "base_filename": "sphere_coarse",
    "formats": ["stl"],
    "mesh_tolerance": 1.0,
}}
exporter_coarse = MultiExporter([sphere], params_coarse)
coarse_files, _ = exporter_coarse.export_all()
coarse_size = os.path.getsize(coarse_files[0]) if coarse_files else 0

# Export with very fine tolerance (0.01 required to see difference)
params_fine = {{
    "directory": "{temp_export_dir}",
    "base_filename": "sphere_fine",
    "formats": ["stl"],
    "mesh_tolerance": 0.01,
}}
exporter_fine = MultiExporter([sphere], params_fine)
fine_files, _ = exporter_fine.export_all()
fine_size = os.path.getsize(fine_files[0]) if fine_files else 0

# Clean up
App.closeDocument("TestTolerance")

_result_ = {{
    "coarse_size": coarse_size,
    "fine_size": fine_size,
    "fine_is_larger": fine_size > coarse_size,
}}
"""
        result = execute_code(xmlrpc_proxy, code)
        data = result.get("result", {})

        # Fine tolerance (0.01) should produce larger file (more triangles)
        assert data["fine_is_larger"] is True
        assert data["fine_size"] > data["coarse_size"]

    def test_export_empty_formats_list(self, xmlrpc_proxy, temp_export_dir):
        """Test that empty formats list returns appropriate error."""
        code = f"""
{MULTI_EXPORTER_CODE}

doc = App.newDocument("TestEmptyFormats")
box = doc.addObject("Part::Box", "TestBox")
doc.recompute()

params = {{
    "directory": "{temp_export_dir}",
    "base_filename": "test",
    "formats": [],
    "mesh_tolerance": 0.1,
}}

exporter = MultiExporter([box], params)
exported_files, errors = exporter.export_all()

App.closeDocument("TestEmptyFormats")

_result_ = {{
    "exported_files": exported_files,
    "errors": errors,
}}
"""
        result = execute_code(xmlrpc_proxy, code)
        data = result.get("result", {})

        assert len(data["exported_files"]) == 0
        assert len(data["errors"]) == 1
        assert "No formats selected" in data["errors"][0]
