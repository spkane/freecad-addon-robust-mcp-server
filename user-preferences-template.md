# Claude User Preferences - Development Standards

## Communication Style

- Be direct and concise - avoid unnecessary filler or excessive validation
- Prioritize technical accuracy over agreement - disagree when warranted
- No time estimates - describe what needs to be done, not how long it takes
- No emojis unless I explicitly request them
- When uncertain, investigate before confirming assumptions

---

## Code Quality Standards

### Type Safety

- Use type hints for ALL function signatures
- Use modern Python syntax (3.10+ features like `str | int` union syntax)
- Add `# type: ignore[error-code]` only as last resort with explanation

### Documentation

- Google-style docstrings for all public functions, classes, and modules
- Document Args, Returns, Raises, and include Examples where helpful
- Inline comments only for genuinely complex logic - code should be self-explanatory

### Testing

- ALL code must have tests - unit tests, integration tests, edge cases
- Use descriptive test names: `test_function_name_with_condition_returns_expected`
- Use pytest fixtures and parametrize for clean, DRY tests
- Add regression tests when fixing bugs

### Security

- Never commit secrets, API keys, or credentials
- Use environment variables for sensitive configuration
- Be aware of OWASP top 10 vulnerabilities (XSS, SQL injection, command injection, etc.)
- Fix security issues immediately if introduced

---

## Implementation Approach

### Avoid Over-Engineering

- Only make changes that are directly requested or clearly necessary
- Keep solutions simple and focused
- Don't add features, refactor code, or make "improvements" beyond what was asked
- A bug fix doesn't need surrounding code cleaned up
- Don't add error handling for scenarios that can't happen
- Trust internal code and framework guarantees
- Don't create helpers/utilities/abstractions for one-time operations
- Three similar lines of code is better than a premature abstraction

### Code Hygiene

- NEVER propose changes to code you haven't read first
- Prefer editing existing files over creating new ones
- Don't create documentation files unless explicitly requested
- Remove unused code completely - no backwards-compatibility hacks like `_unused` variables
- When renaming/removing, delete completely rather than leaving commented tombstones

### Pre-commit and Linting

- Run linting/formatting tools after making changes
- Fix ALL reported issues before finishing
- Run pre-commit hooks on files you edited

---

## Preferred Tools and Technologies

### Python Projects

- **Package management**: `uv` (fast, modern, handles virtualenvs)
- **Task runner**: `just` (organized into modules for larger projects)
- **Tool versions**: `mise` (pins Python, uv, just, and other CLI tools)
- **Linting**: `ruff` (replaces flake8, isort, pyupgrade)
- **Formatting**: `ruff format` (replaces black)
- **Type checking**: `mypy`
- **Testing**: `pytest`
- **Pre-commit**: comprehensive hooks including security scanners

### Security Scanning (Multi-Layer)

- **Gitleaks**: Fast regex-based secrets scanning
- **detect-secrets**: Baseline tracking for known/approved secrets
- **TruffleHog**: Verified secrets detection
- **Bandit**: Python security vulnerability scanning
- **Safety**: Dependency vulnerability checking
- **Trivy**: Container/Dockerfile security scanning

### Documentation

- **MkDocs** with Material theme (dark mode default)
- Auto-generated API docs from docstrings using mkdocstrings
- Keep a Changelog format for CHANGELOG.md

### File Conventions

- Use full file extensions: `.yaml` not `.yml`, `.html` not `.htm`
- Maximum line length: 88 characters
- Horizontal rules in markdown: `---` (3 dashes)

---

## Workflow Expectations

### Before Making Changes

- Read and understand existing code before suggesting modifications
- Verify the current state works (tests pass, linting clean)

### After Making Changes

1. Add/update docstrings for all new/modified code
2. Add/update tests for all new/modified functionality
3. Run formatting and fix issues
4. Run linting and fix ALL issues
5. Run type checking and fix ALL issues
6. Run tests - ALL must pass
7. Run pre-commit hooks on edited files

### Version Control

- Work on feature branches, not main/master
- Use conventional commits format
- Update CHANGELOG.md with significant changes
- Follow SemVer 2.0 for versioning

---

## Dependency Management

- Use `>=` minimum version constraints in pyproject.toml (not `==`)
- Lock files (uv.lock) contain exact pinned versions for reproducibility
- Always use the most recent stable releases of libraries and tools
- Regularly check for security vulnerabilities in dependencies

---

## When I Ask You to Do Something

1. Read relevant code first - understand before modifying
2. Make the minimal changes necessary to accomplish the task
3. Run quality checks before finishing
4. Don't do extra "cleanup" or "improvements" unless asked
5. If something is unclear, ask rather than assume
