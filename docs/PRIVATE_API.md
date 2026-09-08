# Private integration API v1

This is the LamaNotes product contract for the personal ecosystem. Existing
owner sessions and legacy routes retain their current authority. A private
capability never authenticates on those broad routes. No existing note becomes
personal automatically. `research`, `work`, topics and pinning are not ACLs.

Base path: `/api/private/v1`. JSON uses camelCase. Responses carry
`integrationVersion: 1`, `domain: "personal"` and server-derived `ownerId`.
`LAMANOTES_PRIVATE_OWNER_ID` defaults to `personal-owner`; configure it consistently
with LamaStart. `LAMANOTES_PRIVATE_PUBLIC_ORIGIN` defaults to
`https://notes.thuber.org`. Keep both settings server-side.

## Authentication and grants

Use `Authorization: Bearer <capability>`. Tokens start with `lmp_`; only their
SHA-256 digest is retained. They are independent of LamaStart's tokens, cookies
and signing secrets. No owner token belongs in OpenClaw or a model workspace.

The signed-in owner deliberately enrolls an HTML note:

```json
POST /grants/notes
{"title":"Selected personal note","expectedVersion":"<64hex>","personal":true}
```

The response is the identified note and its current version. Enrollment adds one
`lamanotes-note-id` HTML meta field if missing. It does not copy the body or
change visible tags. Markdown stays unchanged. `DELETE /grants/{objectId}`
removes private integration eligibility, not the note/capture/asset itself.

Only the owner can enroll objects. Only the owner or a permitted parent can
issue capabilities. POST `/capabilities` and `/capabilities/delegate` accept:

```json
{
  "clientId":"openclaw-private",
  "jobId":null,
  "expiresIn":3600,
  "scopes":["notes:read","assets:read","references:read"],
  "noteIds":["ln-<32hex>"],
  "captureIds":[]
}
```

`expiresIn` is 60..2592000 seconds. Output is flat: common envelope,
`capabilityId` (`lg-32hex`), `audience: "lamanotes-private-v1"`, `clientId`,
`jobId`, Unix-seconds `expiresAt`, `scopes`, `noteIds`, `captureIds`, `parentId`
and the one-time `token`. `GET /capabilities` is owner-only metadata; it never
returns token digests or plaintext. DELETE `/capabilities/{capabilityId}` returns
204 and invalidates descendants. Owner, the capability itself or its ancestor
can revoke it. Revocation and expiry are checked on every request.

Scopes: `notes:read`, `notes:create`, `notes:update`, `references:read`,
`captures:read`, `captures:create`, `assets:read`, `assets:create`,
`capabilities:delegate`. There is no private delete or public-publication scope.
Delegation only narrows scope, object selection and expiry. It preserves clientId
and an already bound jobId. Objects created by a capability are available to it
and its ancestors; exact same-client, non-null-job capabilities may inspect that
job's creations for verification. Jobless peers do not inherit those objects.
Explicit object grants still require active personal enrollment.

## Notes and references

- GET `/index` returns `{items,total}` after grants are applied.
- GET `/search?term=...` searches only permitted notes, before snippets/ranking.
- GET `/notes/{noteId}` returns noteId, title, content, format, version, URL and
  researchId plus the common envelope.
- GET `/notes/{noteId}/context` returns the structured context, including full
  text, with the same stable noteId/version. It is not a body-free operation.
- GET `/notes/resolve?researchId=lr-...` resolves one permitted Research note.
- POST `/notes` accepts `{noteId?,title,content,captureIds:[],assetIds:[]}`. Content is
  passive HTML using shared components and explicitly attached private assets.
  Work-note text templates are checked too. v1 private imports do not accept
  Markdown image syntax inside those templates; use passive HTML media instead.
  A preassigned fresh noteId must match exactly one `lamanotes-note-id` meta
  field in the HTML. It is preserved. Without both fields the server assigns
  an ID. Public-publication metadata is rejected, not silently stripped.
  Apart from CRLF/CR normalization to LF, a preidentified import remains exact
  for the trusted renderer's HTML hash. Existing/reserved IDs cannot be adopted.
