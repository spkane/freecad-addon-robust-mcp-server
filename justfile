# FreeCAD MCP Server - Development Workflow Commands
# https://just.systems/
#
# Commands are organized into modules. Run `just` to see top-level commands,
# or `just list-<module>` to see commands in a specific module:
#   just list-mcp           - MCP server commands
#   just list-freecad       - FreeCAD plugin/macro commands
#   just list-install       - Installation commands
#   just list-quality       - Code quality commands
#   just list-testing       - Test commands
#   just list-docker        - Docker build/run commands
#   just list-documentation - Documentation commands
#   just list-dev           - Development utilities
#   just list-release       - Release and tagging commands
#   just list-coderabbit    - AI code review commands
#
# Or use `just --list --list-submodules` to see everything at once.

# Import modules
mod coderabbit 'just/coderabbit.just'
mod dev 'just/dev.just'
mod docker 'just/docker.just'
mod documentation 'just/documentation.just'
mod freecad 'just/freecad.just'
mod install 'just/install.just'
mod mcp 'just/mcp.just'
mod quality 'just/quality.just'
mod release 'just/release.just'
mod testing 'just/testing.just'

# Default recipe - show top-level commands and available modules
default:
    @just --list

# =============================================================================
# Setup & Installation
# =============================================================================

# Full development environment setup (installs deps + pre-commit hooks)
setup: (dev::install-deps) (dev::install-pre-commit)
    @echo "Development environment ready!"

# =============================================================================
# Combined Workflows
# =============================================================================

# Run all quality checks and unit tests (use before committing)
all: (quality::check) (testing::unit)
    @echo "All checks passed!"

# Run all quality checks and ALL tests including integration
all-with-integration: (quality::check) (testing::unit) (testing::integration-freecad)
    @echo "All checks and integration tests passed!"

# Full CI pipeline (pre-commit checks + unit tests with coverage)
ci: (quality::check) (testing::cov)
    @echo "CI pipeline complete!"

# =============================================================================
# Module Listings (use these to explore available commands)
# =============================================================================

# List MCP server commands
list-mcp:
    @just --list mcp

# List FreeCAD plugin and macro commands
list-freecad:
    @just --list freecad

# List installation commands
list-install:
    @just --list install

# List code quality commands
list-quality:
    @just --list quality

# List testing commands
list-testing:
    @just --list testing

# List Docker build/run commands
list-docker:
    @just --list docker

# List documentation commands
list-documentation:
    @just --list documentation

# List development utility commands
list-dev:
    @just --list dev

# List release and tagging commands
list-release:
    @just --list release

# List AI code review commands
list-coderabbit:
    @just --list coderabbit

# List ALL commands from all modules
list-all:
    @just --list --list-submodules
