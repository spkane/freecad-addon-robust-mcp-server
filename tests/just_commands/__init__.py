"""Just command test suite.

This test suite validates all just commands in the project to catch
syntax errors, missing dependencies, and runtime failures early.

Test Categories:
- Syntax tests: Verify just can parse the command (--dry-run)
- Runtime tests: Actually execute commands and verify behavior
- Release tests: Special tests for release commands with cleanup

Usage:
    uv run pytest tests/just_commands/                    # Run all just command tests
    uv run pytest tests/just_commands/ -m just_syntax    # Only syntax checks
    uv run pytest tests/just_commands/ -m just_runtime   # Only runtime tests
    uv run pytest tests/just_commands/ -m just_release   # Only release tests (with cleanup)

Maintenance:
    When adding or modifying just commands, update the corresponding test file.
    See CLAUDE.md section "Just Command Testing" for details.
"""