- PATCH `/notes/{noteId}` accepts `{expectedVersion,title?,content?}`.
  Missing expectedVersion is 422; a stale version is 409 `note-conflict`.

Creates require `Idempotency-Key: <opaque ASCII 8..128 chars>`. Repeating the
same actor/operation/key and input returns the same object. For bound jobs,
actor means the same clientId/jobId, so token rotation can resume a receipt.
Jobless grants remain capability-specific. Different input with
that key returns 409. Preserve the same key after an uncertain response.
The object ID is reserved durably before writing its file. Interrupted writes
resume only when existing bytes and metadata match; otherwise they fail closed.

IDs use `ln-` plus 32 lowercase hex digits. The HTML is authoritative for note
identity; an index/filename is not. Rename preserves identity. Legacy edits
which omit the meta field retain it, and replacement is rejected. Duplicate
identities fail closed. The canonical authenticated route is `/n/{noteId}`;
the client resolves it to the current note. Legacy title links still work.

`references:read` is sufficient for these body-free checks:

```json
POST /references/resolve
{"researchId":"lr-<32hex>"}

POST /references/check
{
  "parent":{"noteId":"ln-<32hex>","version":"<64hex>","researchId":"lr-<32hex>"},
  "sources":[{"captureId":"lc-<32hex>","sha256":"<64hex>"}]
}

POST /references/result
{"noteId":"ln-<32hex>","version":"<64hex>","researchId":"lr-<32hex>"}
```

Resolve returns noteId/version/researchId. Check returns the validated parent
(or null) and sources. Result returns noteId/version/researchId/title/url,
researchType/researchOrigin/researchFreshness/primaryResearchTopic/parentResearchId,
`htmlSha256` (UTF-8 HTML normalized to LF, no format prefix) and `assetManifest`.
That manifest is sorted by assetId and contains exactly assetId, sha256, role,
sourceAssetId (null for originals). A job-bound result must match that job.
Unavailable and forbidden objects both return 404; stale references return 409.

## Captures and source-preserving assets

POST `/captures` (idempotent) accepts:

```json
{
  "kind":"link",
  "text":"Explicitly selected personal text",
  "sourceUrl":"https://example.org/source",
  "assetIds":[],
  "provenance":{"channel":"web","description":null,"capturedAt":null}
}
```

Kinds are text/link/image/file/audio. Channels are web/android-share/windows/
telegram/whatsapp/codex. GET `/captures/{captureId}` returns the same data,
`captureId: lc-32hex` and sha256 over canonical input JSON. No source URL is
fetched by this API. No arbitrary local path is accepted as a file source.

POST `/assets` is explicit multipart upload with an Idempotency-Key. Fields:
`file`, `role=source|derived`, optional `sourceAssetId`, optional JSON
`cropReceipt`. Output includes `assetId: la-32hex`, sha256, mediaType, size,
width/height, role, sourceAssetId and cropReceipt. Original filenames are not
needed. Supported types are PNG/JPEG/WebP/GIF/PDF/UTF-8 text and WAV/OGG/MP3-ID3/
FLAC audio. Limit: 20 MB per file. MIME signatures are checked. SVG/HTML uploads
are not an executable media path. GET `/assets/{assetId}` returns metadata and
GET `/assets/{assetId}/content` enforces the same object grant on the bytes.
Non-image inputs download as attachments. Raw source bytes never get overwritten.

LamaPhotos remains a local crop/print step. Its fragment is
`#lp=v1&target=lamanotes&return_id=ln-...&source_id=la-...` with opaque IDs only.
Its return is fixed to `https://notes.thuber.org/n/{return_id}`. Credentials,
paths and caller-selected return origins never belong in that fragment.
An optional `lamaphotos.crop.v1` receipt contains source_system/source_id,
source_size_px/crop_rect_px/output_size_px/target_size_cm/print_dpi,
sha256_source/sha256_output/created_at and optional basename-only output_name.
Import verifies source and output hashes. A derivative is a new asset.
Dimensions and crop bounds are checked too. JPEG source dimensions may be
encoded or transposed because the browser applies EXIF orientation before
cropping. The crop rectangle uses that displayed coordinate space; output
dimensions must match exactly. File integrity is rechecked when reading assets
and result manifests. Corruption returns 409 rather than a stale trusted hash.
Lama-Hiking continues to own tour photos/GPX; reference them, do not clone an archive.

