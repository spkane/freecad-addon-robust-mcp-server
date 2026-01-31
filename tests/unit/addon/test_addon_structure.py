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


@pytest.fixture
def addon_dir() -> Path:
    """Fixture providing the addon directory path."""
    return ADDON_DIR


class TestAddonFileStructure:
    """Tests for addon file structure."""

    def test_addon_directory_exists(self) -> None:
        """The addon directory should exist."""
        assert ADDON_DIR.exists(), f"Addon directory not found: {ADDON_DIR}"
        assert ADDON_DIR.is_dir(), f"Addon path is not a directory: {ADDON_DIR}"

    @pytest.mark.parametrize(
        ("subdir", "description"),
        [
            ("freecad_mcp_bridge", "bridge module"),
            ("Qt", "Qt UI components"),
            (Path("Resources") / "Media", "Resources/Media screenshots"),
        ],
        ids=["bridge_module", "qt_module", "resources_media"],
    )
    def test_subdirectory_exists(self, subdir: str | Path, description: str) -> None:
        """Subdirectories should exist."""
        dir_path = ADDON_DIR / subdir
        assert dir_path.exists(), f"{description} not found: {dir_path}"
        assert dir_path.is_dir(), f"{description} is not a directory: {dir_path}"

    @pytest.mark.parametrize(
        ("filepath", "description"),
        [
            ("__init__.py", "__init__.py (new-style)"),
            ("init_gui.py", "init_gui.py (new-style)"),
            (
                Path("Resources") / "Icons" / "FreecadRobustMCPBridge.svg",
                "workbench icon",
            ),
            (Path("freecad_mcp_bridge") / "__init__.py", "bridge __init__.py"),
            (Path("freecad_mcp_bridge") / "server.py", "bridge server.py"),
            (Path("freecad_mcp_bridge") / "blocking_bridge.py", "blocking_bridge.py"),
            (Path("freecad_mcp_bridge") / "bridge_utils.py", "bridge_utils.py"),
            (Path("Qt") / "__init__.py", "Qt __init__.py"),
            (Path("Qt") / "status_widget.py", "Qt status_widget.py"),
            (Path("Qt") / "preferences_page.py", "Qt preferences_page.py"),
        ],
        ids=[
            "init_py",
            "init_gui_py",
            "icon",
            "bridge_init",
            "bridge_server",
            "blocking_bridge",
            "bridge_utils",
            "qt_init",
            "qt_status_widget",
            "qt_preferences_page",
        ],
    )
    def test_file_exists(self, filepath: str | Path, description: str) -> None:
        """Required files should exist."""
        file_path = ADDON_DIR / filepath
        assert file_path.exists(), f"{description} not found: {file_path}"


class TestAddonPythonSyntax:
    """Tests to verify Python files have valid syntax."""

    @pytest.mark.parametrize(
        "filepath",
        [
            "__init__.py",
            "init_gui.py",
            Path("freecad_mcp_bridge") / "__init__.py",
            Path("freecad_mcp_bridge") / "server.py",
            Path("freecad_mcp_bridge") / "blocking_bridge.py",
            Path("freecad_mcp_bridge") / "bridge_utils.py",
            Path("Qt") / "__init__.py",
            Path("Qt") / "status_widget.py",
            Path("Qt") / "preferences_page.py",
        ],
        ids=[
            "init_py",
            "init_gui_py",
            "bridge_init",
            "bridge_server",
            "blocking_bridge",
            "bridge_utils",
            "qt_init",
            "qt_status_widget",
            "qt_preferences_page",
        ],
    )
    def test_python_file_valid_syntax(self, filepath: str | Path) -> None:
        """Python files should have valid syntax."""
        file_path = ADDON_DIR / filepath
        code = file_path.read_text()
        # This will raise SyntaxError if invalid
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
