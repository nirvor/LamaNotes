import hashlib
import gc
import os
import tempfile
import unittest
from pathlib import Path

from notes.file_system.file_system import FileSystemNotes, IndexSchema, INDEX_SCHEMA_VERSION
from notes.tag_cleanup import run
from notes.tag_policy import normalize_tag_name, rewrite_tag_metadata


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
