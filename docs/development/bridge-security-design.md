# FreeCAD bridge authentication design

Status: scoping. The existing XML-RPC and socket listeners accept unauthenticated
code execution; the controls described here are not yet a release guarantee.

## Trust boundary

The bridge runs inside FreeCAD with the user's privileges. A bridge client that
can submit Python can modify documents, read and write accessible files, and use
network access available to FreeCAD. The MCP server generates Python for ordinary
CAD operations, so disabling the public `execute_python` tool alone does not
remove the bridge's ability to execute arbitrary code.

The release target is an explicitly paired client, a loopback-only listener,
and request authentication before any execution or XML deserialization. A
compromised paired client remains trusted and has FreeCAD's privileges. Remote
access requires a separate authenticated and encrypted deployment, not a wider
bind address.

The stronger threat model also includes another unpaired process running under
the same OS account. This cannot be satisfied solely by file permissions or an
unrestricted per-user credential store. For example, Microsoft's
[CurrentUser DPAPI documentation](https://learn.microsoft.com/en-us/dotnet/api/system.security.cryptography.dpapidataprotector.scope?view=netframework-4.8.1)
states that applications using the same user credentials can access protected
data. On macOS, [keychain ACLs](https://developer.apple.com/documentation/security/access-control-lists)
can restrict keychain operations to trusted applications or require user consent,
but the identity and signing of the actual Python executable matter.

## Protocol requirements

- Fail closed before starting listeners if pairing or key access is unavailable.
- Authenticate every privileged request on both protocols, with a client-specific
  key and a fresh challenge or nonce bound to the method and request body.
- Reject replayed, expired, malformed, and unauthenticated requests before
  placing work in the FreeCAD execution queue.
- Validate XML-RPC authentication before XML parsing; Python's standard XML-RPC
  parser is [not safe for untrusted XML](https://docs.python.org/3.11/library/xml.html).
- Bind only literal loopback addresses. Enforce request size, connection, read
  deadline, and queue limits independently of authentication.
- Keep private keys out of repository files, command-line arguments, logs, and
  model-visible output. Revoke clients independently and document rotation.
- Do not silently connect to an older, unauthenticated bridge.
- Update integration-test readiness probes to authenticate. An occupied port
  whose owner cannot be authenticated must be reported as occupied, not treated
  as a zombie to be terminated; startup and cleanup must target only the FreeCAD
  process started by that test run.

## Pairing and key isolation

The remaining design decision is how to protect each client key on supported
platforms while preserving unattended use. Candidate mechanisms include a
platform-protected signer with explicit user approval or a hardware-backed key;
both need a trusted enrollment flow and real platform testing. A per-user
shared secret is simpler and blocks clients that cannot read it, but it does not
meet the stronger same-account threat model on its own.

Public-key pairing can leave only public keys in the FreeCAD workbench. The
client signs a server challenge and the request, and the bridge checks the
signature against its approved clients. The trust store itself must be protected
from unpaired processes, or those processes can register their own keys. User
approval must identify the client key by fingerprint rather than trusting a
client-supplied display name. Any provider that can sign silently for arbitrary
same-user processes is insufficient for that stronger boundary.

## Verification gates

Exercise both transports with authorized and unauthorized clients, including
missing and wrong credentials, replayed proofs, altered requests, oversized and
slow input, queue saturation, and legacy peers. Verify real FreeCAD GUI and
headless operation across supported Qt5 and Qt6 builds. Platform-specific key
storage, enrollment, revocation, and recovery require tests on each supported
operating system; mocks alone cannot establish OS isolation.
