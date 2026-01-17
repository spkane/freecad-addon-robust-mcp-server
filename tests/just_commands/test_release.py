"""Tests for release module just commands.

These tests verify that release commands work correctly.

IMPORTANT: Release commands are tested carefully to avoid:
- Pushing to PyPI/TestPyPI
- Pushing to Docker Hub
- Creating GitHub releases
- Creating unwanted git tags

Testing Strategy:
1. Syntax tests: Use --dry-run for all commands
2. Read-only tests: Safe commands like status, list-tags, latest-versions
3. Version bump tests: Test bump commands (they only modify local files)
4. Tag tests: Use TEST-RELEASE versions and clean up after
5. Skip push tests: Commands that push to remote are only syntax-tested

For integration testing of actual releases, use:
- TestPyPI with `-alpha` suffix
- Docker with `:test-release` tag
- Cleanup verification
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, ClassVar

import pytest

from tests.just_commands.conftest import PROJECT_ROOT

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from tests.just_commands.conftest import JustRunner


class TestReleaseSyntax:
    """Syntax validation tests for release commands."""

    # All release commands for syntax testing
    RELEASE_COMMANDS: ClassVar[list[tuple[str, list[str]]]] = [
        # Version bump commands
        ("bump-workbench", ["0.0.1-test"]),
        # Tag commands (require version argument)
        ("tag-mcp-server", ["0.0.1-test"]),
        ("tag-workbench", ["0.0.1-test"]),
        # Info commands
        ("list-tags", []),
        ("latest-versions", []),
        ("status", []),
        ("changes-since", ["mcp-server"]),
        ("draft-notes", ["mcp-server"]),
        ("extract-changelog", ["mcp-server", "1.0.0"]),
        # Dry-run command
        ("dry-run-tag", ["mcp-server", "0.0.1-test"]),
        # Tag management
        ("delete-tag", ["test-tag-v0.0.1"]),
        # Wiki commands
        ("wiki-update", ["workbench"]),
        ("wiki-show", ["workbench"]),
        ("wiki-diff", ["workbench"]),
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command,args", RELEASE_COMMANDS)
    def test_release_command_syntax(
        self, just: JustRunner, command: str, args: list[str]
    ) -> None:
        """Release command should have valid syntax."""
        result = just.dry_run(f"release::{command}", *args)
        assert result.success, f"Syntax error in 'release::{command}': {result.stderr}"


class TestReleaseReadOnly:
    """Runtime tests for read-only release commands (safe to run)."""

    @pytest.mark.just_runtime
    def test_status_shows_release_info(self, just: JustRunner) -> None:
        """Status command should show release information."""
        result = just.run("release::status", timeout=30)
        assert result.success, f"Status failed: {result.stderr}"
        assert "Release Status" in result.stdout

    @pytest.mark.just_runtime
    def test_list_tags_works(self, just: JustRunner) -> None:
        """list-tags should show release tags."""
        result = just.run("release::list-tags", timeout=30)
        assert result.success, f"list-tags failed: {result.stderr}"
        # Should have section headers
        assert "MCP Server" in result.stdout or "Workbench" in result.stdout

    @pytest.mark.just_runtime
    def test_latest_versions_works(self, just: JustRunner) -> None:
        """latest-versions should show version information."""
        result = just.run("release::latest-versions", timeout=30)
        assert result.success, f"latest-versions failed: {result.stderr}"
        assert "Latest versions" in result.stdout

    @pytest.mark.just_runtime
    @pytest.mark.parametrize(
        "component",
        ["mcp-server", "workbench"],
    )
    def test_changes_since_works(self, just: JustRunner, component: str) -> None:
        """changes-since should work for each component."""
        result = just.run("release::changes-since", component, timeout=30)
        # Command should succeed (exit 0) even if there are no previous releases
        # The "No previous releases" message is informational, not an error
        assert result.success, (
            f"changes-since failed for {component}: "
            f"exit code {result.returncode}, output: {result.output}"
        )

    @pytest.mark.just_runtime
    @pytest.mark.parametrize(
        "component",
        ["mcp-server", "workbench"],
    )
    def test_draft_notes_works(self, just: JustRunner, component: str) -> None:
        """draft-notes should work for each component."""
        result = just.run("release::draft-notes", component, timeout=30)
        assert result.success, f"draft-notes failed: {result.stderr}"
        assert "Draft Release Notes" in result.stdout

    @pytest.mark.just_runtime
    @pytest.mark.parametrize(
        "component,version",
        [
            ("mcp-server", "1.0.0"),
            ("workbench", "1.0.0"),
        ],
    )
    def test_dry_run_tag_shows_info(
        self, just: JustRunner, component: str, version: str
    ) -> None:
        """dry-run-tag should show what would be created."""
        result = just.run("release::dry-run-tag", component, version, timeout=10)
        assert result.success, f"dry-run-tag failed: {result.stderr}"
        assert "Would create tag" in result.stdout

    @pytest.mark.just_runtime
    def test_wiki_show_works(self, just: JustRunner) -> None:
        """wiki-show should display wiki source content."""
        result = just.run("release::wiki-show", "workbench", timeout=10)
        assert result.success, f"wiki-show failed: {result.stderr}"
        assert "Wiki Source" in result.stdout


class TestReleaseBumpCommands:
    """Tests for version bump commands.

    These commands modify local files but don't push anywhere.
    We test them but restore files afterward.
    """

    @pytest.fixture
    def backup_and_restore_files(
        self,
    ) -> Generator[None, None, None]:
        """Backup files before bump tests and restore after."""
        # Files that bump commands modify
        files_to_backup = [
            # Workbench files
            PROJECT_ROOT
            / "addon/FreecadRobustMCPBridge/freecad_mcp_bridge/__init__.py",
            PROJECT_ROOT / "addon/FreecadRobustMCPBridge/wiki-source.txt",
            PROJECT_ROOT / "package.xml",
        ]

        backups: dict[Path, str] = {}
        for file_path in files_to_backup:
            if file_path.exists():
                backups[file_path] = file_path.read_text(encoding="utf-8")

        yield

        # Restore all files
        for file_path, content in backups.items():
            file_path.write_text(content, encoding="utf-8")

    @pytest.mark.just_runtime
    @pytest.mark.just_release
    def test_bump_workbench_modifies_files(
        self, just: JustRunner, backup_and_restore_files: None
    ) -> None:
        """bump-workbench should modify version files."""
        result = just.run("release::bump-workbench", "99.99.99-test", timeout=30)
        assert result.success, f"bump-workbench failed: {result.stderr}"
        assert "Version bump complete" in result.stdout

        # Verify version was updated
        init_file = (
            PROJECT_ROOT / "addon/FreecadRobustMCPBridge/freecad_mcp_bridge/__init__.py"
        )
        content = init_file.read_text()
        assert "99.99.99-test" in content


class TestReleaseTagCommands:
    """Tests for tag creation commands.

    IMPORTANT: These tests create and clean up test tags.
    They use special test versions to avoid conflicts with real releases.

    Tag naming: *-test-release-v0.0.0-test-XXXXXX
    Where XXXXXX is a random suffix to avoid conflicts.
    """

    @pytest.fixture
    def test_tag_prefix(self) -> str:
        """Generate a unique test tag prefix."""
        import random
        import string

        # S311: Random is fine for test fixture naming, not crypto
        suffix = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=6)  # noqa: S311
        )
        return f"test-release-{suffix}"

    @pytest.mark.just_runtime
    @pytest.mark.just_release
    @pytest.mark.slow
    def test_tag_commands_require_clean_working_tree(self, just: JustRunner) -> None:
        """Tag commands should fail if working tree is dirty.

        We don't actually create tags here, just verify the validation.
        """
        # Create a temporary dirty file
        test_file = PROJECT_ROOT / ".test-dirty-file"
        try:
            test_file.write_text("test")
            # S603, S607: git is a well-known command, safe in test context
            subprocess.run(  # noqa: S603
                ["git", "add", str(test_file)],  # noqa: S607
                cwd=PROJECT_ROOT,
                capture_output=True,
                check=False,
            )

            # Tag commands should fail due to uncommitted changes
            # Use input to respond 'n' to confirmation prompt
            result = just.run(
                "release::tag-mcp-server",
                "0.0.1-test",
                timeout=10,
                input_text="n\n",
            )
            # Should fail before even asking for confirmation
            assert "uncommitted changes" in result.output.lower()

        finally:
            # Cleanup - S603, S607: git is a well-known command, safe in test context
            subprocess.run(  # noqa: S603
                ["git", "reset", "HEAD", str(test_file)],  # noqa: S607
                cwd=PROJECT_ROOT,
                capture_output=True,
                check=False,
            )
            test_file.unlink(missing_ok=True)

    @pytest.mark.just_runtime
    @pytest.mark.just_release
    def test_tag_commands_validate_version_format(self, just: JustRunner) -> None:
        """Tag commands should validate semver format."""
        # Invalid version format
        result = just.run(
            "release::tag-mcp-server",
            "invalid-version",
            timeout=10,
            input_text="n\n",
        )
        assert not result.success
        assert "not valid semver" in result.output.lower()


class TestReleaseValidation:
    """Tests to validate release command behavior without side effects."""

    @pytest.mark.just_runtime
    def test_delete_tag_requires_confirmation(self, just: JustRunner) -> None:
        """delete-tag should require confirmation."""
        result = just.run(
            "release::delete-tag",
            "nonexistent-tag-12345",
            timeout=10,
            input_text="n\n",
        )
        # Should abort when user says 'n'
        assert "Aborted" in result.output or "not found" in result.output.lower()

    @pytest.mark.just_runtime
    @pytest.mark.parametrize(
        "component",
        [
            "mcp-server",
            "server",
            "workbench",
        ],
    )
    def test_changes_since_component_aliases(
        self, just: JustRunner, component: str
    ) -> None:
        """changes-since should accept various component aliases."""
        result = just.run("release::changes-since", component, timeout=30)
        # Should not fail with "Unknown component"
        assert "Unknown component" not in result.output

    @pytest.mark.just_runtime
    @pytest.mark.parametrize(
        "version",
        [
            "1.0.0",
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-rc.1",
        ],
    )
    def test_dry_run_accepts_valid_versions(
        self, just: JustRunner, version: str
    ) -> None:
        """dry-run-tag should accept valid semver versions."""
        result = just.run("release::dry-run-tag", "mcp-server", version, timeout=10)
        assert result.success, f"dry-run-tag rejected valid version {version}"
        assert "Would create tag" in result.stdout

    @pytest.mark.just_runtime
    @pytest.mark.parametrize(
        "version",
        ["invalid", "1.0", "1", "v1.0.0", "1.0.0.0"],
    )
    def test_dry_run_rejects_invalid_versions(
        self, just: JustRunner, version: str
    ) -> None:
        """dry-run-tag should reject invalid versions."""
        result = just.run("release::dry-run-tag", "mcp-server", version, timeout=10)
        assert not result.success
        assert "Invalid version format" in result.output
