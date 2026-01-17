# Release Process

This project uses **component-specific versioning**. Each component (MCP Server, Workbench) has its own version and release cycle, allowing independent updates without affecting other components.

## Quick Start

The complete release workflow in order:

```bash
# 1. Pre-release checks
just release::status                        # Check which components have unreleased changes
just release::changes-since mcp-server      # View specific changes (or workbench)
just all                                    # Run all quality checks (must pass)

# 2. Update release notes
just release::draft-notes mcp-server        # Generate draft notes from commits
# Then edit the component's RELEASE_NOTES.md file (see "Release Notes Files" below)

# 3. Version bump (workbench only - MCP Server uses setuptools-scm)
just release::bump-workbench 1.0.0

# 4. Commit changes
git add -A
git commit -m "chore: bump workbench to 1.0.0"  # or appropriate component/message

# 5. Create & push tag (triggers CI/CD automatically)
just release::tag-workbench 1.0.0           # or tag-mcp-server

# 6. Monitor release at GitHub Actions, then verify
just release::list-tags
just release::latest-versions
```

| Component  | Bump Command                         | Tag Command                          |
| ---------- | ------------------------------------ | ------------------------------------ |
| MCP Server | *(none - uses setuptools-scm)*       | `just release::tag-mcp-server X.Y.Z` |
| Workbench  | `just release::bump-workbench X.Y.Z` | `just release::tag-workbench X.Y.Z`  |

## Components and Their Release Targets

| Component                   | Tag Format                    | Releases To                                |
| --------------------------- | ----------------------------- | ------------------------------------------ |
| MCP Server                  | `robust-mcp-server-vX.Y.Z`    | PyPI/TestPyPI*, Docker Hub, GitHub Release |
| Robust MCP Bridge Workbench | `robust-mcp-workbench-vX.Y.Z` | GitHub Release (archive)                   |

*Stable releases (`X.Y.Z`) publish to PyPI; non-stable releases (alpha, beta, rc) publish to TestPyPI only.

## Version Format

