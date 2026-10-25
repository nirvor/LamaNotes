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

## Workflow and topic tags

- `private`, `work` and `infra` remain ordinary retrieval labels.
- `research` identifies Research retrieval. Valid `r-*` tags are its topic
  facets, with the existing optional primary-topic metadata. A topic tag alone
  does not make a note Research.
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
  "schema": 1,
  "notes": [
    {
      "filename": "Example.html",
      "sourceSha256": "<64 lowercase hex characters>",
      "researchId": "lr-<32 lowercase hex characters>",
      "expectedPrimaryTopic": "r-acceptance",
      "replacements": {"r-acceptance": "r-methods"}
    }
  ]
}
```

Run with the application's Python environment and `server` on `PYTHONPATH`:

```text
python -m notes.tag_cleanup --directory <Library> --changes <private-plan.json>
```

The preview reports tags, hashes and changed span counts, without note bodies.
The transformer edits only the selected tokens in tag metadata, existing
primary-topic metadata and tag-only HTML text. All other source bytes, including
titles, prose, URLs, media, identity and Research provenance, stay exact. It
rejects disagreement between primary-topic metadata and the tag rows.

An approved `--apply` belongs in the coordinated release window after the named
backup, with the note writer stopped. Run as the note-file owner. All entries
preflight before any write. Each file is replaced atomically with its mode and
modification time retained, so old reports do not become recent user edits.
The existing derived search index is rebuilt once after the batch. This is not a claim
of an atomic multi-file transaction or a lock against another running editor.

The general Research title/topic editor has a different purpose and may
normalize HTML formatting. It is not used for this surgical cleanup.
