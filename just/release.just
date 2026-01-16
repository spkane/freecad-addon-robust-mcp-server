# Release commands for component-specific versioning
# Usage: just release::bump-workbench 1.0.0, just release::tag-workbench 1.0.0, etc.
#
# Release Process (two steps):
#   1. Bump version: just release::bump-<component> <version>
#      - Updates all version strings in source files
#      - Commit the changes: git add -A && git commit -m "chore: bump <component> to <version>"
#   2. Create tag: just release::tag-<component> <version>
#      - Verifies versions match the tag
#      - Creates and pushes the git tag
#      - Tag triggers GitHub Actions workflow
#
# This project uses component-specific git tags for releases:
#   - robust-mcp-server-vX.Y.Z      (triggers PyPI, Docker, GitHub release)
#   - robust-mcp-workbench-vX.Y.Z   (triggers workbench archive release)
#   - macro-cut-object-for-magnets-vX.Y.Z
#   - macro-multi-export-vX.Y.Z
#
# Version Format (SemVer 2.0):
#   - X.Y.Z           - Stable release
#   - X.Y.Z-alpha     - Alpha (TestPyPI only)
#   - X.Y.Z-alpha.N   - Alpha with number (TestPyPI only)
#   - X.Y.Z-beta      - Beta (TestPyPI only)
#   - X.Y.Z-beta.N    - Beta with number (TestPyPI only)
#   - X.Y.Z-rc.N      - Release candidate (TestPyPI only)

# Project root directory
project_root := justfile_directory()

# =============================================================================
# Version Bump Commands
# =============================================================================

# Bump the Robust MCP Bridge workbench version in all source files
bump-workbench version:
    #!/usr/bin/env bash
    set -euo pipefail

    VERSION="{{version}}"
    TODAY=$(date +%Y-%m-%d)

    # Validate version format (SemVer 2.0)
    if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
        echo "ERROR: Version '$VERSION' is not valid semver (X.Y.Z or X.Y.Z-prerelease)"
        echo "Examples: 1.0.0, 1.0.0-alpha, 1.0.0-beta.1, 1.0.0-rc.1"
        exit 1
    fi

    echo "Bumping Robust MCP Bridge Workbench to version: $VERSION (date: $TODAY)"
    echo ""

    # Update __version__ in the bridge module's __init__.py
    INIT_FILE="{{project_root}}/addon/FreecadRobustMCPBridge/freecad_mcp_bridge/__init__.py"
    if [ -f "$INIT_FILE" ]; then
        sed 's/^__version__ = "[^"]*"/__version__ = "'"$VERSION"'"/' "$INIT_FILE" > "$INIT_FILE.tmp" && mv "$INIT_FILE.tmp" "$INIT_FILE"
        echo "Updated $INIT_FILE:"
        grep "__version__" "$INIT_FILE"
    else
        echo "ERROR: File not found: $INIT_FILE"
        exit 1
    fi

    # Update wiki-source.txt version and date
    WIKI_FILE="{{project_root}}/addon/FreecadRobustMCPBridge/wiki-source.txt"
    if [ -f "$WIKI_FILE" ]; then
        sed "s/|Version=.*/|Version=${VERSION}/" "$WIKI_FILE" > "$WIKI_FILE.tmp" && mv "$WIKI_FILE.tmp" "$WIKI_FILE"
        sed "s/|Date=.*/|Date=${TODAY}/" "$WIKI_FILE" > "$WIKI_FILE.tmp" && mv "$WIKI_FILE.tmp" "$WIKI_FILE"
        echo ""
        echo "Updated $WIKI_FILE:"
        grep -E "^\|Version=|\|Date=" "$WIKI_FILE"
    else
        echo "WARNING: File not found: $WIKI_FILE"
    fi

    # Update the workbench version in package.xml
    PACKAGE_XML="{{project_root}}/package.xml"
    if [ -f "$PACKAGE_XML" ]; then
        # Use awk for precise XML editing within the workbench section
        awk -v version="$VERSION" -v date="$TODAY" '
            /<workbench>/ { in_workbench=1 }
            /<\/workbench>/ { in_workbench=0 }
            in_workbench && /<version>/ {
                gsub(/<version>[^<]*<\/version>/, "<version>" version "</version>")
            }
            in_workbench && /<date>/ {
                gsub(/<date>[^<]*<\/date>/, "<date>" date "</date>")
            }
            { print }
        ' "$PACKAGE_XML" > "$PACKAGE_XML.tmp" && mv "$PACKAGE_XML.tmp" "$PACKAGE_XML"
        echo ""
        echo "Updated $PACKAGE_XML (workbench section):"
        grep -A3 '<workbench>' "$PACKAGE_XML" | head -5
    else
        echo "ERROR: File not found: $PACKAGE_XML"
        exit 1
    fi

    echo ""
    echo "Version bump complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Review changes: git diff"
    echo "  2. Commit: git add -A && git commit -m 'chore: bump workbench to $VERSION'"
    echo "  3. Tag and release: just release::tag-workbench $VERSION"

