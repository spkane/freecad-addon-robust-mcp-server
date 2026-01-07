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
#   - X.Y.Z-alpha     - Alpha (TestPyPI only for MCP server)
#   - X.Y.Z-alpha.N   - Alpha with number
#   - X.Y.Z-beta      - Beta
#   - X.Y.Z-beta.N    - Beta with number
#   - X.Y.Z-rc.N      - Release candidate

# Project root directory
project_root := justfile_directory()

# =============================================================================
# Version Bump Commands
# =============================================================================

# Bump the MCP Bridge workbench version in all source files
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

    echo "Bumping MCP Bridge Workbench to version: $VERSION (date: $TODAY)"
    echo ""

    # Update __version__ in the bridge module's __init__.py
    INIT_FILE="{{project_root}}/addon/FreecadRobustMCP/freecad_mcp_bridge/__init__.py"
    if [ -f "$INIT_FILE" ]; then
        sed 's/^__version__ = "[^"]*"/__version__ = "'"$VERSION"'"/' "$INIT_FILE" > "$INIT_FILE.tmp" && mv "$INIT_FILE.tmp" "$INIT_FILE"
        echo "Updated $INIT_FILE:"
        grep "__version__" "$INIT_FILE"
    else
        echo "ERROR: File not found: $INIT_FILE"
        exit 1
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

# Create and push a release tag for the MCP server (triggers PyPI + Docker release)
# Note: MCP server uses setuptools-scm, so version is derived from git tag at build time
tag-mcp-server version:
    #!/usr/bin/env bash
    set -euo pipefail
    TAG="robust-mcp-server-v{{version}}"

    # Validate version format
    if [[ ! "{{version}}" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
        echo "ERROR: Version '{{version}}' is not valid semver (X.Y.Z or X.Y.Z-prerelease)"
        exit 1
    fi

    # Check for uncommitted changes
    if ! git diff --quiet HEAD; then
        echo "ERROR: You have uncommitted changes. Please commit or stash them first."
        exit 1
    fi

    echo "Creating tag: $TAG"
    echo ""
    echo "This will trigger:"
    echo "  - PyPI release (beta/rc/stable) or TestPyPI (alpha)"
    echo "  - Docker Hub release"
    echo "  - GitHub release with wheel and tar.gz"
    echo ""
    read -p "Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi

    git tag -a "$TAG" -m "Release MCP Server v{{version}}"
    git push origin "$TAG"
    echo ""
    echo "Tag $TAG created and pushed!"
    echo "Watch the release at: https://github.com/spkane/freecad-robust-mcp-and-more/actions"

# Create and push a release tag for the MCP Bridge workbench
tag-workbench version:
    #!/usr/bin/env bash
    set -euo pipefail
    TAG="robust-mcp-workbench-v{{version}}"
    VERSION="{{version}}"

    if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
        echo "ERROR: Version '$VERSION' is not valid semver"
        exit 1
    fi

    # Check for uncommitted changes
    if ! git diff --quiet HEAD; then
        echo "ERROR: You have uncommitted changes. Please commit or stash them first."
        exit 1
    fi

    # Verify version in source files matches tag version
    echo "Verifying version in source files..."

    # Check __init__.py
    INIT_FILE="{{project_root}}/addon/FreecadRobustMCP/freecad_mcp_bridge/__init__.py"
    INIT_VERSION=$(grep -o '__version__ = "[^"]*"' "$INIT_FILE" | cut -d'"' -f2)
    if [ "$INIT_VERSION" != "$VERSION" ]; then
        echo "ERROR: Version mismatch in $INIT_FILE"
        echo "  Expected: $VERSION"
        echo "  Found:    $INIT_VERSION"
        echo ""
        echo "Run 'just release::bump-workbench $VERSION' first, then commit the changes."
        exit 1
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

    git tag -a "$TAG" -m "Release MCP Bridge Workbench v{{version}}"
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

    VERSION="{{version}}"
    TAG="{{tag_prefix}}v{{version}}"
    MACRO_DIR="{{project_root}}/macros/{{macro_dir}}"
    MACRO_NAME="{{macro_name}}"

    # Validate version format (SemVer 2.0)
    if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
        echo "ERROR: Version '$VERSION' is not valid semver"
        exit 1
    fi

    # Check for uncommitted changes
    if ! git diff --quiet HEAD; then
        echo "ERROR: You have uncommitted changes. Please commit or stash them first."
        exit 1
    fi

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
    echo "=== MCP Server Releases ==="
    git tag -l 'robust-mcp-server-v*' --sort=-v:refname | head -10
    echo ""
    echo "=== MCP Workbench Releases ==="
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
    echo "  MCP Server:      ${SERVER_TAG:-none}"
    echo "  MCP Workbench:   ${WORKBENCH_TAG:-none}"
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
            PATHS="addon/FreecadRobustMCP"
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

    # MCP Server
    SERVER_CHANGES=$(count_changes "robust-mcp-server-v" "src/freecad_mcp pyproject.toml Dockerfile")
    SERVER_TAG=$(git tag -l 'robust-mcp-server-v*' --sort=-v:refname | head -1)
    if [ "$SERVER_CHANGES" -gt 0 ]; then
        echo "MCP Server: $SERVER_CHANGES unreleased commit(s)"
        echo "  Latest: ${SERVER_TAG:-none}"
        echo "  View:   just release::changes-since mcp-server"
    else
        echo "MCP Server: up to date (${SERVER_TAG:-no releases})"
    fi
    echo ""

    # Workbench
    WORKBENCH_CHANGES=$(count_changes "robust-mcp-workbench-v" "addon/FreecadRobustMCP")
    WORKBENCH_TAG=$(git tag -l 'robust-mcp-workbench-v*' --sort=-v:refname | head -1)
    if [ "$WORKBENCH_CHANGES" -gt 0 ]; then
        echo "MCP Workbench: $WORKBENCH_CHANGES unreleased commit(s)"
        echo "  Latest: ${WORKBENCH_TAG:-none}"
        echo "  View:   just release::changes-since workbench"
    else
        echo "MCP Workbench: up to date (${WORKBENCH_TAG:-no releases})"
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
            COMPONENT_NAME="MCP Server"
            ;;
        workbench)
            PREFIX="robust-mcp-workbench-v"
            PATHS="addon/FreecadRobustMCP"
            COMPONENT_NAME="MCP Bridge Workbench"
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

# Extract changelog section for a specific component version (for GitHub Release body)
extract-changelog component version:
    #!/usr/bin/env bash
    set -euo pipefail

    # Match header exactly as it appears in CHANGELOG.md
    case "{{component}}" in
        mcp-server|server)
            HEADER="### MCP Server v{{version}}"
            ;;
        workbench)
            HEADER="### MCP Bridge Workbench v{{version}}"
            ;;
        macro-magnets|magnets)
            HEADER="### Cut Object for Magnets Macro v{{version}}"
            ;;
        macro-export|export)
            HEADER="### Multi Export Macro v{{version}}"
            ;;
        *)
            echo "Unknown component: {{component}}"
            exit 1
            ;;
    esac

    CHANGELOG="{{project_root}}/CHANGELOG.md"

    # Extract section between this version header and the next component header or separator
    # Only exit on: "---" separator OR "### " followed by component name (capital letter)
    # This allows #### Added, #### Changed, etc. to be included
    awk -v header="$HEADER" '
        BEGIN { found=0 }
        $0 == header || $0 == header " " { found=1; next }
        found && /^---$/ { exit }
        found && /^### [A-Z]/ { exit }
        found { print }
    ' "$CHANGELOG"

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
