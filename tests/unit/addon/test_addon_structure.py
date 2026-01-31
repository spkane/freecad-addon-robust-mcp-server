"""Tests for the FreeCAD Robust MCP workbench addon structure.

These tests verify that the addon has the correct file structure and
that the Python files are valid (can be parsed).

Note: This addon uses the new-style namespace package format:
    freecad/RobustMCPBridge/
"""

import ast
from pathlib import Path

import pytest

# Get the addon directory path (new-style namespace package format)
ADDON_DIR = Path(__file__).parent.parent.parent.parent / "freecad" / "RobustMCPBridge"


class TestAddonFileStructure:
    """Tests for addon file structure."""

    def test_addon_directory_exists(self) -> None:
        """The addon directory should exist."""
        assert ADDON_DIR.exists(), f"Addon directory not found: {ADDON_DIR}"
        assert ADDON_DIR.is_dir(), f"Addon path is not a directory: {ADDON_DIR}"

    def test_init_py_exists(self) -> None:
        """__init__.py should exist in the addon directory (new-style)."""
        init_file = ADDON_DIR / "__init__.py"
        assert init_file.exists(), f"__init__.py not found: {init_file}"

    def test_init_gui_py_exists(self) -> None:
        """init_gui.py should exist in the addon directory (new-style)."""
        init_gui_file = ADDON_DIR / "init_gui.py"
        assert init_gui_file.exists(), f"init_gui.py not found: {init_gui_file}"

    def test_icon_exists(self) -> None:
        """The workbench icon should exist in Resources/Icons/."""
        icon_file = ADDON_DIR / "Resources" / "Icons" / "FreecadRobustMCPBridge.svg"
        assert icon_file.exists(), f"Icon not found: {icon_file}"

    def test_bridge_module_exists(self) -> None:
        """The bridge module directory should exist."""
        bridge_dir = ADDON_DIR / "freecad_mcp_bridge"
        assert bridge_dir.exists(), f"Bridge module not found: {bridge_dir}"
        assert bridge_dir.is_dir(), f"Bridge path is not a directory: {bridge_dir}"

    def test_bridge_init_exists(self) -> None:
        """The bridge module __init__.py should exist."""
        init_file = ADDON_DIR / "freecad_mcp_bridge" / "__init__.py"
        assert init_file.exists(), f"Bridge __init__.py not found: {init_file}"

    def test_bridge_server_exists(self) -> None:
        """The bridge server.py should exist."""
        server_file = ADDON_DIR / "freecad_mcp_bridge" / "server.py"
        assert server_file.exists(), f"Bridge server.py not found: {server_file}"

    def test_blocking_bridge_exists(self) -> None:
        """The blocking_bridge.py should exist for blocking server mode."""
        blocking_file = ADDON_DIR / "freecad_mcp_bridge" / "blocking_bridge.py"
        assert blocking_file.exists(), f"blocking_bridge.py not found: {blocking_file}"

    def test_bridge_utils_exists(self) -> None:
        """The bridge_utils.py should exist for shared utilities."""
        utils_file = ADDON_DIR / "freecad_mcp_bridge" / "bridge_utils.py"
        assert utils_file.exists(), f"bridge_utils.py not found: {utils_file}"

    def test_qt_module_exists(self) -> None:
        """The Qt module directory should exist for UI components."""
        qt_dir = ADDON_DIR / "Qt"
        assert qt_dir.exists(), f"Qt module not found: {qt_dir}"
        assert qt_dir.is_dir(), f"Qt path is not a directory: {qt_dir}"

    def test_qt_init_exists(self) -> None:
        """The Qt module __init__.py should exist."""
        init_file = ADDON_DIR / "Qt" / "__init__.py"
        assert init_file.exists(), f"Qt __init__.py not found: {init_file}"

    def test_qt_status_widget_exists(self) -> None:
        """The Qt status_widget.py should exist."""
        widget_file = ADDON_DIR / "Qt" / "status_widget.py"
        assert widget_file.exists(), f"status_widget.py not found: {widget_file}"

    def test_qt_preferences_page_exists(self) -> None:
        """The Qt preferences_page.py should exist."""
        prefs_file = ADDON_DIR / "Qt" / "preferences_page.py"
        assert prefs_file.exists(), f"preferences_page.py not found: {prefs_file}"

    def test_resources_media_exists(self) -> None:
        """The Resources/Media directory should exist for screenshots."""
        media_dir = ADDON_DIR / "Resources" / "Media"
        assert media_dir.exists(), f"Resources/Media not found: {media_dir}"
        assert media_dir.is_dir(), f"Media path is not a directory: {media_dir}"


