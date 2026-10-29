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