# Private helper recipe for bumping macro versions
# Parameters: macro_dir, macro_name, macro_file_basename, readme_basename, tag_command, version
[private]
_bump-macro macro_dir macro_name macro_file_basename readme_basename tag_command version:
    #!/usr/bin/env bash
    set -euo pipefail

    VERSION="{{version}}"
    TODAY=$(date +%Y-%m-%d)
    MACRO_DIR="{{project_root}}/macros/{{macro_dir}}"
    MACRO_NAME="{{macro_name}}"

    # Validate version format (SemVer 2.0)
    if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
        echo "ERROR: Version '$VERSION' is not valid semver (X.Y.Z or X.Y.Z-prerelease)"
        echo "Examples: 1.0.0, 1.0.0-alpha, 1.0.0-beta.1, 1.0.0-rc.1"
        exit 1
    fi

    echo "Bumping $MACRO_NAME Macro to version: $VERSION (date: $TODAY)"
    echo ""

    # Update __Version__ and __Date__ in .FCMacro file
    MACRO_FILE="$MACRO_DIR/{{macro_file_basename}}"
    if [ -f "$MACRO_FILE" ]; then
        sed "s/^__Version__ = [\"'].*[\"']/__Version__ = \"${VERSION}\"/" "$MACRO_FILE" > "$MACRO_FILE.tmp" && mv "$MACRO_FILE.tmp" "$MACRO_FILE"
        sed "s/^__Date__ = [\"'].*[\"']/__Date__ = \"${TODAY}\"/" "$MACRO_FILE" > "$MACRO_FILE.tmp" && mv "$MACRO_FILE.tmp" "$MACRO_FILE"
        echo "Updated $MACRO_FILE:"
        grep -E "^__(Version|Date)__" "$MACRO_FILE"
    else
        echo "ERROR: File not found: $MACRO_FILE"
        exit 1
    fi

    # Update README version line
    README_FILE="$MACRO_DIR/{{readme_basename}}"
    if [ -f "$README_FILE" ]; then
        sed "s/^\*\*Version:\*\* .*/\*\*Version:\*\* ${VERSION}/" "$README_FILE" > "$README_FILE.tmp" && mv "$README_FILE.tmp" "$README_FILE"
        echo ""
        echo "Updated $README_FILE:"
        grep "Version:" "$README_FILE" | head -1
    else
        echo "WARNING: File not found: $README_FILE"
    fi

    # Update wiki-source.txt version and date
    WIKI_FILE="$MACRO_DIR/wiki-source.txt"
    if [ -f "$WIKI_FILE" ]; then
        sed "s/|Version=.*/|Version=${VERSION}/" "$WIKI_FILE" > "$WIKI_FILE.tmp" && mv "$WIKI_FILE.tmp" "$WIKI_FILE"
        sed "s/|Date=.*/|Date=${TODAY}/" "$WIKI_FILE" > "$WIKI_FILE.tmp" && mv "$WIKI_FILE.tmp" "$WIKI_FILE"
        echo ""
        echo "Updated $WIKI_FILE:"
        grep -E "^\|Version=|\|Date=" "$WIKI_FILE"
    else
        echo "WARNING: File not found: $WIKI_FILE"
    fi

    # Update package.xml macro version
    PACKAGE_XML="{{project_root}}/package.xml"
    if [ -f "$PACKAGE_XML" ]; then
        awk -v name="$MACRO_NAME" -v version="$VERSION" -v date="$TODAY" '
            /<macro>/ { in_macro=1 }
            /<\/macro>/ { in_macro=0; found_name=0 }
            in_macro && /<name>.*<\/name>/ {
                if (index($0, name) > 0) found_name=1
            }
            in_macro && found_name && /<version>/ {
                gsub(/<version>[^<]*<\/version>/, "<version>" version "</version>")
            }
            in_macro && found_name && /<date>/ {
                gsub(/<date>[^<]*<\/date>/, "<date>" date "</date>")
            }
            { print }
        ' "$PACKAGE_XML" > "$PACKAGE_XML.tmp" && mv "$PACKAGE_XML.tmp" "$PACKAGE_XML"
        echo ""
        echo "Updated $PACKAGE_XML ($MACRO_NAME section):"
        grep -A4 ">$MACRO_NAME<" "$PACKAGE_XML"
    else
        echo "ERROR: File not found: $PACKAGE_XML"
        exit 1
    fi

    echo ""
    echo "Version bump complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Review changes: git diff"
    echo "  2. Commit: git add -A && git commit -m 'chore: bump $MACRO_NAME macro to $VERSION'"
    echo "  3. Tag and release: just release::{{tag_command}} $VERSION"

# Bump the Cut Object for Magnets macro version in all source files
bump-macro-magnets version: (_bump-macro "Cut_Object_for_Magnets" "Cut Object for Magnets" "CutObjectForMagnets.FCMacro" "README-CutObjectForMagnets.md" "tag-macro-magnets" version)

# Bump the Multi Export macro version in all source files
bump-macro-export version: (_bump-macro "Multi_Export" "Multi Export" "MultiExport.FCMacro" "README-MultiExport.md" "tag-macro-export" version)

# =============================================================================
# Tag Creation Commands
# =============================================================================

# Create and push a release tag for the Robust MCP Server (triggers PyPI + Docker release)
# Note: Robust MCP Server uses setuptools-scm, so version is derived from git tag at build time
tag-mcp-server version:
    #!/usr/bin/env bash
    set -euo pipefail

    # Source shared release helper functions
    . "{{project_root}}/scripts/release-helpers.sh"

    TAG="robust-mcp-server-v{{version}}"

    # Run all pre-release checks (version format, main branch, up-to-date, clean tree)
    pre_release_checks "{{version}}" || exit 1

    echo "Creating tag: $TAG"
    echo ""
    echo "This will trigger:"
    echo "  - PyPI release (stable) or TestPyPI (alpha/beta/rc)"
    echo "  - Docker Hub release"
    echo "  - GitHub release with wheel and tar.gz"
    echo ""
    read -p "Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi

    git tag -a "$TAG" -m "Release Robust MCP Server v{{version}}"
    git push origin "$TAG"
    echo ""
    echo "Tag $TAG created and pushed!"
    echo "Watch the release at: https://github.com/spkane/freecad-robust-mcp-and-more/actions"

# Create and push a release tag for the Robust MCP Bridge workbench
tag-workbench version:
    #!/usr/bin/env bash
    set -euo pipefail

    # Source shared release helper functions
    . "{{project_root}}/scripts/release-helpers.sh"

    TAG="robust-mcp-workbench-v{{version}}"
    VERSION="{{version}}"

    # Run all pre-release checks (version format, main branch, up-to-date, clean tree)
    pre_release_checks "$VERSION" || exit 1

    # Verify version in source files matches tag version
    echo "Verifying version in source files..."

    # Check __init__.py
    INIT_FILE="{{project_root}}/addon/FreecadRobustMCPBridge/freecad_mcp_bridge/__init__.py"
    INIT_VERSION=$(grep -o '__version__ = "[^"]*"' "$INIT_FILE" | cut -d'"' -f2)
    if [ "$INIT_VERSION" != "$VERSION" ]; then
        echo "ERROR: Version mismatch in $INIT_FILE"
        echo "  Expected: $VERSION"
        echo "  Found:    $INIT_VERSION"
        echo ""
        echo "Run 'just release::bump-workbench $VERSION' first, then commit the changes."
        exit 1
    fi
    echo "✓ $INIT_FILE: $INIT_VERSION"

    # Check wiki-source.txt
    WIKI_FILE="{{project_root}}/addon/FreecadRobustMCPBridge/wiki-source.txt"
    if [ -f "$WIKI_FILE" ]; then
        WIKI_VERSION=$(grep -o '|Version=[^|]*' "$WIKI_FILE" | cut -d= -f2 | tr -d '\n')
        if [ "$WIKI_VERSION" != "$VERSION" ]; then
            echo "ERROR: Version mismatch in $WIKI_FILE"
            echo "  Expected: $VERSION"
            echo "  Found:    $WIKI_VERSION"
            echo ""
            echo "Run 'just release::bump-workbench $VERSION' first, then commit the changes."
            exit 1
        fi
        echo "✓ $WIKI_FILE: $WIKI_VERSION"
    fi

    # Check package.xml
    PACKAGE_XML="{{project_root}}/package.xml"
    PKG_VERSION=$(awk '/<workbench>/,/<\/workbench>/' "$PACKAGE_XML" | grep -o '<version>[^<]*</version>' | head -1 | sed 's/<[^>]*>//g')
    if [ "$PKG_VERSION" != "$VERSION" ]; then
        echo "ERROR: Version mismatch in $PACKAGE_XML (workbench section)"
        echo "  Expected: $VERSION"
        echo "  Found:    $PKG_VERSION"
        echo ""
        echo "Run 'just release::bump-workbench $VERSION' first, then commit the changes."
        exit 1
    fi
    echo "✓ $PACKAGE_XML (workbench): $PKG_VERSION"

    echo ""
    echo "Version verification passed!"
    echo ""
    echo "Creating tag: $TAG"
    echo ""
    echo "This will trigger:"
    echo "  - GitHub release with workbench archive"
    echo ""
    read -p "Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi

    git tag -a "$TAG" -m "Release Robust MCP Bridge Workbench v{{version}}"
    git push origin "$TAG"
    echo ""
    echo "Tag $TAG created and pushed!"
    echo "Watch the release at: https://github.com/spkane/freecad-robust-mcp-and-more/actions"

