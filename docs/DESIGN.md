# LamaNotes Design

## V2 is still LamaNotes

Design Study V2 is a careful continuation of V1, not a rebrand. V1 already
established the useful product character: a quiet blue working surface, direct
navigation, compact controls, clear icons, little decoration, and a flat
Library that stays separate from local Workspace files.

V2 makes these rules explicit and shared. It applies to generic and tagless
HTML notes, Work notes, Research notes, legacy Markdown, the web Library, the
PWA on Android, and the bundled Windows WebView. Good typography and media
handling never depend on a tag.

## Product boundaries

- The Library remains flat. Tags are retrieval metadata, not folders.
- Workspace files keep their original local path. "Keep as note" creates an
  independent Library snapshot, not a second sync relationship.
- `research` is an exact normal tag. `r-*` tags are topic facets. Neither is a
  CSS switch.
- The hidden `pinned` state belongs to the star action. Do not expose it as a
  visible replacement tag.
- Work notes remain HTML snapshots with editable Markdown source. Legacy
  Markdown stays compatible and is not mass-migrated.
- The historical server/API `noteKind` name is a storage compatibility
  contract. The client presentation kind for non-Work HTML is `article`.

## Core tokens

Tokens live in `client/style.css` and reuse the existing `--theme-*` contract.
Components should consume these values instead of accumulating isolated
numbers.

| Token                                               | Purpose                                                   |
| --------------------------------------------------- | --------------------------------------------------------- |
| `--theme-brand`                                     | LamaNotes blue for focus, active state, and selected data |
| `--theme-heading`                                   | Heading and hierarchy blue                                |
| `--theme-link`                                      | Links and source references                               |
| `--theme-background`, `--theme-background-elevated` | Main and grouped surfaces                                 |
| `--theme-text`, `--ln-secondary-text`               | Primary and accessible secondary text                     |
| `--theme-border`, `--ln-border-subtle`              | Fine full borders                                         |
| `--theme-warning`                                   | Real warning or unresolved quality state only             |
| `--ln-space-1` to `--ln-space-5`                    | Compact spacing scale                                     |
| `--ln-radius-control`, `--ln-radius-card`           | Small control and card radii                              |
| `--ln-shadow-card`                                  | One restrained card shadow                                |
| `--ln-font-h1`, `--ln-font-h2`, `--ln-font-h3`      | Normal note heading hierarchy                             |
| `--ln-control-size`, `--ln-touch-target`            | Compact pointer controls and about 42px touch targets     |
| `--ln-content-max`, `--ln-toolbar-max`              | Article shell and shared toolbar measure                  |
| `--ln-reading-max`                                  | Optional prose measure                                    |
| `--ln-visual-max`, `--ln-wide-min`                  | Normal visual width and wide-visual pan width             |

Amber and red are reserved for warnings, destructive actions, failure, and
negative states. Do not introduce gradients, glass surfaces, rainbow series,
or a second brand accent.

## Article and content primitives

All primitives work without `research`, `r-*`, or any other tag.

### Article shell

Use:

```html
<article class="lamanote lamanote-article" data-lamanotes-component="article">
  ...
</article>
```

`lamanote-research` may be added when it helps describe the document, but it
does not grant a different theme. Existing Research notes using the legacy
class remain supported.

### Kicker and deck

`lamanote-kicker` is a short document type or date line.
`lamanote-deck` is one compact orientation sentence. Both are optional. Do not
manufacture a slogan or "overview" line for a note that does not need one.

### Summary

`lamanote-summary` is for a real short answer, decision, or compact set of
findings. It uses a quiet full frame. It is not a mandatory abstract and must
not repeat the article.

### Major section

Use `lamanote-section` for one major topic. Put its `h2` outside the optional
`lamanote-section-card`. Related `h3` subsections, prose, lists, tables, and
normal media stay together inside the card. A wide visual may follow the card
as a section sibling when it needs the article width.

Optional tones are:

- `lamanote-section--key`
- `lamanote-section--evidence`
- `lamanote-section--analysis`
- `lamanote-section--method`
- `lamanote-section--limits`

These tones organize content inside the same blue and blue-grey family. They
are not status badges and are never a required sequence. The old
`lamanote-research-section*` names remain aliases for existing notes.

### Metrics, panels, and callouts

- Use `lamanote-metrics` only for several real comparable quantities.
- Use `lamanote-panel` for a grouped instruction, decision, or reference.
- Use `lamanote-callout` for a genuine caveat or action.
- A normal paragraph does not need a card.
- A `blockquote` is a quotation. Inside a V2 article it uses a full frame, not
  a coloured side bracket.

### Media and visuals

- `lamanote-hero` or `lamanote-banner` is optional and only justified when the
  medium materially orients the reader.
