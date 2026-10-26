# Tags and Library retrieval

The Library stays flat. Tags describe or retrieve a note. They do not create
folders, select a document renderer or grant access to an integration.

Tag identity is lowercase with surrounding whitespace and a leading `#`
removed. HTML tag metadata and explicit tag-only rows remain compatible with
older notes. General hashtags mentioned in HTML prose are not note tags.
Legacy Markdown keeps its existing hashtag and code-block rules.

For HTML, explicit visible tag rows are authoritative. Metadata is the
fallback when there is no such row. Hidden `pinned` metadata survives a visible
row change, but stale topic metadata must not reappear through the semantic
index. Search, the semantic index and the tag list use the same extracted tags.

## Retrieval tags and Research topics

- The curated Library labels are `research`, `shared`, `work`, `gaming`,
  `health`, `rezepte`, `stamsried`, `lamahiking`, `lamax` and `lamabot`.
  Manual notes can still receive another useful tag later.
- `research` retrieves Research notes. Their topic ID lives independently in
  `lamanotes-research-topic` metadata. Existing opaque `r-*` IDs stay compatible
  but are no longer retrieval tags. Readers prefer explicit topic metadata and
  fall back to legacy `r-*` tags for older notes. A valid Research ID or explicit
  topic also preserves Research semantics, while Work notes remain excluded.
- `shared` retrieves source material saved through the Android share intake.
  It is provenance, not a second folder or a capability grant.
- Pinning belongs to the star action. The hidden compatibility token `pinned`
  stays available to existing saved queries without becoming a visible topic.

The home suggestions omit exact technical labels `r-acceptance`, `r-fixture`,
`design-reference` and `publisher-demo`. Typed search and All tags still include
them. The six design-reference notes remain useful reference material. They
are not deleted or silently treated as current personal Research.

The home screen uses `client/tagPolicy.js` for suggestion eligibility. Tag
frequency or recent use can determine ordering, never font size or boldness.

## Explicit metadata cleanup

`notes.tag_cleanup` previews a supplied plan. It does not guess synonyms or
derive replacements from a note's body. Keep the real plan and its output
outside Git because they contain Library metadata.

The input uses exact flat filenames and a SHA-256 of the original raw bytes.
This `sourceSha256` is different from the normal API `Note.version`, which also
includes the format marker. Include current note/Research IDs when available.

```json
{
  "schema": 2,
  "notes": [
    {
      "filename": "Example.html",
      "sourceSha256": "<64 lowercase hex characters>",
      "researchId": "lr-<32 lowercase hex characters>",
      "expectedTags": ["private", "research", "r-methods", "pinned"],
      "tags": ["research"],
      "expectedPrimaryTopic": "r-methods",
      "researchTopic": "r-methods"
    }
  ]
}
```

Run with the application's Python environment and `server` on `PYTHONPATH`:

```text
python -m notes.tag_cleanup --directory <Library> --changes <private-plan.json>
```

The preview reports tags, hashes and changed span counts, without note bodies.
Schema 2 replaces the exact audited tag set, preserves hidden pinning and writes
the planned topic explicitly. It updates tag-only HTML rows and tag-only lines
in canonical Work/text Markdown sources together with tag metadata. All other
source bytes, including titles, prose, URLs, media, identity and Research
provenance, stay exact. Source hashes, tag sets and previous primary topics are
guards. Schema 1 remains available for older replacement-only plans.

An approved `--apply` belongs in the coordinated release window after the named
backup, with the note writer stopped. Run as the note-file owner. All entries
preflight before any write. Each file is replaced atomically with its mode and
modification time retained, so old reports do not become recent user edits.
The existing derived search index is rebuilt once after the batch. This is not a claim
of an atomic multi-file transaction or a lock against another running editor.

The general Research title/topic editor has a different purpose and may
normalize HTML formatting. It is not used for this surgical cleanup.