# Private helper recipe for tagging macro releases
# Parameters: macro_dir, macro_name, macro_file_basename, tag_prefix, bump_command, tag_message, version
[private]
_tag-macro macro_dir macro_name macro_file_basename tag_prefix bump_command tag_message version:
    #!/usr/bin/env bash
    set -euo pipefail

    # Source shared release helper functions
    . "{{project_root}}/scripts/release-helpers.sh"

    VERSION="{{version}}"
    TAG="{{tag_prefix}}v{{version}}"
    MACRO_DIR="{{project_root}}/macros/{{macro_dir}}"
    MACRO_NAME="{{macro_name}}"

    # Run all pre-release checks (version format, main branch, up-to-date, clean tree)
    pre_release_checks "$VERSION" || exit 1

    # Verify version in source files matches tag version
    echo "Verifying version in source files..."

    # Check .FCMacro file
    MACRO_FILE="$MACRO_DIR/{{macro_file_basename}}"
    MACRO_VERSION=$(grep -o '__Version__ = "[^"]*"' "$MACRO_FILE" | cut -d'"' -f2)
    if [ "$MACRO_VERSION" != "$VERSION" ]; then
        echo "ERROR: Version mismatch in $MACRO_FILE"
        echo "  Expected: $VERSION"
        echo "  Found:    $MACRO_VERSION"
        echo ""
        echo "Run 'just release::{{bump_command}} $VERSION' first, then commit the changes."
        exit 1
    fi
    echo "✓ $MACRO_FILE: $MACRO_VERSION"

    # Check wiki-source.txt
    WIKI_FILE="$MACRO_DIR/wiki-source.txt"
    if [ -f "$WIKI_FILE" ]; then
        WIKI_VERSION=$(grep -o '|Version=[^|]*' "$WIKI_FILE" | cut -d= -f2 | tr -d '\n')
        if [ "$WIKI_VERSION" != "$VERSION" ]; then
            echo "ERROR: Version mismatch in $WIKI_FILE"
            echo "  Expected: $VERSION"
            echo "  Found:    $WIKI_VERSION"
            echo ""
            echo "Run 'just release::{{bump_command}} $VERSION' first, then commit the changes."
            exit 1
        fi
        echo "✓ $WIKI_FILE: $WIKI_VERSION"
    fi

    # Check package.xml
    PACKAGE_XML="{{project_root}}/package.xml"
    PKG_VERSION=$(awk -v name="$MACRO_NAME" '
        /<macro>/ { in_macro=1 }
        /<\/macro>/ { in_macro=0; found_name=0 }
        in_macro && index($0, name) > 0 { found_name=1 }
        in_macro && found_name && /<version>/ {
            gsub(/.*<version>/, ""); gsub(/<\/version>.*/, ""); print; exit
        }
    ' "$PACKAGE_XML")
    if [ "$PKG_VERSION" != "$VERSION" ]; then
        echo "ERROR: Version mismatch in $PACKAGE_XML ($MACRO_NAME section)"
        echo "  Expected: $VERSION"
        echo "  Found:    $PKG_VERSION"
        echo ""
        echo "Run 'just release::{{bump_command}} $VERSION' first, then commit the changes."
        exit 1
    fi

    echo "Version verification passed!"
    echo ""
    echo "Creating tag: $TAG"
    echo ""
    echo "This will trigger:"
    echo "  - GitHub release with macro archive"
    echo ""
    read -p "Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi

    git tag -a "$TAG" -m "{{tag_message}} v{{version}}"
    git push origin "$TAG"
    echo ""
    echo "Tag $TAG created and pushed!"
    echo "Watch the release at: https://github.com/spkane/freecad-robust-mcp-and-more/actions"

# Create and push a release tag for the Cut Object for Magnets macro
tag-macro-magnets version: (_tag-macro "Cut_Object_for_Magnets" "Cut Object for Magnets" "CutObjectForMagnets.FCMacro" "macro-cut-object-for-magnets-" "bump-macro-magnets" "Release Cut Object for Magnets Macro" version)

# Create and push a release tag for the Multi Export macro
tag-macro-export version: (_tag-macro "Multi_Export" "Multi Export" "MultiExport.FCMacro" "macro-multi-export-" "bump-macro-export" "Release Multi Export Macro" version)

# =============================================================================
# Tag Information Commands
# =============================================================================

# List all release tags grouped by component
list-tags:
    #!/usr/bin/env bash
    echo "=== Robust MCP Server Releases ==="
    git tag -l 'robust-mcp-server-v*' --sort=-v:refname | head -10
    echo ""
    echo "=== Robust MCP Bridge Workbench Releases ==="
    git tag -l 'robust-mcp-workbench-v*' --sort=-v:refname | head -10
    echo ""
    echo "=== Cut Object for Magnets Macro Releases ==="
    git tag -l 'macro-cut-object-for-magnets-v*' --sort=-v:refname | head -10
    echo ""
    echo "=== Multi Export Macro Releases ==="
    git tag -l 'macro-multi-export-v*' --sort=-v:refname | head -10

# Show the latest version of each component
latest-versions:
    #!/usr/bin/env bash
    echo "Latest versions:"
    echo ""
    SERVER_TAG=$(git tag -l 'robust-mcp-server-v*' --sort=-v:refname | head -n1)
    WORKBENCH_TAG=$(git tag -l 'robust-mcp-workbench-v*' --sort=-v:refname | head -n1)
    MAGNETS_TAG=$(git tag -l 'macro-cut-object-for-magnets-v*' --sort=-v:refname | head -n1)
    EXPORT_TAG=$(git tag -l 'macro-multi-export-v*' --sort=-v:refname | head -n1)
    echo "  Robust MCP Server:      ${SERVER_TAG:-none}"
    echo "  MCP Bridge Workbench:   ${WORKBENCH_TAG:-none}"
    echo "  Macro Magnets:   ${MAGNETS_TAG:-none}"
    echo "  Macro Export:    ${EXPORT_TAG:-none}"

# Show commits since the last release of a component
changes-since component:
    #!/usr/bin/env bash
    set -euo pipefail

    case "{{component}}" in
        mcp-server|server)
            PREFIX="robust-mcp-server-v"
            PATHS="src/freecad_mcp pyproject.toml Dockerfile"
            ;;
        workbench)
            PREFIX="robust-mcp-workbench-v"
            PATHS="addon/FreecadRobustMCPBridge"
            ;;
        macro-magnets|magnets)
            PREFIX="macro-cut-object-for-magnets-v"
            PATHS="macros/Cut_Object_for_Magnets"
            ;;
        macro-export|export)
            PREFIX="macro-multi-export-v"
            PATHS="macros/Multi_Export"
            ;;
        *)
            echo "Unknown component: {{component}}"
            echo "Valid: mcp-server, workbench, macro-magnets, macro-export"
            exit 1
            ;;
    esac

    LATEST_TAG=$(git tag -l "${PREFIX}*" --sort=-v:refname | head -1)

    if [ -z "$LATEST_TAG" ]; then
        echo "No previous releases found for {{component}}"
        echo "Showing all commits for relevant paths:"
        git log --oneline -- $PATHS | head -20
    else
        echo "Changes since $LATEST_TAG:"
        echo ""
        git log --oneline "$LATEST_TAG"..HEAD -- $PATHS
    fi

