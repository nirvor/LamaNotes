# LamaNotes architecture

LamaNotes combines a local Windows editor with a private HTML Library. The two
surfaces share one Vue client but have separate storage and availability
contracts.

## Components

### Web client

The Vue/Vite client contains the editor, note reader, search, Library index and
small publishing tools. Rich rendering modules are loaded only when their
content requires them. The same theme tokens, article primitives and viewer
stylesheet are used by web/PWA and the Windows WebView; see `docs/DESIGN.md`.

### Windows shell

The Python desktop shell hosts the bundled client in WebView2 and exposes a
loopback-only bridge for local file operations. It owns file associations,
window/session state, native open/save, local drafts, update installation and
the system-browser authentication handoff.

Local files are opened through this shell. They do not pass through the hosted
Library service. A launch without a file creates an independent application
window, which also supports separate Windows virtual desktops. A launch with a
file hands at most one path to an existing instance. The shell prefers the
currently focused LamaNotes process, then an instance on the same Windows
virtual desktop. It falls back to the most recently active instance only when
Windows cannot resolve any desktop identity; otherwise, an empty current
desktop gets its own window. The client applies the shared Save/Discard/Cancel
replacement guard.

Every file handoff carries a short random request ID. The target reserves that
ID before reading the file, so a timeout retry cannot dispatch it twice. An
ambiguous timeout against a still-running target never falls through into a
new window. The client serializes replacements and reports whether the handoff
completed, was cancelled, or failed after the save decision.

The last Workspace file session is stored once in the native local application
state under `%LOCALAPPDATA%\LamaNotes`. Independent windows may use different
loopback ports, so origin-bound browser storage is only a compatibility cache
and never the authoritative restore pointer. A normal launch therefore reopens
the last recorded Workspace file across all LamaNotes windows on that PC.

### Library server

The FastAPI server owns authentication, HTML note storage, search metadata,
attachments, publications and the bounded index consumed by the client. It
stores no local Workspace paths.

After authentication, `/api/bootstrap` combines the public UI configuration
and body-free semantic index in one safe first-load response. The separate
`/api/config`, `/api/index` and legacy `/api/auth-check` routes remain
compatible fallbacks. The client seeds its existing bounded caches from the
combined response; this is not another persistence layer.

The bounded `/api/index` response and per-note context share a derived
`researchTopics` field. It is populated only when the normalized tags contain
the exact `research` tag, and then only with sorted, deduplicated
`r-<lowercase-ascii-slug>` tags. The field does not persist a second index,
note bodies or a folder hierarchy.

New Research Notes may additionally carry six small provenance fields:
`researchId`, `primaryResearchTopic`, `researchType`, `researchFreshness`,
`researchOrigin` and an optional `parentResearchId`. They are derived from
`lamanotes-research-*` HTML metadata and exposed through the same bounded
index. The stable Research ID identifies the note across title changes; the
primary topic is the single broad retrieval facet used by LamaStart. Type
selects an information anatomy and Freshness records its verification horizon.
Neither changes the theme, visibility, flat Library, queue, or sync model.

LamaStart uses a dedicated API token with `notes:read` and the narrow
`research:edit` scope. The corresponding endpoint can change only the
Research Note filename/title and its one primary `r-*` topic. It checks the
previous modification time, normalizes metadata and the final visible tag
line, and writes atomically. It cannot change note bodies or ordinary Library
notes and does not grant `notes:write`.

### Edge and deployment

Caddy terminates public HTTPS, serves approved note assets and proxies the
application. The app container has no direct public port. Runtime secrets,
Library content and deployment state remain outside the source repository.

## Data flows

### Open a local file

1. Windows passes a path to the desktop shell.
2. The shell chooses the current virtual desktop's LamaNotes instance when one
   exists and reserves one idempotent handoff. If all known windows are on
   other desktops, it starts one window on the current desktop.
3. The current note enters Save, Discard or Cancel when it is dirty. Save must
   finish successfully before the replacement continues.
4. The shell reads at most one file and returns content plus safe metadata to
   the bundled client.
