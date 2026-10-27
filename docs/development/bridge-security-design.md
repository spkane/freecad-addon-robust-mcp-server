# FreeCAD bridge authentication design

Status: implementation in progress. Released XML-RPC and socket listeners accept
unauthenticated code execution; the controls described here are not yet a
release guarantee. On the development branch, startup refuses to open listeners
without an injected authentication provider. A production provider and pairing
flow are not yet available, so the development branch is not usable for normal
bridge connections. The chosen release boundary protects paired clients and the
bridge's authorization state from unpaired programs running under the same OS
account. The bridge must fail closed if this boundary is unavailable.

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
An attacker that can change the installed workbench code or its approved-client
list can bypass application-level authentication altogether. Defending against
that attacker requires an OS-enforced isolation boundary for the FreeCAD process,
workbench, and trust store; credential protection by itself is insufficient.

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
- Captured stdout and stderr are each limited to 1,000,000 UTF-8 bytes and
  marked when truncated. Exception messages, types, and tracebacks use the same
  output limit. Rendering an exception can still allocate memory before the
  limit is applied.
- Result values are checked against a 1,000,000-byte structural budget, a depth
  limit, and the scalar types shared by XML-RPC and JSON before serialization.
  Unsupported or oversized results return an explicit error; the submitted code
  may already have changed FreeCAD. This does not limit allocations made by the
  submitted code before its result is checked.
- The socket client accepts response frames up to 32 MiB, including JSON
  escaping, and closes the connection on larger frames. This client-side limit
  does not prevent code from allocating an oversized result before validation.
- Keep private keys out of repository files, command-line arguments, logs, and
  model-visible output. Revoke clients independently and document rotation.
- Do not silently connect to an older, unauthenticated bridge.
- Update integration-test readiness probes to authenticate. An occupied port
  whose owner cannot be authenticated must be reported as occupied, not treated
  as a zombie to be terminated; startup and cleanup must target only the FreeCAD
  process started by that test run.

## Pairing and key isolation

The implementation must protect each client key on supported platforms while
preserving unattended use where possible. Candidate mechanisms include a
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

The protocol supports raw 32-byte Ed25519 public keys and 65-byte uncompressed
SEC1 P-256 public keys, identified by the lowercase SHA-256 fingerprint of the
canonical key bytes. P-256 signatures use ECDSA with SHA-256 and DER encoding.
The verifier resolves the approved key for each request,
checks that its fingerprint matches, and delegates signature validation to a
provider. Revocation prevents later lookups; it does not cancel an already
authorized request. Both signature verifiers require the `cryptography` package
inside FreeCAD and fail closed if it is unavailable. This fingerprint check does
not make the underlying lookup or signature provider trustworthy on its own.

