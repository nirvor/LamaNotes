# LamaNotes product contract

This document defines the product boundary behind LamaNotes. It is the first
reference for feature, interface and architecture decisions.

## Core job

LamaNotes should make two related tasks quick:

1. Open, read, edit and save ordinary text-based project files on Windows.
2. Keep a smaller set of durable notes in a private, visually richer Library.

The distinction is intentional. Most working material should remain local and
temporary. A note enters the Library only through an explicit user action.

## Workspace contract

- A Workspace file stays at its original local path.
- Opening it does not require a working network connection or Library login.
- Saving writes back to that same path without a save-as dialog.
- Syntax colour, previews and helper actions never alter raw copy output.
- External changes are detected, but LamaNotes does not become a sync engine.
- Unsaved content is protected through a local draft and conflict-aware save.

## Library contract

- Every Library note is one standalone HTML file.
- All active notes live in one server-side folder.
- Search, sparse tags and pinning provide retrieval; there are no subfolders.
- Tags describe content rather than recreate an organizational tree.
- `research` stays an ordinary tag. On notes carrying that exact tag,
  `r-<lowercase-ascii-slug>` tags may be exposed as derived topic facets; they
  do not create folders or another stored hierarchy.
- Media may enrich a note, but the text remains readable and machine-friendly.
- The server is authoritative; the desktop cache is bounded and disposable.

## Promotion contract

`Keep as note` creates a deliberate snapshot from Workspace to Library:

- one direction only;
- no local path in the resulting note;
- no silent overwrite on title collision;
- no reverse synchronization; and
- no future coupling between local and Library copies.

This keeps cloud memory useful without turning every work file into a durable
note.

## Interaction standard

The interface should feel closer to a small text editor than to a web
dashboard. `docs/DESIGN.md` defines the shared V2 tokens, content primitives,
responsive rules and anti-patterns for every host and note type.

- Local content appears before network-dependent surfaces initialize.
- LamaNotes has one active note in one application window. Opening another
  local file or Library note replaces it after Save, Discard or Cancel when
  the current note has unsaved changes.
- Common commands use compact familiar icons with labels available as
  tooltips and accessible names.
- Reading and editing use one main vertical scroll surface.
- Narrow windows remain first-class rather than showing a compressed desktop
  dashboard.
- Persistent controls stay few; contextual controls appear only when useful.
- A feature should not add a permanent panel merely because it can.
- Existing HTML checklists may enter the simple Work-note editor on first
  manual edit; ordinary HTML articles keep their source editor.

## Performance standard

- Local startup is independent of authentication and Library availability.
- Heavy viewers, diagrams, media tools and uncommon syntax modes load lazily.
- Warm Library data may accelerate reads but never becomes a second source of
  truth.
- Background polling pauses or slows when the app is hidden.
- Repeated note switches must settle without unbounded memory growth.

## Non-goals

LamaNotes is not a folder-based vault, graph browser, team wiki, project
manager, database notebook or general file synchronization service. Those
models add state and navigation that work against the product's main value:
opening text quickly and keeping only selected knowledge durable.