# =============================================================================
# Tag Management
# =============================================================================

# Delete a release tag (local and remote)
delete-tag tag:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "This will delete the tag '{{tag}}' both locally and from the remote."
    echo ""
    read -p "Are you sure? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi

    # Delete local tag
    if git tag -l '{{tag}}' | grep -F -q '{{tag}}'; then
        git tag -d '{{tag}}'
        echo "Deleted local tag: {{tag}}"
    else
        echo "Local tag '{{tag}}' not found (may already be deleted)"
    fi

    # Delete remote tag
    if git ls-remote --tags origin | grep -F -q 'refs/tags/{{tag}}'; then
        git push origin --delete '{{tag}}'
        echo "Deleted remote tag: {{tag}}"
    else
        echo "Remote tag '{{tag}}' not found (may already be deleted)"
    fi

    echo ""
    echo "Tag '{{tag}}' deleted."

# Show information about a release (useful before rollback)
show-release-info tag:
    #!/usr/bin/env bash
    set -euo pipefail

    TAG="{{tag}}"

    echo "=========================================="
    echo "Release Information: $TAG"
    echo "=========================================="
    echo ""

    # Check if tag exists locally
    if git tag -l "$TAG" | grep -qF "$TAG"; then
        echo "Local tag: EXISTS"
        COMMIT=$(git rev-parse "$TAG" 2>/dev/null)
        echo "  Commit: $COMMIT"
        echo "  Date:   $(git log -1 --format=%ai "$TAG")"
        echo "  Author: $(git log -1 --format='%an <%ae>' "$TAG")"
    else
        echo "Local tag: NOT FOUND"
    fi

    # Check if tag exists on remote
    if git ls-remote --tags origin | grep -qF "refs/tags/$TAG"; then
        echo "Remote tag: EXISTS"
    else
        echo "Remote tag: NOT FOUND"
    fi

    echo ""

    # Check which branches contain the tag
    echo "Branches containing this tag:"
    BRANCHES=$(git branch -a --contains "$TAG" 2>/dev/null || true)
    if [ -n "$BRANCHES" ]; then
        echo "$BRANCHES" | sed 's/^/  /'
    else
        echo "  (none or tag not found)"
    fi

    echo ""

    # Check if GitHub Release exists
    echo "GitHub Release:"
    if command -v gh &> /dev/null; then
        if gh release view "$TAG" --json tagName,name,isDraft,isPrerelease,createdAt &>/dev/null; then
            gh release view "$TAG" --json tagName,name,isDraft,isPrerelease,createdAt | \
                jq -r '"  Name: \(.name)\n  Draft: \(.isDraft)\n  Prerelease: \(.isPrerelease)\n  Created: \(.createdAt)"'
            echo ""
            echo "  Assets:"
            gh release view "$TAG" --json assets | jq -r '.assets[].name' | sed 's/^/    - /'
        else
            echo "  NOT FOUND (no GitHub Release for this tag)"
        fi
    else
        echo "  (gh CLI not installed - cannot check)"
    fi

    echo ""

    # Determine component type and show additional info
    case "$TAG" in
        robust-mcp-server-v*)
            VERSION="${TAG#robust-mcp-server-v}"
            echo "Component: Robust MCP Server"
            echo "Version:   $VERSION"
            echo ""
            echo "Published to:"
            echo "  - PyPI: https://pypi.org/project/freecad-robust-mcp/$VERSION/"
            echo "  - Docker Hub: spkane/freecad-robust-mcp:$VERSION"
            echo ""
            echo "NOTE: PyPI packages cannot be fully deleted, only yanked."
            echo "      Docker tags can be deleted from Docker Hub."
            ;;
        robust-mcp-workbench-v*)
            VERSION="${TAG#robust-mcp-workbench-v}"
            echo "Component: Robust MCP Bridge Workbench"
            echo "Version:   $VERSION"
            ;;
        macro-cut-object-for-magnets-v*)
            VERSION="${TAG#macro-cut-object-for-magnets-v}"
            echo "Component: Cut Object for Magnets Macro"
            echo "Version:   $VERSION"
            ;;
        macro-multi-export-v*)
            VERSION="${TAG#macro-multi-export-v}"
            echo "Component: Multi Export Macro"
            echo "Version:   $VERSION"
            ;;
        *)
            echo "Component: Unknown (not a recognized release tag format)"
            ;;
    esac

