# Release candidate and recovery

Release tags are immutable. Review the commit, version, release notes, and CI
results before creating a component tag. Use a new prerelease version for an
end-to-end rehearsal; do not move or reuse a previously published tag.

For the server, an example candidate tag is `robust-mcp-server-v0.7.0-rc.1`.
The workflow builds the wheel and sdist once, tests the wheel on its OS/Python
matrix, and stages a multi-platform container under a unique candidate tag.
It verifies the image's package version and calls a real FreeCAD tool using the
candidate digest on the native CI runner. It then promotes that digest, publishes
the Python distributions to TestPyPI, and creates a GitHub prerelease. The
other image architecture is built but is not exercised by this native smoke test.

After publication, download the exact candidate artifacts and verify their
checksums and versions. In a disposable environment, install the exact version
from TestPyPI with PyPI as the dependency source, install the workbench archive
into an isolated FreeCAD profile, pair the bridge, and exercise a real tool call.
Confirm both stdio and HTTP with representative harnesses. Record the wheel,
archive, and image digests and the tested FreeCAD and Python versions.

## If a channel fails

1. Stop promotion and inspect the workflow results and each channel directly.
   Record which immutable package versions, image digests, tags, and releases
   already exist; a successful earlier job is not rolled back automatically.
2. Fix the underlying problem and rerun only failed jobs when safe. A rerun may
   encounter an already-published immutable Python version: verify its digest
   rather than trying to replace it. Never move a published Git tag.
3. If the published artifact itself is wrong, prepare a new version and tag.
   If the artifacts are correct, complete only the missing channels, verify the
   versions and digests, and document the recovery in the release record.
4. Verify that the new public package installs cleanly and its FreeCAD 1.x
   regressions pass against the published artifact, even though #87 is closed.

A failed run may leave a candidate image tag, and a failure after promotion can
leave the Docker release tag published before the Python package. Examine both
before recovery. Candidate tags are not evidence that a release passed.

## Recovering an interrupted CAM release

The component workflows stage a GitHub draft release containing
`cam-gate-v1.json` before exposing the release. A later release stops if it finds
such a draft. The receipt records the tested component tag, asset name and
SHA-256; it does not prove that publication to every channel completed.

1. Inspect the failed workflow and the draft release. Record the receipt and
   the SHA-256 of the staged wheel or workbench zip. Verify the staged asset
   matches both the receipt and the candidate artifact from the successful CAM
   gate. Confirm that the companion component used in the gate was tested as
   described in the workflow output.
2. Inspect every relevant publication channel independently. For a server,
   this includes PyPI or TestPyPI, Docker Hub, and GitHub Releases; for the
   workbench, inspect GitHub Releases. Record which channels contain the
   candidate version and compare the actual bytes or image digest. A published
   package or image is not rolled back when a later job fails.
3. If all published artifacts are the tested candidates, complete only the
   missing publication steps. If an immutable package already exists, verify
   it rather than trying to replace it. If any artifact is wrong or cannot be
   verified, do not publish the draft; follow the channel's correction or
   withdrawal process and prepare a new version and tag.
4. Once publication is complete, check that the draft is published and still
   contains its matching receipt and release asset. Retry the inventory-update
   job, or create a PR from its existing `automation/cam-inventory-<tag>`
   branch if GitHub rejected PR creation. Review and merge the exact asset and
   digest before tagging the next component. If the branch no longer matches
   the current proposal, regenerate it from current `main` and review the
   resulting diff rather than merging a stale inventory.

Do not delete a draft merely to clear the release gate. If a partially
published version is intentionally withdrawn, first resolve each channel and
record the decision. Then remove the withdrawn draft through a reviewed
recovery procedure, or publish the verified draft and retire the published
release in the compatibility inventory. Adding an unpublished draft to
`retired_servers` or `retired_workbenches` does not unblock subsequent releases:
the gate rejects staged drafts before checking retirements. A published CAM-capable release without a receipt also
requires investigation. Restore a receipt only if the successful CAM gate and
exact published asset can be verified from the original run. Otherwise correct
or withdraw the affected publication and create a new, properly gated release.

The server and workbench workflows share one release queue. Wait for the active
release run to finish before pushing the next component tag. If a queued run
was canceled because a newer run replaced it, rerun the canceled release after
the active run finishes.
