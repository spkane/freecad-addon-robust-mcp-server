# FreeCAD Robust MCP Suite Release Plan

**Audit date:** 2026-09-05  
**MCP migration update:** 2026-09-14
**Repository snapshot:** `d9a3711` on `main`  
**Intended reader:** The maintainer returning to the project after time away  
**Intended outcome:** Execute a secure, tested, repeatable public release of the
MCP server and FreeCAD workbench

## Executive decision

Do not publish the current `main` branch as a stable release.

The application is functional and has substantial tests, documentation, and
release automation. It has also already been released publicly: GitHub has
server and workbench `0.6.2` releases, while PyPI currently has server `0.6.1`.
The practical problem is therefore not a first release. It is repairing a
partially released product whose distribution channels, dependency constraints,
security model, and repository metadata have diverged.

Target a **`0.7.0` release candidate** rather than publishing another v1-based
maintenance release. The source and lockfile now migrate directly to MCP Python
SDK 2.2.0, and stdio, Streamable HTTP, first-tool-call, unit, and headless
FreeCAD integration tests pass. Complete the remaining security, packaging, GUI,
and clean-install gates before publishing the candidate. Follow with tool-catalog
profiles, complete risk annotations, task-oriented evaluations, and MCP Registry
publication.

Do not call either release `1.0`. A `1.0.0` release should follow at least one
release-candidate cycle and a short compatibility soak across supported FreeCAD,
Python, operating-system, and MCP-client combinations.

## Immediate release blockers

| Priority | Blocker                                                         | Why it blocks release                                                                                                     | Required result                                                                                              |
| -------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| P0       | MCP 2.2 migration needs final release certification             | The code migration and first-call regressions pass, but GUI and clean unlocked-install matrices are not yet complete      | Verify the wheel through stdio and HTTP on supported Python/FreeCAD/client combinations                      |
| P0       | Unauthenticated code execution bridge                           | Any process able to reach ports 9875 or 9876 can submit Python that runs inside FreeCAD with the user's privileges        | Per-launch authentication, loopback-only binding, bounded requests, and an explicit unsafe-code policy       |
| P0       | HTTP transport listens on all interfaces                        | Streamable HTTP binds `0.0.0.0` without application authentication or explicit Origin policy                              | Bind to `127.0.0.1` by default; require deliberate remote configuration, authentication, and TLS termination |
| P0       | Workbench release archive cannot be built                       | The workflow copies `LICENSE`, but only `LICENSE-CODE` and `LICENSE-ICON` exist                                           | Archive job passes and manifest/archive license names agree                                                  |
| P0       | Package verification fails                                      | The current build succeeds, but locked Twine 6.2 rejects generated Metadata 2.5                                           | Upgrade the packaging verification stack and make `twine check` or its supported replacement pass in CI      |
| P0       | Runtime default contradicts documentation                       | Configuration defaults to embedded mode, while the CLI and docs say XML-RPC; embedded mode can crash on macOS             | Make XML-RPC or socket the single default everywhere; make embedded explicitly opt-in and Linux-only         |
| P0       | Published identity is split across old and new repository names | Package URLs, docs, Docker labels, and PyPI provenance still reference `freecad-robust-mcp-and-more`                      | All live metadata points to `freecad-addon-robust-mcp-server`; PyPI Trusted Publishing is reconfigured       |
| P0       | Real FreeCAD integration has not been re-certified              | Unit tests cannot establish that GUI-thread, transport, file import/export, and shutdown behavior work in current FreeCAD | Required headless and GUI integration matrices pass against supported stable FreeCAD versions                |

## Live issue and pull-request triage

**Triage date:** 2026-09-13

**Live inventory:** 15 open issues and 11 open pull requests

**Remote `main` at triage:** `bde407c`

This queue combines user impact, release risk, ease, and whether a usable pull
request already exists. Effort is estimated for one maintainer who knows the
repository and includes focused tests and documentation:

- **XS:** less than half a day
- **S:** one to two days
- **M:** three to five days
- **L:** one to two weeks
- **XL:** a multi-week design or migration

### Recommended implementation order

