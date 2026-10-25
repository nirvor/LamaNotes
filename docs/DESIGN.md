# LamaNotes Design

## LamaX application profile

LamaFocus is the first working reference, LamaStart the second and this
application the third. Match their quiet blue hierarchy, compact Poppins
400/600 type, fine frames and short, task-specific controls. A normal app bar
uses a 15px blue name and the existing 28px app mark, with a 43px minimum
height. Related controls use 4-8px gaps and groups use 8-12px gaps. Preserve
42-44px coarse-pointer targets and 16px editable text on phones.

The shared light page/surface pair is `#eff4f9` / `#ffffff`. Dark uses
`#1b1f25` / `#2b313a`. Brand blue is `#1e5c91` in light and `#97d2ff` in dark.
Use a meaningful surface with a fine complete border instead of extra cards
or shadow. Maps, photo stages and documents keep their useful content layout.
The document-title copper accent remains a reading convention, not a second
application brand. Product controls use English. User content keeps its language.

Short checklist sections group their label, list and local actions without a
visible box. Add, Edit and Hide/Show content sit directly beside the section
label. Entry and section-edit forms stay within their own section. Use compact,
uniform heading sizes and list spacing, while preserving coarse-pointer targets.
Collapsing a section is local display state. Editing only updates that section,
with a retained draft and version check. Preserve item order, heading semantics,
keyboard focus and note bodies. No progress counters or list administration
controls are added.

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
- Quicknotes uses a plain Markdown writing surface. Its legacy scratch-note
  wrapper is adapted on open without a storage write. The first changed save
  keeps its HTML file, stable identity and head metadata, with rendered content
  and a canonical Markdown template. Preserve existing prose, including old
  helper text. This mode is structural, not tied to the title or a tag, and
  does not apply to rich articles or Research notes.
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
| `--theme-title-accent`                              | Warm document-title accent; never a status colour         |
| `--theme-link`                                      | Links and source references                               |
| `--theme-background`, `--theme-background-elevated` | Main and grouped surfaces                                 |
| `--theme-text`, `--ln-secondary-text`               | Primary and accessible secondary text                     |
| `--theme-border`, `--ln-border-subtle`              | Fine full borders                                         |
| `--theme-warning`                                   | Real warning or unresolved quality state only             |
| `--ln-space-1` to `--ln-space-5`                    | Compact spacing scale                                     |
| `--ln-radius-control`, `--ln-radius-card`           | Small control and card radii                              |
| `--ln-shadow-card`                                  | One restrained card shadow                                |
| `--ln-font-body`, `--ln-font-small`                 | Normal and compact secondary text                         |
| `--ln-line-small`                                   | Compact row line height                                   |
| `--ln-font-h1` to `--ln-font-h3`                    | Note heading hierarchy                                    |
| `--ln-control-size`, `--ln-touch-target`            | Compact pointer controls and about 42px touch targets     |
| `--ln-content-max`, `--ln-toolbar-max`              | Article shell and shared toolbar measure                  |
| `--ln-reading-max`                                  | Optional prose measure                                    |
| `--ln-visual-max`, `--ln-wide-min`                  | Normal visual width and wide-visual pan width             |

The light main surface is a very pale blue-grey rather than pure white.
Elevated controls and real groups may use white, so hierarchy remains visible
without glare. The warm copper title token is the one narrow exception to the
blue hierarchy: it distinguishes a document `h1` from blue `h2` and `h3`
headings. It does not colour tags, data series, controls, or status. Brighter
amber and red remain reserved for warnings, destructive actions, failure, and
negative states in the application UI. Scientific figures may use other
colours, including these hues, when the subject and perceptual clarity justify
them. The UI palette is not a restriction on data encodings. Avoid decorative
gradients, glass surfaces, and arbitrary rainbow series.

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
Research Notes may use the deck as an unlabeled introduction. Do not spend a
line on `Introduction` when placement and composition already make that role
clear.

Substantial Research Notes group kicker, literal title, and deck in
`lamanote-research-header`. The header is an editorial entry point, not a hero:
no giant title, empty banner space, decorative gradient, or generic metadata.
Synthetic references may use `lamanote-reference-status` for a compact factual
disclaimer. Normal notes should not manufacture status chips.

### Summary

`lamanote-summary` is for a real short answer, decision, or compact set of
findings. It uses a quiet full frame. It is not a mandatory abstract and must
not repeat the article.

Research Brief V2 does not require this component. A type-specific result near
the end may instead use normal prose, a recommendation, route result, action
list, risk view, or assessment without a generic `Summary` heading.

### Type-specific result

