# Contributing to LamaNotes

LamaNotes is currently developed as a tightly scoped single-user product.
Small bug fixes, performance work and focused usability improvements are a
better fit than broad feature additions.

## Before changing code

Read [the product contract](docs/PRODUCT.md) and
[the architecture](docs/ARCHITECTURE.md). A change normally fits when it:

- keeps local files at their original path;
- preserves raw copied and saved content;
- avoids automatic upload or synchronization;
- keeps the Library flat and HTML-based;
- reduces latency, ambiguity or permanent interface weight; and
- remains useful on both a narrow Win11 window and the reading surface.

Features that introduce a vault hierarchy, knowledge graph, collaboration
layer, background sync or a second project-management model are outside the
current direction.

## Issues and pull requests

Do not include credentials, private note content, host names or production
configuration in an issue. Security problems belong in a private GitHub
security advisory as described in [SECURITY.md](SECURITY.md).

Unsolicited feature pull requests are not actively accepted. For a compact bug
fix, first describe the visible problem, a reproducible case and the intended
behaviour. Keep the eventual diff narrow and add tests at the behavioural
boundary it changes.

## Local validation

At minimum, run the checks relevant to the changed layer:

```shell
npm run build
python -m compileall -q server windows-client
```

Frontend, server and Windows-client tests should also pass before a release.
Changes affecting layout need a desktop and narrow-window visual check.
