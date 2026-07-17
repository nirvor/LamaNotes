import unittest
from unittest.mock import patch

from notes.file_system.file_system import FileSystemNotes
from notes.models import Note


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
        notes = object.__new__(FileSystemNotes)
        notes._list_all_note_filenames = lambda: ["current.html"]
        notes._get_by_filename = lambda _: Note(
            title="current",
            content='<meta name="flatnotes-tags" content="work,current">',
            last_modified=1,
            format="html",
        )

        self.assertEqual(notes.get_tags(), ["current", "work"])

    def test_delete_optimizes_index_after_removing_note(self):
        notes = object.__new__(FileSystemNotes)
        notes._existing_path_from_title = lambda _: "deleted.html"
        sync_calls = []
        notes._sync_index_with_retry = lambda **kwargs: sync_calls.append(kwargs)

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


if __name__ == "__main__":
    unittest.main()
