# Code quality commands
# Usage: just quality::check, just quality::format, etc.
#
# Note: Tools installed via mise (gitleaks, markdownlint-cli2, etc.) use `mise exec`.
# Python tools use `uv run`. This ensures commands work even without mise shell activation.

# Project root directory (justfile_directory() returns the main justfile's directory)
project_root := justfile_directory()

# Run all pre-commit checks
check: _check-safety-auth
    uv run pre-commit run --all-files

# Verify Safety CLI authentication (skipped in CI where SAFETY_API_KEY is used)
_check-safety-auth:
    #!/usr/bin/env bash
    # Skip check if SAFETY_API_KEY is set (CI environment)
    if [[ -n "${SAFETY_API_KEY:-}" ]]; then
        exit 0
    fi
    # Check if authenticated locally
    if ! uv run safety auth status >/dev/null 2>&1; then
        echo "ERROR: Safety CLI not authenticated."
        echo ""
        echo "Safety CLI requires a free account for dependency vulnerability scanning."
        echo "Run the following command to authenticate:"
        echo ""
        echo "    uv run safety auth login"
        echo ""
        echo "This only needs to be done once per machine."
        echo "See CLAUDE.md for more details."
        exit 1
    fi

# Format code with ruff
format:
    uv run ruff format {{project_root}}/src {{project_root}}/tests
    uv run ruff check --fix {{project_root}}/src {{project_root}}/tests

# Run linting
lint:
    uv run ruff check {{project_root}}/src {{project_root}}/tests

# Run type checking
typecheck:
    cd {{project_root}} && uv run mypy src

# Run security scanning (code vulnerabilities)
security:
    uv run bandit -c {{project_root}}/pyproject.toml -r {{project_root}}/src
    uv run safety scan --detailed-output

# Run spell checking
spellcheck:
    uv run codespell {{project_root}}/src {{project_root}}/tests {{project_root}}/docs

# =============================================================================
# Secrets Scanning (quality::scan-* commands)
# =============================================================================

# Run all secrets scanners
scan: scan-gitleaks scan-detect scan-trufflehog  # pragma: allowlist secret
    @echo "All secrets scans complete!"

# Run gitleaks secrets scanner (installed via mise)
scan-gitleaks:
    mise exec -- gitleaks detect --source {{project_root}} --config {{project_root}}/.gitleaks.toml --verbose

# Run gitleaks on git history
scan-gitleaks-history:
    mise exec -- gitleaks detect --source {{project_root}} --config {{project_root}}/.gitleaks.toml --verbose --log-opts="--all"

# Run detect-secrets scanner (installed via uv)
scan-detect:
    uv run detect-secrets scan --baseline {{project_root}}/.secrets.baseline

# Audit detect-secrets baseline (interactive)
scan-audit:
    uv run detect-secrets audit {{project_root}}/.secrets.baseline

# Update detect-secrets baseline with new findings
scan-baseline-update:
    uv run detect-secrets scan --baseline {{project_root}}/.secrets.baseline --update

# Run trufflehog for verified secrets (via pre-commit - not installed standalone)
scan-trufflehog:
    uv run pre-commit run trufflehog --all-files

# =============================================================================
# Markdown Linting
# =============================================================================

# Lint all markdown files (markdownlint-cli2 installed via mise)
markdown-lint:
    cd {{project_root}} && mise exec -- markdownlint-cli2 "**/*.md" "#.venv" "#.pytest_cache" "#node_modules" "#site" "#htmlcov"

# Lint and fix markdown files
markdown-fix:
    cd {{project_root}} && mise exec -- markdownlint-cli2 --fix "**/*.md" "#.venv" "#.pytest_cache" "#node_modules" "#site" "#htmlcov"
