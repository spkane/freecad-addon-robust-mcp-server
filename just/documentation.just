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
# Note: The leading `-` suppresses the error when the user interrupts with Ctrl+C
serve:
    -cd {{project_root}} && uv run mkdocs serve

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

# --- Versioned Documentation (mike) ---

# List all deployed documentation versions
list-versions:
    cd {{project_root}} && uv run mike list

# Serve versioned documentation locally (from gh-pages branch)
serve-versioned:
    -cd {{project_root}} && uv run mike serve

# Deploy documentation as "dev" version (for local testing)
# Note: This modifies the gh-pages branch locally
deploy-dev:
    #!/usr/bin/env bash
    cd "{{project_root}}"
    git config user.name "local-dev"
    git config user.email "local@dev"
    uv run mike deploy dev

# Deploy a specific version (for local testing)
# Usage: just documentation::deploy-version 1.0.0
# Note: This modifies the gh-pages branch locally
deploy-version VERSION:
    #!/usr/bin/env bash
    cd "{{project_root}}"
    git config user.name "local-dev"
    git config user.email "local@dev"
    uv run mike deploy "{{VERSION}}"

# Deploy a version and set it as latest (for local testing)
# Usage: just documentation::deploy-latest 1.0.0
deploy-latest VERSION:
    #!/usr/bin/env bash
    cd "{{project_root}}"
    git config user.name "local-dev"
    git config user.email "local@dev"
    uv run mike deploy --update-aliases "{{VERSION}}" latest
    uv run mike set-default latest

# Delete a deployed version (for local cleanup)
# Usage: just documentation::delete-version 1.0.0
delete-version VERSION:
    cd {{project_root}} && uv run mike delete "{{VERSION}}"
