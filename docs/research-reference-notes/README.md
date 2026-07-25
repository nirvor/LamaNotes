# Research Note Reference Set

These six HTML files are synthetic editorial and visual fixtures for the
LamaNotes Research workflow. They are not private Library notes and must not be
published as factual advice. Their small datasets, prices, schedules, products,
and incidents are invented and explicitly labelled as such.

The useful contract is the composition:

- one shared LamaNotes visual language;
- a different reasoning and result structure for each Note Type;
- an editorial note header and, where useful, a compact fact strip;
- quiet section eyebrows and restrained filled surfaces rather than a stack of
  equal blue boxes;
- modern comparison tables without spreadsheet-like vertical grids;
- media which answers a named question;
- a final type-specific result with the condition which changes it;
- a canonical final tag line.

Do not copy headings mechanically. Future notes should copy the editorial
discipline and choose their own anatomy from the real request. The fixtures are
deliberately synthetic and may be published privately for design review, but
must never be presented as factual advice.

## Files

- `research.html` demonstrates evidence, mechanism, counterevidence, and an
  assessment.
- `travel.html` demonstrates a route decision, transfer risk, fallback, and a
  route result.
- `shopping.html` demonstrates requirements, like-for-like comparison,
  exclusion, and a recommendation.
- `invest.html` demonstrates assumptions, scenarios, downside, and a risk view.
- `practical.html` demonstrates prerequisites, bounded actions, failure
  branches, and independent verification.
- `aluhut.html` demonstrates fair claim reconstruction, a falsifiable test,
  ordinary alternatives, and a respectful evidence assessment.

## Local preview

Build LamaNotes first so the preview uses the exact production stylesheet:

```powershell
npm run build
```

From `C:\Users\thoma\Desktop\work`, start a local static server:

```powershell
python -m http.server 8765
```

Open:

```text
http://127.0.0.1:8765/LamaNotes/docs/research-reference-notes/preview.html?note=research&theme=light
```

Use `note=research|travel|shopping|invest|practical|aluhut` and
`theme=light|dark`. The harness loads the hashed CSS from the current
`LamaNotes/client/dist/index.html`, then inserts the selected fixture inside
the same viewer classes used by the application.
