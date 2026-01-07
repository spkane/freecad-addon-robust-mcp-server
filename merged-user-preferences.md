# Claude User Preferences

## Communication Style

- Be direct and concise - avoid unnecessary filler or excessive validation
- Prioritize technical accuracy over agreement - disagree when warranted
- No time estimates - describe what needs to be done, not how long it takes
- No emojis unless explicitly requested
- When uncertain, investigate and ask rather than assume

---

## Implementation Philosophy

### Avoid Over-Engineering

- Only make changes that are directly requested or clearly necessary
- Keep solutions simple and focused
- Don't add features, refactor code, or make "improvements" beyond what was asked
- A bug fix doesn't need surrounding code cleaned up
- Don't add error handling for scenarios that can't happen
- Don't create helpers/utilities/abstractions for one-time operations
- Three similar lines of code is better than a premature abstraction

### Code Hygiene

- NEVER propose changes to code you haven't read first
- Prefer editing existing files over creating new ones
- Don't create documentation files unless explicitly requested
- Remove unused code completely - no backwards-compatibility hacks
- When renaming/removing, delete completely rather than leaving commented tombstones

---

## Development Standards

### Languages & Environment

- Primary languages: Go, Rust, Python
- Local tooling: `mise` with `.mise.toml` for managing tool versions
- Task runner: `just` (organized into modules for most projects)
- Deployment: `just` workflows for local dev; GitHub Actions + containers for production
- Always assume production-grade quality standards

### For ALL Code

1. Include/update `.pre-commit-config.yaml` in repo root
2. Fix linting/formatting errors properly rather than disabling rules (but recommend rule changes if overly strict)
3. Include/update GitHub Actions workflows (`.github/workflows/`)
4. Comprehensive error handling - no bare try/catch or ignored errors
5. Structured logging (JSON preferred for services)
6. Health checks for long-running services (HTTP `/health` and `/ready` endpoints)
7. Document environment variables and configuration
8. Docstrings/comments that enable auto-documentation generation
9. Reasonable test coverage for anything beyond standalone scripts

---

## Language-Specific Standards

### Python

**Tooling:** `uv` (package management), `ruff` (lint + format), `mypy` (types), `bandit` + `safety` (security), `pytest` (testing)

**Standards:**

- Type hints for ALL function signatures (mypy-compatible)
- Modern syntax (3.10+ features like `str | int` union syntax)
- Google-style docstrings for public functions, classes, modules
- Use `pyproject.toml` for all config (not setup.py/setup.cfg)
- Use `>=` minimum version constraints, lock files for reproducibility
- `# type: ignore[error-code]` only as last resort with explanation

### Go

**Tooling:** `golangci-lint`, `gofmt`, `go vet`, `gosec` (security)

**Standards:**

- Structured logging (`slog` or `zap`)
- Include `go.mod` and `go.sum`
- Graceful shutdown for services (handle SIGTERM)
- Use contexts for cancellation
- Proper error wrapping and handling

### Rust

**Tooling:** `cargo fmt`, `cargo clippy`, `cargo audit` (security)

**Standards:**

- Use `Result` types properly - no `unwrap()` in production code
- Include `Cargo.toml` and `Cargo.lock`
- Use `tracing`/`log` for structured logging
- Document `unsafe` code blocks if absolutely necessary
- Proper error handling with `thiserror` or `anyhow`

---

## Security

- Secrets scanning in pre-commit: `gitleaks`, `detect-secrets`, and/or `trufflehog`
- No credentials, API keys, tokens, or hardcoded passwords in code
- Security linters per language: `bandit` (Python), `gosec` (Go), `cargo audit` (Rust)
- GitHub Actions: use Secrets for sensitive values, run same checks as pre-commit
- Container security scanning with `trivy`
- Fail CI on security findings

---

## Containers & Kubernetes

### Dockerfiles

- Multi-stage builds (builder + minimal runtime)
- Non-root user
- Minimal base images (distroless, alpine, or scratch where possible)
- `HEALTHCHECK` instruction included
- `.dockerignore` file
- Lint with `hadolint`, scan with `trivy`

### Kubernetes Manifests

- Resource limits AND requests defined
- Liveness and readiness probes configured
- Security context: `runAsNonRoot`, `readOnlyRootFilesystem` where possible
- ConfigMaps for config, Secrets for sensitive data
- Include HPA if relevant

---

## Testing

- Unit tests with >70% coverage target
- Integration tests for services
- Descriptive test names: `test_function_with_condition_returns_expected`
- Use fixtures and parametrize for clean, DRY tests
- Add regression tests when fixing bugs
- Tests must pass in CI before merge

---

## Repository Structure

Standard files:

- `README.md` - setup, testing, deployment instructions
- `.pre-commit-config.yaml` - code quality hooks
- `.github/workflows/` - CI and security scanning
- `.gitignore` - language-appropriate
- `.mise.toml` - tool versions
- `justfile` - task runner (with modules in `just/` for larger projects)
- `CHANGELOG.md` - for significant projects

If containerized: `Dockerfile`, `.dockerignore`
If K8s deployment: `k8s/` directory

### File Conventions

- Full extensions: `.yaml` not `.yml`, `.html` not `.htm`
- Line length: 88 chars (Python), language defaults otherwise
- Markdown horizontal rules: `---`

---

## Workflow

### Before Making Changes

- Read and understand existing code before modifying
- Verify current state works (tests pass, linting clean)

### After Making Changes

1. Add/update docstrings for new/modified code
2. Add/update tests for new/modified functionality
3. Run pre-commit hooks on edited files - fix ALL issues
4. Verify tests pass
5. Verify affected `just` commands still work

### Version Control

- Never commit without explicit permission
- Work on feature branches, not main/master
- Use conventional commits format
- Update CHANGELOG.md with significant changes
- Follow SemVer 2.0 for versioning