5. The editor renders immediately.
6. Authentication and optional Library warm-up continue later in the
   background.
7. Save writes atomically to the original path after checking for an external
   change.

### Open a Library note

1. The client uses its bounded warm index when available.
2. The server remains authoritative for the note body and current metadata.
3. The reader selects lightweight text rendering or richer HTML/media modules
   according to the note.

### Keep a local file as a note

1. The client creates a clean title and HTML snapshot.
2. The server rejects a title collision rather than overwriting silently.
3. The snapshot enters the flat Library without recording the source path.
4. Local and Library copies are independent from that point onward.

## Storage boundaries

| Surface             | Source of truth                | Persistence                             |
| ------------------- | ------------------------------ | --------------------------------------- |
| Workspace           | Original Windows file          | Original path                           |
| Unsaved local edit  | Desktop draft store            | Local and disposable after save         |
| Library             | Hosted HTML file               | One server-side folder                  |
| Library warm cache  | Desktop profile                | Bounded, clearable read cache           |
| Media               | Hosted asset file              | Served through the approved asset route |
| Session             | Server plus Windows protection | Cleared on logout or invalid auth       |
| Last Workspace file | Native desktop state           | Shared by all local app windows         |

Every installed Windows device uses the same fixed RackNerd Library origin.
Giving the build to another trusted device does not introduce another server,
account namespace or synchronization path; see `docs/TRUSTED_BETA.md`.

## Compatibility boundary

Some internal environment variables, HTML metadata attributes, CSS selectors,
runtime paths and service identifiers predate the LamaNotes product identity.
They remain compatibility contracts until a separate migration supplies
aliases, data conversion and rollback. They must not shape new user-facing
language or new APIs.

This boundary allows the product description to be clean now without risking
existing notes, installed clients or the live deployment through a cosmetic
global rename.

## Editing state and optimistic concurrency

`SourceEditor.vue` owns the shared CodeMirror editing surface. Work and HTML
editors adapt source/envelope handling and contextual tools. The mounted
document owns an in-memory CodeMirror state snapshot, including undo history.
It is discarded on document replacement, not persisted as another Library.

`documentSession.js` compares a pre-save snapshot with the current editor after
the response. Only a matching snapshot clears the draft or closes editing.
Local saves likewise advance the saved baseline to the submitted content,
without replacing text typed while the native write was pending.

Full-note responses include `version`, SHA-256 of format plus a NUL separator
plus the UTF-8 body. The client sends it as `expectedVersion` on PATCH. The
filesystem adapter checks it under the existing publication lock before rename
or write. A mismatch returns HTTP 409 with `detail.code = "note-conflict"`.
The field is derived, with no sidecar or index persistence. Older callers may
omit it for compatibility and therefore do not receive this protection.
New clients require a current version before modifying a cached Library note.

Checklist controls mutate the source through the same guarded save path.
Markdown matching excludes fenced code examples. Reader-only completed-item
visibility and touch hit areas are never serialized into note bodies.

## Release discipline

Private integrations are isolated under `/api/private/v1` and defined in
`docs/PRIVATE_API.md`. Immutable HTML note IDs survive renames. Personal-object
grants are checked before metadata/context/search/media projection. Legacy
owner sessions retain their current authority; private tokens cannot use those
routes. `.private` stores access/capture/provenance/receipt data and imported
assets, never another note body. Include it in Library backups. The v1 writer
uses the existing process-wide publication lock and assumes one application
worker per Library, as the current runtime does.

The exact-note Reader is a separate Vite entry using existing viewer components
and extracted, unchanged `appShell.css` / `noteShell.css`. Its single-object
cookie cannot bootstrap the broad owner app. This supports trusted rendering
without putting unrelated Library titles in screenshots.

1. Build and test the exact Git commit.
2. Create a named backup of configuration, Library data and the previous
   Windows update manifest.
3. Deploy an immutable image tag.
4. Wait for container health and verify note count and public HTTPS.
5. Publish the Windows package first and its verified manifest last.
6. Keep the previous image and update package available for rollback.
