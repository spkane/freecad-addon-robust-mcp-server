# Code quality commands
# Usage: just quality::check, just quality::format, etc.
#
# Note: Tools installed via mise (gitleaks, markdownlint-cli2, etc.) use `mise exec`.
# Python tools use `uv run`. This ensures commands work even without mise shell activation.

# Run all pre-commit checks
check:
    uv run pre-commit run --all-files

# Format code with ruff
format:
    uv run ruff format src tests
    uv run ruff check --fix src tests

# Run linting
lint:
    uv run ruff check src tests

# Run type checking
typecheck:
    uv run mypy src

# Run security scanning (code vulnerabilities)
security:
    uv run bandit -c pyproject.toml -r src
    uv run safety scan --detailed-output

# Run spell checking
spellcheck:
    uv run codespell src tests docs

# =============================================================================
# Secrets Scanning
# =============================================================================

# Run all secrets scanners
secrets: secrets-gitleaks secrets-detect secrets-trufflehog  # pragma: allowlist secret
    @echo "All secrets scans complete!"

# Run gitleaks secrets scanner (installed via mise)
secrets-gitleaks:
    mise exec -- gitleaks detect --config .gitleaks.toml --verbose

# Run gitleaks on git history
secrets-gitleaks-history:
    mise exec -- gitleaks detect --config .gitleaks.toml --verbose --log-opts="--all"

# Run detect-secrets scanner (installed via uv)
secrets-detect:
    uv run detect-secrets scan --baseline .secrets.baseline

# Audit detect-secrets baseline (interactive)
secrets-audit:
    uv run detect-secrets audit .secrets.baseline

# Update detect-secrets baseline with new findings
secrets-baseline-update:
    uv run detect-secrets scan --baseline .secrets.baseline --update

# Run trufflehog for verified secrets (via pre-commit - not installed standalone)
secrets-trufflehog:
    uv run pre-commit run trufflehog --all-files

# =============================================================================
# Markdown Linting
# =============================================================================

# Lint all markdown files (markdownlint-cli2 installed via mise)
markdown-lint:
    mise exec -- markdownlint-cli2 "**/*.md"

# Lint and fix markdown files
markdown-fix:
    mise exec -- markdownlint-cli2 --fix "**/*.md"
