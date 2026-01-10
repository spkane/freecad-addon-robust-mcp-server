"""Tests for the FreeCAD Robust MCP workbench addon structure.

These tests verify that the addon has the correct file structure and
that the Python files are valid (can be parsed).
"""

import ast
from pathlib import Path

import pytest

# Get the addon directory path
ADDON_DIR = Path(__file__).parent.parent.parent.parent / "addon" / "FreecadRobustMCP"


class TestAddonFileStructure:
    """Tests for addon file structure."""

    def test_addon_directory_exists(self):
        """The addon directory should exist."""
        assert ADDON_DIR.exists(), f"Addon directory not found: {ADDON_DIR}"
        assert ADDON_DIR.is_dir(), f"Addon path is not a directory: {ADDON_DIR}"

    def test_init_py_exists(self):
        """Init.py should exist in the addon directory."""
        init_file = ADDON_DIR / "Init.py"
        assert init_file.exists(), f"Init.py not found: {init_file}"

    def test_initgui_py_exists(self):
        """InitGui.py should exist in the addon directory."""
        initgui_file = ADDON_DIR / "InitGui.py"
        assert initgui_file.exists(), f"InitGui.py not found: {initgui_file}"

    def test_icon_exists(self):
        """The workbench icon should exist."""
        icon_file = ADDON_DIR / "FreecadRobustMCP.svg"
        assert icon_file.exists(), f"Icon not found: {icon_file}"

    def test_bridge_module_exists(self):
        """The bridge module directory should exist."""
        bridge_dir = ADDON_DIR / "freecad_mcp_bridge"
        assert bridge_dir.exists(), f"Bridge module not found: {bridge_dir}"
        assert bridge_dir.is_dir(), f"Bridge path is not a directory: {bridge_dir}"

    def test_bridge_init_exists(self):
        """The bridge module __init__.py should exist."""
        init_file = ADDON_DIR / "freecad_mcp_bridge" / "__init__.py"
        assert init_file.exists(), f"Bridge __init__.py not found: {init_file}"

    def test_bridge_server_exists(self):
        """The bridge server.py should exist."""
        server_file = ADDON_DIR / "freecad_mcp_bridge" / "server.py"
        assert server_file.exists(), f"Bridge server.py not found: {server_file}"

    def test_blocking_bridge_exists(self):
        """The blocking_bridge.py should exist for blocking server mode."""
        blocking_file = ADDON_DIR / "freecad_mcp_bridge" / "blocking_bridge.py"
        assert blocking_file.exists(), f"blocking_bridge.py not found: {blocking_file}"

    def test_bridge_utils_exists(self):
        """The bridge_utils.py should exist for shared utilities."""
        utils_file = ADDON_DIR / "freecad_mcp_bridge" / "bridge_utils.py"
        assert utils_file.exists(), f"bridge_utils.py not found: {utils_file}"


class TestAddonPythonSyntax:
    """Tests to verify Python files have valid syntax."""

    def test_init_py_valid_syntax(self):
        """Init.py should have valid Python syntax."""
        init_file = ADDON_DIR / "Init.py"
        code = init_file.read_text()
        # This will raise SyntaxError if invalid
        ast.parse(code)

    def test_initgui_py_valid_syntax(self):
        """InitGui.py should have valid Python syntax."""
        initgui_file = ADDON_DIR / "InitGui.py"
        code = initgui_file.read_text()
        # This will raise SyntaxError if invalid
        ast.parse(code)

    def test_bridge_init_valid_syntax(self):
        """Bridge __init__.py should have valid Python syntax."""
        init_file = ADDON_DIR / "freecad_mcp_bridge" / "__init__.py"
        code = init_file.read_text()
        ast.parse(code)

    def test_bridge_server_valid_syntax(self):
        """Bridge server.py should have valid Python syntax."""
        server_file = ADDON_DIR / "freecad_mcp_bridge" / "server.py"
        code = server_file.read_text()
        ast.parse(code)

    def test_blocking_bridge_valid_syntax(self):
        """blocking_bridge.py should have valid Python syntax."""
        blocking_file = ADDON_DIR / "freecad_mcp_bridge" / "blocking_bridge.py"
        code = blocking_file.read_text()
        ast.parse(code)

    def test_bridge_utils_valid_syntax(self):
        """bridge_utils.py should have valid Python syntax."""
        utils_file = ADDON_DIR / "freecad_mcp_bridge" / "bridge_utils.py"
        code = utils_file.read_text()
        ast.parse(code)


