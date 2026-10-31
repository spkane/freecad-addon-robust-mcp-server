# Security policy

The bridge gives paired clients the ability to run Python with the FreeCAD
user's privileges. Pair only with clients you trust and protect the credential
as described in the [configuration guide](docs/getting-started/configuration.md).

## Reporting a vulnerability

Please report suspected security vulnerabilities privately to
[spkane@gmail.com](mailto:spkane@gmail.com). Include affected versions, steps to
reproduce, impact, and any relevant logs with credentials and private model data
removed. Please avoid posting exploit details in a public issue before a fix is
available. The maintainer will acknowledge reports within 14 calendar days
and coordinate validation, remediation, and appropriate disclosure with the
reporter.

## Supported versions

Security fixes are developed for the current maintained release. Older releases
may require upgrading; backports are evaluated individually. Users should use
FreeCAD 1.1.4 or newer for upstream security fixes and update both the bridge
and MCP server when fixes are published.
