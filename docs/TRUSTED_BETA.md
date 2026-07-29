# Trusted beta boundary

LamaNotes can be installed on another manually trusted Windows device without
becoming an account or collaboration product. This is a trusted-device beta
for one logical Library principal, not multi-user hosting.

## Fixed system

- The Windows client is built for the fixed Library at
  `https://notes.thuber.org`.
- RackNerd remains the authoritative cloud store for Library notes, search,
  attachments and media.
- Local Workspace files stay on the Windows device where they were opened.
- There is one flat Library, one permission set and no per-person account,
  sharing, invite, ownership or attribution layer.
- Every authenticated beta device can read and change the same private
  Library. There is no private subset for the owner.

This is suitable only when the additional person and device may be trusted
with the complete Library. If that boundary is too broad, stop. Do not simulate
separation with tags or local folders.

## Device onboarding

1. Give the beta tester one manually verified installer through a private
   channel.
2. Verify the installer hash out of band. For a development certificate, trust
   that certificate manually on each intended Windows device. Never disable
   Windows verification globally.
3. Complete the existing single-principal login. Do not copy a DPAPI token
   between PCs; it is protected for the Windows account that stored it.
4. Confirm local file editing while offline, then Library login, one read and
   one reversible test edit.
5. Confirm that the client accepts the signed in-app update manifest before
   relying on automatic updates.

The current Ed25519 update key protects update continuity after the first
verified install. A public code-signing certificate is the cleaner next step
before distribution grows beyond a few manually managed devices.

## Offboarding and incident response

The system has no per-device server revocation control. Removing one beta
device therefore means:

1. log out and uninstall LamaNotes on that device, removing user data;
2. rotate the shared login credential or invalidate the single-principal
   server sessions;
3. verify the remaining trusted devices can log in again; and
4. review server logs and the Library backup if unexpected changes are
   suspected.

This limitation is intentional for the small beta. Adding per-device or
per-person identity would be a separate product decision, not a hidden
extension of this contract.

## Release gate

A beta release follows `docs/RELEASE.md` unchanged: exact commit, full tests,
immutable VPS image, named backup, signed and hashed Windows update, manifest
published last, live route/count checks and rollback retained. The additional
device does not justify another backend URL or a parallel synchronization
system.
