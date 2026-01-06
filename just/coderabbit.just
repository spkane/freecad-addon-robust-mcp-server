# CodeRabbit CLI commands
# Usage: just coderabbit::install, just coderabbit::review, etc.
#
# CodeRabbit CLI provides AI-powered code reviews in your terminal.
# https://www.coderabbit.ai/cli
#
# IMPORTANT - RATE LIMITS:
#   - Free tier: 1 review per hour
#   - Pro tier: 5 reviews per hour
#   Run reviews manually when needed to avoid hitting limits.
#
# Note: In CI, skip CodeRabbit CLI since the GitHub App handles PR reviews.
# These commands are for local, on-demand development workflow only.

# =============================================================================
# Installation
# =============================================================================

# Install CodeRabbit CLI (prefers Homebrew on macOS/Linux, falls back to official installer)
#
# SECURITY NOTE:
# - Homebrew (preferred): Uses Homebrew's cask verification and signed binaries
#   from https://formulae.brew.sh/cask/coderabbit
# - Fallback installer: Downloads from https://cli.coderabbit.ai/install.sh
#   The installer script is from CodeRabbit's official domain and installs
#   signed binaries. We download to a temp file first for inspection if needed.
#
# Trust decision: CodeRabbit is a well-known code review service with a public
# GitHub organization (https://github.com/coderabbitai). The CLI is optional
# and only used for local development reviews.
install:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Installing CodeRabbit CLI..."

    # Prefer Homebrew if available (macOS and Linux)
    if command -v brew &>/dev/null; then
        echo "Using Homebrew to install CodeRabbit CLI..."
        brew install --cask coderabbit
        echo ""
        echo "CodeRabbit CLI installed via Homebrew."
        echo "Run 'just coderabbit::login' to authenticate."
        exit 0
    fi

    # Fallback: Download installer to temp file first (allows inspection)
    echo "Homebrew not found. Using official installer..."
    INSTALLER_URL="https://cli.coderabbit.ai/install.sh"
    TEMP_SCRIPT=$(mktemp /tmp/coderabbit-install.XXXXXX.sh)

    echo "Downloading installer to: $TEMP_SCRIPT"
    curl -fsSL "$INSTALLER_URL" -o "$TEMP_SCRIPT"

    echo "Installer downloaded. You can inspect it at: $TEMP_SCRIPT"
    echo "Executing installer..."
    sh "$TEMP_SCRIPT"

    # Clean up
    rm -f "$TEMP_SCRIPT"

    echo ""
    echo "CodeRabbit CLI installed. Run 'just coderabbit::login' to authenticate."

# Check if CodeRabbit CLI is installed
check-installed:
    @command -v coderabbit >/dev/null 2>&1 || { echo "CodeRabbit CLI not installed. Run: just coderabbit::install"; exit 1; }
    @coderabbit --version

# =============================================================================
# Authentication
# =============================================================================

# Login to CodeRabbit (opens browser for authentication)
login: check-installed
    coderabbit auth login

# Logout from CodeRabbit
logout: check-installed
    coderabbit auth logout

# Check authentication status
auth-status: check-installed
    coderabbit auth status

# =============================================================================
# Code Reviews
# =============================================================================

# Review staged changes (preserves user's staging state)
review: check-installed
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Reviewing staged changes..."

    # Check if there are staged changes
    if ! git diff --cached --quiet; then
        # Stash unstaged changes, keeping staged changes in working tree
        # This allows coderabbit to review only what's staged
        STASH_OUTPUT=$(git stash push --keep-index -m "coderabbit-review-temp" 2>&1) || true

        # Run the review on staged changes
        coderabbit review --plain --type uncommitted || true

        # Restore unstaged changes if we stashed anything
        if [[ "$STASH_OUTPUT" != "No local changes to save" ]]; then
            git stash pop --quiet || true
        fi
    else
        echo "No staged changes to review. Stage changes with 'git add' first."
        echo "Or use 'just coderabbit::review-all' to review all uncommitted changes."
    fi

# Review staged changes with auto-fix suggestions (preserves user's staging state)
review-fix: check-installed
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Reviewing staged changes with auto-fix..."

    # Check if there are staged changes
    if ! git diff --cached --quiet; then
        # Stash unstaged changes, keeping staged changes in working tree
        STASH_OUTPUT=$(git stash push --keep-index -m "coderabbit-review-temp" 2>&1) || true

        # Run the review with auto-fix on staged changes
        coderabbit review --plain --type uncommitted --auto-fix || true

        # Restore unstaged changes if we stashed anything
        if [[ "$STASH_OUTPUT" != "No local changes to save" ]]; then
            git stash pop --quiet || true
        fi
    else
        echo "No staged changes to review. Stage changes with 'git add' first."
    fi

# Review ALL uncommitted changes (staged + unstaged)
review-all: check-installed
    @echo "Reviewing all uncommitted changes..."
    coderabbit review --plain --type uncommitted

# Review the last commit
review-last: check-installed
    coderabbit review --plain --type committed --base-commit HEAD~1

# Review changes since a specific commit (usage: just coderabbit::review-since abc123)
review-since commit: check-installed
    coderabbit review --plain --type committed --base-commit {{commit}}

# Review changes between current branch and main
review-branch: check-installed
    coderabbit review --plain --type committed --base-commit main

# =============================================================================
# Output Formats
# =============================================================================

# Generate prompt-only output for staged changes (for AI agents like Claude Code)
prompt-only: check-installed
    #!/usr/bin/env bash
    set -euo pipefail

    # Check if there are staged changes
    if ! git diff --cached --quiet; then
        # Stash unstaged changes, keeping staged changes in working tree
        STASH_OUTPUT=$(git stash push --keep-index -m "coderabbit-prompt-temp" 2>&1) || true

        # Generate prompt for staged changes
        coderabbit review --prompt-only --type uncommitted || true

        # Restore unstaged changes if we stashed anything
        if [[ "$STASH_OUTPUT" != "No local changes to save" ]]; then
            git stash pop --quiet || true
        fi
    else
        echo "No staged changes. Stage changes with 'git add' first."
    fi

# Review staged changes with JSON output
review-json: check-installed
    #!/usr/bin/env bash
    set -euo pipefail

    # Check if there are staged changes
    if ! git diff --cached --quiet; then
        # Stash unstaged changes, keeping staged changes in working tree
        STASH_OUTPUT=$(git stash push --keep-index -m "coderabbit-json-temp" 2>&1) || true

        # Run review with JSON output
        coderabbit review --format json --type uncommitted || true

        # Restore unstaged changes if we stashed anything
        if [[ "$STASH_OUTPUT" != "No local changes to save" ]]; then
            git stash pop --quiet || true
        fi
    else
        echo "No staged changes. Stage changes with 'git add' first."
    fi

# =============================================================================
# Configuration
# =============================================================================

# Show CodeRabbit configuration
config-show: check-installed
    coderabbit config show

# Show help for all CodeRabbit commands
help: check-installed
    coderabbit --help
