#!/usr/bin/env bash
# Shared helper functions for release management
# Source this file in Just recipes: . ./scripts/release-helpers.sh

# Validate semver version format
# Usage: validate_semver "1.0.0" || exit 1
validate_semver() {
    local version="$1"
    if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
        echo "ERROR: Version '$version' is not valid semver (X.Y.Z or X.Y.Z-prerelease)"
        echo "Examples: 1.0.0, 1.0.0-alpha, 1.0.0-beta.1, 1.0.0-rc.1"
        return 1
    fi
    return 0
}

# Verify we're on the main branch
# Usage: require_main_branch || exit 1
require_main_branch() {
    local current_branch
    current_branch=$(git rev-parse --abbrev-ref HEAD)
    if [[ "$current_branch" != "main" ]]; then
        echo "ERROR: Release tags must be created from the 'main' branch."
        echo "  Current branch: $current_branch"
        echo ""
        echo "Please merge your changes to main first, then run this command from main."
        return 1
    fi
    return 0
}

# Verify local main is up to date with origin/main
# Usage: require_up_to_date || exit 1
require_up_to_date() {
    # Fetch latest from origin (quietly)
    git fetch origin main --quiet 2>/dev/null || {
        echo "WARNING: Could not fetch from origin. Continuing with local state."
        return 0
    }

    local local_sha remote_sha base_sha
    local_sha=$(git rev-parse HEAD)
    remote_sha=$(git rev-parse origin/main 2>/dev/null) || {
        echo "WARNING: Could not find origin/main. Continuing with local state."
        return 0
    }

    if [[ "$local_sha" != "$remote_sha" ]]; then
        # Check if we're behind, ahead, or diverged
        base_sha=$(git merge-base HEAD origin/main 2>/dev/null)

        if [[ "$base_sha" == "$local_sha" ]]; then
            echo "ERROR: Local main is behind origin/main."
            echo "  Please run: git pull origin main"
            return 1
        elif [[ "$base_sha" == "$remote_sha" ]]; then
            echo "ERROR: Local main is ahead of origin/main."
            echo "  Please push your changes first: git push origin main"
            return 1
        else
            echo "ERROR: Local main has diverged from origin/main."
            echo "  Please reconcile the branches before releasing."
            return 1
        fi
    fi
    return 0
}

# Check for uncommitted changes
# Usage: require_clean_tree || exit 1
require_clean_tree() {
    if ! git diff --quiet HEAD 2>/dev/null; then
        echo "ERROR: You have uncommitted changes. Please commit or stash them first."
        return 1
    fi
    return 0
}

# Run all pre-release checks
# Usage: pre_release_checks "1.0.0" || exit 1
pre_release_checks() {
    local version="$1"

    validate_semver "$version" || return 1
    require_main_branch || return 1
    require_up_to_date || return 1
    require_clean_tree || return 1

    return 0
}