class TestAddonMetadata:
    """Tests for addon metadata and content."""

    def test_init_py_has_freecad_import(self):
        """Init.py should import FreeCAD."""
        init_file = ADDON_DIR / "Init.py"
        code = init_file.read_text()
        assert "import FreeCAD" in code

    def test_initgui_py_has_workbench_class(self):
        """InitGui.py should define the workbench class."""
        initgui_file = ADDON_DIR / "InitGui.py"
        code = initgui_file.read_text()
        assert "FreecadRobustMCPWorkbench" in code
        assert "Gui.Workbench" in code or "Workbench" in code

    def test_initgui_py_has_commands(self):
        """InitGui.py should define start/stop commands."""
        initgui_file = ADDON_DIR / "InitGui.py"
        code = initgui_file.read_text()
        assert "StartMCPBridgeCommand" in code
        assert "StopMCPBridgeCommand" in code

    def test_initgui_py_registers_workbench(self):
        """InitGui.py should register the workbench."""
        initgui_file = ADDON_DIR / "InitGui.py"
        code = initgui_file.read_text()
        assert "Gui.addWorkbench" in code

    def test_bridge_server_has_plugin_class(self):
        """Bridge server.py should have FreecadMCPPlugin class."""
        server_file = ADDON_DIR / "freecad_mcp_bridge" / "server.py"
        code = server_file.read_text()
        assert "class FreecadMCPPlugin" in code

    def test_blocking_bridge_imports_plugin(self):
        """blocking_bridge.py should import FreecadMCPPlugin."""
        blocking_file = ADDON_DIR / "freecad_mcp_bridge" / "blocking_bridge.py"
        code = blocking_file.read_text()
        assert "FreecadMCPPlugin" in code

    def test_blocking_bridge_has_run_forever(self):
        """blocking_bridge.py should call run_forever for blocking execution."""
        blocking_file = ADDON_DIR / "freecad_mcp_bridge" / "blocking_bridge.py"
        code = blocking_file.read_text()
        assert "run_forever" in code

    def test_bridge_utils_has_get_running_plugin(self):
        """bridge_utils.py should have get_running_plugin function."""
        utils_file = ADDON_DIR / "freecad_mcp_bridge" / "bridge_utils.py"
        code = utils_file.read_text()
        assert "def get_running_plugin" in code

    def test_icon_is_valid_svg(self):
        """The icon should be a valid SVG file."""
        icon_file = ADDON_DIR / "FreecadRobustMCP.svg"
        content = icon_file.read_text()
        assert content.startswith("<?xml") or content.startswith("<svg")
        assert "<svg" in content
        assert "</svg>" in content


class TestAddonIconSize:
    """Tests for addon icon size requirements."""

    def test_icon_size_under_10kb(self):
        """The icon file should be under 10KB (FreeCAD requirement)."""
        icon_file = ADDON_DIR / "FreecadRobustMCP.svg"
        size_bytes = icon_file.stat().st_size
        size_kb = size_bytes / 1024
        assert size_kb <= 10, f"Icon is {size_kb:.2f}KB, must be <= 10KB"


class TestPackageXml:
    """Tests for package.xml workbench entry."""

    @pytest.fixture
    def package_xml(self):
        """Load package.xml content."""
        package_file = ADDON_DIR.parent.parent / "package.xml"
        return package_file.read_text()

    def test_workbench_entry_exists(self, package_xml):
        """package.xml should have a workbench entry."""
        assert "<workbench>" in package_xml

    def test_workbench_classname(self, package_xml):
        """package.xml should reference the correct workbench classname."""
        assert "<classname>FreecadRobustMCPWorkbench</classname>" in package_xml

    def test_workbench_subdirectory(self, package_xml):
        """package.xml should reference the correct subdirectory."""
        assert "./addon/FreecadRobustMCP/" in package_xml

    def test_workbench_icon(self, package_xml):
        """package.xml should reference the workbench icon."""
        assert "<icon>FreecadRobustMCP.svg</icon>" in package_xml
