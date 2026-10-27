import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import {
  buildTextNoteHtml,
  escapePlainMarkdown,
  extractTextMarkdown,
  hasSharedQuicknotes,
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

test("plain capture text escapes all Markdown punctuation and normalizes newlines", () => {
  assert.equal(
    escapePlainMarkdown(
      "#tag\r\n*bold* [link](https://example.org) <small>text</small> \\*",
    ),
    "\\#tag\n\\*bold\\* \\[link\\]\\(https\\:\\/\\/example\\.org\\) \\<small\\>text\\<\\/small\\> \\\\\\*",
  );
});

test("canonical plain captures roundtrip as literal lines without creating tags", () => {
  const text =
    "#tag\n*bold*\n[link](https://example.org/a)\n<small>text</small>\n\\*literal\\*";
  const addition = `<small>26 Oct 2026, 08:30</small>  \n${escapePlainMarkdown(text).replace(/\n/g, "  \n")}`;
  const markdown = `Existing text.\n\n#private\n\n${addition}`;
  const html = buildTextNoteHtml("Quicknotes", markdown, legacy);
  const doc = parse(html);
  const capture = [...doc.querySelectorAll(".lamanote-text-body p")].at(-1);

  assert.equal(extractTextMarkdown(html), markdown);
  assert.equal(capture.textContent, `26 Oct 2026, 08:30\n${text}`);
  assert.equal(capture.querySelectorAll("br").length, 5);
  assert.equal(capture.querySelectorAll("a,strong,em,code,script").length, 0);
  assert.equal(capture.querySelectorAll("small").length, 1);
  assert.equal(
    doc.querySelector("meta[name='lamanotes-tags']").content,
    "private,pinned",
  );
});

test("legacy appended captures retain literal text, identity and idempotency metadata", () => {
  const text =
    "#tag\n*bold*\n[link](https://example.org/a)\n<small>text</small>\n\\*literal\\*";
  const doc = parse(legacy);
  const id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  const marker = doc.createElement("meta");
  marker.name = "lamanotes-quicknote-entry";
  marker.content = `${id}:${"a".repeat(64)}`;
  doc.head.append(marker);
  const entry = doc.createElement("p");
  entry.dataset.lamanotesQuicknoteEntry = id;
  const timestamp = doc.createElement("small");
  timestamp.textContent = "26 Oct 2026, 08:30";
  const capturedText = doc.createElement("span");
  capturedText.dataset.lamanotesQuicknoteText = "";
  capturedText.style.whiteSpace = "pre-wrap";
  capturedText.textContent = text;
  entry.append(timestamp, doc.createElement("br"), capturedText);
  doc.querySelector("article").append(entry);

  const adapted = extractTextMarkdown(
    doc.documentElement.outerHTML,
    "Quicknotes",
  );
  const addition = `<small>26 Oct 2026, 08:30</small>  \n${escapePlainMarkdown(text).replace(/\n/g, "  \n")}`;
  assert.equal(adapted.endsWith(addition), true);
  assert.match(adapted, /Unterwegs eine \*\*Idee\*\*/);
  const saved = buildTextNoteHtml(
    "Quicknotes",
    adapted,
    doc.documentElement.outerHTML,
  );
  const savedDoc = parse(saved);
  const capture = [...savedDoc.querySelectorAll(".lamanote-text-body p")].at(
    -1,
  );

  assert.equal(extractTextMarkdown(saved), adapted);
  assert.equal(capture.textContent, `26 Oct 2026, 08:30\n${text}`);
  assert.equal(capture.querySelectorAll("br").length, 5);
  assert.equal(capture.querySelectorAll("a,strong,em,code,script").length, 0);
  assert.equal(
    savedDoc.querySelector("meta[name='lamanotes-quicknote-entry']").content,
    marker.content,
  );
  assert.equal(
    savedDoc.querySelector("meta[name='lamanotes-note-id']").content,
    "ln-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  );
  assert.equal(
    savedDoc.querySelector("meta[name='custom-origin']").content,
    "preserve me",
  );
  assert.equal(
    savedDoc.querySelector("meta[name='lamanotes-tags']").content,
    "private,pinned",
  );
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

test("shared photo, source link and double separator survive legacy edit and a second save", () => {
  const doc = parse(legacy);
  const marker = doc.createElement("meta");
  marker.name = "lamanotes-share-quicknote";
  marker.content = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa:" + "b".repeat(64);
  doc.head.append(marker);
  const entry = doc.createElement("section");
  entry.dataset.lamanotesShareEntry = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  const asset = "/api/private/v1/assets/la-" + "a".repeat(32) + "/content";
  const url = "https://example.org/a%28b%29?x=1&y=2";
  const markdown = `---\n\n<small>27 Oct 2026, 07:45</small>\n\n\\#literal\n\n![PXL_\\[original\\].png](${asset})\n\n[Source](${url})`;
  entry.innerHTML = `<hr class="lamanote-share-separator"><p><img src="${asset}" alt="PXL_[original].png"></p>`;
  const source = doc.createElement("template");
  source.dataset.lamanotesShareMarkdown = "";
  source.innerHTML = markdown
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  entry.append(source);
  doc.querySelector("article").append(entry);
  const previous = doc.documentElement.outerHTML;
  assert.equal(hasSharedQuicknotes(previous), true);
  assert.equal(hasSharedQuicknotes(legacy), false);
  assert.equal(
    hasSharedQuicknotes("Text mentions lamanotes-share-quicknote"),
    false,
  );
  assert.equal(isTextNoteHtml(previous), true);
  const writing = extractTextMarkdown(previous, "Quicknotes");
  assert.equal(writing.endsWith(markdown), true);
  assert.match(writing, /Unterwegs eine \*\*Idee\*\*/);
  let saved = buildTextNoteHtml("Quicknotes", writing, previous);
  saved = buildTextNoteHtml("Quicknotes", extractTextMarkdown(saved), saved);
  const output = parse(saved);
  assert.equal(
    output.querySelectorAll(".lamanote-quicknotes .lamanote-text-body hr")
      .length,
    1,
  );
  assert.equal(output.querySelectorAll(".lamanote-text-body img").length, 1);
  assert.equal(
    output.querySelector(".lamanote-text-body img").getAttribute("src"),
    asset,
  );
  assert.equal(
    output.querySelector(".lamanote-text-body img").alt,
    "PXL_[original].png",
  );
  assert.equal(
    [...output.querySelectorAll("a")].at(-1).getAttribute("href"),
    url,
  );
  assert.equal(
    output.querySelector("meta[name='lamanotes-share-quicknote']").content,
    marker.content,
  );
  assert.equal(extractTextMarkdown(saved), writing);
  assert.doesNotMatch(writing, /<section|<template|<img|<meta/);
});

test("media outside the generated share fragment keeps the original legacy editor", () => {
  const broken = legacy.replace(
    "</article>",
    '<section data-lamanotes-share-entry="untrusted"><img src="/important.png"></section></article>',
  );
  assert.equal(isTextNoteHtml(broken), false);
  assert.throws(() => extractTextMarkdown(broken), /original editor/);
});