P-256 is needed for the macOS Secure Enclave candidate: Apple documents that
[Secure Enclave signing uses P-256 keys](https://developer.apple.com/documentation/security/protecting-keys-with-the-secure-enclave).
Support for the algorithm does not demonstrate that a signing identity or its
trust store is isolated; those remain platform verification gates.

### Deployment decision

None of the following options currently satisfies the selected threat model
without additional protections and platform testing:

| Candidate | What it can protect | Remaining requirement |
| --------- | ------------------- | --------------------- |
| Signed macOS helper and protected app container | Helper identity, key access, and container data, subject to OS policy | Protect the FreeCAD process, its loaded add-ons, and the approved-client store; authenticate callers to the helper. A signing identity and distribution process are required. |
| Administrator-managed separate OS identity | Files and processes from an ordinary desktop-user identity, when OS permissions enforce separation | Provide usable GUI, document access, updates, and a verified IPC boundary for that identity on each supported platform. |
| Hardware key with user approval | The private key and, depending on device policy, each signing operation | Protect the workbench and trust store independently; prevent an unpaired process from using the signer as an unrestricted signing service. |

The implementation cannot treat a signed helper or hardware key alone as proof
that the same-user boundary holds. In particular, third-party code loaded inside
the FreeCAD process shares that process's authority. A viable deployment must
define which add-ons can run, where the verifier and approved-client store live,
how a client is identified at signing time, and how enrollment and revocation
remain protected. Existing user-writable workbench installations do not provide
those guarantees. The developer's choice of deployment model is pending.

### Platform feasibility gates

- **macOS:** Evaluate a signed, sandboxed app and protected app container for
  the trust store, together with a signer bound to a distinct client identity.
  Apple documents [app-container access controls](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox)
  on macOS 14 and later. Verify the FreeCAD process and loaded workbench are
  actually covered; merely storing a key in a container does not protect a
  workbench installed in a user-writable directory.
- **Windows:** Evaluate a packaged AppContainer process with isolated storage
  and protected signing identity. Microsoft distinguishes
  [AppContainer from full-trust desktop apps](https://learn.microsoft.com/en-us/windows/msix/msix-containerization-overview).
  Verify FreeCAD, Python extensions, networking, and document access in the actual
  packaged configuration before claiming support.
- **Linux:** Investigate an isolated service identity or a distribution-specific
  sandbox with a protected trust store and signer. Landlock restricts the process
  that opts into it; it does not by itself stop an unrestricted same-user process
  from modifying a user-owned trust store. Check the deployment boundary and
  test it against a separate unpaired process.

These are evaluation candidates, not established capabilities of the current
FreeCAD distribution. For each supported operating system, document the exact
packaging, identities, access controls, recovery flow, and limitations, and test
the boundary against an unpaired same-user process. A platform without a
verified boundary must refuse to enable the execution listener; it must not
fall back to an unprotected key or an unauthenticated bridge.

The locally inspected macOS FreeCAD 27.1 development installation uses Python
3.13 and does not include the `cryptography` package. The MCP server's Python
environment has that package through its dependencies, but it is a separate
runtime. Signature verification in the workbench must therefore use a verified
compatible provider or an explicitly packaged dependency; availability in the
server environment is not evidence that the workbench can import it. This is an
observation about that installation, not a claim about every FreeCAD release.

On 2026-10-27, a headless FreeCAD 27.1 development process was exercised with
the workbench source, a temporary Python 3.13-compatible crypto dependency, and
an in-memory test trust store. Signed XML-RPC and socket clients both created a
2 × 3 × 4 box and returned its volume; a different private key claiming the same
client ID was rejected on each transport. This manual probe did not test a GUI,
production credential storage, pairing, or same-account isolation. The
temporary dependency and test credential are not a deployment mechanism.

The repeatable standalone test in `tests/integration/test_authenticated_standalone.py`
starts its own headless FreeCAD process on ephemeral ports. Set
`FREECAD_AUTH_TEST_COMMAND` to the FreeCAD command executable and
`FREECAD_AUTH_TEST_DEPS` to a disposable directory containing a compatible
`cryptography` installation, then run that test with `uv run pytest`. It uses a
public test-only key and skips when these inputs are absent. It does not test
the production provider, GUI, or same-account isolation.

A separate Qt6 GUI probe on that development build displayed the permanent
Python-execution warning with the test authenticator and exited with code 0.
FreeCAD also logged an application-initialization warning during direct launch,
so this is a narrow widget check, not a clean GUI integration result. Qt5 and
the supported stable Qt6 build still require their normal GUI test lanes.

The same local macOS development installation has a Developer ID signature and
the hardened-runtime flag, but its entitlements include
`com.apple.security.cs.disable-library-validation` and
`com.apple.security.get-task-allow`. The installed application and workbench
directories are owned by the desktop user. Apple's documentation states that
[disabled library validation permits third-party libraries](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.disable-library-validation),
and that [debugger access to a process with `get-task-allow` can require an
administrator authorization dialog](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.debugger).
These observations do not demonstrate a successful bypass. They do show that
the current installation cannot simply be assumed to protect the workbench and
trust store against other programs under the same account. Verify any proposed
packaging and process isolation with an actual unpaired-process test, without
assuming that code signing alone protects user-writable add-on code.

## Verification gates

Exercise both transports with authorized and unauthorized clients, including
missing and wrong credentials, replayed proofs, altered requests, oversized and
slow input, queue saturation, and legacy peers. Verify real FreeCAD GUI and
headless operation across supported Qt5 and Qt6 builds. Platform-specific key
storage, enrollment, revocation, and recovery require tests on each supported
operating system; mocks alone cannot establish OS isolation.
