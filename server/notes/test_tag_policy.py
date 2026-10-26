import hashlib
import gc
import os
import tempfile
import unittest
from pathlib import Path

from notes.file_system.file_system import FileSystemNotes, IndexSchema, INDEX_SCHEMA_VERSION
from notes.tag_cleanup import run
from notes.models import Note
from notes.tag_policy import normalize_tag_name, replace_tag_metadata, rewrite_tag_metadata


def research_html(topic="r-acceptance"):
    return ("\ufeff<!DOCTYPE html>\r\n<html><head>\r\n"
            '<meta name="lamanotes-note-id" content="ln-0123456789abcdef0123456789abcdef">\r\n'
            '<meta name="lamanotes-research-id" content="lr-0123456789abcdef0123456789abcdef">\r\n'
            f'<meta content="private,research,{topic},pinned" name="lamanotes-tags">\r\n'
            f"<meta name='lamanotes-research-topic' content='{topic}'>\r\n"
            '</head><body><h1>Unchanged &amp; precise</h1>\r\n'
            '<p>This prose mentions #r-acceptance and keeps https://example.test/r-acceptance.</p>\r\n'
            '<script>const x="#r-acceptance";</script>\r\n'
            f'<footer class="tags"><span>#private</span> <span>#research</span> <span>#{topic}</span></footer>\r\n'
            '</body></html>\r\n')


