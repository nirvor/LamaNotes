# LamaNotes Project Instructions

These instructions apply to work in this LamaNotes repository and take
precedence over the shared workspace instructions where they are more specific.

## Default Delivery Contract

For completed LamaNotes code or product changes, do not stop after local
validation. Unless Thomas explicitly asks for local-only work or says not to
release, continue through the normal delivery chain:

1. Validate the intended change locally.
2. Commit only the intended LamaNotes paths and preserve unrelated local work.
3. Push the exact commit to the active LamaNotes branch.
4. Build the immutable VPS image and the signed or hash-verified Windows client
   update from that exact commit.
5. Create a named, verified VPS backup with an explicit rollback path.
6. Deploy the LamaNotes app and publish the matching Windows client update.
7. Verify the live revision, health routes, note-count invariants, unchanged
   Caddy state, and the published Windows update metadata and hashes.
8. Verify the result on the active Windows targets when reachable.

This is standing authorization for the normal scoped commit, push, deployment,
and release steps needed to make a requested LamaNotes change available for
testing. It does not authorize unrelated changes, broad cleanup, destructive
data operations, infrastructure redesign, or bypassing a failed safety gate.

## Active Windows Acceptance Targets

- The primary PC and the Mini-PC are the active NirvNotes/LamaNotes test
  targets. Make releases available to both and verify their update state when
  they are reachable.
- The laptop is currently switched off and not needed. Do not wait for it,
  wake it, target it, or treat it as a release blocker until Thomas explicitly
  puts it back into scope.
- A successful VPS deployment alone is not a Windows release. Keep server
  deployment, Windows update publication, and device acceptance as separate
  verified gates.

## Release Safety

- Preserve unrelated dirty work. Never use broad staging, reset, checkout, or
  cleanup commands.
- Use one coordinated SSH/deployment lane.
- Build the release artifact once from the committed revision and transfer that
  exact artifact. For Podman, retain Docker image format so the healthcheck is
  preserved.
- Before live mutation, capture and verify the backup. Recreate only the
  LamaNotes application unless the requested change genuinely requires more.
- Note counts may increase concurrently. Use a monotonic post-deploy guard and
  reconcile API and filesystem counts instead of requiring stale exact
  pre/post equality.
- Do not report a commit, push, deployment, client publication, device update,
  or live verification unless that specific step has current evidence.
