# Security

The Robust MCP Bridge runs inside FreeCAD. A paired client can submit Python
that runs with the FreeCAD user's permissions, including access to files and
the network. Use a client and models you trust, review its approval settings,
and stop the bridge when you are finished.

!!! note "Availability"
    The persistent permissions warning and the advisory tool annotations
    described below are available in the current development version. Check
    your installed release for its actual behavior.

## The FreeCAD warning

When the GUI bridge is running, an amber status-bar indicator says that client
Python has full user permissions. Hover over the workbench indicator for the
bridge version, listener status, and details about access to files and the
network. The warning is non-modal and remains visible while other status
messages appear, so it does not interrupt automated workflows. A warning is
also shown when the bridge runs without the workbench status widget.

![FreeCAD status bar showing the standalone bridge's full-permissions warning](../assets/images/bridge-permissions-full.png)

The example shows the standalone bridge in an isolated FreeCAD test profile;
the warning is at the bottom right. The workbench indicator also shows the
listener ports. Your theme and port numbers may differ.

The warning describes the bridge's capabilities. It does not mean a client is
currently connected or that code is being executed. It remains appropriate
even when the MCP server's arbitrary-code tools are disabled: ordinary modeling
tools generate Python, and a paired client can communicate with the bridge
directly. Headless FreeCAD has no GUI status bar; check its startup output and
stop the process when it is no longer needed.

## Pairing and local connections

In workbench 0.7.0 and later, the bridge's XML-RPC and JSON-RPC listeners bind
to loopback and require a per-user pairing credential. Older 0.6.x bridges do
not provide pairing authentication; update both components to compatible
versions. Auto-start is disabled by default. Pairing keeps
clients without the credential from making authenticated requests; it does not
protect against malicious software running as the same operating-system user,
or against a paired agent following malicious instructions in a document.

Run `freecad-mcp --pair-bridge` before starting the bridge, and protect the
credential as described in [configuration](../getting-started/configuration.md#pairing-the-freecad-bridge).
If a credential is compromised, stop both components and replace it using the
instructions there. Pairing fails closed when valid credentials are unavailable.

## Tools, files, and approvals

The MCP server hides `execute_python`, `safe_execute`, `run_macro`,
`create_macro`, and `create_macro_from_template` by default. Setting
`FREECAD_ALLOW_UNSAFE_CODE=true` before starting the server exposes them. This
is a tool-registration setting, not a Python sandbox or a bridge access control.
Other tools can read or write files and modify FreeCAD documents; enable unsafe
tools only when you need them and trust the client.

Some code and file tools advertise MCP annotations describing their potential
effects. These annotations are advisory: clients decide whether and how to
present an approval. The bridge does not enforce a human approval, and a
client may truncate code, automatically approve a call, or show only a macro
name rather than its contents. Check your client's actual approval behavior
and review sensitive operations and code before allowing them. See the
[tool risk inventory](../development/bridge-security-design.md#mcp-tool-risk-inventory-and-approval-boundaries)
for details and tested client behavior.

## Data leaving the machine

The workbench does not itself choose or contact an AI provider. Your MCP
client may send document contents, screenshots, tool results, or prompts to
its configured provider. Check the client's settings and provider policy
before opening sensitive material. Documents and tool results can also contain
instructions intended to mislead an agent; pairing does not make that content
trustworthy.

The bridge is loopback-only. The MCP server's optional HTTP transport is a
separate endpoint: it requires a bearer key and defaults to loopback. For remote
HTTP access, use a trusted TLS-terminating proxy and protect the key. See
[HTTP authentication](../getting-started/configuration.md#http-authentication)
and [connection modes](connection-modes.md#security-boundary). Do not expose
the bridge by rebinding it to a public interface.

## Practical precautions

- Keep FreeCAD, the workbench, server, and client updated; FreeCAD 1.1.4 or
  newer is recommended when opening untrusted files.
- Review client approval and automatic-execution settings before connecting.
- Use only models and macros you trust, and review requested file operations.
- Leave arbitrary-code tools disabled unless needed.
- Stop the bridge when it is not in use and rotate a compromised pairing.
