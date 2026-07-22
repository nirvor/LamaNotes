import base64
import tempfile
import unittest
from pathlib import Path

from .errors import PublicationError
from .normalizer import PublicProjectionBuilder

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8A"
    "AQUBAScY42YAAAAASUVORK5CYII="
)


class PublicProjectionTests(unittest.TestCase):
    def test_work_projection_removes_raw_source_and_internal_tags(self):
        content = """<!doctype html>
<html lang="en"><head>
  <meta name="flatnotes-note-kind" content="work">
  <meta name="flatnotes-tags" content="work,project-orion,public-topic">
  <style>body { color: #eee; position: fixed } .lead { max-width: 60rem }</style>
</head><body>
  <article data-flatnotes-note-kind="work" class="flatnote-work-rendered">
    <h1>Review Note</h1>
    <section class="lead" data-flatnotes-component="summary"><h2>Result</h2><p>Safe rendered result.</p></section>
    <footer>#work #project-orion #public-topic</footer>
  </article>
  <template data-flatnotes-work-markdown>RAW_PRIVATE_MARKDOWN</template>
</body></html>"""

        with tempfile.TemporaryDirectory() as directory:
            projection = PublicProjectionBuilder(directory).build(
                "Review Note", content
            )

        self.assertEqual(projection.note_kind, "work")
        self.assertEqual(projection.language, "en")
        self.assertEqual(projection.tags, ("public-topic",))
        self.assertNotIn("RAW_PRIVATE_MARKDOWN", projection.public_html)
        self.assertNotIn("<template", projection.public_html)
        self.assertNotIn("<h1", projection.public_html)
        self.assertIn(
            'data-lamanotes-component="summary"', projection.public_html
        )
        self.assertIn("Safe rendered result", projection.public_html)
        self.assertNotIn("position:fixed", projection.public_css)
        self.assertIn(".nirvnote-source .lead", projection.public_css)
        self.assertNotIn("body", projection.public_css)
        self.assertNotIn("\n", projection.public_css)

    def test_public_css_is_consumer_canonical_without_changing_strings(self):
        content = """<html><head><style>
          .lead, .detail > p {
            margin: 0 auto;
            border: 1px solid red;
            width: calc(100% - 2rem);
            content: "two words";
          }
          @media (max-width: 600px) { .lead { color: rgb(1, 2, 3); } }
        </style></head><body><article><h1>CSS</h1><p>Text</p></article></body></html>"""

        with tempfile.TemporaryDirectory() as directory:
            projection = PublicProjectionBuilder(directory).build(
                "CSS Canonical", content
            )

        self.assertIn(
            ".nirvnote-source .lead,.nirvnote-source .detail>p"
            "{margin:0 auto;border:1px solid red;"
            'width:calc(100% - 2rem);content:"two words"}',
            projection.public_css,
        )
        self.assertIn(
            "@media (max-width:600px){.nirvnote-source .lead"
            "{color:rgb(1,2,3)}}",
            projection.public_css,
        )

    def test_local_asset_is_snapshotted_and_hash_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "plot.png").write_bytes(PNG_1X1)
            content = """<html><body><article>
              <h1>Asset Note</h1>
              <p>A useful plot.</p>
              <figure data-flatnotes-component="plot">
                <img src="/note-assets/plot.png" alt="Measured result">
              </figure>
            </article></body></html>"""
            first = PublicProjectionBuilder(directory).build(
                "Asset Note", content
            )
            second = PublicProjectionBuilder(directory).build(
                "Asset Note", content
            )

        self.assertEqual(first.content_hash, second.content_hash)
        self.assertEqual(len(first.assets), 1)
        self.assertEqual(first.assets[0].content, PNG_1X1)
        self.assertIn(f"assets/{first.assets[0].file_name}", first.public_html)
        self.assertNotIn("/note-assets/", first.public_html)
        self.assertEqual(first.assets[0].asset_id, "asset_1")

    def test_private_paths_and_credentials_are_rejected_without_echoing_value(
        self,
    ):
        cases = (
            "<p>See C:\\Users\\example\\private.txt</p>",
            "<p>Connect to private-host.example.ts.net</p>",
            "<p>password=abcdefghijklmnop</p>",
        )
        with tempfile.TemporaryDirectory() as directory:
            for content in cases:
                with self.subTest(content=content):
                    with self.assertRaises(PublicationError) as raised:
                        PublicProjectionBuilder(directory).build(
                            "Unsafe", content
                        )
                    self.assertEqual(
                        raised.exception.code, "unsafe_public_content"
                    )
                    self.assertNotIn(
                        "abcdefghijklmnop", raised.exception.detail
                    )
                    self.assertNotIn("private-host", raised.exception.detail)

    def test_runtime_content_and_secret_css_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(PublicationError) as runtime:
                PublicProjectionBuilder(directory).build(
                    "Runtime",
                    "<p>Text</p><iframe src='https://example.com'></iframe>",
                )
            self.assertEqual(runtime.exception.code, "runtime_component")

            with self.assertRaises(PublicationError) as css:
                PublicProjectionBuilder(directory).build(
                    "CSS",
                    '<style>.x{content:"password=abcdefghijklmnop"}</style><p>Text</p>',
                )
            self.assertEqual(css.exception.code, "unsafe_public_content")

    def test_nested_content_in_removed_container_does_not_break_projection(self):
        content = """<html><body><article>
          <h1>Legacy note</h1>
          <template><section><p>Internal source</p></section></template>
          <p>Safe rendered result.</p>
        </article></body></html>"""

        with tempfile.TemporaryDirectory() as directory:
            projection = PublicProjectionBuilder(directory).build(
                "Legacy note", content
            )

        self.assertIn("Safe rendered result.", projection.public_html)
        self.assertNotIn("Internal source", projection.public_html)


if __name__ == "__main__":
    unittest.main()
