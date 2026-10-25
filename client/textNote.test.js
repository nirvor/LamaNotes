import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import {
  buildTextNoteHtml,
  extractTextMarkdown,
  isTextNoteHtml,
  normalizeTextMarkdown,
} from "./components/text/textNote.js";
import { isWorkNoteHtml } from "./components/work/workNote.js";

globalThis.DOMParser = new JSDOM().window.DOMParser;
const legacy = `<!doctype html><html lang="de"><head>
<meta charset="utf-8"><meta name="lamanotes-note-id" content="ln-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">
<meta name="lamanotes-tags" content="pinned,private"><meta name="custom-origin" content="preserve me"><title>Quicknotes</title>
</head><body><article class="flatnote flatnote-migrated">
<p class="flatnote-kicker">Pinned Scratch Note</p><h1>Quicknotes</h1>
<p>Unterwegs eine <strong>Idee</strong> und ein <a href="https://example.org/a">Link</a>.</p>
<ul><li>Erster Gedanke</li><li>Zweiter Gedanke</li></ul><p>#pinned #private</p>
</article></body></html>`;
const parse = (html) => new DOMParser().parseFromString(html, "text/html");

test("legacy scratch note opens as writing text, without document markup or identity", () => {
  assert.equal(isTextNoteHtml(legacy), true);
  const markdown = extractTextMarkdown(legacy, "Quicknotes");
  assert.match(markdown, /Pinned Scratch Note/);
  assert.match(
    markdown,
    /Unterwegs eine \*\*Idee\*\* und ein \[Link\]\(https:\/\/example.org\/a\)/,
  );
  assert.match(markdown, /- Erster Gedanke\n- Zweiter Gedanke/);
  assert.match(markdown, /#private$/);
  assert.doesNotMatch(
    markdown,
    /<!doctype|<head|<meta|#pinned|ln-aaaaaaaa|# Quicknotes/,
  );
});

test("ordinary HTML articles and rich legacy documents keep their existing editor", () => {
  assert.equal(
    isTextNoteHtml(legacy.replace("Pinned Scratch Note", "Research Note")),
    false,
  );
  assert.equal(
    isTextNoteHtml(legacy.replace("<ul>", '<img src="/original.jpg"><ul>')),
    false,
  );
  assert.throws(
    () =>
      extractTextMarkdown(
        "<html><body><table><tr><td>Important</td></tr></table></body></html>",
      ),
    /original editor/,
  );
});

test("writing roundtrip retains exact text and stable note metadata", () => {
  const markdown =
    "Notiz unterwegs. Äpfel & Idee <x>\n\n- [ ] Etwas erledigen\n- [x] Schon gemacht\n\n#private #ideen\n";
  const html = buildTextNoteHtml("Quicknotes", markdown, legacy);
  const doc = parse(html);
  assert.equal(isTextNoteHtml(html), true);
  assert.equal(isWorkNoteHtml(html), false);
  assert.equal(extractTextMarkdown(html), markdown);
  assert.equal(
    doc.querySelector("meta[name='lamanotes-note-id']").content,
    "ln-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  );
  assert.equal(
    doc.querySelector("meta[name='custom-origin']").content,
    "preserve me",
  );
  assert.deepEqual(
    new Set(
      doc.querySelector("meta[name='lamanotes-tags']").content.split(","),
    ),
    new Set(["private", "ideen", "pinned"]),
  );
  assert.equal(
    doc.querySelectorAll("meta[name='lamanotes-note-id']").length,
    1,
  );
  assert.equal(
    doc.querySelectorAll(".lamanote-text-body input[checked]").length,
    1,
  );
});

test("renamed text notes retain their writing mode without relying on title or tags", () => {
  const html = buildTextNoteHtml("Unterwegs", "Gedanke\n\n#ideen", legacy);
  assert.equal(isTextNoteHtml(html), true);
  assert.equal(extractTextMarkdown(html), "Gedanke\n\n#ideen");
});

test("literal hashtags and fenced snippets are not moved or rewritten", () => {
  const source =
    "Ticket #123 bleibt im Satz.\n\n```text\n#pinned\n#not-a-tag\n```\n\n#private";
  assert.equal(normalizeTextMarkdown(source), source);
  const doc = parse(buildTextNoteHtml("Quicknotes", source, legacy));
  assert.deepEqual(
    new Set(
      doc.querySelector("meta[name='lamanotes-tags']").content.split(","),
    ),
    new Set(["private", "pinned"]),
  );
  assert.equal(extractTextMarkdown(doc.documentElement.outerHTML), source);
});

test("removed visible topic tags do not return through stale metadata", () => {
  const previous = buildTextNoteHtml(
    "Quicknotes",
    "Text\n\n#private #old",
    legacy,
  );
  const doc = parse(
    buildTextNoteHtml("Quicknotes", "Text\n\n#private #new", previous),
  );
  assert.equal(
    doc.querySelector("meta[name='lamanotes-tags']").content,
    "private,new,pinned",
  );
});

test("HTML-looking typed content stays literal and no template is closed by user input", () => {
  const source = "<script>alert('text')</script>\n</template>\n\n#private";
  const html = buildTextNoteHtml("<Notiz>", source, legacy);
  const doc = parse(html);
  assert.equal(doc.title, "<Notiz>");
  assert.equal(doc.body.querySelectorAll("script").length, 0);
  assert.equal(
    doc.querySelectorAll("template[data-lamanotes-text-markdown]").length,
    1,
  );
  assert.equal(extractTextMarkdown(html), source);
});

test("check states and nested list text survive the legacy adapter", () => {
  const html = legacy.replace(
    "<ul><li>Erster Gedanke</li><li>Zweiter Gedanke</li></ul>",
    '<ul><li><input type="checkbox" checked>Erster Gedanke<ul><li>Unterpunkt</li></ul></li><li><input type="checkbox">Zweiter Gedanke</li></ul>',
  );
  const markdown = extractTextMarkdown(html, "Quicknotes");
  assert.match(
    markdown,
    /- \[x\] Erster Gedanke\n  - Unterpunkt\n- \[ \] Zweiter Gedanke/,
  );
  assert.equal(
    extractTextMarkdown(buildTextNoteHtml("Quicknotes", markdown, html)),
    markdown,
  );
});
