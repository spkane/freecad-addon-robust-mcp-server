# Documentation commands
# Usage: just documentation::build, just documentation::serve, etc.

# Project root directory (justfile_directory() returns the main justfile's directory)
project_root := justfile_directory()

# Build documentation
build:
    cd {{project_root}} && uv run mkdocs build

# Build documentation with strict mode (fails on warnings, for CI)
build-strict:
    cd {{project_root}} && uv run mkdocs build --strict

# Serve documentation locally
serve:
    cd {{project_root}} && uv run mkdocs serve

# Build and open documentation in browser
open:
    #!/usr/bin/env bash
    cd "{{project_root}}"
    uv run mkdocs build
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "{{project_root}}/site/index.html"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "{{project_root}}/site/index.html"
    else
        echo "Documentation built at: {{project_root}}/site/index.html"
    fi
