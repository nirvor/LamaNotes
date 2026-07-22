# LamaNotes

LamaNotes is a fast, local-first text editor for Windows with a deliberate
private Library for durable notes. Everyday project files stay where they are.
Only material worth keeping is promoted explicitly into a clean, media-rich
HTML note.

The result is intentionally smaller than a knowledge-management suite: one
editor, one flat Library, sparse tags and no hidden synchronization.

## Two scopes

### Workspace

Workspace files are normal `.md`, `.txt`, `.cfg`, `.ini`, `.json`, `.yaml`,
`.yml`, `.toml`, `.xml`, `.log`, `.csv` and `.tex` files. LamaNotes opens and
saves them at their original Windows path. Raw copy and saved content remain
unchanged by previews, syntax colours or formatting helpers.

Workspace files are local work material. They are not uploaded, imported or
mirrored automatically.

### Library

The Library contains selected durable notes as standalone HTML files in one
server-side folder. Notes are found through search, sparse tags and a short
pinned list rather than through subfolders.

Library notes can combine readable text with images, diagrams, plots, maps,
tables, code and source links. They remain ordinary HTML files rather than
records in a proprietary notebook database.

`Keep as note` is the explicit bridge between both scopes. It creates a
one-way HTML snapshot from a Workspace file without storing the local path,
overwriting an existing title or establishing reverse synchronization.

## Product principles

- **Local first.** Opening a local file must not wait for login, network or the
  Library.
- **Explicit durability.** Cloud storage happens because the user asks for it,
  never as background synchronization.
- **Raw-file fidelity.** Editing, copying and saving preserve the real source.
- **Flat on purpose.** Search and a small tag vocabulary replace folder trees.
- **Reader and editor.** Plain work files stay quick to edit; durable notes may
  use the richer HTML reading surface.
- **Small interface.** Every permanent control must earn its space.
- **Private by default.** The normal deployment is a controlled single-user
  system.

LamaNotes is not intended to become a graph database, project manager,
collaboration suite or automatic multi-device file-sync service.

## Documentation

- [Product contract](docs/PRODUCT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Windows client](windows-client/README.md)
- [RackNerd deployment](deploy/racknerd/README.md)
- [Security](SECURITY.md)

## Development

```shell
npm install
npm run build
```

The server targets Python 3.11 and uses the dependencies declared in
`Pipfile`. Windows client dependencies are listed in
`windows-client/requirements.txt`.

## Authentication

The hosted Library supports a controlled single-user Google login and a
temporary password fallback for rollout and recovery. OAuth secrets stay on
the server. The Windows app completes login through the system browser and
stores its resulting session with Windows data protection.

Deployment-specific environment names and the cutover procedure belong in the
private operations repository, not in public product documentation.

## License

LamaNotes is available under the [MIT License](LICENSE).
