# CLAUDE.md - AI Assistant Guidelines for This Project

## Project Overview

This is a Python project that provides an MCP (Model Context Protocol) server for FreeCAD integration. It follows strict code quality, security, and documentation standards.

### Critical: Python Version Must Match FreeCAD

**CRITICAL**: This project **MUST** use the same Python version that the current stable FreeCAD release bundles internally. FreeCAD embeds a specific Python version (e.g., `libpython3.11.dylib`), and using a different Python version causes **fatal crashes** (SIGSEGV) due to ABI incompatibility.

Before changing the Python version in `.mise.toml` or `pyproject.toml`:

1. Check which Python version FreeCAD bundles:
   - macOS: `ls /Applications/FreeCAD.app/Contents/Resources/lib/libpython*`
   - Linux: `ls /usr/lib/freecad/lib/libpython*` or check FreeCAD's Python console
1. The Python minor version (e.g., 3.11) **must match exactly**
1. Using Python 3.12+ with FreeCAD that bundles Python 3.11 will crash on `import FreeCAD`

Current requirement: **Python 3.11** (matching FreeCAD 1.0.x bundled Python)

### FreeCAD Connection Modes

This MCP server supports three connection modes. **Embedded mode does NOT work on macOS** due to how FreeCAD's libraries are linked.

| Mode       | Description                                 | Platform Support                  | Testing Level    |
| ---------- | ------------------------------------------- | --------------------------------- | ---------------- |
| `xmlrpc`   | Connects to FreeCAD via XML-RPC (port 9875) | **All platforms** (recommended)   | Full integration |
| `socket`   | Connects via JSON-RPC socket (port 9876)    | **All platforms**                 | Full integration |
| `embedded` | Imports FreeCAD directly into process       | **Linux only** (crashes on macOS) | Unit tests only  |

**Embedded mode testing:** Embedded mode is tested via mocked unit tests in CI. It does not have integration tests with actual FreeCAD because that would require running FreeCAD in-process on Linux CI runners. For production use, prefer `xmlrpc` or `socket` modes which have full integration test coverage.

**Why embedded mode fails on macOS:**
FreeCAD's `FreeCAD.so` library links to `@rpath/libpython3.11.dylib` (FreeCAD's bundled Python). When you try to import it from a different Python interpreter (even the same version), it causes a crash because the Python runtime state is incompatible.

**Recommended setup for macOS/Windows:**

1. Use `xmlrpc` or `socket` mode in your configuration

1. Start FreeCAD and start the MCP bridge:

   - Install the MCP Bridge workbench via Addon Manager, or
   - Use `just run-gui` from the source repository

1. The MCP server will then connect to FreeCAD over the network

---

## Development Environment Setup

### Required Tools (managed via `mise`)