- Use `lamanote-media`, `lamanote-media-row`, or `lamanote-media-grid` for
  explanatory images.
- Use `lamanote-plot`, `lamanote-diagram`, `lamanote-map`, or
  `lamanote-schematic` with `lamanote-visual-frame`.
- Add `lamanote-visual-wide` only when labels or panels need an intrinsic wide
  canvas. The medium then pans horizontally inside its frame. Caption and
  takeaway stay at article width. Its media focus target supports Left/Right,
  Home, and End for keyboard panning.
- Use `lamanote-visual-takeaway` for the one relationship or mechanism the
  reader should retain.
- Captions state source, date, protocol, units, assumptions, and uncertainty as
  applicable.

Plots answer an explicit quantitative question. They use honest comparable
rows, units, readable labels, exact values for small datasets, and annotations
for protocol breaks or important exceptions. Do not draw a continuous trend
through incompatible measurements.

Diagrams have a clear reading direction, named roles, consistent nodes and
connectors, and visible gates or feedback where relevant. Colour and line style
need a small legend only when they encode meaning. Illustration and measured
evidence must stay distinguishable.

### Links, sources, code, tables, and tags

Use `lamanote-link-list` for several related destinations and
`lamanote-link-card` for one link that needs context. `lamanote-source-list`
keeps sources compact and preserves normal link blue.

Code and tables may pan inside their own boundary. On a narrow screen, do not
compress an eight-column table or diagram until labels become unreadable.
Bottom tags stay the last metadata line and are enhanced by the shared viewer.

## Editor contract

The HTML editor offers separate "Generic article" and "Research article"
scaffolds. The generic scaffold adds no tags. The Research scaffold adds exact
`#research` and a clearly replaceable `#r-topic` placeholder.

The editor preview uses the same `HtmlViewer` and shared stylesheet as the
saved Library note. Component snippets use semantic HTML,
`data-lamanotes-component`, and shared classes. Do not generate layout
`style` attributes.

Scaffolds contain only short replaceable prompts. The editor and publish modal
show a non-blocking warning for known example links, media paths, topic
placeholders, or scaffold prose. The warning supports review; it does not
silently rewrite content.

## App shell and host rules

- Home, search, reader, editor, and Workspace use the same theme tokens.
- Every route uses the same centered toolbar measure. Context actions grow to
  the left; Home and Menu stay in the same two positions at the right edge.
- Creation, file opening, publishing/promotion, and view preferences belong in
  the Menu. The top row keeps only immediate document actions.
- Known global actions are icon-first with a tooltip, `aria-label`, visible
  keyboard focus, and a compact visual footprint.
- Ambiguous, rare, or destructive actions may keep short text. Delete remains
  confirmed.
- Pointer controls stay compact. Coarse-pointer targets use
  `--ln-touch-target`.
- PWA safe areas are respected. Android uses this responsive Web/PWA surface;
  there is no separate native Android design layer.
- Windows hosts the same Vue application in WebView2. Native-host overrides
  may adapt chrome and density, not fork the note design.

## Responsive and accessibility rules

- The page has one vertical main scrollbar and no horizontal body overflow.
- Only code, tables, Mermaid, and an opted-in `lamanote-visual-wide` may pan
  horizontally.
- Check desktop, about 390px, and the narrow 300px case in light and dark.
- Check 200 percent zoom and an effective 320px CSS viewport.
- Normal text needs at least 4.5:1 contrast. Large text and focus/non-text
  indicators need at least 3:1.
- Every icon control needs an accessible name and visible focus.
- The media preview is a modal focus boundary, closes with Escape, and restores
  focus to its trigger.
- Respect `prefers-reduced-motion`.
- Alt text explains the useful content or relationship. Captions do not replace
  alt text.

## Anti-patterns

Do not add:

- giant hero titles or empty landing-page space;
- filler KPIs, slogans, stock media, or decorative "insights";
- one card per paragraph;
- permanent sidebars or folder trees;
- coloured left or right callout brackets;
- inline layout styles in generated notes;
- a Research-only base stylesheet;
- note-specific global CSS for one new article;
- body-level horizontal scrolling;
- multiple icon sets or emoji product icons.

Large legacy note-specific styles remain scoped for compatibility. They are not
templates for new work.

## Release visual gate

Before release, render at least:

- a generic tagless article;
- a normal private or Work note;
- a Research note with `research` and one `r-*` facet;
- a short and a long note;
- code, a wide table, a normal image, and a wide visual;
- light and dark at desktop, 390px, and 300px;
- the web/PWA surface and the bundled Windows WebView.

Verify keyboard navigation, focus order, media dialog focus trapping, Escape,
touch targets, zoom, reduced motion, link/source contrast, and absence of body
overflow. Existing note bodies and Library data are not rewritten for a design
release.
