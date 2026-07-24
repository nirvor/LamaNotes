import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from notes.errors import ResearchNoteConflictError
from notes.file_system.file_system import FileSystemNotes
from notes.models import ResearchNoteUpdate


class HtmlTagExtractionTests(unittest.TestCase):
    def test_inline_hashtag_mentions_are_not_html_tags(self):
        content = """<!doctype html>
<html>
  <head><meta name="flatnotes-tags" content="infra,research"></head>
  <body>
    <article>
      <h1>System tags</h1>
      <p>Users do not need to type #pinned in normal prose.</p>
      <p>#infra #research</p>
    </article>
  </body>
</html>
"""

        _, tags = FileSystemNotes._extract_tags(content)

        self.assertEqual(tags, {"infra", "research"})

    def test_legacy_tag_only_html_blocks_remain_supported(self):
        content = """<article>
  <h1>Legacy note</h1>
  <p>#private #pinned</p>
</article>"""

        _, tags = FileSystemNotes._extract_tags(content)

        self.assertEqual(tags, {"private", "pinned"})

    def test_visible_tags_override_stale_non_system_metadata(self):
        content = """<!doctype html>
<html>
  <head><meta name="flatnotes-tags" content="private,pinned,robotics"></head>
  <body><article>
    <footer class="tags" data-flatnotes-component="tags">
      <span>#private</span><span>#nirv-bot</span>
    </footer>
  </article></body>
</html>"""

        _, tags = FileSystemNotes._extract_tags(content)

        self.assertEqual(tags, {"private", "nirv-bot", "pinned"})


class LiveTagTests(unittest.TestCase):
    def test_get_tags_only_returns_tags_from_existing_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "current.html").write_text(
                '<meta name="flatnotes-tags" content="work,current">',
                encoding="utf-8",
            )
            notes = object.__new__(FileSystemNotes)
            notes.storage_path = directory

            self.assertEqual(notes.get_tags(), ["current", "work"])

    def test_semantic_index_reuses_unchanged_note_contexts(self):
        with tempfile.TemporaryDirectory() as directory:
            note_path = Path(directory, "cached.html")
            note_path.write_text(
                "<article><h1>Cached</h1><p>#work</p></article>",
                encoding="utf-8",
            )
            notes = object.__new__(FileSystemNotes)
            notes.storage_path = directory
            original_context = notes._context_from_note
            parsed_titles = []

            def tracked_context(note):
                parsed_titles.append(note.title)
                return original_context(note)

            notes._context_from_note = tracked_context

            first = notes.get_semantic_index()
            second = notes.get_semantic_index()
            note_path.write_text(
                "<article><h1>Changed</h1><p>#work #current</p></article>",
                encoding="utf-8",
            )
            third = notes.get_semantic_index()

            self.assertEqual([entry.title for entry in first], ["cached"])
            self.assertEqual([entry.title for entry in second], ["cached"])
            self.assertEqual(third[0].tags, ["current", "work"])
            self.assertEqual(parsed_titles, ["cached", "cached"])

    def test_delete_optimizes_index_after_removing_note(self):
        notes = object.__new__(FileSystemNotes)
        notes._existing_path_from_title = lambda _: "deleted.html"
        sync_calls = []
        notes._sync_index_with_retry = lambda **kwargs: sync_calls.append(
            kwargs
        )

        with patch("notes.file_system.file_system.os.remove") as remove:
            notes.delete("deleted")

        remove.assert_called_once_with("deleted.html")
        self.assertEqual(sync_calls, [{"optimize": True}])

    def test_pinned_metadata_remains_a_system_tag(self):
        content = """<html>
  <head><meta name="flatnotes-tags" content="private,pinned"></head>
  <body><p>Normal text mentioning #other.</p></body>
</html>"""

        _, tags = FileSystemNotes._extract_tags(content)

        self.assertEqual(tags, {"private", "pinned"})


