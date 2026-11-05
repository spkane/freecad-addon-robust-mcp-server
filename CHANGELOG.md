# Changelog

This project uses **component-specific versioning**. Each component has its own
release notes and version history.

## 0.7.0

Version 0.7.0 updates both the server and workbench. It adds authenticated
bridge pairing and CAM tooling, migrates to MCP Python SDK 2, improves FreeCAD
Qt5/Qt6 compatibility, and fixes screenshot, modeling, startup, and timeout
reliability. The component release notes below contain details and limitations.
Install or update both components together; FreeCAD 1.1.4 or newer is
recommended for security.

## Component Release Notes

| Component              | Release Notes                                                        | Description                                           |
| ---------------------- | -------------------------------------------------------------------- | ----------------------------------------------------- |
| **Robust MCP Server**  | [RELEASE_NOTES.md](src/freecad_mcp/RELEASE_NOTES.md)                 | MCP server for AI assistant integration (PyPI/Docker) |
| **Robust MCP Bridge**  | [RELEASE_NOTES.md](freecad/RobustMCPBridge/RELEASE_NOTES.md)         | FreeCAD workbench addon                               |

## Versioning Scheme

Each component follows [Semantic Versioning](https://semver.org/) independently:

- **Robust MCP Server**: Released via git tags `robust-mcp-server-vX.Y.Z`
- **Robust MCP Bridge**: Released via git tags `robust-mcp-workbench-vX.Y.Z`

## Latest Versions

To see the current latest versions of each component:

```bash
just release::latest-versions
```

## Full Documentation

For detailed release process and contribution guidelines, see:

- [Release Process](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/development/releasing/)
- [Contributing Guide](https://spkane.github.io/freecad-addon-robust-mcp-server/latest/development/contributing/)