All versions follow [Semantic Versioning 2.0](https://semver.org/):

- `X.Y.Z` - Stable release (published to PyPI only)
- `X.Y.Z-alpha` or `X.Y.Z-alpha.N` - Alpha pre-release (published to TestPyPI only)
- `X.Y.Z-beta` or `X.Y.Z-beta.N` - Beta pre-release (published to TestPyPI only)
- `X.Y.Z-rc.N` - Release candidate (published to TestPyPI only)

## Release Workflow Overview

Releases follow a **two-step process**:

1. **Bump**: Update version in all source files locally, then commit
2. **Tag**: Create and push the git tag (triggers CI/CD)

This ensures the version in source files matches the git tag on the same commit.

```text
┌─────────────────────────────────────────────────────────────────┐
│  1. just release::bump-<component> X.Y.Z                        │
│     └── Updates version in all relevant files                   │
│                                                                 │
│  2. git add -A && git commit -m "chore: bump ... to X.Y.Z"      │
│     └── Commit the version changes                              │
│                                                                 │
│  3. just release::tag-<component> X.Y.Z                         │
│     └── Verifies versions match, then creates & pushes tag      │
│                                                                 │
│  4. GitHub Actions workflow runs automatically                  │
│     └── Verifies versions, builds, and publishes release        │
└─────────────────────────────────────────────────────────────────┘
```

## Pre-Release Checklist

Before creating any release, complete these steps:

### 1. Check Release Status

See which components have unreleased changes:

```bash
just release::status
```

This shows the number of commits since the last release for each component.

### 2. Review Changes

View the specific changes for the component you're releasing:

```bash
# For MCP Server
just release::changes-since mcp-server

# For Workbench
just release::changes-since workbench
```

### 3. Run All Quality Checks

Ensure all tests and checks pass:

```bash
just all
```

For a more thorough check including integration tests:

```bash
just all-with-integration
```

### 4. Update Release Notes

Each component has its own `RELEASE_NOTES.md` file. Release workflows automatically extract the relevant section for GitHub Releases.

#### Release Notes Files

| Component                   | Release Notes File                              |
| --------------------------- | ----------------------------------------------- |
| MCP Server                  | `src/freecad_mcp/RELEASE_NOTES.md`              |
| Robust MCP Bridge Workbench | `addon/FreecadRobustMCPBridge/RELEASE_NOTES.md` |

#### Draft Release Notes

Use the `draft-notes` command to generate a starting point from conventional commits:

```bash
# Generate draft notes for a component
just release::draft-notes mcp-server
just release::draft-notes workbench
```

This categorizes commits by type (feat, fix, refactor, etc.) to help you write the release notes.

#### Release Notes Format

Add a new version section **at the top** of the component's `RELEASE_NOTES.md`:

```markdown
## Version X.Y.Z (YYYY-MM-DD)

Release notes for changes between vA.B.C and vX.Y.Z.

### Added

- New feature description

### Changed

- Changed behavior description

### Fixed

- Bug fix description
```

**Important:** The version header format must match exactly for the GitHub Release workflow to extract it:

- Format: `## Version X.Y.Z (YYYY-MM-DD)`
- Example: `## Version 1.0.0 (2026-01-15)`

The release workflows automatically extract the version section and include it in the GitHub Release body.

## Releasing Each Component

### MCP Server Release

The MCP Server is the main Python package. It uses `setuptools-scm` to derive version from git tags at build time, so there's no version bump step needed.

```bash
# 1. Ensure all changes are committed
git status  # Should show clean working tree

# 2. Update src/freecad_mcp/RELEASE_NOTES.md and commit
git add src/freecad_mcp/RELEASE_NOTES.md
git commit -m "docs: update release notes for MCP Server v1.0.0"

# 3. Create and push the release tag
just release::tag-mcp-server 1.0.0
```

**What happens automatically:**

1. GitHub Actions validates the tag format
2. Builds Python wheel and source distribution (version from tag)
3. Tests installation on Ubuntu and macOS
4. Publishes to PyPI (or TestPyPI for alpha, beta, and rc versions)
5. Builds multi-architecture Docker image (amd64 + arm64)
6. Pushes to Docker Hub as `spkane/freecad-robust-mcp:1.0.0`
7. Creates GitHub Release with wheel and tar.gz artifacts

**Pre-release versions:**

```bash
# Alpha (goes to TestPyPI only)
just release::tag-mcp-server 1.0.0-alpha.1

# Beta (goes to TestPyPI only)
just release::tag-mcp-server 1.0.0-beta.1

# Release candidate (goes to TestPyPI only)
just release::tag-mcp-server 1.0.0-rc.1
```

### Robust MCP Bridge Workbench Release

The workbench is a FreeCAD addon that provides the Robust MCP Bridge GUI.

```bash
# 1. Bump version in source files
just release::bump-workbench 1.0.0

# 2. Review and commit the changes
git diff  # Review changes
git add -A
git commit -m "chore: bump workbench to 1.0.0"

# 3. Create and push the release tag
just release::tag-workbench 1.0.0
```

**Files updated by `bump-workbench`:**

- `addon/FreecadRobustMCPBridge/freecad_mcp_bridge/__init__.py` (`__version__`)
- `package.xml` (workbench section: `<version>` and `<date>`)

**What happens automatically:**

1. GitHub Actions validates the tag format
2. Verifies version in source files matches tag
3. Creates archive (tar.gz and zip)
4. Creates GitHub Release with the archives

## Verifying a Release

### Check GitHub Actions

After pushing a tag, monitor the release workflow:

1. Go to [GitHub Actions](https://github.com/spkane/freecad-addon-robust-mcp-server/actions)
2. Find the workflow run triggered by your tag
3. Verify all steps complete successfully

### Verify Published Artifacts

**For MCP Server:**

```bash
# Check PyPI
pip index versions freecad-robust-mcp

# Check Docker Hub
docker pull spkane/freecad-robust-mcp:1.0.0
```

**For Workbench:**

- Check the GitHub Releases page for the archive downloads
- Verify the `package.xml` version was updated

## Managing Release Tags

### List All Tags

```bash
# All tags grouped by component
just release::list-tags

# Latest version of each component
just release::latest-versions
```

### Delete a Tag (If Needed)

If a release has issues and needs to be removed:

```bash
just release::delete-tag robust-mcp-server-v1.0.0
```

!!! warning "Deleting Published Releases"
    Deleting a tag does not unpublish from PyPI or Docker Hub. Contact the respective registries to remove published artifacts if necessary.

### Preview a Release (Dry Run)

To see what a release tag would look like without creating it:

```bash
just release::dry-run-tag mcp-server 1.0.0
just release::dry-run-tag workbench 1.0.0
```

## Troubleshooting

### Release Workflow Failed

1. Check the GitHub Actions logs for the specific error
2. Common issues:
   - Invalid version format (must be semver)
   - Version mismatch between source files and tag
   - Missing secrets (PyPI token, Docker credentials)
   - Tests failing during the release build

### Version Mismatch Error

If the workflow fails with "Version mismatch":

```bash
# You forgot to bump the version before tagging
# Delete the tag
just release::delete-tag <full-tag-name>

# Bump the version
just release::bump-<component> X.Y.Z

# Commit the changes
git add -A && git commit -m "chore: bump <component> to X.Y.Z"

# Create the tag again
just release::tag-<component> X.Y.Z
```

### Tag Already Exists

If you try to create a tag that already exists:

```bash
# Delete the existing tag first
just release::delete-tag robust-mcp-server-v1.0.0

# Then create the new tag
just release::tag-mcp-server 1.0.0
```

### Wrong Version Released

1. Delete the tag: `just release::delete-tag <tag>`
2. Create a new release with the correct version
3. For PyPI: you cannot re-upload the same version; increment the patch version instead

## Release Cadence Recommendations

- **MCP Server**: Release when there are significant new features or important bug fixes
- **Workbench**: Release in sync with server changes that affect the bridge protocol

## Quick Reference

```bash
# Check what needs releasing
just release::status

# View changes for a component
just release::changes-since mcp-server

# Draft release notes from commits
just release::draft-notes mcp-server
just release::draft-notes workbench

# Bump versions (for workbench only)
just release::bump-workbench 1.0.0

# Commit version changes
git add -A && git commit -m "chore: bump <component> to X.Y.Z"

# Create releases (verifies versions, creates and pushes tag)
just release::tag-mcp-server 1.0.0
just release::tag-workbench 1.0.0

# List existing releases
just release::list-tags
just release::latest-versions

# Extract changelog for a version (used by CI)
just release::extract-changelog mcp-server 1.0.0

# Delete a tag if needed
just release::delete-tag <full-tag-name>
```