Use `lamanote-result` near the end when the note needs one compact answer the
reader can act on. Set `data-result-kind` to a plain semantic value such as
`assessment`, `route`, `recommendation`, `risk`, or `action`. These values do
not create six visual themes. They keep the result legible to humans and tools
inside one quiet LamaNotes component. `risk` may use the warning token when the
risk itself is the result.

The result contains:

- a short label which fits the Note Type;
- one direct main sentence;
- one condition, reservation, or next action which can change the answer.

Do not repeat the opening or add a generic conclusion paragraph after it.

### Major section

Use `lamanote-section` for one major topic. Put its `h2` outside the optional
`lamanote-section-card`. A section owns at most one visible surface:

- use the section card for related prose, `h3` subsections, and lists when a
  grouped surface improves the hierarchy;
- when the main component is a visual, comparison table, callout, panel, or
  result, keep that component as a direct section child and leave the
  surrounding prose open;
- never place a surfaced component inside a section card. The shared viewer
  flattens this old pattern for compatibility, but new HTML must not produce it.

This is the surface-ownership rule. A fine border around the meaningful object
is enough. The reader should never see card, inner card, and a third SVG canvas
for one idea.

`lamanote-section-eyebrow` is an optional short role label such as `Evidence`,
`Mechanism`, `Route`, or `Model limit`. It helps a long note scan without
turning the heading into a numbered encyclopedia outline. Omit it when it would
only repeat the `h2`.

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
- At the top level of a Research Note, two or three metrics render as a quiet
  fact strip rather than a dashboard card grid.
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
- Add `lamanote-flow` to process and decision diagrams. It uses the compact
  flow canvas and fine connector defaults. A figure title or background canvas
  is allowed when it makes the figure self-contained or preserves contrast.
- Add `lamanote-visual-wide` only when labels or panels need an intrinsic wide
  canvas. The medium then pans horizontally inside its frame. Caption and
  takeaway stay at article width. Its media focus target supports Left/Right,
  Home, and End for keyboard panning.
- Optionally use `lamanote-visual-takeaway` for the one relationship or
  mechanism the reader should retain. Omit it when the caption already says it.
- Captions state source, date, protocol, units, assumptions, and uncertainty as
  applicable.

Plots answer an explicit quantitative question. They use honest comparable
rows, units, readable labels, exact values for small datasets, and annotations
for protocol breaks or important exceptions. Do not draw a continuous trend
through incompatible measurements.

Paper-grade scientific clarity takes priority over a fixed visual template.
Use the shared `scientific_figures.py` toolkit and `SCIENTIFIC_FIGURES.md` in
LamaNotes-Research for figure construction. Matplotlib SVG/PNG, scientific
schematics, and the existing Plotly/Kaleido light/dark pairs are supported.
Choose plot form, shapes, fills, colours, type sizes, scale, ticks, grid,
facets, and uncertainty representation for the scientific question. Units,
axes where used, uncertainties where applicable, readable labels and a
documented source/date basis remain required. Do not invent error bars where
no uncertainty estimate exists. Ordinary magnitude bars start at zero; explain
a scientifically justified truncated axis. Legends, legend titles, figure
titles, subtitles, and separate question/takeaway blocks are optional. Direct
labels or a caption can be sufficient. Do not add empty structure to satisfy
a template.

A single neutral paper figure can use this tag-independent envelope:

```html
<figure
  class="lamanote-plot lamanote-visual-frame"
  data-lamanotes-component="plot"
>
  <img
    class="lamanote-figure-paper"
    src="attachments/figure.svg"
    alt="Describe the variables, relationship and important uncertainty"
    loading="lazy"
    decoding="async"
  />
  <figcaption>
    Finding, measurement basis, uncertainty and direct source/date.
  </figcaption>
</figure>
```

`lamanote-figure-paper` belongs on an image or inline SVG. It supplies a white
canvas in either theme, including for a transparent export with dark ink.
The caption still uses the application theme. Exporting an opaque background
is also valid; do not invert or recolour scientific images in the reader.
Matching light/dark figures may continue to use `lamanote-plot-pair` and
`lamanote-plot-image--light` / `--dark`. Two exports are not mandatory.
Check the actual rendered figure, including its labels, caption and mobile
panning, in both themes. A readable neutral figure is preferable to a broken
dark variant.

Additional CSV/JSON files of the actually plotted data are created only when
explicitly requested. This does not restrict embedded interactive data,
original inputs, or source attribution.

Diagrams have a clear reading direction, named roles, consistent nodes and
connectors, and visible gates or feedback where relevant. Use short node labels,
one optional secondary line, fine non-scaling strokes, and a compact layout
grid. Most flow diagrams should fit in a roughly 52rem frame without using the
full article height. Colour and line style need a small legend only when they
encode meaning. Illustration and measured evidence must stay distinguishable.

