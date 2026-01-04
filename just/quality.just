# Code quality commands
# Usage: just quality::check, just quality::format, etc.

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
    uv pip list --format=freeze | uv run safety check --stdin

# Run spell checking
spellcheck:
    uv run codespell src tests docs

# =============================================================================
# Secrets Scanning
# =============================================================================

# Run all secrets scanners
secrets: secrets-gitleaks secrets-detect secrets-trufflehog  # pragma: allowlist secret
    @echo "All secrets scans complete!"

# Run gitleaks secrets scanner
secrets-gitleaks:
    uv run gitleaks detect --config .gitleaks.toml --verbose

# Run gitleaks on git history
secrets-gitleaks-history:
    uv run gitleaks detect --config .gitleaks.toml --verbose --log-opts="--all"

# Run detect-secrets scanner
secrets-detect:
    uv run detect-secrets scan --baseline .secrets.baseline

# Audit detect-secrets baseline (interactive)
secrets-audit:
    uv run detect-secrets audit .secrets.baseline

# Update detect-secrets baseline with new findings
secrets-baseline-update:
    uv run detect-secrets scan --baseline .secrets.baseline --update

# Run trufflehog for verified secrets
secrets-trufflehog:
    uv run trufflehog filesystem . --no-update --only-verified

# Run trufflehog on git history
secrets-trufflehog-history:
    uv run trufflehog git file://. --no-update --only-verified

# =============================================================================
# Markdown Linting
# =============================================================================

# Lint all markdown files
markdown-lint:
    uv run markdownlint-cli2 "**/*.md"

# Lint and fix markdown files
markdown-fix:
    uv run markdownlint-cli2 --fix "**/*.md"

# Format markdown files with mdformat
markdown-format:
    uv run mdformat docs/*.md README.md ARCHITECTURE-MCP.md CLAUDE.md
