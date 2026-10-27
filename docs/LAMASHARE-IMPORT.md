# LamaShare import

`/share-import#ticket=lst_...` is an explicit Save to Notes handoff. The router
removes the fragment before authentication and retains it in this tab's
session storage for at most ten minutes. Google login returns to the clean
`/share-import` path. This view resumes the requested import automatically,
shows a real Notes receipt and offers Open note. Errors retain a retryable
ticket, while expired tickets point back to LamaShare. Home and ordinary
Android OS sharing never start an import.

The only new API is owner-only `POST /api/private/v1/share-import`, JSON
`{"ticket":"lst_..."}`. It requires a writing owner session, exact configured
Notes public Origin and `X-LamaNotes-Share: 1`. Device tokens, capabilities,
API tokens and anonymous requests cannot use it. All responses are no-store.

Notes uses only the fixed `http://nirvstart:8080` origin, POST
`/api/share/v1/notes-export` and the validated opaque file routes below it.
It forwards no browser cookies or owner token, follows no redirects and does
not fetch the item's source URL. Export metadata is bounded to 1 MiB. Files
are limited to ten and 20 MiB combined, checked against their exact declared
size, SHA-256, response MIME and the existing Notes media signature check.
No new long-lived credential or environment variable is required.

The existing private Capture, Asset and passive HTML note services perform
the save. Existing integration receipts provide stable per-item and per-file
idempotency. New tickets for an already imported item return the same note,
including subsequent owner edits. A different payload under the same item ID
is rejected. Original file bytes and the complete exported item, including
title, text, URL, annotation, filenames and optional unverified source, remain
in the source asset/capture metadata. Only the normal `shared` tag is added.
Source metadata grants no access and starts no Research job. Empty plain-text
files are supported by the existing source asset service.

## Coordinated release

This change is prepared in the Notes chat. LamaDroid Root owns production
ordering, backup and deployment. Do not independently deploy either service.

1. Make the matching Share export API available on `nirvstart:8080` in the
   shared `lamanotes_default` Docker network. Keep its scoped tickets/files
   contract and 600-second expiry.
2. From this exact committed Notes revision, build one Docker-format image
   with `org.opencontainers.image.revision` and its matching signed Windows
   update. Keep Notes data and unrelated dirty source work intact.
3. Under the shared release lock, run the normal verified compact Notes
   backup and app-only deployment, then publish the signed Windows manifest.
   No Library migration or import of existing clips is needed.
4. Verify health, revision, existing note hashes/counts, unchanged Caddy and
   updater signatures/hashes. Run one synthetic or owner-selected Share item
   through Save to Notes, Google return if needed, exact media retrieval and
   a second ticket returning the same note. Do not use an owner's unrelated
   clip as a test fixture.
5. Run normal post-release retention and guarded updates of the reachable PC
   and Mini-PC, preserving open editors and saved profiles.

Focused checks are `node --test client/shareImport.test.js` and
`PYTHONPATH=server python -m unittest test_share_import test_private_api`.