class ResearchTopicFacetTests(unittest.TestCase):
    def test_index_exposes_stable_research_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "provenance.html").write_text(
                """<!doctype html>
<html>
  <head>
    <meta name="lamanotes-tags" content="private,research,r-agent-tools">
    <meta name="lamanotes-research-topic" content="r-agent-tools">
    <meta name="lamanotes-research-id"
          content="lr-0123456789abcdef0123456789abcdef">
    <meta name="lamanotes-research-origin" content="lamastart">
    <meta name="lamanotes-research-parent"
          content="lr-fedcba9876543210fedcba9876543210">
  </head>
  <body><article><p>#private #research #r-agent-tools</p></article></body>
</html>""",
                encoding="utf-8",
            )
            notes = object.__new__(FileSystemNotes)
            notes.storage_path = directory

            context = notes.get_context("provenance")
            entry = notes.get_semantic_index()[0]

            self.assertEqual(
                context.primary_research_topic,
                "r-agent-tools",
            )
            self.assertEqual(
                entry.research_id,
                "lr-0123456789abcdef0123456789abcdef",
            )
            self.assertEqual(entry.research_origin, "lamastart")
            self.assertEqual(
                entry.parent_research_id,
                "lr-fedcba9876543210fedcba9876543210",
            )
            payload = entry.model_dump(by_alias=True)
            self.assertEqual(
                payload["primaryResearchTopic"],
                "r-agent-tools",
            )
            self.assertEqual(
                payload["researchId"],
                "lr-0123456789abcdef0123456789abcdef",
            )

    def test_context_and_index_derive_strict_research_topics(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "research-note.html").write_text(
                """<article>
  <h1>Research note</h1>
  <p>
    #research #r-agent-tools #r-2026 #r-agent-tools
    #r-double--dash #r-trailing- #r_under #other
  </p>
</article>""",
                encoding="utf-8",
            )
            notes = object.__new__(FileSystemNotes)
            notes.storage_path = directory

            context = notes.get_context("research-note")
            index_entry = notes.get_semantic_index()[0]

            expected_topics = ["r-2026", "r-agent-tools"]
            self.assertEqual(context.research_topics, expected_topics)
            self.assertEqual(index_entry.research_topics, expected_topics)
            self.assertIsNone(context.primary_research_topic)
            self.assertIsNone(index_entry.primary_research_topic)
            self.assertEqual(
                context.model_dump(by_alias=True)["researchTopics"],
                expected_topics,
            )
            self.assertEqual(
                index_entry.model_dump(by_alias=True)["researchTopics"],
                expected_topics,
            )
            self.assertEqual(
                index_entry.tags,
                [
                    "other",
                    "r-2026",
                    "r-agent-tools",
                    "r-double--dash",
                    "r-trailing-",
                    "r_under",
                    "research",
                ],
            )
            self.assertNotIn(
                "content",
                index_entry.model_dump(by_alias=True),
            )
            self.assertNotIn(
                "text",
                index_entry.model_dump(by_alias=True),
            )

    def test_research_topics_require_exact_research_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "not-research.html").write_text(
                "<article><p>#research-note #r-agent-tools</p></article>",
                encoding="utf-8",
            )
            notes = object.__new__(FileSystemNotes)
            notes.storage_path = directory

            context = notes.get_context("not-research")
            index_entry = notes.get_semantic_index()[0]

            self.assertEqual(context.research_topics, [])
            self.assertEqual(index_entry.research_topics, [])
            self.assertIsNone(context.research_id)
            self.assertEqual(
                index_entry.tags,
                ["r-agent-tools", "research-note"],
            )