# Rollback a release (delete tag and GitHub Release)
rollback-release tag:
    #!/usr/bin/env bash
    set -euo pipefail

    TAG="{{tag}}"

    echo "=========================================="
    echo "ROLLBACK RELEASE: $TAG"
    echo "=========================================="
    echo ""

    # Determine component type and version
    COMPONENT=""
    VERSION=""
    case "$TAG" in
        robust-mcp-server-v*)
            COMPONENT="mcp-server"
            VERSION="${TAG#robust-mcp-server-v}"
            ;;
        robust-mcp-workbench-v*)
            COMPONENT="workbench"
            VERSION="${TAG#robust-mcp-workbench-v}"
            ;;
        macro-cut-object-for-magnets-v*)
            COMPONENT="macro-magnets"
            VERSION="${TAG#macro-cut-object-for-magnets-v}"
            ;;
        macro-multi-export-v*)
            COMPONENT="macro-export"
            VERSION="${TAG#macro-multi-export-v}"
            ;;
        *)
            COMPONENT="unknown"
            ;;
    esac

    # Show what will be affected
    echo "This will:"
    echo "  1. Delete the GitHub Release (if exists)"
    echo "  2. Delete the git tag (local and remote)"
    if [ "$COMPONENT" = "mcp-server" ]; then
        echo "  3. Optionally yank from PyPI"
        echo "  4. Provide Docker Hub cleanup instructions"
    fi
    echo ""

    # Check what exists
    LOCAL_TAG_EXISTS=false
    REMOTE_TAG_EXISTS=false
    GH_RELEASE_EXISTS=false

    if git tag -l "$TAG" | grep -qF "$TAG"; then
        LOCAL_TAG_EXISTS=true
        echo "  Local tag:      WILL BE DELETED"
    else
        echo "  Local tag:      not found (already deleted?)"
    fi

    if git ls-remote --tags origin | grep -qF "refs/tags/$TAG"; then
        REMOTE_TAG_EXISTS=true
        echo "  Remote tag:     WILL BE DELETED"
    else
        echo "  Remote tag:     not found (already deleted?)"
    fi

    if command -v gh &> /dev/null; then
        if gh release view "$TAG" &>/dev/null; then
            GH_RELEASE_EXISTS=true
            echo "  GitHub Release: WILL BE DELETED"
        else
            echo "  GitHub Release: not found (already deleted?)"
        fi
    else
        echo "  GitHub Release: (gh CLI not installed - cannot check/delete)"
    fi

    echo ""

    # Component-specific info
    case "$COMPONENT" in
        mcp-server)
            echo "Component: Robust MCP Server v$VERSION"
            echo ""
            echo "IMPORTANT: MCP Server releases publish to multiple registries:"
            echo "  - PyPI: Package cannot be deleted, only yanked (hidden from pip install)"
            echo "  - Docker Hub: Tags can be deleted via web UI or API"
            echo ""
            ;;
        workbench)
            echo "Component: Robust MCP Bridge Workbench v$VERSION"
            echo ""
            echo "This release only creates a GitHub Release with archive files."
            echo "Rollback will fully clean up this release."
            echo ""
            ;;
        macro-magnets)
            echo "Component: Cut Object for Magnets Macro v$VERSION"
            echo ""
            echo "This release only creates a GitHub Release with archive files."
            echo "Rollback will fully clean up this release."
            echo ""
            ;;
        macro-export)
            echo "Component: Multi Export Macro v$VERSION"
            echo ""
            echo "This release only creates a GitHub Release with archive files."
            echo "Rollback will fully clean up this release."
            echo ""
            ;;
        *)
            echo "WARNING: Unrecognized tag format. Proceeding with generic rollback."
            echo ""
            ;;
    esac

    # Nothing to do?
    if [ "$LOCAL_TAG_EXISTS" = false ] && [ "$REMOTE_TAG_EXISTS" = false ] && [ "$GH_RELEASE_EXISTS" = false ]; then
        echo "Nothing to rollback - tag and release not found."
        exit 0
    fi

    read -p "Proceed with rollback? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi

    echo ""

    # Delete GitHub Release first (before tag, since release references tag)
    if [ "$GH_RELEASE_EXISTS" = true ]; then
        echo "Deleting GitHub Release..."
        if gh release delete "$TAG" --yes; then
            echo "  ✓ GitHub Release deleted."
        else
            echo "  WARNING: Failed to delete GitHub Release."
        fi
    fi

    # Delete remote tag
    if [ "$REMOTE_TAG_EXISTS" = true ]; then
        echo "Deleting remote tag..."
        if git push origin --delete "$TAG"; then
            echo "  ✓ Remote tag deleted."
        else
            echo "  WARNING: Failed to delete remote tag."
        fi
    fi

    # Delete local tag
    if [ "$LOCAL_TAG_EXISTS" = true ]; then
        echo "Deleting local tag..."
        if git tag -d "$TAG"; then
            echo "  ✓ Local tag deleted."
        else
            echo "  WARNING: Failed to delete local tag."
        fi
    fi

    echo ""
    echo "=========================================="
    echo "Git/GitHub Rollback complete!"
    echo "=========================================="

    # MCP Server: Provide PyPI and Docker cleanup instructions
    if [ "$COMPONENT" = "mcp-server" ]; then
        echo ""
        echo "--- PyPI Cleanup ---"
        echo ""
        echo "To yank version $VERSION from PyPI (hides from 'pip install'):"
        echo ""
        echo "  1. Go to: https://pypi.org/manage/project/freecad-robust-mcp/releases/"
        echo "  2. Click 'Options' → 'Yank'"
        echo "  3. Enter a reason (e.g., 'Released from wrong branch')"
        echo "  4. Confirm"
        echo ""
        echo "Note: Yanking hides the version from default pip install, but users"
        echo "      who pin to this exact version can still install it."
        echo "      Yanking can be undone from the same page."
        echo ""
        read -p "Open PyPI release page in browser? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            PYPI_URL="https://pypi.org/manage/project/freecad-robust-mcp/releases/"
            if command -v open &> /dev/null; then
                open "$PYPI_URL"
            elif command -v xdg-open &> /dev/null; then
                xdg-open "$PYPI_URL"
            else
                echo "Could not open browser. Visit: $PYPI_URL"
            fi
        fi

        echo ""
        echo "--- Docker Hub Cleanup ---"
        echo ""
        echo "To delete Docker Hub tags:"
        echo ""
        echo "  1. Go to: https://hub.docker.com/repository/docker/spkane/freecad-robust-mcp/tags"
        echo "  2. Find tag: $VERSION"
        echo "  3. Click the checkbox and 'Delete'"
        echo "  4. Also delete 'latest' tag if this was the latest release"
        echo ""
        read -p "Open Docker Hub tags page in browser? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            DOCKER_URL="https://hub.docker.com/repository/docker/spkane/freecad-robust-mcp/tags"
            if command -v open &> /dev/null; then
                open "$DOCKER_URL"
            elif command -v xdg-open &> /dev/null; then
                xdg-open "$DOCKER_URL"
            else
                echo "Could not open browser. Visit: $DOCKER_URL"
            fi
        fi
    fi

    echo ""
    echo "=========================================="
    echo "ROLLBACK SUMMARY"
    echo "=========================================="
    echo ""

    # Show what was done and what remains
    case "$COMPONENT" in
        mcp-server)
            echo "COMPLETED (automated):"
            echo "  ✓ GitHub Release deleted"
            echo "  ✓ Git tag deleted (local and remote)"
            echo ""
            echo "MANUAL STEPS REQUIRED:"
            echo "  □ PyPI: Yank version $VERSION"
            echo "    URL: https://pypi.org/manage/project/freecad-robust-mcp/releases/"
            echo ""
            echo "  □ Docker Hub: Delete tag $VERSION"
            echo "    URL: https://hub.docker.com/repository/docker/spkane/freecad-robust-mcp/tags"
            echo ""
            echo "  □ Docker Hub: Delete 'latest' tag (if this was the latest release)"
            echo "    URL: https://hub.docker.com/repository/docker/spkane/freecad-robust-mcp/tags"
            ;;
        workbench|macro-magnets|macro-export)
            echo "COMPLETED (automated):"
            echo "  ✓ GitHub Release deleted"
            echo "  ✓ Git tag deleted (local and remote)"
            echo ""
            echo "MANUAL STEPS REQUIRED:"
            echo "  (none - rollback is complete!)"
            ;;
        *)
            echo "COMPLETED (automated):"
            echo "  ✓ GitHub Release deleted (if existed)"
            echo "  ✓ Git tag deleted (local and remote)"
            echo ""
            echo "MANUAL STEPS REQUIRED:"
            echo "  (unknown component - verify no additional cleanup needed)"
            ;;
    esac

    echo ""