class TagPolicyTests(unittest.TestCase):
    def test_headless_shared_fragment_keeps_its_tag_row_without_adding_a_document_shell(self):
        source = '<article><p>Keep the source and attachment.</p><p>#shared</p></article>'
        result = replace_tag_metadata(source, ["shared"], expected_tags=["shared"])
        self.assertEqual(result.content, source)
        self.assertEqual(result.changed_spans, ())
        renamed = replace_tag_metadata(source, ["lamax"], expected_tags=["shared"])
        self.assertEqual(renamed.content, source.replace('#shared', '#lamax'))

    def test_exact_set_cleanup_preserves_prose_figures_identity_and_topic(self):
        original = research_html().replace(
            '</head>', '<meta name="lamanotes-research-origin" content="codex"><meta name="custom-data" content="keep &amp; exact"></head>'
        ).replace('<script>', '<figure><img src="attachments/original.svg" alt="Data"></figure><script>')
        result = replace_tag_metadata(original, ["research", "gaming"],
                                      expected_tags=["private", "research", "r-acceptance", "pinned"],
                                      research_topic="r-acceptance", expected_primary_topic="r-acceptance")
        self.assertEqual(result.tags, ("gaming", "pinned", "research"))
        self.assertIn('<p>This prose mentions #r-acceptance and keeps https://example.test/r-acceptance.</p>', result.content)
        self.assertIn('<script>const x="#r-acceptance";</script>', result.content)
        self.assertIn('<figure><img src="attachments/original.svg" alt="Data"></figure>', result.content)
        self.assertIn('<meta name="custom-data" content="keep &amp; exact">', result.content)
        self.assertIn("<meta name='lamanotes-research-topic' content='r-acceptance'>", result.content)
        rebuilt = original
        for start, end, replacement in reversed(result.changed_spans):
            rebuilt = rebuilt[:start] + replacement + rebuilt[end:]
        self.assertEqual(result.content, rebuilt)
        self.assertTrue(result.content.startswith("\ufeff<!DOCTYPE html>\r\n"))
        context = FileSystemNotes._context_from_note(Note(title="Retained", content=result.content, last_modified=1))
        self.assertEqual(context.research_id, "lr-0123456789abcdef0123456789abcdef")
        self.assertEqual(context.research_origin, "codex")
        self.assertEqual(context.primary_research_topic, "r-acceptance")

    def test_exact_set_adds_explicit_topic_and_updates_both_canonical_sources_only_on_tag_lines(self):
        for marker in ("data-lamanotes-work-markdown", "data-lamanotes-text-markdown"):
            source = '<html><head><meta name="lamanotes-tags" content="research,private,r-food,pinned"></head><body><p>#research #private #r-food</p>'
            source += f'<template {marker}>Keep #private in prose.\r\n\r\n```text\r\n#private\r\n```\r\n\r\n\\#private\r\n\r\n#private #research #r-food\r\n</template></body></html>'
            result = replace_tag_metadata(source, ["research", "rezepte"],
                                          expected_tags=["research", "private", "r-food", "pinned"],
                                          research_topic="r-food", expected_primary_topic="r-food")
            self.assertIn('<meta name="lamanotes-research-topic" content="r-food">', result.content)
            self.assertIn('Keep #private in prose.\r\n\r\n```text\r\n#private\r\n```\r\n\r\n\\#private\r\n\r\n#research #rezepte\r\n</template>', result.content)
            self.assertEqual(FileSystemNotes._extract_tags(result.content)[1], {"research", "rezepte", "pinned"})

    def test_removing_last_visible_and_canonical_tags_does_not_resurrect_stale_metadata(self):
        source = '<html><head><meta name="flatnotes-tags" content="private,old,pinned"></head><body><p>Keep my text.</p><p>#private</p><template data-lamanotes-text-markdown>Keep my text.\n\n#private</template></body></html>'
        result = replace_tag_metadata(source, [], expected_tags=["private", "pinned"])
        self.assertEqual(result.tags, ("pinned",))
        self.assertIn('<meta name="flatnotes-tags" content="pinned">', result.content)
        self.assertIn('>Keep my text.\n\n</template>', result.content)
        self.assertEqual(FileSystemNotes._extract_tags(result.content)[1], {"pinned"})

    def test_new_retrieval_tags_are_kept_in_a_canonical_source_without_existing_tag_lines(self):
        source = '<html><head><meta name="lamanotes-tags" content="private,pinned"></head><body><p>Keep my text.</p><template data-lamanotes-text-markdown>Keep my text.</template></body></html>'
        result = replace_tag_metadata(source, ["lamax"], expected_tags=["private", "pinned"])
        self.assertIn('>Keep my text.\n\n#lamax</template>', result.content)
        self.assertEqual(FileSystemNotes._extract_tags(result.content)[1], {"lamax", "pinned"})

    def test_exact_set_rejects_changed_tags_topic_loss_and_new_pinning(self):
        with self.assertRaisesRegex(ValueError, "tag set"):
            replace_tag_metadata(research_html(), ["research"], expected_tags=["research"], research_topic="r-acceptance", expected_primary_topic="r-acceptance")
        with self.assertRaisesRegex(ValueError, "Keep the Research topic"):
            replace_tag_metadata(research_html(), ["research"], expected_tags=["private", "research", "r-acceptance", "pinned"], expected_primary_topic="r-acceptance")
        with self.assertRaisesRegex(ValueError, "pinning"):
            replace_tag_metadata('<html><head><meta name="lamanotes-tags" content="work"></head><body><p>#work</p></body></html>', ["work", "pinned"], expected_tags=["work"])

    def test_schema_two_exact_set_preview_and_guarded_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "Exact.html")
            raw = research_html().encode("utf-8")
            path.write_bytes(raw)
            plan = {"schema": 2, "notes": [{"filename": path.name, "sourceSha256": hashlib.sha256(raw).hexdigest(),
                    "expectedTags": ["private", "research", "r-acceptance", "pinned"], "tags": ["research", "gaming"],
                    "researchTopic": "r-acceptance", "expectedPrimaryTopic": "r-acceptance"}]}
            preview = run(directory, plan)
            self.assertEqual(preview["schema"], 2)
            self.assertEqual(path.read_bytes(), raw)
            run(directory, plan, apply=True)
            self.assertEqual(FileSystemNotes._extract_tags(path.read_text(encoding="utf-8"))[1], {"research", "gaming", "pinned"})
    def test_tag_identity_trims_before_hash_and_deduplicates_existing_metadata(self):
        self.assertEqual(normalize_tag_name("  #ReSeArCh  "), "research")
        self.assertEqual(normalize_tag_name("two words"), "")
        self.assertEqual(FileSystemNotes._split_tag_list(" #Private,private #RESEARCH"), {"private", "research"})

    def test_semantic_context_does_not_resurrect_removed_html_metadata_tags(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "Current.html").write_text('<html><head><meta name="lamanotes-tags" content="research,r-old,private,pinned"></head><body><p>#research #r-current</p></body></html>')
            notes = object.__new__(FileSystemNotes)
            notes.storage_path = directory
            entry = notes.get_semantic_index()[0]
            self.assertEqual(entry.tags, ["pinned", "r-current", "research"])
            self.assertEqual(entry.primary_research_topic, "r-current")
            self.assertEqual(notes.get_tags(), ["pinned", "r-current", "research"])

    def test_rewrite_changes_only_selected_metadata_and_tag_row_spans(self):
        original = research_html()
        result = rewrite_tag_metadata(original, {"r-acceptance": "r-messdaten"}, expected_primary_topic="r-acceptance")
        self.assertEqual(result.tags, ("pinned", "private", "r-messdaten", "research"))
        self.assertEqual(len(result.changed_spans), 3)
        for start, end, replacement in result.changed_spans:
            self.assertEqual(end-start, len(replacement) + len("r-acceptance") - len("r-messdaten"))
        self.assertEqual(result.content, original.replace('content="private,research,r-acceptance,pinned"', 'content="private,research,r-messdaten,pinned"').replace("content='r-acceptance'", "content='r-messdaten'").replace('<span>#r-acceptance</span>', '<span>#r-messdaten</span>'))

    def test_approved_exact_aliases_leave_other_research_topics_and_prose_alone(self):
        original = '<html><head><meta name="lamanotes-tags" content="private,research,r-game,roguelite"></head><body><p>roguelite r-game #r-game</p><p>#private #research #r-game #roguelite</p></body></html>'
        result = rewrite_tag_metadata(original, {"roguelite": "roguelites", "r-game": "r-games"}, expected_primary_topic="r-game")
        self.assertIn('<p>roguelite r-game #r-game</p>', result.content)
        self.assertIn("r-games", result.tags)
        self.assertIn("roguelites", result.tags)
        self.assertNotIn("r-game", result.tags)
        self.assertEqual(rewrite_tag_metadata(result.content, {"r-game": "r-games"}).content, result.content)

    def test_rewrite_rejects_disagreeing_or_ambiguous_research_topics(self):
        for content in [research_html().replace("content='r-acceptance'", "content='r-other'"), research_html().replace('<span>#r-acceptance</span>', '<span>#r-other</span>'), research_html().replace('private,research,r-acceptance,pinned', 'private,research,r-acceptance,r-other,pinned')]:
            with self.assertRaisesRegex(ValueError, "topic"):
                rewrite_tag_metadata(content, {"r-acceptance": "r-messdaten"}, expected_primary_topic="r-acceptance")

    def test_entity_encoded_tag_state_is_verified_with_normal_parser(self):
        original = research_html().replace('<span>#r-acceptance</span>', '<span>&#35;r-acceptance</span>')
        with self.assertRaisesRegex(ValueError, "parser"):
            rewrite_tag_metadata(original, {"r-acceptance": "r-messdaten"}, expected_primary_topic="r-acceptance")

    def test_cleanup_plan_is_body_free_and_apply_preserves_filename_and_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "Example.html")
            original = research_html().encode("utf-8")
            path.write_bytes(original)
            changes = {"schema": 1, "notes": [{"filename": path.name, "sourceSha256": hashlib.sha256(original).hexdigest(),
                "researchId": "lr-0123456789abcdef0123456789abcdef", "noteId": "ln-0123456789abcdef0123456789abcdef",
                "expectedPrimaryTopic": "r-acceptance", "replacements": {"r-acceptance": "r-messdaten"}}]}
            mode = path.stat().st_mode
            modified = path.stat().st_mtime_ns
            preview = run(directory, changes)
            self.assertEqual(path.read_bytes(), original)
            self.assertNotIn("content", preview["notes"][0])
            self.assertEqual(preview["changedNotes"], 1)
            result = run(directory, changes, apply=True)
            self.assertEqual(result["changedNotes"], 1)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), preview["notes"][0]["resultSha256"])
            self.assertEqual(path.stat().st_mode, mode)
            self.assertEqual(path.stat().st_mtime_ns, modified)
            self.assertTrue(result["indexRebuilt"])
            self.assertEqual({p.name for p in Path(directory).iterdir()}, {path.name, ".lamanotes"})

    def test_preserved_mtime_cleanup_rebuilds_existing_index_with_all_notes(self):
        from datetime import datetime
        import whoosh.index
        from whoosh.query import Term
        with tempfile.TemporaryDirectory() as directory:
            raw = research_html().encode("utf-8")
            path = Path(directory, "Example.html")
            path.write_bytes(raw)
            old_time = 1_700_000_000_000_000_000
            os.utime(path, ns=(old_time, old_time))
            other = Path(directory, "Retained.html")
            other.write_text('<html><head><meta name="lamanotes-tags" content="private,retained"></head><body>Other note</body></html>')
            index_dir = Path(directory, ".lamanotes")
            index_dir.mkdir()
            index = whoosh.index.create_in(str(index_dir), IndexSchema, indexname=INDEX_SCHEMA_VERSION)
            with index.writer() as writer:
                writer.update_document(filename=path.name, last_modified=datetime.fromtimestamp(path.stat().st_mtime), title="Example", content="before", tags="private research r-acceptance")
                writer.update_document(filename=other.name, last_modified=datetime.fromtimestamp(other.stat().st_mtime), title="Retained", content="other", tags="private retained")
            del writer
            index.close()
            del index
            gc.collect()
            changes = {"schema": 1, "notes": [{"filename": path.name, "sourceSha256": hashlib.sha256(raw).hexdigest(), "expectedPrimaryTopic": "r-acceptance", "replacements": {"r-acceptance": "r-messdaten"}}]}
            run(directory, changes, apply=True)
            self.assertEqual(path.stat().st_mtime_ns, old_time)
            index = whoosh.index.open_dir(str(index_dir), indexname=INDEX_SCHEMA_VERSION)
            with index.searcher() as searcher:
                self.assertEqual(len(searcher.search(Term("tags", "r-messdaten"))), 1)
                self.assertEqual(len(searcher.search(Term("tags", "r-acceptance"))), 0)
                self.assertEqual(len(searcher.search(Term("tags", "retained"))), 1)
            index.close()
            del searcher, index
            gc.collect()

    def test_entire_plan_preflights_before_any_file_is_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            original = research_html().encode("utf-8")
            path = Path(directory, "First.html")
            path.write_bytes(original)
            Path(directory, "Second.html").write_bytes(original)
            changes = {"schema": 1, "notes": [{"filename": name, "sourceSha256": digest,
                "expectedPrimaryTopic": "r-acceptance", "replacements": {"r-acceptance": "r-messdaten"}} for name, digest in [("First.html", hashlib.sha256(original).hexdigest()), ("Second.html", "0"*64)]]}
            with self.assertRaisesRegex(ValueError, "audit"):
                run(directory, changes, apply=True)
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