| Order | Priority | Effort | Work item                                                                   | Issue or PR disposition                                                                                                                                                                                                                                                                                                                                                                              | Why this position                                                                                                                                                                                                                                                                                                          |
| ---:  | :---:    | :---:  | ---                                                                         | ---                                                                                                                                                                                                                                                                                                                                                                                                  | ---                                                                                                                                                                                                                                                                                                                        |
| 1     | P0       | S      | Complete MCP 2.2 migration certification                                    | Finish [PR #122](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/122); [#107](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/107), [#119](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/119), and [PR #117](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/117) are closed as resolved or superseded                             | The direct MCP 2.2.0 migration now passes bounded stdio and HTTP `initialize`/`tools/list`/first `tools/call` tests, all unit tests, and the headless FreeCAD suite. Finish the unlocked wheel and GUI/client matrix before merging.                                                                                       |
| 2     | P0       | XS     | Stop unrelated `.env` files from crashing startup                           | Implement [#105](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/105) directly                                                                                                                                                                                                                                                                                                      | It is a small, well-diagnosed startup failure common to MCP hosts that launch from another project's directory. Prefer eliminating implicit current-directory `.env` loading; if compatibility requires it, ignore unrelated entries and test both paths.                                                                  |
| 3     | P0       | S      | Fix symmetric Pad, Revolution, and Groove across supported FreeCAD versions | Ask the author to revise/rebase [PR #100](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/100), then merge and close [#94](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/94)                                                                                                                                                                                       | Core Part Design operations fail on FreeCAD 1.1.x. The PR preserves the public `symmetric` argument and has the correct `SideType`/`Midplane` compatibility direction; only test-quality and rebase work remains.                                                                                                          |
| 4     | P0       | S      | Fix external-geometry counting                                              | Ask the author to revise/rebase [PR #101](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/101), then merge and close [#95](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/95)                                                                                                                                                                                       | `get_sketch_info` and `add_external_geometry` fail on FreeCAD 1.1.x. The proposed subelement sum is materially better than the tempting but incorrect `len(ExternalGeometry)` replacement.                                                                                                                                 |
| 5     | P0       | S-M    | Repair STL, 3MF, and OBJ tessellation/export                                | Keep [#96](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/96) canonical; close [#121](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/121) as a duplicate                                                                                                                                                                                                         | This blocks a primary deliverable: exported models. Fix all three formats together, preferably through one shared `MeshPart.meshFromShape` helper, with curved, filleted, fused, and multiple-object regressions.                                                                                                          |
| 6     | P0       | M      | Consolidate screenshot correctness into one safe PR                         | Revise [PR #102](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/102) to absorb closed PR #106; close [#120](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/120) as a duplicate of [#82](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/82); close #82 and [#92](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/92) after merge | There are two distinct defects: fragile FreeCAD proxy type inspection crashes, and capture can produce a background-only image. The consolidated fix needs duck-typed view capability checks, render flush/framing, camera restoration and temporary-file cleanup in `finally`, and live XML-RPC/socket coverage.          |
| 7     | P0       | M      | Detect subtractive features that changed no geometry                        | Implement [#99](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/99)                                                                                                                                                                                                                                                                                                                 | Silent success can produce a valid-looking printable model with missing holes. Return pre/post volume and a clear `no_material_removed` warning or error with a reversed-direction suggestion; do not silently reverse a user-requested operation. Extend the postcondition pattern to Groove and other subtractive tools. |
| 8     | P0       | S-M    | Fix HTTP startup without reopening network exposure                         | Close [PR #84](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/84) as superseded; implement its HTTP settings concept separately                                                                                                                                                                                                                                                      | PR #84 mixes a useful SDK compatibility fix with a breaking Part Design API change and retains `0.0.0.0`. Implement against the selected MCP version with `127.0.0.1` as the default, an explicit bind option, Origin validation, and tests.                                                                               |
| 9     | P0       | M      | Publish the MCP 2.2 and compatibility fixes as `0.7.0`                      | Keep [#87](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/87) open as the release-verification issue                                                                                                                                                                                                                                                                               | Users on PyPI 0.6.1 do not receive fixes already present on `main`. Close this only after a clean `uv tool install` from PyPI passes initialization and representative tool calls against FreeCAD 1.1.3.                                                                                                                   |
| 10    | P1       | XS     | Correct Addon Manager and Windows installation documentation now            | Consolidate [#104](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/104) into [#73](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/73); implement the documentation half of [#97](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/97)                                                                                                             | This is the easiest high-impact user improvement: state that the addon is not yet indexed, provide exact manual/custom-repository steps, distinguish the Rust `just` utility from the Python package, and document the current Git Bash limitation.                                                                        |
| 11    | P1       | S-M    | Make the installer genuinely cross-platform                                 | Continue [#97](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/97) as an implementation issue                                                                                                                                                                                                                                                                                       | Detect `python3` or `python`, support PowerShell without `cygpath`, discover versioned FreeCAD user directories, and add Windows CI tests. Once this works, `just` can remain a developer convenience rather than an end-user prerequisite.                                                                                |
| 12    | P1       | S-M    | Serialize or isolate XML-RPC client calls                                   | Create a focused issue from the concurrency report in #107                                                                                                                                                                                                                                                                                                                                           | `xmlrpc.client.ServerProxy` is not thread-safe; concurrent tool calls can raise `CannotSendRequest`. Use an async lock around one proxy or a per-call proxy with bounded concurrency, then add a concurrent-call regression.                                                                                               |
| 13    | P1       | L      | Resubmit to the FreeCAD Addon Index                                         | Keep #73 canonical; close [#19](https://github.com/spkane/freecad-addon-robust-mcp-server/issues/19) because its original wiki-source defect was fixed                                                                                                                                                                                                                                               | The prior FreeCAD submission PR #528 was closed without merge. Resubmit only after security defaults, packaging, license metadata, install layout, and FreeCAD 1.1.3 compatibility are release-ready.                                                                                                                      |
| 14    | P2       | XS     | Take the lowest-risk dependency automation update                           | Review and merge [PR #114](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/114) first                                                                                                                                                                                                                                                                                                 | The Trivy action patch is isolated and its checks are green. It is a useful test of the dependency-update path before larger action majors.                                                                                                                                                                                |
| 15    | P2       | S-M    | Consolidate GitHub Action major updates                                     | Batch [#113](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/113), [#116](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/116), and [#118](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/118); handle [#115](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/115) separately                                                           | Setup Python, checkout, and metadata action updates have green checks but cross several workflows. Buildx changes affect container behavior and deserve a separate build/push smoke test. Prefer one maintained dependency branch and close superseded bot PRs.                                                            |
| 16    | P2       | XL     | Extract the task-oriented MCP redesign into reviewable changes              | Do not merge [PR #112](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/112) as-is                                                                                                                                                                                                                                                                                                     | The direction matches the `0.7.0` plan, but the PR is conflicting and changes 118 files with roughly 18,500 additions and 21,900 deletions. Treat it as a tested prototype and design source, not a merge unit.                                                                                                            |

### Acceptance criteria for the first nine items

The first maintenance-release queue is complete only when all of these are true:

1. A clean, unlocked installation resolves MCP 2.2.x and performs `initialize`,
   `tools/list`, and at least one real `tools/call` over stdio and Streamable HTTP
   without relying on the repository lockfile.
2. Starting from a directory containing unrelated secret-shaped `.env` entries
   neither crashes nor reads those entries into the configuration model.
3. Pad, Revolution, Groove, external geometry, curved/multi-object export,
   screenshot, and pocket regressions run against FreeCAD 1.1.3, not only mocks
   of generated Python strings.
4. Screenshot tests cover supported and unsupported active views, non-empty image
   data, preserved camera state, and cleanup after a forced `saveImage` failure.
5. Subtractive operations report a measurable postcondition, including a
   distinct no-change result.
6. HTTP listens only on loopback unless a user explicitly changes the bind
   address; its startup test targets the actual selected MCP SDK.
7. The exact wheel intended for PyPI passes the same clean-install and real tool
   call test on Linux, macOS, and Windows.

### Pull-request disposition summary

| Pull request | Recommended action | Merge condition |
| --- | --- | --- |
| [#100](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/100) | Revise, rebase, merge | Name/annotate helpers and assert every property fallback plus the single bound symmetry value |
| [#101](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/101) | Revise, rebase, merge | Address review feedback and verify the real FreeCAD 1.x `ExternalGeometry` shape |
| [#102](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/102) | Expand, rebase, merge | Incorporate duck typing from #106 and use exception-safe camera/temp-file cleanup |
| [#84](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/84) | Close as superseded | Reimplement only the HTTP concept with loopback-safe defaults; #100 replaces its Part Design change |
| [#112](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/112) | Park or close after extracting design notes | Replace with small RFC-backed slices; no direct merge of the 118-file branch |
| [#117](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/117) | Close as superseded | The direct migration updates the SDK API, metadata, lockfile, docs, and protocol regressions rather than only widening the dependency range |
| [#114](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/114) | Merge after normal review | Green security/pre-commit checks and no Trivy behavior regression |
| #113, #116, #118 | Consolidate | One cross-workflow validation run on the combined action-major update |
| [#115](https://github.com/spkane/freecad-addon-robust-mcp-server/pull/115) | Review separately | Local and CI multi-architecture container build and smoke test pass |

### Decompose PR #112 into `0.7.0` slices

Preserve the contributor's real-world local-model results, but separate the
architecture decisions from the deletion of the existing catalog:

1. **S, high value:** Add task-completion evaluations and retain the current
   catalog unchanged. This creates a baseline for comparing designs.
2. **M, high value:** Add an opt-in parametric profile alongside the existing
   profile. Measure tool-selection accuracy and context size.
3. **M, high value:** Introduce shared structured postconditions and FreeCAD
   diagnostics for recompute, constraint, transaction, and mutation failures.
4. **M-L, high risk:** Move transaction ownership to one executor boundary with
   rollback integration tests.
5. **S-M, medium value:** Add progressive guides as on-demand MCP resources.
6. **L, breaking:** Remove or rename legacy tools only after profile comparison,
   deprecation, migration documentation, and a `0.7.0` release candidate.

This ordering lets the project measure whether the redesign improves task
completion before accepting its largest compatibility cost.

## Codebase map

### Product boundaries

The repository contains two separately versioned products plus shared release and
documentation infrastructure.

| Product or area           | Responsibility                                                                                               | Current shape                                                      | Release unit                                        |
| ------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ | --------------------------------------------------- |
| Python MCP server         | Presents tools, resources, and prompts to MCP clients; delegates FreeCAD work to a bridge                    | `freecad_mcp` package, CLI `freecad-mcp`, stdio or Streamable HTTP | PyPI package, Docker image, GitHub release          |
| FreeCAD Robust MCP Bridge | Runs inside FreeCAD, serializes work onto the GUI thread, and exposes XML-RPC and newline-delimited JSON-RPC | Namespaced FreeCAD addon under `freecad/RobustMCPBridge`           | FreeCAD Addon Manager repository and GitHub archive |
| Bridge adapters           | Let the MCP server use XML-RPC, socket JSON-RPC, or direct embedded imports                                  | Common `FreecadBridge` abstraction with three implementations      | Included in the Python package                      |
| MCP surface               | CAD operations grouped by domain                                                                             | 152 tools, 13 resources, and 12 prompts                            | Included in the Python package                      |
| Documentation             | Installation, connection modes, API references, development, and release procedures                          | MkDocs Material with versioning through mike                       | GitHub Pages                                        |
| Engineering automation    | Development commands, tests, security scans, packaging, docs, and releases                                   | `just`, `uv`, pre-commit, GitHub Actions, Dependabot               | Repository infrastructure                           |

### Runtime flow

```text
MCP client
    |
    | stdio (recommended) or Streamable HTTP
    v
Python MCP server
    |
    | XML-RPC :9875 or JSON-RPC socket :9876
    v
FreeCAD workbench bridge
    |
    | queued execution on the FreeCAD GUI thread
    v
FreeCAD document, GUI, filesystem, import/export, and Python runtime
```

Embedded mode bypasses the workbench bridge and imports FreeCAD directly into
the MCP server process. It is a separate compatibility problem, not merely
another transport. On macOS it is unsafe because FreeCAD's bundled Python
runtime cannot be mixed with an ordinary interpreter, even when both report the
same minor version.

### Source organization

| Area                  | Notable modules                                            | Notes                                                                                                                                           |
| --------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Server startup        | `freecad_mcp.server`, `freecad_mcp.config`                 | Creates the MCP server, selects the FreeCAD bridge, and starts stdio or HTTP                                                                    |
| Bridge contract       | `freecad_mcp.bridge.base`                                  | Shared asynchronous CAD and execution interface                                                                                                 |
| External adapters     | `freecad_mcp.bridge.xmlrpc`, `freecad_mcp.bridge.socket`   | Client implementations for the in-FreeCAD workbench                                                                                             |
| Embedded adapter      | `freecad_mcp.bridge.embedded`                              | Linux-only direct import; version and ABI sensitive                                                                                             |
| Tool domains          | `freecad_mcp.tools` package                                | Documents, objects, Part, Part Design, Sketcher, Draft, Spreadsheet, view, import/export, macros, execution, validation, and supporting domains |
| Resources and prompts | `freecad_mcp.resources`, `freecad_mcp.prompts`             | Read-oriented context and reusable workflows                                                                                                    |
| Workbench lifecycle   | `RobustMCPBridge.init_gui`, command and preference modules | Registration, controls, status UI, and settings                                                                                                 |
| Workbench bridge      | `RobustMCPBridge.freecad_mcp_bridge.server`                | TCP/XML-RPC listeners, execution queue, arbitrary Python execution, and shutdown                                                                |
| Tests                 | Unit, integration, and `just` command tests                | Strong unit breadth; real bridge coverage is intentionally excluded from unit coverage                                                          |

The project is not small: the production Python under `src/` and `freecad/` is
approximately 20,900 lines, tests approximately 17,500 lines, and documentation
approximately 7,200 lines. This supports a staged release rather than a rewrite.

## Current release state

### What is already public

- GitHub marks Robust MCP Server `0.6.2` as the latest server release.
- GitHub also contains a Robust MCP Bridge Workbench `0.6.2` release.
- PyPI contains `freecad-robust-mcp` `0.6.1`, uploaded on 2026-01-13 with
  Trusted Publishing and Sigstore-backed provenance.
- PyPI does not contain `0.6.2`, so GitHub and PyPI are already on different
  public versions.
- Fourteen commits follow the `0.6.2` tag, including tool additions, packaging
  layout changes, installer changes, and crash fixes. These are release-worthy
  changes, not merely documentation cleanup.

### Distribution gaps

- PyPI provenance for `0.6.1` is bound to the old
  `spkane/freecad-robust-mcp-and-more` repository and workflow identity. Trusted
  Publisher settings must be changed before the renamed repository can publish.
- Project URLs in Python metadata, documentation variables, installation pages,
  issue links, Docker OCI labels, workbench release text, and contributor docs
  still reference the old repository.
- The workbench is not present under its current name or repository URL in the
  current FreeCAD Addon Index. Instructions that say users can already search
  for it in Addon Manager are therefore premature.
- There is no MCP Registry `server.json`, and the PyPI README lacks the required
  `mcp-name` ownership marker.

## Verification snapshot

These checks were run against the audited working tree. They are evidence for
planning, not a release certificate.

| Check                       | Result                                                             | Interpretation                                                                                                         |
| --------------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| Unit tests                  | 420 passed                                                         | Strong baseline for server logic                                                                                       |
| Unit coverage               | 83.47%, threshold 80%                                              | Passes the configured gate; bridge adapters are excluded                                                               |
| `just` command syntax tests | 190 passed                                                         | Command recipes parse correctly                                                                                        |
| Ruff                        | Passed with one invalid `noqa` warning in workbench path utilities | Fix warning before raising lint strictness                                                                             |
| MyPy                        | Passed for 26 server source files                                  | Does not type-check the FreeCAD workbench                                                                              |
| MkDocs strict build         | Passed                                                             | Current documentation builds, even though many links are stale                                                         |
| Actionlint                  | Passed                                                             | Workflow syntax is valid; semantic release defects remain                                                              |
| Bandit                      | Passed for server and workbench when invoked directly              | Configuration skips the exact arbitrary-execution and XML-RPC rules central to this product                            |
| Lockfile check              | Passed                                                             | The checked-in lock is internally consistent                                                                           |
| Python package build        | Passed                                                             | Produced a development wheel and source archive                                                                        |
| Package metadata check      | Current lock fails; Twine 7 passes                                 | The MCP 2.2 wheel and sdist build; locked Twine 6.2 rejects Metadata 2.5 while an isolated Twine 7 check passes        |
| CLI version                 | Corrected in MCP 2.2 migration                                     | CLI and server metadata now query the `freecad-robust-mcp` distribution                                                |
| Safety scan                 | Inconclusive                                                       | Account is authenticated, but the scan did not return and was stopped                                                  |
| Dependency inventory        | MCP runtime major resolved locally                                 | MCP 2.2.0 is locked and passes protocol and unit checks; unrelated updates remain                                      |
| Real FreeCAD integration    | Headless passed; GUI pending                                       | 46 passed and 17 GUI-only tests skipped against FreeCAD 26.3; run the isolated GUI suite before release                |

The local `uv` environment ran tests with Python 3.13.11 even though development
configuration and FreeCAD compatibility guidance call for Python 3.11. This is a
useful warning: the project declares an intention but does not currently enforce
which interpreter `uv` selects.

The installed local FreeCAD is a 2026-03-04 weekly arm64 build with bundled
`libpython3.11.dylib`. Its main executable has hardened-runtime signing metadata,
but the local `spctl` assessment returned an internal Code Signing subsystem
error. That weekly build is not suitable evidence for a stable release gate.

## Security assessment

### Security model to document

This server is a privileged local automation component. Its arbitrary Python
tool is not safely sandboxed merely because calls pass through MCP or a queue.
An authorized caller can read and write data available to the user's FreeCAD
process, change or delete models, access the filesystem through Python, and make
network requests if the runtime allows them.

The release must state this directly:

- The default trust boundary is one local user and one explicitly paired MCP
  client.
- The FreeCAD bridge is not a general network service.
- Arbitrary Python execution is a high-risk capability and should be disabled by
  default or placed in an explicit `unsafe-code` capability profile.
- “Sandbox” may only describe deterministic, enforced controls. Configuration
  flags that are not enforced must not be presented as security controls.
- Remote MCP access is a separately deployed mode that requires real
  authentication, encrypted transport, request limits, and operational logging.

### Findings

#### CRITICAL-1: Unauthenticated arbitrary code execution inside FreeCAD

**Category:** Spoofing, tampering, information disclosure, elevation of privilege  
**Reachability:** Any same-host process by default; remote clients if the bind
host is changed  
**Evidence:** The workbench bridge accepts socket `execute` requests, registers
XML-RPC `execute`, and calls `exec` with builtins in
`freecad/RobustMCPBridge/freecad_mcp_bridge/server.py:773-786`, with listeners
created at lines 838-844 and 1022-1028. No authentication check appears in either
request path.  
**Exploit:** A malicious local webpage helper, compromised process, or another
local user able to reach the port submits Python that reads files, modifies CAD
documents, or runs with the FreeCAD user's permissions. A non-loopback bind turns
the same path into remote unauthenticated execution.  
**Remediation:** Require application-level challenge-response for every bridge
connection, using a client-specific key that is protected by a distinct OS
identity, sandbox boundary, or hardware-backed credential. Unix peer credentials
and Windows named-pipe identity checks are supplementary transport checks, not
pairing proof by themselves. Store pairing material only in the platform
credential store or exchange it through protected IPC; do not rely on a
user-readable per-launch token. Validate proofs in constant time before every
method. Bind explicitly to `127.0.0.1` and `::1`; do not accept arbitrary bind
hosts in normal UI. Put arbitrary execution in an opt-in profile and show a
persistent FreeCAD warning while it is enabled.

#### CRITICAL-2: MCP HTTP exposes the privileged tool set on all interfaces

**Category:** Spoofing, tampering, elevation of privilege  
**Reachability:** Network-adjacent or remote, depending on host firewall and
routing  
**Evidence:** `src/freecad_mcp/server.py:429-433` starts Streamable HTTP on
`0.0.0.0`. The project adds no application authentication or explicit Origin
allowlist.  
**Exploit:** A reachable client invokes tools that ultimately execute in FreeCAD,
including arbitrary Python. DNS rebinding is also relevant when Origin is not
validated.  
**Remediation:** Default to `127.0.0.1`, validate Origin, and reject nonlocal
binding unless the operator explicitly configures a production remote profile.
For remote use, put the server behind HTTPS and implement MCP-compliant OAuth
with audience-bound tokens, least-privilege scopes, rate and concurrency limits,
and an allowlist of origins. Keep stdio as the recommended installation path.

#### HIGH-3: Security configuration is declarative but unenforced

**Category:** Elevation of privilege and security-boundary confusion  
**Reachability:** Any authorized MCP caller, plus unauthenticated callers through
the findings above  
**Evidence:** `enable_sandbox`, `allow_file_access`, and
`allow_network_access` are declared at `src/freecad_mcp/config.py:100-103`; only a
configuration unit test references them. The execution path does not enforce
them.  
**Exploit:** An operator believes network access is disabled and sandboxing is
active, while submitted Python still receives normal builtins and process
permissions.  
**Remediation:** Remove the flags for `0.7.0` or implement hard enforcement. Do
not promise an in-process Python sandbox. A genuine arbitrary-code sandbox needs
OS-level process isolation, a constrained filesystem, resource limits, and a
network policy. Use explicit capability profiles for application-level controls.

#### HIGH-4: Supported FreeCAD floor includes known-vulnerable releases

**Category:** Tampering and code execution through malicious files  
**Reachability:** A user or MCP workflow opening an untrusted FCStd file  
**Evidence:** `package.xml` declares FreeCAD `0.21` as the minimum. FreeCAD 1.1.3
states that all previously released versions are affected by one or more
code-execution or file-handling vulnerabilities triggered by malicious FCStd
files.  
**Exploit:** A prompt or external workflow induces the server to open an
attacker-controlled FreeCAD file on a vulnerable FreeCAD version.  
**Remediation:** Make FreeCAD 1.1.3 the security-supported baseline for the next
public release, or document older versions as unsupported and block opening
untrusted files. Test and declare the actual compatibility interval in both
manifest and docs.

#### MEDIUM-5: Timeouts do not cancel queued or running Python

**Category:** Denial of service and integrity  
**Reachability:** Any caller able to invoke execution tools  
**Evidence:** `server.py:742-758` stops waiting after a timeout, while queue
processing at lines 714-719 may still execute or complete the request. Python
`exec` occurs synchronously on the FreeCAD thread.  
**Exploit:** A request times out from the client's perspective but later modifies
the model, or an infinite/long computation blocks the GUI after the caller has
already retried.  
**Remediation:** Treat timeout as a client wait limit, not an execution limit, in
current documentation. Reject new work while a timed-out action may still be
active, add request state and cancellation where FreeCAD operations permit it,
and move arbitrary code that needs enforceable limits to an isolated process.

#### MEDIUM-6: Socket and XML-RPC request handling is weakly bounded

**Category:** Denial of service and information disclosure  
**Reachability:** Any process able to reach bridge ports  
**Evidence:** Socket handling repeatedly calls unbounded `readline` at
`server.py:857-879`; XML-RPC uses the standard server with introspection enabled.
There is no application request-size limit, per-client quota, or concurrency
limit.  
**Exploit:** A client holds connections open, sends oversized lines or XML
payloads, or queues expensive requests until FreeCAD becomes unresponsive.  
**Remediation:** Enforce strict byte, parse-depth, timeout, connection, and queue
limits. Disable XML-RPC introspection in production. Return a clear busy response
when the queue is full.

#### MEDIUM-7: Internal tracebacks are returned to callers

**Category:** Information disclosure  
**Reachability:** Any caller that can provoke an exception  
**Evidence:** The bridge returns `traceback.format_exc()` at
`server.py:797-807`, and many MCP tools forward `error_traceback` in results or
exceptions.  
**Exploit:** Errors disclose paths, module names, document names, or environment
details that help an attacker or leak user information into model context.  
**Remediation:** Log a correlation ID and full traceback locally; return a stable,
actionable error category and safe message over MCP. MCP SDK 2.x provides
`ToolError` for messages intended for the model and hides unexpected exception
details by default.

#### MEDIUM-8: Audit trail is insufficient for a privileged bridge

**Category:** Repudiation  
**Reachability:** All bridge clients  
**Evidence:** XML-RPC request logging is deliberately suppressed and bridge
requests have no authenticated client identity, operation digest, result status,
or tamper-resistant audit record.  
**Exploit:** After an unexpected model or file change, the operator cannot tell
which client invoked which operation.  
**Remediation:** Add structured local logs with request ID, paired client ID,
tool/method, risk class, duration, result class, and affected document. Never log
tokens, full arbitrary code, private model data, or file contents by default.

### Positive controls already present

- MCP uses stdio by default, which is the safest normal transport for a local
  client-launched server.
- The workbench binds to `localhost` by default rather than intentionally using a
  public interface.
- FreeCAD GUI work is serialized through a queue, reducing thread-affinity
  crashes.
- The Docker runtime uses a non-root user and removes packaging tools from the
  runtime layer.
- Tool inputs and outputs are typed, and all locally inspected tools advertise an
  output schema.
- Secrets scanning, CodeQL, dependency automation, linting, and security tooling
  are already represented in project automation.

These controls reduce risk but do not compensate for unauthenticated arbitrary
execution.

## Modern MCP plan

### Complete the MCP 2.2 boundary

The runtime now uses MCP Python SDK 2.2.0 and `MCPServer`, with the dependency
range aligned across project and MyPy environments. The server publishes its
name, human title, description, and actual installed package version. Bounded
protocol regressions now perform `initialize`, `tools/list`, and the first
`tools/call` over both stdio and Streamable HTTP; this directly covers the hang
reported against MCP 1.29.1. All unit tests and the headless FreeCAD 26.3
integration suite pass on Python 3.11.

Before `0.7.0`:

- Add a clean-environment installation test that resolves from `pyproject.toml`
  without the project lockfile. This is what PyPI users experience.
- Run the GUI integration suite and representative calls from the supported
  desktop MCP clients.
- Add server instructions, website URL, and icon metadata once the canonical
  release URLs and final icon asset are settled.
- Replace raw handler exceptions with safe `ToolError` or `ResourceError`
  messages where the caller can act; let unexpected exceptions stay local.
- Verify structured outputs after v2's content-block behavior changes.
- Exercise 2026-07-28 and earlier negotiated protocol revisions in CI.
- Do not adopt the Tasks extension yet solely for novelty. The current Python SDK
  2.0 release notes list it as a known gap. Reevaluate it when both spec and SDK
  support are stable and a real long-running CAD workflow benefits.

### Redesign the tool catalog for model usability

The current catalog contains 152 tools and serializes to approximately 170 KB,
with nearly 88 KB of descriptions. Broad CAD coverage is valuable, but presenting
all of it to every client increases discovery cost and makes similar tools harder
for a model to select reliably.

Introduce explicit profiles without deleting expert functionality:

| Profile       | Intended content                                                                           | Default                                  |
| ------------- | ------------------------------------------------------------------------------------------ | ---------------------------------------- |
| `core-read`   | Version, document/list/get, selection, view/status, and other nonmutating inspection tools | Yes for first connection                 |
| `modeling`    | Common document, sketch, Part, Part Design, transform, and export workflows                | Yes for normal local use                 |
| `domain-*`    | Draft, Spreadsheet, advanced Part, advanced Sketcher, and other specialist groups          | Opt-in                                   |
| `unsafe-code` | Arbitrary Python and macro creation/execution                                              | No; explicit enable plus visible warning |
| `all`         | Full compatibility catalog for expert users and regression testing                         | No                                       |

For every tool:

- Add a clear display title.
- Add correct `readOnlyHint`, `destructiveHint`, `idempotentHint`, and
  `openWorldHint` annotations. Treat annotations as UX hints, never enforcement.
- State when to use and when not to use the tool, important preconditions, units,
  coordinate systems, document effects, and whether recompute is automatic.
- Keep decision-ready structured output and avoid embedding raw tracebacks.
- Prefer one workflow-level tool over multiple low-level tools only when the
  workflow is stable and failure semantics are clear. Do not create a one-to-one
  wrapper for every FreeCAD API function.
- Move large, read-only reference material to resources when clients benefit from
  fetching it on demand.

### Add task-completion evaluations

Protocol and unit tests prove plumbing, not whether an LLM can successfully build
a model. Add a versioned evaluation set of at least ten realistic requests. Each
should require multiple tool calls and assert observable FreeCAD state or an
exported artifact.

Required cases:

- Create, constrain, pad, inspect, and export a simple part.
- Recover from a missing document or invalid object name.
- Select the correct tool among similar Part and Part Design operations.
- Use a specialist profile only after recognizing the capability is absent.
- Detect and recover from a recompute failure.
- Reject or request confirmation for destructive deletion.
- Demonstrate that `unsafe-code` is unavailable in the default profile.
- Exercise pagination or bounded listing if large object catalogs are introduced.
- Complete an operation over both XML-RPC and socket bridges.
- Confirm safe errors contain an action and no local traceback.

Run the official MCP Inspector for registration, schemas, notifications, errors,
and manual smoke tests. Add the MCP conformance harness for the protocol revisions
the server claims to support.

### Publish to the MCP Registry

After `0.7.0-rc.1` is available on PyPI:

1. Reserve a stable reverse-DNS identity, recommended
   `io.github.spkane/freecad-robust-mcp`.
2. Add the exact `mcp-name` marker to the package README.
3. Generate and validate `server.json` with the official publisher.
4. Declare the PyPI package, stdio transport, command, supported environment
   variables, repository, license, and version.
5. Publish from a protected GitHub Actions environment after PyPI publication and
   clean-install verification.
6. Add a CI check that `server.json`, package version, PyPI identifier, README
   ownership marker, and server runtime identity stay synchronized.

## Dependency and runtime update plan

Do not update everything in one change. The outdated inventory includes many
development and transitive packages, with several unrelated major versions.
Batch by risk and run the full relevant verification after each batch.

### Batch A: Emergency runtime compatibility

- Keep MCP on the migrated `>=2.2.0,<3` line and refresh the lockfile under
  Python 3.11.
- Verify clean PyPI-style resolution on Python 3.11, 3.12, and 3.13.
- Preserve bounded stdio and Streamable HTTP first-call regressions.
- Run GUI integration, build, and Inspector smoke tests; unit and headless
  integration checks already pass.

### Batch B: Packaging and security tooling

- Upgrade Twine from 6.2 to a version that accepts Metadata 2.5, currently 7.x,
  and update related `build`, `packaging`, and `readme-renderer` packages as one
  packaging batch.
- Upgrade Safety, Bandit, Ruff, pre-commit, and patch/minor security tooling.
- Repair Bandit's scope to include both `src` and `freecad`; remove the obsolete
  `macros` path.
- Reconsider blanket skips for `exec` and XML-RPC. If they remain intentional,
  use narrowly scoped suppressions with written threat-model references rather
  than global exclusions.
- Make the vulnerability scan noninteractive, time bounded, and reliable in CI.
  Keep a second independent advisory source such as OSV or `pip-audit` so one
  vendor outage does not erase the gate.

### Batch C: Development and documentation updates

- Upgrade patch and minor releases first.
- Isolate majors such as MyPy 2, Griffe 2, MkDocs-related plugins, Rich 15,
  Pygments 2.21, and PySide 6.11 into separate or semantically grouped changes.
- Avoid adding PySide from PyPI to the production workbench path; FreeCAD addons
  must use the Qt wrappers supplied by FreeCAD.
- Pin GitHub Actions to immutable commit SHAs while allowing Dependabot to update
  the references.
- Bring the docs workflow's setup-uv action onto the same reviewed release as the
  other workflows.

### Batch D: MCP SDK 2.2 certification

- Keep the MCP 2.2 migration and its required runtime dependency changes isolated
  from unrelated tool behavior changes.
- Validate clean unlocked installation from the built wheel, then run every
  server, schema, transport-security, Inspector, conformance, and integration
  test.
- Follow with an explicit catalog/annotation change rather than mixing 152 tool
  behavior edits into the SDK migration commit.

### Python and FreeCAD compatibility policy

The Python minor-version ABI requirement belongs specifically to embedded mode.
The external XML-RPC/socket server is a normal Python process and can support more
than the Python bundled inside FreeCAD.

Adopt this policy:

- FreeCAD 1.1.3 currently ships Python 3.11 builds and is the supported stable
  FreeCAD baseline.
- The external MCP server supports Python 3.11 through 3.13 after the matrix
  passes. Add an upper bound before an untested future Python release if required.
- Embedded mode is Linux-only, off by default, and supported only when the Python
  minor version exactly matches that FreeCAD build.
- Add a `.python-version` or equivalent `uv` configuration for the development
  baseline and pass `--python 3.11` explicitly in release workflows.
- Test the installed wheel on every claimed Python version; build artifacts once
  and reuse the same files for all publication jobs.

## Packaging, licensing, and product identity

### Versioning

- Fix CLI version lookup to use distribution `freecad-robust-mcp`.
- Feed the same resolved version into MCP server identity, wheel/sdist, Docker
  labels and tags, `server.json`, GitHub release text, and documentation.
- Keep the workbench independently versioned, but generate or validate its Python
  `__version__`, `package.xml`, archive names, and release notes from one value.
- Add a release consistency test before tag creation and again in CI.
- Do not reuse or move published tags. Use `0.7.0` for the MCP 2.2 release.

### License repair

- Decide whether `LICENSE-CODE` becomes the canonical `LICENSE` or whether every
  reference should name `LICENSE-CODE`.
- Update `package.xml`, release archives, PyPI metadata, README, and contributor
  docs to use the same exact SPDX identity and file name.
- Keep the icon's `CC-BY-NC-SA-4.0` notice clearly separate from MIT-licensed
  code. Confirm whether the icon may be included in every intended distribution,
  especially any registry or commercial downstream use.
- Inspect wheel/sdist license metadata so the noncommercial icon license is not
  ambiguously presented as the license of the Python code package.
- Include both applicable license texts in workbench archives and a short file
  mapping explaining which assets each license covers.

### Documentation and names

- Replace every stale repository URL and clone directory.
- Make “server,” “workbench bridge,” “MCP transport,” and “FreeCAD bridge
  transport” distinct terms. XML-RPC and socket are internal bridge transports,
  not MCP transports.
- Correct claims that the workbench is available in Addon Manager until it is
  accepted into the index.
- Add a compatibility table for FreeCAD version, bundled Python, operating
  system, connection mode, MCP SDK line, and supported MCP protocol revisions.
- Add `SECURITY.md` with a private reporting path, supported versions, expected
  response time, and the privileged-code-execution warning.
- Add a release support policy and a concise migration guide from `0.6.x` to
  `0.7.x`.

## FreeCAD Addon Manager release

The namespaced `freecad/RobustMCPBridge` layout aligns with current FreeCAD addon
guidance. Before requesting inclusion in the Addon Index:

1. Resolve bridge authentication and unsafe-code defaults.
2. Repair license consistency and validate `package.xml` against the current
   Addon Manager schema.
3. Test install, upgrade, disable, uninstall, and reinstall through the current
   stable FreeCAD Addon Manager on macOS arm64/x86_64, Windows, and Linux.
4. Verify `classname`, `subdirectory`, icon, branch, minimum FreeCAD version, and
   repository URLs from an actual index checkout or Addon Manager developer mode.
5. Ensure import and startup do not start listeners or perform network work
   without an explicit user action or clearly documented opt-in auto-start.
6. Publish the security and privacy behavior expected by the Addon Index,
   including what local ports open and what data can leave the machine.
7. Submit the repository to the FreeCAD Addons catalog following the current
   contribution process. Track review feedback as release-blocking until accepted.

Do not make GitHub release archives the primary workbench installation path once
Addon Manager distribution is available. Keep archives as reproducible fallback
artifacts and test their exact directory layout in a temporary FreeCAD user home.

## macOS signing and notarization

### Current products

No project-level Apple notarization is required for the current distribution
formats:

- The PyPI wheel is pure Python.
- The workbench archive contains Python, XML, SVG, and other addon resources
  loaded by the already signed FreeCAD application.
- The Docker image runs in a Linux virtual machine.

Notarizing a ZIP of source files would not give meaningful Gatekeeper protection
to the code FreeCAD imports. For the current products, prioritize cryptographic
checksums, GitHub artifact attestations, Sigstore provenance, SBOMs, immutable
release tags, and a documented verification procedure.

### If a native macOS deliverable is added later

If the project ships a standalone `.app`, native launcher/helper, `.pkg`, or
`.dmg`, add a separate macOS release pipeline:

1. Build universal or separate arm64/x86_64 artifacts from a clean tagged commit.
2. Sign every Mach-O component and the outer bundle with a Developer ID
   certificate and hardened runtime, using explicit entitlements.
3. Verify nested signatures with `codesign --verify --deep --strict` and assess
   with `spctl` before submission.
4. Package as a supported notarization container, submit with `notarytool`, wait
   for acceptance, and retain the notarization log.
5. Staple the ticket where the container supports stapling, then reassess the
   final distributed artifact offline.
6. Store signing credentials in a protected GitHub environment, use short-lived
   keychain access, and never expose certificates or passwords to pull-request
   jobs.

Do not bundle or modify the FreeCAD application unless its upstream licensing,
signature, update process, and notarization implications have been reviewed
separately.

## CI/CD and release engineering

### Required workflow shape

```text
tag candidate
    -> validate version, changelog, metadata, licenses, and clean tree
    -> run lint, types, unit, security, docs, and protocol conformance
    -> run stable FreeCAD GUI/headless integration matrix
    -> build wheel, sdist, workbench archives, and container once
    -> inspect and test the exact artifacts
    -> generate SBOM, provenance, attestations, and checksums
    -> protected release approval
    -> publish TestPyPI/prerelease candidate and smoke-test clean install
    -> publish PyPI, Docker, GitHub release, docs, and MCP Registry metadata
    -> verify every public channel and record immutable artifact digests
```

### Workflow fixes

- Make every publishing job depend on all validation and artifact-smoke-test jobs.
  The current container flow can push before the pushed-image test completes.
- Use one build output per artifact type and download it in later jobs. Do not
  rebuild after approval.
- Add Windows to wheel installation tests. Add Python 3.11, 3.12, and 3.13 for
  the external server if those versions remain supported.
- Add stable FreeCAD 1.1.3 GUI and headless jobs. Test weekly FreeCAD builds as
  allowed-to-fail early-warning jobs, not as release evidence.
- Update MCP initialize smoke tests from the hard-coded 2024-11-05 revision to a
  negotiation matrix. Keep an older revision only if compatibility is intentional.
- Validate workbench archives by extracting them into a temporary FreeCAD user
  directory and starting FreeCAD with an isolated profile.
- Use PyPI and TestPyPI Trusted Publishing bound to the new repository, exact
  workflow, and protected environment. Remove long-lived publication tokens where
  OIDC is available.
- Pin third-party GitHub Actions to full commit SHAs and let Dependabot maintain
  them.
- Add workflow timeouts, least-privilege job permissions, environment approvals
  for stable release, and concurrency that cannot cancel a publication halfway
  through.
- Generate SHA-256 files for every archive, sign or attest them, and attach the
  SBOM/provenance to the GitHub release.
- Make post-publication verification fail visibly if any channel has the wrong
  version, digest, command behavior, documentation URL, or server identity.
- Write a partial-release runbook. PyPI and tags are immutable, so recovery means
  completing missing channels or publishing a new patch, not rewriting history.

## Staged implementation roadmap

### Phase 0: Record release policy and threat model

**Goal:** Make product boundaries and trust assumptions explicit before changing
code.

- Approve `0.7.0` as the next release because the MCP 2.2 migration is a breaking
  runtime change.
- Decide whether arbitrary Python remains a supported feature and, if so, require
  explicit enablement.
- Decide whether XML-RPC remains compatibility-only and when it can be deprecated.
- Set the supported FreeCAD, Python, OS, client, and protocol matrices.
- Add `SECURITY.md` and a private reporting route before publishing sensitive
  findings externally.

**Exit gate:** A maintainer can state exactly who is trusted, what privileges the
server grants, and which combinations are supported.

### Phase 1: Make `0.7.0` installable and internally consistent

**Goal:** Finish certification of the MCP 2.2 migration and release packaging.

- Keep the tested MCP 2.2 range, lockfile, and protocol-level first-call tests.
- Preserve the corrected CLI/server version identity.
- Make XML-RPC or authenticated socket mode the consistent default.
- Repair license files and the workbench archive job.
- Upgrade package verification for Metadata 2.5.
- Replace all stale repository URLs.
- Reconfigure PyPI/TestPyPI Trusted Publishers.
- Synchronize release notes for the 14 post-`0.6.2` commits.

**Exit gate:** A clean machine can install the built wheel without the lockfile,
run `--version`, initialize over stdio, and see correct current metadata.

### Phase 2: Close the privileged transport boundary

**Goal:** Make the local architecture defensible before wider distribution.

- Add per-launch pairing/authentication for both bridge protocols.
- Bind bridge and local HTTP endpoints explicitly to loopback.
- Disable or isolate arbitrary Python by default.
- Remove or enforce misleading security flags.
- Add request, connection, queue, output, and execution-state limits.
- Sanitize remote errors and add structured local audit logs.
- Add adversarial tests for unauthenticated calls, oversized payloads, slow
  clients, replayed credentials, timeout races, and traceback leakage.

**Exit gate:** No unauthenticated caller can execute code or mutate a document,
and published configuration cannot accidentally expose that capability on a LAN.

### Phase 3: Certify `0.7.0` release candidates

**Goal:** Test the exact artifacts users will receive.

- Run all static, unit, packaging, docs, secrets, dependency, and security gates.
- Run stable FreeCAD GUI and headless integration on all supported platforms.
- Test PyPI-style wheel install, Docker-to-host bridge, manual workbench archive,
  and Addon Manager developer installation.
- Publish `0.7.0rc1` to TestPyPI and a GitHub prerelease; test from clean systems.
- Resolve all critical/high security findings and all release workflow failures.

**Exit gate:** Release checklist is green using immutable candidate artifacts and
recorded digests.

### Phase 4: Publish and verify `0.7.0`

**Goal:** Restore a trustworthy public stable release.

- Publish PyPI, Docker, GitHub server/workbench releases, and versioned docs.
- Verify public installs and digests independently of the build workspace.
- Announce the privileged execution model and security-supported FreeCAD floor.
- Monitor installation and crash reports for at least one week.

**Exit gate:** Every advertised channel serves the same expected version and all
critical user paths pass.

### Phase 5: Continue post-release MCP modernization

**Goal:** Improve tool safety and discoverability after the SDK 2.2 release.

- Expand safe errors, tool annotations, and capability profiles.
- Add Inspector, conformance, and ten-plus task-completion evaluations.
- Add and validate MCP Registry metadata.
- Test older clients through protocol negotiation and maintain the `0.6.x`
  migration guide.

**Exit gate:** At least 80% of the end-to-end evaluation set completes without
manual tool selection, protocol conformance passes, and default sessions do not
expose unsafe code.

### Phase 6: Addon Index and `1.0.0` readiness

**Goal:** Make installation and long-term maintenance predictable.

- Complete FreeCAD Addon Index review and address all catalog feedback.
- Run a compatibility soak with stable FreeCAD and several major MCP clients.
- Define semantic-versioning guarantees for tool names, input/output schemas,
  profiles, saved configuration, and workbench preferences.
- Establish monthly dependency/security maintenance and a supported-version
  retirement policy.
- Cut `1.0.0` only after release-candidate evidence supports those guarantees.

**Exit gate:** Installation is discoverable, upgrades are documented, the support
contract is explicit, and no P0/P1 release findings remain.

## Release checklist

### Product and security

- [ ] Threat model and privileged execution warning are public.
- [ ] `SECURITY.md` provides private disclosure instructions.
- [ ] Bridge requires pairing/authentication and loopback binding.
- [ ] Remote HTTP is disabled by default and production configuration is secured.
- [ ] Arbitrary Python is explicitly opt-in.
- [ ] Request, queue, body, output, and concurrency limits are tested.
- [ ] Full tracebacks stay in local logs.
- [ ] Supported FreeCAD floor includes required upstream security fixes.

### Compatibility and MCP

- [ ] Dependency constraints cannot resolve an incompatible MCP major.
- [ ] Server identity reports the correct version and metadata.
- [ ] Claimed protocol revisions pass conformance and negotiation tests.
- [ ] Tool annotations are complete and reviewed for accuracy.
- [ ] Default tool profile is small enough for reliable model selection.
- [ ] At least 8 of 10 representative task evaluations pass.
- [ ] MCP Inspector smoke test passes for each public transport.

### Quality

- [ ] Unit tests and configured coverage pass.
- [ ] Workbench tests and type/lint checks include the `freecad` tree.
- [ ] Stable FreeCAD GUI and headless integration pass.
- [ ] Windows, macOS, and Linux installation paths pass.
- [ ] Dependency vulnerability checks complete successfully from two sources.
- [ ] Secrets history and current-tree scans pass.
- [ ] Documentation builds strictly with link validation.

### Packaging and publication

- [ ] Wheel, sdist, workbench archives, and container are built once from the tag.
- [ ] Package metadata verification passes.
- [ ] License files and SPDX identifiers agree everywhere.
- [ ] Version and repository URLs agree everywhere.
- [ ] PyPI/TestPyPI Trusted Publishing targets the renamed repository.
- [ ] Exact artifacts pass clean installation and startup tests.
- [ ] SBOM, checksums, provenance, and attestations are attached.
- [ ] GitHub Actions are SHA-pinned and use least privilege.
- [ ] FreeCAD Addon Index status is described accurately.
- [ ] Post-publication verification passes on every channel.
- [ ] Partial-release recovery runbook has been exercised in a dry run.

## Recommended next work session

Keep the next implementation session intentionally narrow:

1. Finish review of the MCP 2.2 migration on PR #122.
2. Build the wheel and verify that a clean, unlocked installation resolves the
   supported MCP 2.2 range without using the repository lockfile.
3. Run bounded first-tool-call regressions over stdio and Streamable HTTP,
   including HTTP Host and Origin allowlist coverage.
4. Run MCP Inspector and conformance checks across the supported protocol/client
   matrix.
5. Assert `--version` and MCP server identity against built wheel metadata.
6. Repair the license/archive mismatch and Metadata 2.5 verification.
7. Run unit, `just` syntax, build, package verification, and real FreeCAD GUI and
   headless integration flows before cutting `0.7.0rc1`.

This completes the release-candidate evidence for the migrated runtime. The
following work session should focus only on bridge authentication and unsafe-code
policy, because that work deserves its own threat model, tests, and review.

## Authoritative references

- [MCP Python SDK releases and v1/v2 support policy](https://github.com/modelcontextprotocol/python-sdk/releases)
- [MCP Python SDK v1-to-v2 migration guide](https://py.sdk.modelcontextprotocol.io/migration/)
- [MCP 2026-07-28 Streamable HTTP security requirements](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
- [MCP security best practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices)
- [MCP tool annotations and their limits](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/)
- [MCP Registry publishing quickstart](https://modelcontextprotocol.io/registry/quickstart)
- [MCP Registry PyPI package requirements](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx)
- [Published PyPI package and provenance](https://pypi.org/project/freecad-robust-mcp/)
- [Current GitHub releases](https://github.com/spkane/freecad-addon-robust-mcp-server/releases)
- [FreeCAD 1.1.3 release and security notice](https://github.com/FreeCAD/FreeCAD/releases/)
- [FreeCAD Addon Index quality requirements](https://freecad.github.io/Addon-Academy/Topics/Addon-Index/Index/Qualities)
- [FreeCAD addon compatibility guidance](https://freecad.github.io/Addon-Academy/Guides/Maintaining/Compatibility/)
- [Apple notarization guidance](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)

## Audit limits

- This was a source, configuration, packaging, and release-readiness audit, not a
  penetration test.
- Real GUI/headless integration was intentionally left as a release gate rather
  than run against a possibly active desktop FreeCAD session.
- External registries and release pages were checked on the audit date and may
  change later.
- The authenticated Safety scan did not complete, so this plan makes successful
  vulnerability scanning a release requirement rather than asserting that the
  current dependency set is clean.
- Existing working-tree changes to `AGENTS.md` and `CLAUDE.md` were preserved and
  were not part of this audit.