# Delete only the GitHub Release (keep tag)
delete-github-release tag:
    #!/usr/bin/env bash
    set -euo pipefail

    TAG="{{tag}}"

    if ! command -v gh &> /dev/null; then
        echo "ERROR: gh CLI is required but not installed."
        echo "Install: https://cli.github.com/"
        exit 1
    fi

    if ! gh release view "$TAG" &>/dev/null; then
        echo "No GitHub Release found for tag: $TAG"
        exit 0
    fi

    echo "This will delete the GitHub Release for: $TAG"
    echo "(The git tag will be preserved)"
    echo ""

    gh release view "$TAG" --json name,createdAt,assets | \
        jq -r '"Release: \(.name)\nCreated: \(.createdAt)\nAssets: \(.assets | length)"'

    echo ""
    read -p "Delete this release? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi

    gh release delete "$TAG" --yes
    echo "GitHub Release deleted. Tag '$TAG' preserved."

# =============================================================================
# Release Status
# =============================================================================

# Show unreleased changes across all components
status:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "=========================================="
    echo "Release Status - Unreleased Changes"
    echo "=========================================="
    echo ""

    # Helper function to count changes
    count_changes() {
        local prefix="$1"
        local paths="$2"
        local latest_tag=$(git tag -l "${prefix}*" --sort=-v:refname | head -1)

        if [ -z "$latest_tag" ]; then
            # No releases yet, count all commits
            git log --oneline -- $paths 2>/dev/null | wc -l | tr -d ' '
        else
            git log --oneline "$latest_tag"..HEAD -- $paths 2>/dev/null | wc -l | tr -d ' '
        fi
    }

    # Robust MCP Server
    SERVER_CHANGES=$(count_changes "robust-mcp-server-v" "src/freecad_mcp pyproject.toml Dockerfile")
    SERVER_TAG=$(git tag -l 'robust-mcp-server-v*' --sort=-v:refname | head -1)
    if [ "$SERVER_CHANGES" -gt 0 ]; then
        echo "Robust MCP Server: $SERVER_CHANGES unreleased commit(s)"
        echo "  Latest: ${SERVER_TAG:-none}"
        echo "  View:   just release::changes-since mcp-server"
    else
        echo "Robust MCP Server: up to date (${SERVER_TAG:-no releases})"
    fi
    echo ""

    # Robust MCP Bridge Workbench
    WORKBENCH_CHANGES=$(count_changes "robust-mcp-workbench-v" "addon/FreecadRobustMCPBridge")
    WORKBENCH_TAG=$(git tag -l 'robust-mcp-workbench-v*' --sort=-v:refname | head -1)
    if [ "$WORKBENCH_CHANGES" -gt 0 ]; then
        echo "Robust MCP Bridge Workbench: $WORKBENCH_CHANGES unreleased commit(s)"
        echo "  Latest: ${WORKBENCH_TAG:-none}"
        echo "  View:   just release::changes-since workbench"
    else
        echo "Robust MCP Bridge Workbench: up to date (${WORKBENCH_TAG:-no releases})"
    fi
    echo ""

    # Macro Magnets
    MAGNETS_CHANGES=$(count_changes "macro-cut-object-for-magnets-v" "macros/Cut_Object_for_Magnets")
    MAGNETS_TAG=$(git tag -l 'macro-cut-object-for-magnets-v*' --sort=-v:refname | head -1)
    if [ "$MAGNETS_CHANGES" -gt 0 ]; then
        echo "Macro (Cut Object for Magnets): $MAGNETS_CHANGES unreleased commit(s)"
        echo "  Latest: ${MAGNETS_TAG:-none}"
        echo "  View:   just release::changes-since macro-magnets"
    else
        echo "Macro (Cut Object for Magnets): up to date (${MAGNETS_TAG:-no releases})"
    fi
    echo ""

    # Macro Export
    EXPORT_CHANGES=$(count_changes "macro-multi-export-v" "macros/Multi_Export")
    EXPORT_TAG=$(git tag -l 'macro-multi-export-v*' --sort=-v:refname | head -1)
    if [ "$EXPORT_CHANGES" -gt 0 ]; then
        echo "Macro (Multi Export): $EXPORT_CHANGES unreleased commit(s)"
        echo "  Latest: ${EXPORT_TAG:-none}"
        echo "  View:   just release::changes-since macro-export"
    else
        echo "Macro (Multi Export): up to date (${EXPORT_TAG:-no releases})"
    fi
    echo ""
    echo "=========================================="

# =============================================================================
# Changelog / Release Notes Helpers
# =============================================================================

# Draft release notes for a component by extracting conventional commits since last release
draft-notes component:
    #!/usr/bin/env bash
    set -euo pipefail

    case "{{component}}" in
        mcp-server|server)
            PREFIX="robust-mcp-server-v"
            PATHS="src/freecad_mcp pyproject.toml Dockerfile"
            COMPONENT_NAME="Robust MCP Server"
            ;;
        workbench)
            PREFIX="robust-mcp-workbench-v"
            PATHS="addon/FreecadRobustMCPBridge"
            COMPONENT_NAME="Robust MCP Bridge Workbench"
            ;;
        macro-magnets|magnets)
            PREFIX="macro-cut-object-for-magnets-v"
            PATHS="macros/Cut_Object_for_Magnets"
            COMPONENT_NAME="Cut Object for Magnets Macro"
            ;;
        macro-export|export)
            PREFIX="macro-multi-export-v"
            PATHS="macros/Multi_Export"
            COMPONENT_NAME="Multi Export Macro"
            ;;
        *)
            echo "Unknown component: {{component}}"
            echo "Valid: mcp-server, workbench, macro-magnets, macro-export"
            exit 1
            ;;
    esac

    LATEST_TAG=$(git tag -l "${PREFIX}*" --sort=-v:refname | head -1)

    echo "# Draft Release Notes for $COMPONENT_NAME"
    echo ""

    if [ -z "$LATEST_TAG" ]; then
        echo "No previous releases found. Showing all commits for component paths."
        echo ""
        REV_RANGE="HEAD"
    else
        echo "Changes since: $LATEST_TAG"
        echo ""
        REV_RANGE="${LATEST_TAG}..HEAD"
    fi

    # Get commits and categorize by conventional commit type
    echo "## Added"
    echo ""
    git log --oneline "$REV_RANGE" -- $PATHS 2>/dev/null | grep -iE "^[a-f0-9]+ feat(\(|:)" | sed -E 's/^[a-f0-9]+ /- /' || true
    echo ""

    echo "## Changed"
    echo ""
    git log --oneline "$REV_RANGE" -- $PATHS 2>/dev/null | grep -iE "^[a-f0-9]+ (refactor|perf|style)(\(|:)" | sed -E 's/^[a-f0-9]+ /- /' || true
    echo ""

    echo "## Fixed"
    echo ""
    git log --oneline "$REV_RANGE" -- $PATHS 2>/dev/null | grep -iE "^[a-f0-9]+ fix(\(|:)" | sed -E 's/^[a-f0-9]+ /- /' || true
    echo ""

    echo "## Documentation"
    echo ""
    git log --oneline "$REV_RANGE" -- $PATHS 2>/dev/null | grep -iE "^[a-f0-9]+ docs(\(|:)" | sed -E 's/^[a-f0-9]+ /- /' || true
    echo ""

    echo "## Other Changes"
    echo ""
    git log --oneline "$REV_RANGE" -- $PATHS 2>/dev/null | grep -ivE "^[a-f0-9]+ (feat|fix|refactor|perf|style|docs|test|ci|build|chore)(\(|:)" | sed -E 's/^[a-f0-9]+ /- /' || true
    echo ""

    echo "---"
    echo ""
    echo "## All Commits (chronological)"
    echo ""
    git log --oneline "$REV_RANGE" -- $PATHS 2>/dev/null | sed -E 's/^[a-f0-9]+ /- /' || echo "(no commits)"

