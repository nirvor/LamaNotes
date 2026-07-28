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

## Compatibility boundary

Some internal environment variables, HTML metadata attributes, CSS selectors,
runtime paths and service identifiers predate the LamaNotes product identity.
They remain compatibility contracts until a separate migration supplies
aliases, data conversion and rollback. They must not shape new user-facing
language or new APIs.

This boundary allows the product description to be clean now without risking
existing notes, installed clients or the live deployment through a cosmetic
global rename.

## Release discipline

1. Build and test the exact Git commit.
2. Create a named backup of configuration, Library data and the previous
   Windows update manifest.
3. Deploy an immutable image tag.
4. Wait for container health and verify note count and public HTTPS.
5. Publish the Windows package first and its verified manifest last.
6. Keep the previous image and update package available for rollback.