class TestAddonPythonSyntax:
    """Tests to verify Python files have valid syntax."""

    def test_init_py_valid_syntax(self) -> None:
        """__init__.py should have valid Python syntax."""
        init_file = ADDON_DIR / "__init__.py"
        code = init_file.read_text()
        # This will raise SyntaxError if invalid
        ast.parse(code)

    def test_init_gui_py_valid_syntax(self) -> None:
        """init_gui.py should have valid Python syntax."""
        init_gui_file = ADDON_DIR / "init_gui.py"
        code = init_gui_file.read_text()
        # This will raise SyntaxError if invalid
        ast.parse(code)

    def test_bridge_init_valid_syntax(self) -> None:
        """Bridge __init__.py should have valid Python syntax."""
        init_file = ADDON_DIR / "freecad_mcp_bridge" / "__init__.py"
        code = init_file.read_text()
        ast.parse(code)

    def test_bridge_server_valid_syntax(self) -> None:
        """Bridge server.py should have valid Python syntax."""
        server_file = ADDON_DIR / "freecad_mcp_bridge" / "server.py"
        code = server_file.read_text()
        ast.parse(code)

    def test_blocking_bridge_valid_syntax(self) -> None:
        """blocking_bridge.py should have valid Python syntax."""
        blocking_file = ADDON_DIR / "freecad_mcp_bridge" / "blocking_bridge.py"
        code = blocking_file.read_text()
        ast.parse(code)

    def test_bridge_utils_valid_syntax(self) -> None:
        """bridge_utils.py should have valid Python syntax."""
        utils_file = ADDON_DIR / "freecad_mcp_bridge" / "bridge_utils.py"
        code = utils_file.read_text()
        ast.parse(code)

    def test_qt_init_valid_syntax(self) -> None:
        """Qt __init__.py should have valid Python syntax."""
        init_file = ADDON_DIR / "Qt" / "__init__.py"
        code = init_file.read_text()
        ast.parse(code)

    def test_qt_status_widget_valid_syntax(self) -> None:
        """Qt status_widget.py should have valid Python syntax."""
        widget_file = ADDON_DIR / "Qt" / "status_widget.py"
        code = widget_file.read_text()
        ast.parse(code)

    def test_qt_preferences_page_valid_syntax(self) -> None:
        """Qt preferences_page.py should have valid Python syntax."""
        prefs_file = ADDON_DIR / "Qt" / "preferences_page.py"
        code = prefs_file.read_text()
        ast.parse(code)


class TestAddonMetadata:
    """Tests for addon metadata and content."""

    def test_init_py_has_freecad_import(self) -> None:
        """__init__.py should import FreeCAD."""
        init_file = ADDON_DIR / "__init__.py"
        code = init_file.read_text()
        assert "import FreeCAD" in code

    def test_init_gui_py_has_workbench_class(self) -> None:
        """init_gui.py should define the workbench class."""
        init_gui_file = ADDON_DIR / "init_gui.py"
        code = init_gui_file.read_text()
        assert "FreecadRobustMCPBridgeWorkbench" in code
        assert "Gui.Workbench" in code or "Workbench" in code

    def test_init_gui_py_has_commands(self) -> None:
        """init_gui.py should define start/stop commands."""
        init_gui_file = ADDON_DIR / "init_gui.py"
        code = init_gui_file.read_text()
        assert "StartMCPBridgeCommand" in code
        assert "StopMCPBridgeCommand" in code

    def test_init_gui_py_registers_workbench(self) -> None:
        """init_gui.py should register the workbench."""
        init_gui_file = ADDON_DIR / "init_gui.py"
        code = init_gui_file.read_text()
        assert "Gui.addWorkbench" in code

    def test_bridge_server_has_plugin_class(self) -> None:
        """Bridge server.py should have FreecadMCPPlugin class."""
        server_file = ADDON_DIR / "freecad_mcp_bridge" / "server.py"
        code = server_file.read_text()
        assert "class FreecadMCPPlugin" in code

    def test_blocking_bridge_imports_plugin(self) -> None:
        """blocking_bridge.py should import FreecadMCPPlugin."""
        blocking_file = ADDON_DIR / "freecad_mcp_bridge" / "blocking_bridge.py"
        code = blocking_file.read_text()
        assert "FreecadMCPPlugin" in code

    def test_blocking_bridge_has_run_forever(self) -> None:
        """blocking_bridge.py should call run_forever for blocking execution."""
        blocking_file = ADDON_DIR / "freecad_mcp_bridge" / "blocking_bridge.py"
        code = blocking_file.read_text()
        assert "run_forever" in code

    def test_bridge_utils_has_get_running_plugin(self) -> None:
        """bridge_utils.py should have get_running_plugin function."""
        utils_file = ADDON_DIR / "freecad_mcp_bridge" / "bridge_utils.py"
        code = utils_file.read_text()
        assert "def get_running_plugin" in code

    def test_icon_is_valid_svg(self) -> None:
        """The icon should be a valid SVG file."""
        icon_file = ADDON_DIR / "Resources" / "Icons" / "FreecadRobustMCPBridge.svg"
        content = icon_file.read_text()
        assert content.startswith("<?xml") or content.startswith("<svg")
        assert "<svg" in content
        assert "</svg>" in content


class TestAddonIconSize:
    """Tests for addon icon size requirements."""

    def test_icon_size_under_10kb(self) -> None:
        """The icon file should be under 10KB (FreeCAD requirement)."""
        icon_file = ADDON_DIR / "Resources" / "Icons" / "FreecadRobustMCPBridge.svg"
        size_bytes = icon_file.stat().st_size
        size_kb = size_bytes / 1024
        assert size_kb <= 10, f"Icon is {size_kb:.2f}KB, must be <= 10KB"


class TestPackageXml:
    """Tests for package.xml workbench entry."""

    @pytest.fixture
    def package_xml(self) -> str:
        """Load package.xml content."""
        package_file = ADDON_DIR.parent.parent / "package.xml"
        return package_file.read_text()

    def test_workbench_entry_exists(self, package_xml: str) -> None:
        """package.xml should have a workbench entry."""
        assert "<workbench>" in package_xml

    def test_workbench_classname(self, package_xml: str) -> None:
        """package.xml should reference the correct workbench classname."""
        assert "<classname>FreecadRobustMCPBridgeWorkbench</classname>" in package_xml

    def test_workbench_subdirectory(self, package_xml: str) -> None:
        """package.xml should reference the correct subdirectory (new-style)."""
        assert "./freecad/RobustMCPBridge/" in package_xml

    def test_workbench_icon(self, package_xml: str) -> None:
        """package.xml should reference the workbench icon (new-style path)."""
        assert "Resources/Icons/FreecadRobustMCPBridge.svg</icon>" in package_xml