# Extract release notes section for a specific component version (for GitHub Release body)
# Reads from component-specific RELEASE_NOTES.md files
extract-changelog component version:
    #!/usr/bin/env bash
    set -euo pipefail

    # Map component to RELEASE_NOTES.md path
    case "{{component}}" in
        mcp-server|server)
            RELEASE_NOTES="{{project_root}}/src/freecad_mcp/RELEASE_NOTES.md"
            ;;
        workbench)
            RELEASE_NOTES="{{project_root}}/addon/FreecadRobustMCPBridge/RELEASE_NOTES.md"
            ;;
        macro-magnets|magnets)
            RELEASE_NOTES="{{project_root}}/macros/Cut_Object_for_Magnets/RELEASE_NOTES.md"
            ;;
        macro-export|export)
            RELEASE_NOTES="{{project_root}}/macros/Multi_Export/RELEASE_NOTES.md"
            ;;
        *)
            echo "Unknown component: {{component}}"
            exit 1
            ;;
    esac

    if [ ! -f "$RELEASE_NOTES" ]; then
        echo "No RELEASE_NOTES.md found at: $RELEASE_NOTES"
        exit 0
    fi

    # Extract section for this version
    # Format: ## Version X.Y.Z (date)
    awk -v version="{{version}}" '
        BEGIN { found=0 }
        /^## Version / {
            if (found) exit
            if (index($0, version) > 0) { found=1; next }
        }
        found { print }
    ' "$RELEASE_NOTES"

# =============================================================================
# Dry Run Commands (preview without pushing)
# =============================================================================

# Preview what a release tag would look like (no actual tag created)
dry-run-tag component version:
    #!/usr/bin/env bash
    # Validate version format (SemVer 2.0)
    if [[ ! "{{version}}" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
        echo "Error: Invalid version format '{{version}}'"
        echo "Expected: X.Y.Z or X.Y.Z-prerelease (e.g., 1.0.0, 1.0.0-alpha, 1.0.0-beta.1)"
        exit 1
    fi

    case "{{component}}" in
        mcp-server|server)
            TAG="robust-mcp-server-v{{version}}"
            echo "Would create tag: $TAG"
            echo "Triggers: PyPI, Docker Hub, GitHub Release"
            ;;
        workbench)
            TAG="robust-mcp-workbench-v{{version}}"
            echo "Would create tag: $TAG"
            echo "Triggers: GitHub Release with workbench archive"
            ;;
        macro-magnets|magnets)
            TAG="macro-cut-object-for-magnets-v{{version}}"
            echo "Would create tag: $TAG"
            echo "Triggers: GitHub Release with macro archive"
            ;;
        macro-export|export)
            TAG="macro-multi-export-v{{version}}"
            echo "Would create tag: $TAG"
            echo "Triggers: GitHub Release with macro archive"
            ;;
        *)
            echo "Unknown component: {{component}}"
            echo "Valid: mcp-server, workbench, macro-magnets, macro-export"
            exit 1
            ;;
    esac

# =============================================================================
# FreeCAD Wiki Update Helpers
# =============================================================================

# Helper to update FreeCAD wiki for a component (copies content to clipboard and opens edit page)
wiki-update component:
    #!/usr/bin/env bash
    set -euo pipefail

    case "{{component}}" in
        workbench|bridge)
            WIKI_SOURCE="{{project_root}}/addon/FreecadRobustMCPBridge/wiki-source.txt"
            WIKI_PAGE="Robust_MCP_Bridge_Workbench"
            COMPONENT_NAME="Robust MCP Bridge Workbench"
            ;;
        macro-magnets|magnets|cut)
            WIKI_SOURCE="{{project_root}}/macros/Cut_Object_for_Magnets/wiki-source.txt"
            WIKI_PAGE="Macro_Cut_Object_for_Magnets"
            COMPONENT_NAME="Cut Object for Magnets"
            ;;
        macro-export|export|multi)
            WIKI_SOURCE="{{project_root}}/macros/Multi_Export/wiki-source.txt"
            WIKI_PAGE="Macro_Multi_Export"
            COMPONENT_NAME="Multi Export"
            ;;
        *)
            echo "Unknown component: {{component}}"
            echo "Valid options: workbench (or bridge), macro-magnets (or magnets, cut), macro-export (or export, multi)"
            exit 1
            ;;
    esac

    WIKI_URL="https://wiki.freecad.org/index.php?title=${WIKI_PAGE}&action=edit"

    echo "=========================================="
    echo "FreeCAD Wiki Update Helper"
    echo "=========================================="
    echo ""
    echo "Component: $COMPONENT_NAME"
    echo "Wiki Page: https://wiki.freecad.org/${WIKI_PAGE}"
    echo ""

    # Check if wiki-source.txt exists
    if [ ! -f "$WIKI_SOURCE" ]; then
        echo "ERROR: Wiki source file not found: $WIKI_SOURCE"
        exit 1
    fi

    # Extract current version from wiki-source.txt
    CURRENT_VERSION=$(grep -o '|Version=[^|]*' "$WIKI_SOURCE" | cut -d= -f2 | tr -d '\n')
    CURRENT_DATE=$(grep -o '|Date=[^|]*' "$WIKI_SOURCE" | cut -d= -f2 | tr -d '\n')

    echo "Current version in wiki-source.txt:"
    echo "  Version: $CURRENT_VERSION"
    echo "  Date:    $CURRENT_DATE"
    echo ""

    # Try to copy to clipboard (platform-specific)
    COPIED=false
    if command -v pbcopy &> /dev/null; then
        # macOS
        cat "$WIKI_SOURCE" | pbcopy
        COPIED=true
        echo "Content copied to clipboard (macOS pbcopy)"
    elif command -v xclip &> /dev/null; then
        # Linux with xclip
        cat "$WIKI_SOURCE" | xclip -selection clipboard
        COPIED=true
        echo "Content copied to clipboard (xclip)"
    elif command -v xsel &> /dev/null; then
        # Linux with xsel
        cat "$WIKI_SOURCE" | xsel --clipboard --input
        COPIED=true
        echo "Content copied to clipboard (xsel)"
    elif command -v wl-copy &> /dev/null; then
        # Wayland
        cat "$WIKI_SOURCE" | wl-copy
        COPIED=true
        echo "Content copied to clipboard (wl-copy)"
    else
        echo "NOTE: No clipboard utility found (pbcopy, xclip, xsel, wl-copy)"
        echo "      You'll need to manually copy the content."
    fi

    echo ""
    echo "=========================================="
    echo "INSTRUCTIONS"
    echo "=========================================="
    echo ""
    echo "1. The wiki edit page will open in your browser"
    echo "2. Log in to your FreeCAD wiki account if prompted"
    echo "3. Select ALL content in the edit box (Ctrl+A / Cmd+A)"
    echo "4. Paste the new content (Ctrl+V / Cmd+V)"
    echo "5. Add an edit summary like: 'Update to version $CURRENT_VERSION'"
    echo "6. Click 'Show preview' to verify changes"
    echo "7. Click 'Save changes' when satisfied"
    echo ""

    # Ask for confirmation before opening browser
    read -p "Open wiki edit page in browser? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo ""
        echo "Aborted. You can manually visit:"
        echo "  $WIKI_URL"
        echo ""
        echo "Wiki source file location:"
        echo "  $WIKI_SOURCE"
        exit 0
    fi

    # Open the wiki edit page in browser (platform-specific)
    if command -v open &> /dev/null; then
        # macOS
        open "$WIKI_URL"
    elif command -v xdg-open &> /dev/null; then
        # Linux
        xdg-open "$WIKI_URL"
    elif command -v wslview &> /dev/null; then
        # WSL
        wslview "$WIKI_URL"
    else
        echo "Could not open browser automatically."
        echo "Please manually visit: $WIKI_URL"
    fi

    echo ""
    echo "Browser opened to: $WIKI_URL"
    if [ "$COPIED" = true ]; then
        echo ""
        echo "The wiki content is in your clipboard - ready to paste!"
    fi