This project uses [`mise`](https://mise.jdx.dev/) for local development tool management. All tool versions are pinned in `.mise.toml`.

```bash
# Install mise via the Official mise installer script (if not already installed)
curl https://mise.run | sh

# Install all project tools
mise install

# Activate mise in your shell (add to .bashrc/.zshrc)
eval "$(mise activate bash)"  # or zsh/fish
```

### Package Management (via `uv`)

This project uses [`uv`](https://docs.astral.sh/uv/) for Python package and virtual environment management.

**CRITICAL**: All Python tools (pytest, ruff, mypy, etc.) are installed in the virtual environment managed by `uv`. You must use `uv run` to execute them.

```bash
# Install dependencies
uv sync --all-extras

# Run any Python tool
uv run pytest              # Run tests
uv run ruff check src      # Run linter
uv run mypy src            # Run type checker
uv run pre-commit run      # Run pre-commit

# Run the project
uv run freecad-mcp
```

**Why `uv run` is required:**

- Tools like `pytest`, `ruff`, `mypy` are NOT installed globally
- They exist only in the project's virtual environment
- Running `pytest` directly will fail with "command not found"
- Always prefix with `uv run` when running Python tools directly

### Safety CLI Account (for Security Scanning)

This project uses [Safety CLI](https://safetycli.com/) for dependency vulnerability scanning. Safety requires a **free account** for the `safety scan` command.

**First-time setup:**

```bash
# Register for a free account (interactive)
uv run safety auth

# Or login if you already have an account
uv run safety auth --login
```

**Note:** The Safety CLI authentication is stored locally and only needs to be done once per machine. If you skip this step, `just check` will show a clear error message with instructions. The `safety` pre-commit hook will also fail with an authentication prompt.

**CI/CD:** Safety runs in CI using the `SAFETY_API_KEY` repository secret. The API key is passed via environment variable to the pre-commit hook.

### CodeRabbit CLI (for AI Code Reviews)

This project supports [CodeRabbit CLI](https://www.coderabbit.ai/cli) for AI-powered code reviews in your terminal. The CLI is optional for local development - the CodeRabbit GitHub App automatically reviews all PRs.

**First-time setup:**

```bash
# Install CodeRabbit CLI
just coderabbit::install

# Authenticate (opens browser)
just coderabbit::login
```

**Usage:**

```bash
# Review staged changes (most common)
just review

# Review with auto-fix suggestions
just coderabbit::review-fix

# Review changes since main branch
just coderabbit::review-branch

# See all available commands
just --list coderabbit
```

**Rate limits:** Free tier allows 1 review per hour. Pro tier allows 5 reviews per hour.

**CI/CD:** The CodeRabbit GitHub App handles PR reviews automatically. The CLI is skipped in CI since it's for local development workflow only.

### Workflow Commands (via `just`)

This project uses [`just`](https://just.systems/) as a command runner. Always prefer `just` commands over raw commands.

Commands are organized into modules for better organization:

```bash
# List all available commands
just --list

# List commands in a specific module
just --list docker
just --list quality
just --list testing
just --list freecad
just --list documentation
just --list coderabbit

# Common shortcut commands (aliases to module commands)
just install      # Install project dependencies
just lint         # Run all linters (quality::lint)
just format       # Format code (quality::format)
just test         # Run tests (testing::unit)
just check        # Run pre-commit checks (quality::check)
just docs         # Build documentation (documentation::build)
just all          # Run all checks and tests

# Module commands (use :: syntax)
just docker::build        # Build Docker image for local architecture
just docker::build-multi  # Build multi-arch image (amd64 + arm64)
just docker::run          # Run Docker container
just quality::secrets     # Run all secrets scanners
just testing::cov         # Run tests with coverage
just freecad::run-gui     # Run FreeCAD GUI with MCP bridge
just documentation::serve # Serve documentation locally
```

#### Just Module Structure

| Module          | Description                         | Key Commands                                 |
| --------------- | ----------------------------------- | -------------------------------------------- |
| `docker`        | Docker build and run commands       | `build`, `build-multi`, `build-push`, `run`  |
| `quality`       | Code quality and linting            | `check`, `lint`, `format`, `secrets`         |
| `testing`       | Test execution                      | `unit`, `cov`, `integration`, `all`          |
| `freecad`       | FreeCAD plugin and macro management | `run-gui`, `run-headless`, `install-*-macro` |
| `documentation` | Documentation building              | `build`, `serve`, `open`                     |
| `coderabbit`    | AI code reviews (local)             | `install`, `login`, `review`, `review-fix`   |

Module files are located in the `just/` directory.

---

## Code Quality Standards

### Pre-commit Hooks

**CRITICAL**: This project uses `pre-commit` for all code quality checks. Before finishing ANY code changes:

1. Run `just check` or `uv run pre-commit run --all-files`
1. Fix ALL issues reported
1. Re-run until all checks pass

Pre-commit runs these checks:

- **Ruff**: Linting and import sorting (replaces flake8, isort, pyupgrade)
- **Ruff Format**: Code formatting (replaces black)
- **MyPy**: Static type checking
- **Bandit**: Security vulnerability scanning
- **Safety**: Dependency vulnerability checking
- **Codespell**: Spell checking in code and docs
- **YAML/TOML/JSON validation**: Config file validation
- **Trailing whitespace and EOF fixes**: File hygiene

### Linting Rules

- Follow PEP 8 style guidelines
- Use type hints for ALL function signatures
- Maximum line length: 88 characters (ruff/black default)
- Use modern Python syntax (3.10+ features encouraged)

### Security Scanning

- Bandit scans for common security issues
- Never commit secrets, API keys, or credentials
- Use environment variables for sensitive configuration
- Safety checks dependencies for known vulnerabilities

### Secrets Detection (Multi-Layer)

This project uses a comprehensive, multi-layer approach to secrets detection:

| Tool               | Purpose                                            | Config File         |
| ------------------ | -------------------------------------------------- | ------------------- |
| **Gitleaks**       | Fast regex-based scanning of files and git history | `.gitleaks.toml`    |
| **detect-secrets** | Baseline tracking for known/approved secrets       | `.secrets.baseline` |
| **TruffleHog**     | Verified secrets (actually tests if they work)     | CLI args            |

```bash
# Run all secrets scanners
just secrets

# Individual scanners
just secrets-gitleaks         # Fast pattern matching
just secrets-gitleaks-history # Scan git history
just secrets-detect           # Check against baseline
just secrets-audit            # Interactive baseline audit
just secrets-trufflehog       # Verified secrets only
```

**Managing False Positives:**

1. **Gitleaks**: Add patterns to `.gitleaks.toml` allowlist section
1. **detect-secrets**: Run `just secrets-audit` to mark false positives in baseline
1. **TruffleHog**: Uses `--only-verified` to minimize false positives

### Markdown Linting

All markdown files are linted for consistency:

```bash
just markdown-lint  # Check markdown files
just markdown-fix   # Auto-fix markdown issues
```

Configuration: `.markdownlint.yaml`

---

## Documentation Requirements

### Code Documentation

**ALL code must be documented** for auto-documentation building:

1. **Module docstrings**: Every Python file must have a module-level docstring explaining its purpose

1. **Class docstrings**: Use Google-style or NumPy-style docstrings

   ```python
   class Example:
       """Short description of the class.

       Longer description if needed, explaining the purpose
       and usage of this class.

       Attributes:
           name: Description of the name attribute.
           value: Description of the value attribute.

       Example:
           >>> obj = Example("test", 42)
           >>> obj.process()
       """
   ```

1. **Function/Method docstrings**: Document all public functions

   ```python
   def calculate_total(items: list[Item], tax_rate: float = 0.0) -> Decimal:
       """Calculate the total price including optional tax.

       Args:
           items: List of Item objects to sum.
           tax_rate: Tax rate as a decimal (e.g., 0.08 for 8%).

       Returns:
           The total price as a Decimal, including tax.

       Raises:
           ValueError: If tax_rate is negative.

       Example:
           >>> items = [Item(price=10), Item(price=20)]
           >>> calculate_total(items, tax_rate=0.1)
           Decimal('33.00')
       """
   ```

1. **Inline comments**: Use sparingly, only for complex logic

### Documentation Building

Documentation is auto-generated using the docstrings. Run:

```bash
just docs        # Build documentation
just docs-serve  # Serve documentation locally
```

---

## Testing Requirements

### Test Coverage

**ALL code must have tests**. Create tests for:

1. **Unit tests**: Test individual functions and methods
1. **Integration tests**: Test component interactions
1. **Edge cases**: Test boundary conditions and error handling
1. **Regression tests**: Add tests when fixing bugs

### Test Structure

```text
tests/
├── __init__.py
├── conftest.py          # Shared fixtures
├── unit/                # Unit tests
│   ├── __init__.py
│   └── test_*.py
├── integration/         # Integration tests
│   ├── __init__.py
│   └── test_*.py
└── fixtures/            # Test data files
```

### Writing Tests

- Use `pytest` as the test framework
- Use descriptive test names: `test_calculate_total_with_empty_list_returns_zero`
- Use fixtures for common test data
- Use parametrize for testing multiple inputs
- Aim for high coverage but prioritize meaningful tests

```python
import pytest
from myproject import calculate_total

class TestCalculateTotal:
    """Tests for the calculate_total function."""

    def test_empty_list_returns_zero(self):
        """Empty item list should return zero total."""
        assert calculate_total([]) == Decimal("0")

    @pytest.mark.parametrize("tax_rate,expected", [
        (0.0, Decimal("100")),
        (0.1, Decimal("110")),
    ])
    def test_tax_calculation(self, sample_items, tax_rate, expected):
        """Tax should be correctly applied to total."""
        result = calculate_total(sample_items, tax_rate=tax_rate)
        assert result == expected
```

### Running Tests

```bash
just test                       # Run all tests
just test-cov                   # Run tests with coverage report
just test-fast                  # Run tests without slow markers
uv run pytest tests/unit/       # Run specific test directory
uv run pytest -k "test_name"    # Run specific test by name
```

---

## Workflow for Code Changes

### Before Making Changes

1. Ensure you're on the latest code
1. Run `just install` to update dependencies
1. Run `just all` to verify clean starting state

### After Making Changes

**MANDATORY CHECKLIST** - Complete ALL steps before finishing:

1. [ ] **Add/update docstrings** for all new/modified code
1. [ ] **Add/update tests** for all new/modified functionality
1. [ ] **Run formatting**: `just format`
1. [ ] **Run linting**: `just lint` - fix ALL issues
1. [ ] **Run type checking**: `just typecheck` - fix ALL issues
1. [ ] **Run security checks**: `just security` - fix ALL issues
1. [ ] **Run tests**: `just test` - ALL tests must pass
1. [ ] **Run pre-commit**: `just check` - ALL checks must pass

### Quick Verification Command

```bash
# Run everything at once - must complete with no errors
just all
```

### Running Pre-commit on Specific Files

**IMPORTANT**: After editing any files, always run pre-commit hooks on those specific files before considering the task complete:

```bash
# Run pre-commit on specific files you edited
uv run pre-commit run --files path/to/file1.py path/to/file2.py

# Or run on all files (slower but comprehensive)
uv run pre-commit run --all-files
```

This catches issues early and ensures code quality standards are met. Never skip this step - fix all reported issues before finishing.

---

## Library and Tool Versions

### Version Policy

- **Always use the most recent stable releases** of all libraries and tools
- **Dependency specification follows Python best practices**:
  - `pyproject.toml` uses `>=` minimum version constraints (e.g., `pydantic>=2.0`)
  - `uv.lock` contains exact pinned versions for reproducible builds
  - This allows the package to work as a library while ensuring reproducibility
  - **Do not change `>=` to `==` in pyproject.toml** - this would break library usability
- Regularly update dependencies with `just update-deps` (updates uv.lock)
- Check for security vulnerabilities with `just security`

### Core Dependencies

Keep these tools at their latest stable versions:

- Python: **3.11** (must match FreeCAD's bundled Python - see "Critical: Python Version Must Match FreeCAD" above)
- Ruff: Latest stable
- MyPy: Latest stable
- Pytest: Latest stable
- Pre-commit: Latest stable

---

## File Structure Conventions

```text
project-root/
├── .mise.toml               # Tool version management
├── .pre-commit-config.yaml  # Pre-commit hook configuration
├── justfile                 # Main task runner (imports modules)
├── just/                    # Just module files
│   ├── docker.just          # Docker build/run commands
│   ├── quality.just         # Code quality commands
│   ├── testing.just         # Test commands
│   ├── freecad.just         # FreeCAD plugin/macro commands
│   └── documentation.just   # Documentation commands
├── pyproject.toml           # Project configuration and dependencies
├── Dockerfile               # Docker image definition
├── src/
│   └── package_name/        # Main package source
│       ├── __init__.py
│       └── *.py
├── tests/                   # Test files
├── docs/                    # Documentation source
└── CLAUDE.md                # This file
```

---

## File Extension Conventions

**Use full file extensions, not DOS-style shortened versions:**

| Correct Extension | Incorrect (DOS-style) |
| ----------------- | --------------------- |
| `.yaml`           | `.yml`                |
| `.jpeg`           | `.jpg`                |
| `.html`           | `.htm`                |
| `.conf`           | (varies)              |

This applies to:

- GitHub workflow files: `.github/workflows/*.yaml`
- GitHub issue templates: `.github/ISSUE_TEMPLATE/*.yaml`
- Dependabot config: `.github/dependabot.yaml`
- MkDocs config: `mkdocs.yaml`
- Any other YAML, JPEG, or similar files

When creating new files, always use the full extension.

---

## Justfile HEREDOC Syntax

**CRITICAL**: When writing heredocs in justfile recipes, the content must be indented to match the recipe body (4 spaces). Just parses non-indented lines as justfile syntax, which causes errors with Python code containing dots (e.g., `sys.path`).

**Important**: Just automatically strips leading indentation from heredoc content when executing. So while you write indented code in the justfile, the output will be properly unindented. Use `just --dry-run recipe-name` to verify the output.

### Correct Pattern

```just
# Recipe with heredoc - content MUST be indented with 4 spaces
my-recipe:
    #!/usr/bin/env bash
    cat > "$FILE" << EOF
    # Python code goes here - indented with 4 spaces
    import sys
    if project_path not in sys.path:
        sys.path.insert(0, project_path)
    EOF
```

When executed, just strips the 4-space indent, producing valid Python:

```python
# Python code goes here - indented with 4 spaces
import sys
if project_path not in sys.path:
    sys.path.insert(0, project_path)
```

### Incorrect Pattern (Will Fail)

```just
# This FAILS - just interprets sys.path as justfile syntax
my-recipe:
    #!/usr/bin/env bash
    cat > "$FILE" << EOF
import sys
if project_path not in sys.path:  # ERROR: Unknown start of token '.'
    sys.path.insert(0, project_path)
EOF
```

### Key Rules

1. **Indent heredoc content with 4 spaces**: Match the recipe body indentation
2. **Indent the EOF marker**: The closing `EOF` must also be indented
3. **Do NOT double-indent**: 4 spaces is correct; 8 spaces would produce indented output
4. **Variable expansion**: `${VAR}` works inside heredocs for bash variables
5. **Use `\\n` for newlines**: In heredoc strings that need literal `\n`, use `\\n`

See the recipes in `just/freecad.just` (e.g., `run-gui`, `run-headless`, `install-cut-macro`) for working examples.

---

## Justfile Working Directory in Modules

**CRITICAL**: When writing recipes in just modules (files in the `just/` directory), be aware that the working directory behavior can be surprising.

### The Problem

When you use `$(pwd)` in a module recipe, it returns the **module's directory** (e.g., `/path/to/project/just/`), NOT the project root. This causes path errors like:

```text
Exception while processing file: /path/to/project/just/src/freecad_mcp/...
```

The path incorrectly includes `just/` because `$(pwd)` returned the module directory.

### The Solution

Use `justfile_directory()` to get the project root. In modules, this function returns the directory of the **main justfile** (project root), not the module file's directory.

```just
# At the top of your module file (e.g., just/freecad.just)
project_root := justfile_directory()

# In recipes, use the variable instead of $(pwd)
my-recipe:
    #!/usr/bin/env bash
    PROJECT_DIR="{{project_root}}"  # Correct: /path/to/project
    # NOT: PROJECT_DIR="$(pwd)"     # Wrong: /path/to/project/just
```

### Key Points

1. **`$(pwd)` in modules**: Returns the module's directory (`just/`), not project root
1. **`justfile_directory()` in modules**: Returns the main justfile's directory (project root)
1. **Always define `project_root`**: Add `project_root := justfile_directory()` at the top of module files
1. **Use `{{project_root}}`**: Reference paths relative to the project root using this variable

### Example Fix

Before (broken):

```just
run-headless:
    #!/usr/bin/env bash
    PROJECT_DIR="$(pwd)"  # Returns /path/to/project/just/ - WRONG!
    SCRIPT="${PROJECT_DIR}/src/script.py"  # /path/to/project/just/src/script.py
```

After (correct):

```just
project_root := justfile_directory()

run-headless:
    #!/usr/bin/env bash
    PROJECT_DIR="{{project_root}}"  # Returns /path/to/project/ - CORRECT!
    SCRIPT="${PROJECT_DIR}/src/script.py"  # /path/to/project/src/script.py
```

---

## FreeCAD GUI vs Headless Mode

FreeCAD can run in two modes:

1. **GUI mode**: Full graphical interface with 3D view, accessed via `FreeCAD.app` or `freecad`
1. **Headless mode**: Console-only, no GUI, accessed via `FreeCADCmd` or `freecadcmd`

### Detecting GUI Availability

**CRITICAL**: Always use `FreeCAD.GuiUp` to check if the GUI is available. **Never** check for Qt/PySide availability as a proxy for GUI mode.

```python
if FreeCAD.GuiUp:
    # GUI is available - can use FreeCADGui, ViewObjects, screenshots
    import FreeCADGui
    view = FreeCADGui.ActiveDocument.ActiveView
else:
    # Headless mode - no GUI features available
    pass
```

### Why NOT to Check for PySide/Qt

**WRONG** - Do not use Qt availability to detect GUI mode:

```python
# WRONG - PySide is available even in headless mode!
try:
    from PySide6 import QtCore
    # This will be True even in headless mode
    is_gui_mode = True
except ImportError:
    is_gui_mode = False
```

**RIGHT** - Use `FreeCAD.GuiUp`:

```python
# CORRECT - GuiUp is False in headless mode
is_gui_mode = FreeCAD.GuiUp
```

**Why this matters**: FreeCAD bundles PySide6 even in headless mode (`freecadcmd`), but without a running Qt event loop:

- Qt timers (`QTimer`) will never fire
- GUI widgets cannot be created or displayed
- Any code relying on Qt events will hang indefinitely

This caused a bug where the MCP bridge queue processor used a `QTimer` in headless mode, resulting in `execute` calls hanging forever because the timer callbacks never ran.

### GUI-Only Features

These features **only work in GUI mode** and will fail or crash in headless mode:

| Feature             | Requires GUI | Alternative in Headless |
| ------------------- | ------------ | ----------------------- |
| `FreeCADGui` module | Yes          | Not available           |
| `obj.ViewObject`    | Yes          | Returns `None`          |
| Screenshots         | Yes          | Not available           |
| Camera/view control | Yes          | Not available           |
| Display mode/color  | Yes          | Not available           |
| Object visibility   | Yes          | Not available           |
| Zoom in/out         | Yes          | Not available           |

### Implementing GUI-Safe Tools

**CRITICAL**: All MCP tools that use GUI features must check `FreeCAD.GuiUp` and return a structured error response instead of crashing.

#### Pattern for GUI-Safe Tools

```python
@mcp.tool()
async def set_object_visibility(object_name: str, visible: bool) -> dict[str, Any]:
    """Set object visibility. Requires GUI mode."""
    bridge = await get_bridge()

    code = f"""
if not FreeCAD.GuiUp:
    _result_ = {{"success": False, "error": "GUI not available - visibility cannot be set in headless mode"}}
else:
    doc = FreeCAD.ActiveDocument
    obj = doc.getObject({object_name!r})
    if obj is None:
        _result_ = {{"success": False, "error": f"Object not found: {object_name!r}"}}
    elif hasattr(obj, "ViewObject") and obj.ViewObject:
        obj.ViewObject.Visibility = {visible}
        _result_ = {{"success": True, "visible": {visible}}}
    else:
        _result_ = {{"success": False, "error": "Object has no ViewObject"}}
"""
    result = await bridge.execute_python(code)
    if result.success and result.result:
        return result.result
    return {{"success": False, "error": result.error_traceback or "Operation failed"}}
```

#### Key Requirements

1. **Check `FreeCAD.GuiUp` first**: Before accessing any GUI features
1. **Return structured errors**: Use `{"success": False, "error": "..."}` format
1. **Never raise exceptions**: Return error dicts instead of raising `ValueError`
1. **Document GUI requirement**: Add "Requires GUI mode" to docstrings

### Tools Updated for GUI Safety

The following tools in `src/freecad_mcp/tools/view.py` check `FreeCAD.GuiUp`:

- `set_object_visibility`
- `set_display_mode`
- `set_object_color`
- `zoom_in` / `zoom_out`
- `set_camera_position`
- `get_screenshot`

### Running FreeCAD in Each Mode

```bash
# GUI mode - with MCP bridge auto-started
just run-gui

# Headless mode - console only
just run-headless

# Or manually:
# GUI: /Applications/FreeCAD.app (macOS) or freecad (Linux)
# Headless: FreeCADCmd or freecadcmd
```

### FreeCAD Plugin Import Restrictions

**CRITICAL**: Code running inside FreeCAD's Python environment cannot import packages that aren't available in FreeCAD's bundled Python (like `mcp`, `pydantic`, etc.).

The `headless_server.py` script in the workbench addon imports the plugin directly from the module file to avoid triggering the `mcp` import:

```python
# CORRECT - import directly from the module file in the same directory
script_dir = str(Path(__file__).resolve().parent)
sys.path.insert(0, script_dir)
from server import FreecadMCPPlugin  # Direct module import
```

This pattern is required because:

1. The MCP SDK is installed in the project's virtualenv, not in FreeCAD's Python
1. Python processes parent package `__init__.py` files when importing nested modules
1. Importing from `freecad_mcp/__init__.py` would trigger MCP SDK imports that don't exist in FreeCAD

---

## Common Issues and Solutions

### Pre-commit Failing

```bash
# Update pre-commit hooks
uv run pre-commit autoupdate

# Clear pre-commit cache
uv run pre-commit clean

# Run specific hook for debugging
uv run pre-commit run <hook-id> --all-files
```

### Type Checking Errors

- Ensure all function parameters and return types have type hints
- Use `typing` module for complex types
- Add `# type: ignore[error-code]` only as last resort with explanation

### Test Failures

- Read the full error message and traceback
- Check if fixtures are properly defined
- Verify test isolation (no shared state between tests)

---

## Pre-commit Hook Requirements

This section documents specific requirements for each pre-commit hook to avoid common issues.

### Ruff Linting

- **UP038**: Use modern union syntax for isinstance: `isinstance(obj, str | int)` NOT `isinstance(obj, (str, int))`
- **Line length**: 88 characters max (but `E501` is ignored for embedded code strings)
- **Import sorting**: Ruff handles this automatically with `ruff --fix`

### MyPy Type Checking

This project uses relaxed mypy settings because FastMCP lacks proper type stubs.

- **Type ignores**: When needed, use specific error codes: `# type: ignore[attr-defined]`
- **FastMCP methods**: `on_startup`, `on_shutdown`, and some `run()` args need type ignores
- **XML-RPC**: `register_function` has overly restrictive types, use `# type: ignore[arg-type]`
- **Lambda captures**: If mypy complains about union types in lambdas, assign to a local variable first

### Codespell

- **Technical terms**: Add legitimate technical terms to `.codespell-ignore-words.txt`
- **FreeCAD API**: "vertexes" is valid FreeCAD terminology (not "vertices")
- **Tool names**: Add tool/library names that look like typos

### Markdownlint (MD035)

- **Horizontal rules**: Must use `---` format (3 dashes)

### Bandit Security

These checks are intentionally skipped in `pyproject.toml`:

- **B101**: Asserts allowed (needed for validation)
- **B102**: `exec()` required for FreeCAD Python execution
- **B110**: `try-except-pass` used for optional cleanup operations
- **B411**: XML-RPC required for FreeCAD compatibility

### detect-secrets

- **False positives**: Add `# pragma: allowlist secret` comment to lines with false positives
- **Baseline updates**: Run `just secrets-audit` to update `.secrets.baseline`

### no-commit-to-branch

- This hook fails when on `main` or `master` branch - this is expected behavior
- Always work on feature branches for actual commits

---

## Changelog Maintenance

**IMPORTANT**: Update `CHANGELOG.md` at the end of any session where files in the repository are modified.

- Follow [Keep a Changelog](https://keepachangelog.com/) format
- Group changes under: Added, Changed, Deprecated, Removed, Fixed, Security
- Include date for each release version
- Document all significant changes, not just code changes

---

## FreeCAD MCP Tools Reference

When Claude Code is connected to the FreeCAD MCP server, the following tools are available for interacting with FreeCAD. Use these tools to control FreeCAD, create/modify objects, and debug issues.

### Discovering Capabilities at Runtime

The MCP server provides a `freecad://capabilities` resource that returns a complete JSON catalog of all available tools, resources, and prompts. This is the authoritative source for what's available.

**IMPORTANT**: When adding new MCP tools or resources, you MUST also update the `freecad://capabilities` resource in `src/freecad_mcp/resources/freecad.py` to keep it in sync. The capabilities resource is defined in the `resource_capabilities()` function.

### Execution & Debugging Tools

| Tool                         | Description                                                                                                                                           |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `execute_python`             | Execute arbitrary Python code in FreeCAD's context. Use `_result_ = value` to return data. Has access to FreeCAD, App, Part, and all FreeCAD modules. |
| `get_console_output`         | **Get recent FreeCAD console output** - useful for debugging macros and seeing error messages. Returns up to N lines of console history.              |
| `get_console_log`            | Alternative console log access with different formatting.                                                                                             |
| `get_freecad_version`        | Get FreeCAD version, build date, Python version, and GUI availability.                                                                                |
| `get_connection_status`      | Check MCP bridge connection status, mode, and latency.                                                                                                |
| `get_mcp_server_environment` | Get MCP server environment info (OS, hostname, Docker detection). Useful for verifying container vs host.                                             |

### Document Management Tools

| Tool                  | Description                                          |
| --------------------- | ---------------------------------------------------- |
| `list_documents`      | List all open FreeCAD documents.                     |
| `get_active_document` | Get information about the currently active document. |
| `create_document`     | Create a new FreeCAD document.                       |
| `open_document`       | Open an existing .FCStd file.                        |
| `save_document`       | Save a document to disk.                             |
| `close_document`      | Close a document.                                    |
| `recompute_document`  | Force recomputation of document features.            |

### Object Creation Tools (Part Workbench)

| Tool              | Description                                                     |
| ----------------- | --------------------------------------------------------------- |
| `list_objects`    | List all objects in a document with their types and properties. |
| `inspect_object`  | Get detailed information about a specific object.               |
| `create_object`   | Create a generic FreeCAD object.                                |
| `create_box`      | Create a Part::Box primitive.                                   |
| `create_cylinder` | Create a Part::Cylinder primitive.                              |
| `create_sphere`   | Create a Part::Sphere primitive.                                |
| `create_cone`     | Create a Part::Cone primitive.                                  |
| `create_torus`    | Create a Part::Torus primitive.                                 |
| `create_wedge`    | Create a Part::Wedge primitive.                                 |
| `create_helix`    | Create a Part::Helix primitive.                                 |

### Object Manipulation Tools

| Tool                | Description                                     |
| ------------------- | ----------------------------------------------- |
| `edit_object`       | Modify object properties.                       |
| `delete_object`     | Delete an object from the document.             |
| `boolean_operation` | Perform union, cut, or intersection operations. |
| `set_placement`     | Set object position and rotation.               |
| `scale_object`      | Scale an object by a factor.                    |
| `rotate_object`     | Rotate an object around an axis.                |
| `copy_object`       | Create a copy of an object.                     |
| `mirror_object`     | Mirror an object across a plane.                |

### Selection Tools

| Tool              | Description                     |
| ----------------- | ------------------------------- |
| `get_selection`   | Get currently selected objects. |
| `set_selection`   | Select specific objects.        |
| `clear_selection` | Clear the current selection.    |

### PartDesign Tools (Parametric Modeling)

| Tool                     | Description                                   |
| ------------------------ | --------------------------------------------- |
| `create_partdesign_body` | Create a new PartDesign::Body container.      |
| `create_sketch`          | Create a sketch attached to a plane or face.  |
| `add_sketch_rectangle`   | Add a rectangle to a sketch.                  |
| `add_sketch_circle`      | Add a circle to a sketch.                     |
| `add_sketch_line`        | Add a line to a sketch.                       |
| `add_sketch_arc`         | Add an arc to a sketch.                       |
| `add_sketch_point`       | Add a point to a sketch (for hole placement). |
| `pad_sketch`             | Extrude a sketch (additive).                  |
| `pocket_sketch`          | Cut into solid using a sketch (subtractive).  |
| `revolution_sketch`      | Revolve a sketch around an axis.              |
| `groove_sketch`          | Cut by revolving a sketch (subtractive).      |
| `create_hole`            | Create parametric holes from sketch points.   |
| `fillet_edges`           | Add fillets (rounded edges).                  |
| `chamfer_edges`          | Add chamfers (beveled edges).                 |
| `loft_sketches`          | Create a loft between multiple sketches.      |
| `sweep_sketch`           | Sweep a sketch along a path.                  |

### Pattern Tools

| Tool               | Description                                |
| ------------------ | ------------------------------------------ |
| `linear_pattern`   | Create linear pattern of features.         |
| `polar_pattern`    | Create polar/circular pattern of features. |
| `mirrored_feature` | Mirror a feature across a plane.           |

### View & GUI Tools (Require GUI Mode)

| Tool                    | Description                                                 |
| ----------------------- | ----------------------------------------------------------- |
| `get_screenshot`        | Capture a screenshot of the 3D view. **Requires GUI mode.** |
| `set_view_angle`        | Set camera to standard views (front, top, isometric, etc.). |
| `fit_all`               | Zoom to fit all objects in view.                            |
| `zoom_in` / `zoom_out`  | Adjust zoom level.                                          |
| `set_camera_position`   | Set exact camera position and orientation.                  |
| `set_object_visibility` | Show/hide objects. **Requires GUI mode.**                   |
| `set_display_mode`      | Set display mode (wireframe, shaded, etc.).                 |
| `set_object_color`      | Change object colors. **Requires GUI mode.**                |
| `list_workbenches`      | List available FreeCAD workbenches.                         |
| `activate_workbench`    | Switch to a different workbench.                            |

### Undo/Redo Tools

| Tool                   | Description                         |
| ---------------------- | ----------------------------------- |
| `undo`                 | Undo the last operation.            |
| `redo`                 | Redo an undone operation.           |
| `get_undo_redo_status` | Get available undo/redo operations. |

### Export/Import Tools

| Tool          | Description                                        |
| ------------- | -------------------------------------------------- |
| `export_step` | Export objects to STEP format.                     |
| `export_stl`  | Export objects to STL format (for 3D printing).    |
| `export_3mf`  | Export objects to 3MF format (modern 3D printing). |
| `export_obj`  | Export objects to OBJ format.                      |
| `export_iges` | Export objects to IGES format.                     |
| `import_step` | Import STEP files.                                 |
| `import_stl`  | Import STL files.                                  |

### Macro Tools

| Tool                         | Description                     |
| ---------------------------- | ------------------------------- |
| `list_macros`                | List available FreeCAD macros.  |
| `run_macro`                  | Execute a macro by name.        |
| `create_macro`               | Create a new macro file.        |
| `read_macro`                 | Read macro source code.         |
| `delete_macro`               | Delete a macro file.            |
| `create_macro_from_template` | Create a macro from a template. |

### Parts Library Tools

| Tool                       | Description                                      |
| -------------------------- | ------------------------------------------------ |
| `list_parts_library`       | List available parts in FreeCAD's parts library. |
| `insert_part_from_library` | Insert a part from the library.                  |

### Example: Debugging a Macro

To debug issues with a macro running in FreeCAD:

```python
# Get recent console output to see errors
console_output = await get_console_output(lines=50)

# Or execute Python to check state
result = await execute_python('''
doc = FreeCAD.ActiveDocument
if doc:
    _result_ = {
        "doc_name": doc.Name,
        "objects": [obj.Name for obj in doc.Objects],
        "errors": [obj.Name for obj in doc.Objects if hasattr(obj, 'isValid') and not obj.isValid()]
    }
else:
    _result_ = {"error": "No active document"}
''')
```

### Example: Creating a Simple Part

```python
# Create a document
await create_document(name="MyPart")

# Create a PartDesign body
await create_partdesign_body(name="Body")

# Create a sketch on the XY plane
await create_sketch(body_name="Body", plane="XY_Plane", sketch_name="Sketch")

# Add a rectangle to the sketch
await add_sketch_rectangle(sketch_name="Sketch", x=-10, y=-10, width=20, height=20)

# Extrude the sketch
await pad_sketch(body_name="Body", sketch_name="Sketch", length=15)

# Add fillets
await fillet_edges(body_name="Body", edges=["Edge1", "Edge2"], radius=2)

# Export to STL
await export_stl(object_names=["Body"], file_path="/tmp/mypart.stl")
```

---

## Summary Checklist

When working on this project, ALWAYS:

- [ ] Use `mise` for tool management
- [ ] Use `just` commands for workflows
- [ ] Write comprehensive docstrings (Google-style)
- [ ] Write tests for all new code
- [ ] Run `just all` before finishing - everything must pass
- [ ] Use latest stable library versions
- [ ] Follow security best practices
- [ ] Update `CHANGELOG.md` with session changes
