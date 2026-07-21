# LamaNotes

LamaNotes is the independent source repository for a small HTML-first note
library and Windows text editor. Local project files stay at their original
paths. Selected durable notes live as HTML files in one flat server-side
library and are organized through sparse tags rather than folders.

## Current migration state

This repository starts from the tested NirvNotes codebase. The application,
installer, compatibility metadata and deployment paths still use the
`NirvNotes` and `flatnotes` names during the staged product rename. The
repository split deliberately happens first so that branding changes do not
get mixed with the Git history and deployment migration.

## Product model

- Workspace files (`.md`, `.txt`, `.cfg`, `.ini`, `.json`, `.yaml`, `.yml`,
  `.toml`, `.xml`, `.log`) are edited in place on Windows.
- Library notes are HTML files in one server folder.
- `Keep as note` creates an explicit one-way HTML snapshot of a local file.
- Rich notes can contain diagrams, plots, maps, images and source lists.
- The app stays intentionally flat, fast and small. It is not a notebook tree
  or an automatic file-sync system.

## Development

```shell
npm install
npm run build
```

Server tests use Python 3.11 and the dependencies declared in `Pipfile`.
Windows client dependencies are listed in `windows-client/requirements.txt`.

## Single-user Google login

Google login is an optional second authentication path for one exact verified
email address. Set `NIRVNOTES_GOOGLE_AUTH_ENABLED=true`, the Google client ID
and secret, `NIRVNOTES_GOOGLE_ALLOWED_EMAIL`, and
`NIRVNOTES_GOOGLE_PUBLIC_ORIGIN`. Register
`<public-origin>/api/auth/google/callback` as the web OAuth redirect URI. Keep
`NIRVNOTES_PASSWORD_LOGIN_ENABLED=true` during migration; it can be disabled
after web and Windows-client login have both been accepted.

Use the exact verified email for the controlled bootstrap login. Afterwards,
store its Google `sub` as `NIRVNOTES_GOOGLE_ALLOWED_SUB` in the private server
environment. Once set, both email and `sub` must match; do not print or commit
the account identifier.

## History and attribution

LamaNotes grew from the open-source flatnotes project by Adam Dullage. The new
repository is independent rather than a GitHub fork, while the original MIT
license and attribution remain intact. See `ACKNOWLEDGEMENTS.md`.