Mermaid is a convenient default for flow and decision diagrams, not a required
renderer for every scientific diagram. Its Dagre layout, 14px type, linear
connectors and compact spacing are defaults, not authoring restrictions.
Decision diamonds, rounded terminals, scientific symbols, filled regions and
subject-appropriate colours or font sizes are valid. The reader preserves
authored Mermaid styling and SVG geometry. Hand-written or tool-generated SVG
and PNG are equally valid when they explain the mechanism better. Preserve
clear reading direction, contrast, meaningful connectors and accessible text.
Keep Mermaid's strict security mode and the existing HTML safety boundary.

### Links, sources, code, tables, and tags

Use `lamanote-link-list` for several related destinations and
`lamanote-link-card` for one link that needs context. `lamanote-source-list`
keeps sources compact and preserves normal link blue.

Code and tables may pan inside their own boundary. On a narrow screen, do not
compress an eight-column table or diagram until labels become unreadable.
Bottom tags stay the last metadata line and are enhanced by the shared viewer.

Use `lamanote-comparison` for a decision table whose rows are genuinely
comparable. Give it a caption with date, basis, and decision context. Use units
and denominators in the cells, `scope` on row and column headers, and
`data-preferred="true"` only when the prose has justified a preferred row.
The component uses one transparent table surface, horizontal row rules, and
text weight or border emphasis for the preferred row. Header, first column, and
preferred row must not create three different filled bands. Avoid checkmark
matrices which hide trade-offs.

Use `lamanote-steps` for bounded practical work. Each step states the action,
the expected observation, and a stop or failure branch where relevant. The
last step verifies the result independently. It is not a decorative timeline.

## Editor contract

The HTML editor offers separate "Generic article" and "Research article"
scaffolds. The generic scaffold adds no tags. The Research scaffold adds exact
`#research` and a clearly replaceable `#r-topic` placeholder.

The editor preview uses the same `HtmlViewer` and shared stylesheet as the
saved Library note. Component snippets use semantic HTML,
`data-lamanotes-component`, and shared classes. Do not generate inline layout
styles for the note shell. Scientific SVG presentation attributes and renderer
styles are allowed; they are part of the figure, not a second application UI.

Work-note Markdown may wrap a short secondary status or detail in
`<small>...</small>`. The compact editor action inserts this semantic tag and
the text otherwise inherits the normal typeface, colour and weight. A fully
compact row also receives the matching tighter line height and spacing. The
action preserves Markdown list, checklist, number and quote markers, supports
several selected rows and toggles an existing compact selection off. Use it for
individual phrases or rows, not as a replacement for the normal note body or
heading hierarchy.

Scaffolds contain only short replaceable prompts. The editor and publish modal
show a non-blocking warning for known example links, media paths, topic
placeholders, or scaffold prose. The warning supports review; it does not
silently rewrite content.

## App shell and host rules

- Home, search, reader, editor, and Workspace use the same theme tokens.
- Home uses search, a count-aware tag cloud, and one compact, unlabelled,
  single-column pinned-note list as real navigation. A monochrome LamaNotes
  mark may sit behind this content as a low-contrast watermark; it must remain
  non-interactive and must not compete with note links.
- Local and Library documents show one content surface at a time. Markdown and
  text-like files open as a rendered reading view. Edit or double-click
  replaces that view with the source editor; Done returns to the rendered
  view. An editor preview may replace the source temporarily, but source and
  preview are never stacked as a dual view.
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
- Workspace path actions stay in the toolbar row. `Local`, size, encoding, and
  line endings share one compact pill row below it, without increasing the
  header height.

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
- nested card, visual-frame, table, callout, panel, or result surfaces;
- redundant figure headings or decorative nested canvases; a scientific
  figure's own background or self-contained title is not a violation;
- tables which use a separate fill for the caption, header, first column, and
  highlighted row;
- permanent sidebars or folder trees;
- coloured left or right callout brackets;
- inline application-layout styles in generated notes;
- a Research-only base stylesheet;
- note-specific global CSS for one new article;
- body-level horizontal scrolling;
- multiple icon sets or emoji product icons.

Research Note cards and visual frames retain their quiet square geometry.
That surrounding UI choice must not flatten scientific shapes, erase fills,
force a palette, or change type inside a figure. Compact product controls
elsewhere may keep their normal radius.

Large legacy note-specific styles remain scoped for compatibility. They are not
templates for new work.

## Release visual gate

The shared source editor keeps one compact icon toolbar, with labels/tooltips
and keyboard equivalents. Link entry appears only when requested. Formatting
retains the selected text, so applying or removing a style is repeatable.
Work/HTML previews replace the editor rather than stacking a second view.
Completed checklist rows use the existing muted-text token. Section add, edit
and collapse controls belong beside their label, not the global toolbar.
No completion counter, progress card or automatic sorting is added.

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