# Show the wiki source content for a component (for review)
wiki-show component:
    #!/usr/bin/env bash
    set -euo pipefail

    case "{{component}}" in
        workbench|bridge)
            WIKI_SOURCE="{{project_root}}/addon/FreecadRobustMCPBridge/wiki-source.txt"
            COMPONENT_NAME="Robust MCP Bridge Workbench"
            ;;
        macro-magnets|magnets|cut)
            WIKI_SOURCE="{{project_root}}/macros/Cut_Object_for_Magnets/wiki-source.txt"
            COMPONENT_NAME="Cut Object for Magnets"
            ;;
        macro-export|export|multi)
            WIKI_SOURCE="{{project_root}}/macros/Multi_Export/wiki-source.txt"
            COMPONENT_NAME="Multi Export"
            ;;
        *)
            echo "Unknown component: {{component}}"
            echo "Valid options: workbench (or bridge), macro-magnets (or magnets, cut), macro-export (or export, multi)"
            exit 1
            ;;
    esac

    echo "=========================================="
    echo "Wiki Source: $COMPONENT_NAME"
    echo "=========================================="
    echo "File: $WIKI_SOURCE"
    echo ""

    # Show version info
    CURRENT_VERSION=$(grep -o '|Version=[^|]*' "$WIKI_SOURCE" | cut -d= -f2 | tr -d '\n')
    CURRENT_DATE=$(grep -o '|Date=[^|]*' "$WIKI_SOURCE" | cut -d= -f2 | tr -d '\n')
    echo "Version: $CURRENT_VERSION"
    echo "Date:    $CURRENT_DATE"
    echo ""
    echo "=========================================="
    echo ""

    cat "$WIKI_SOURCE"

# Diff the local wiki source against the current wiki page (requires curl)
wiki-diff component:
    #!/usr/bin/env bash
    set -euo pipefail

    case "{{component}}" in
        workbench|bridge)
            WIKI_SOURCE="{{project_root}}/addon/FreecadRobustMCPBridge/wiki-source.txt"
            WIKI_PAGE="Robust_MCP_Bridge_Workbench"
            COMPONENT_NAME="Robust MCP Bridge Workbench"
            ;;
        macro-magnets|magnets|cut)
            WIKI_SOURCE="{{project_root}}/macros/Cut_Object_for_Magnets/wiki-source.txt"
            WIKI_PAGE="Macro_Cut_Object_for_Magnets"
            COMPONENT_NAME="Cut Object for Magnets"
            ;;
        macro-export|export|multi)
            WIKI_SOURCE="{{project_root}}/macros/Multi_Export/wiki-source.txt"
            WIKI_PAGE="Macro_Multi_Export"
            COMPONENT_NAME="Multi Export"
            ;;
        *)
            echo "Unknown component: {{component}}"
            echo "Valid options: workbench (or bridge), macro-magnets (or magnets, cut), macro-export (or export, multi)"
            exit 1
            ;;
    esac

    WIKI_RAW_URL="https://wiki.freecad.org/index.php?title=${WIKI_PAGE}&action=raw"

    echo "Fetching current wiki content for $COMPONENT_NAME..."
    echo ""

    # Create temp file for wiki content
    TEMP_WIKI=$(mktemp)
    trap "rm -f $TEMP_WIKI" EXIT

    # Fetch current wiki content
    if ! curl -sS "$WIKI_RAW_URL" > "$TEMP_WIKI" 2>/dev/null; then
        echo "ERROR: Could not fetch wiki page. The page may not exist yet."
        echo "URL: $WIKI_RAW_URL"
        exit 1
    fi

    # Check if page exists (MediaWiki returns specific content for missing pages)
    if grep -q "There is currently no text in this page" "$TEMP_WIKI"; then
        echo "NOTE: Wiki page does not exist yet."
        echo "This will be a new page creation."
        echo ""
        echo "Local content to be uploaded:"
        echo "=========================================="
        head -20 "$WIKI_SOURCE"
        echo "..."
        echo "(truncated - run 'just release::wiki-show {{component}}' to see full content)"
        exit 0
    fi

    echo "Comparing local wiki-source.txt with live wiki page..."
    echo ""

    # Show diff
    if diff -u "$TEMP_WIKI" "$WIKI_SOURCE"; then
        echo "No differences found - wiki is up to date!"
    else
        echo ""
        echo "=========================================="
        echo "Differences found (above)"
        echo "Run 'just release::wiki-update {{component}}' to update the wiki"
    fi