GET `/notes/{noteId}/assets` requires notes:read and assets:read. POST to the
same route accepts `{expectedVersion,assetIds:[]}` with notes:update. It adds
ownership links without rewriting the note body or replacing an original.
The owner can use Note menu -> Note media to download sources and explicitly
attach a returned crop. Media placement in the body remains an editor action.
GET `/settings` is owner-only. `LAMANOTES_PRIVATE_CROP_ORIGIN` optionally sets
the HTTPS LamaPhotos entry point; unset/invalid means no crop link. There is
no hardcoded private host or guessed public deployment.

## Exact-note reader for trusted rendering

POST `/reader-session` with a private bearer and `{noteId,expiresIn:120}`
requires notes:read, assets:read and that note's grant. Lifetime is 30..300
seconds, bounded by the capability. The response contains readerUrl, expiresAt
and noteId. A HttpOnly, SameSite=Strict cookie is scoped to
`/api/private/v1/reader/{noteId}` and Secure on HTTPS (HTTP only for loopback
development). It never authenticates an owner or general private API route.
The parent capability chain and object grant are checked on every read.

Open readerUrl in a fresh trusted browser context without owner cookies. The
page uses the production HtmlViewer/WorkNoteViewer, enhancements, typography
and shared app/note shell CSS. It does not load the owner App, store, router,
index, sidebar or config bootstrap. It maps managed media URLs to its exact-note
asset routes, which also check attachment membership. Its CSP limits data/media
requests to that reader subtree. No capability belongs in a URL or note body.

Theme follows prefers-color-scheme. The root exposes data-note-id,
data-note-version and `data-private-reader-ready="true"` only after shared
enhancements, fonts, image decoding and layout frames complete. A failed image
keeps readiness false. The trusted renderer must wait for this marker and use
the returned ID/version for the validation receipt. A standalone local HTML
lookalike is not evidence of the real LamaNotes reader.

## Owner/PWA UX and storage

Menu -> Private access is the explicit enrollment/grant/revoke UI. Private
capture previews selected data and requires a personal-content confirmation
before importing. A separate Keep as note action creates durable HTML.

The PWA Share Target posts to `/capture/share`; the controlling service worker
holds the selection locally in IndexedDB and redirects to a preview containing
only an opaque intake ID. No API upload occurs until Import. Import/discard
clears the held selection. Other fetches remain network-native. This does not
introduce offline sync or a native Android application. Real Pixel acceptance
is a separate host gate; desktop Chrome emulation is not proof of Android sharing.
The v1 Share Target assumes the deployed root path, as does the current PWA
manifest. An installation below a URL prefix needs a separate PWA-path pass.
Private requests are bounded before multipart parsing (21 MB for asset upload,
8 MB for other requests). Individual files remain limited to 20 MB and images
to 40 megapixels. Responses, including errors, use no-store.

The flat HTML Library remains authoritative. `.private/integration.sqlite3`
stores grants, token hashes, capture provenance, asset ownership and idempotency
receipts, not a second note body/index. `.private/assets` holds explicitly
imported note media. Back up this directory together with Library data. Do not
serve it as static content, commit it or import professional project archives.

## Trusted publisher boundary

The model/worker never receives a LamaNotes write capability. The parent trusted
publisher serializes per job, validates the live queue claim/fence/revision,
writes with a durable idempotency key, verifies the result and completes the
same queue job. Queue verification gets only a short-lived references:read
capability for that client/job. Revoke it after checking.

The queue check and note write are not an atomic distributed transaction.
Cancellation after the check can leave a private unannounced note. Reconcile
using the same receipt instead of creating a duplicate or reporting completion.
This is the accepted v1 boundary, not a claim of cross-service atomicity.