class ResearchNoteUpdateTests(unittest.TestCase):
    def test_title_and_topic_update_is_atomic_and_contract_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "Old title.html")
            source.write_text(
                """<!doctype html>
<html>
  <head>
    <title>Old title</title>
    <meta name="lamanotes-tags"
          content="private,research,r-old-topic,r-extra-topic">
    <meta name="lamanotes-research-topic" content="r-old-topic">
    <meta name="lamanotes-research-id"
          content="lr-0123456789abcdef0123456789abcdef">
    <meta name="lamanotes-research-origin" content="lamastart">
    <meta name="lamanotes-public-slug" content="stable-publication">
  </head>
  <body>
    <article>
      <h1><span>Old title</span></h1>
      <p>Evidence remains untouched.</p>
      <p>#research #r-old-topic #r-extra-topic #research</p>
    </article>
  </body>
</html>""",
                encoding="utf-8",
            )
            notes = object.__new__(FileSystemNotes)
            notes.storage_path = directory

            updated = notes.update_research_note(
                ResearchNoteUpdate(
                    currentTitle="Old title",
                    newTitle="New title",
                    primaryResearchTopic="r-new-topic",
                    expectedLastModified=source.stat().st_mtime,
                    researchId="lr-0123456789abcdef0123456789abcdef",
                )
            )

            target = Path(directory, "New title.html")
            content = target.read_text(encoding="utf-8")
            self.assertFalse(source.exists())
            self.assertTrue(target.exists())
            self.assertEqual(updated.title, "New title")
            self.assertEqual(updated.research_topics, ["r-new-topic"])
            self.assertEqual(updated.primary_research_topic, "r-new-topic")
            self.assertIn("<title>New title</title>", content)
            self.assertIn("<h1>New title</h1>", content)
            self.assertIn("Evidence remains untouched.", content)
            self.assertRegex(
                content,
                r'<meta content="stable-publication" '
                r'name="lamanotes-public-slug"\s*/>',
            )
            self.assertEqual(content.count("#research"), 1)
            self.assertEqual(content.count("#r-new-topic"), 1)
            self.assertNotIn("#r-old-topic", content)
            self.assertNotIn("#r-extra-topic", content)
            self.assertRegex(
                content,
                r'<p class="lamanotes-research-tags">'
                r"#research #r-new-topic</p>\s*</body>",
            )

    def test_legacy_note_without_research_id_can_be_updated_by_version(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "Legacy.html")
            source.write_text(
                """<html><head>
<meta name="lamanotes-tags" content="research,r-old">
<meta name="lamanotes-research-topic" content="r-old">
</head><body><h1>Legacy</h1><p>#research #r-old</p></body></html>""",
                encoding="utf-8",
            )
            notes = object.__new__(FileSystemNotes)
            notes.storage_path = directory

            updated = notes.update_research_note(
                ResearchNoteUpdate(
                    currentTitle="Legacy",
                    newTitle="Legacy",
                    primaryResearchTopic="r-current",
                    expectedLastModified=source.stat().st_mtime,
                )
            )

            self.assertEqual(updated.primary_research_topic, "r-current")
            self.assertIsNone(updated.research_id)

    def test_unsorted_research_note_can_receive_its_first_topic(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "Unsorted.html")
            source.write_text(
                """<html><head>
<meta name="lamanotes-tags" content="research">
</head><body><h1>Unsorted</h1><p>#research</p></body></html>""",
                encoding="utf-8",
            )
            notes = object.__new__(FileSystemNotes)
            notes.storage_path = directory

            updated = notes.update_research_note(
                ResearchNoteUpdate(
                    currentTitle="Unsorted",
                    newTitle="Categorised",
                    primaryResearchTopic="r-current",
                    expectedLastModified=source.stat().st_mtime,
                )
            )

            content = Path(directory, "Categorised.html").read_text(
                encoding="utf-8"
            )
            self.assertEqual(updated.primary_research_topic, "r-current")
            self.assertEqual(updated.research_topics, ["r-current"])
            self.assertEqual(content.count("#research"), 1)
            self.assertEqual(content.count("#r-current"), 1)

    def test_stale_version_is_rejected_without_modifying_the_note(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "Stable.html")
            original = (
                '<html><head><meta name="lamanotes-tags" '
                'content="research,r-stable"></head>'
                "<body><h1>Stable</h1><p>#research #r-stable</p></body></html>"
            )
            source.write_text(original, encoding="utf-8")
            notes = object.__new__(FileSystemNotes)
            notes.storage_path = directory

            with self.assertRaisesRegex(
                ResearchNoteConflictError,
                "changed",
            ):
                notes.update_research_note(
                    ResearchNoteUpdate(
                        currentTitle="Stable",
                        newTitle="Changed",
                        primaryResearchTopic="r-changed",
                        expectedLastModified=source.stat().st_mtime - 10,
                    )
                )

            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertFalse(Path(directory, "Changed.html").exists())


if __name__ == "__main__":
    unittest.main()
