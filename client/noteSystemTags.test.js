import assert from "node:assert/strict";
import test from "node:test";

import {
  documentHasSystemTag,
  getFlatnotesMetaTags,
  setDocumentSystemTag,
  synchronizeDocumentTags,
} from "./noteSystemTags.js";

const researchNote = `<!doctype html>
<html><head><meta name="flatnotes-tags" content="private,research"></head>
<body><article><h1>Test</h1><p>#private #research #pinned</p></article></body></html>`;

test("pin state migrates from visible tag to metadata", () => {
  assert.equal(documentHasSystemTag(researchNote, "pinned", "html"), true);
  const pinned = setDocumentSystemTag({
    content: researchNote,
    title: "Test",
    format: "html",
    enabled: true,
  });
  assert.deepEqual(getFlatnotesMetaTags(pinned), [
    "private",
    "research",
    "pinned",
  ]);
  assert.doesNotMatch(pinned, /<p>#private #research #pinned<\/p>/);
  assert.match(pinned, /<p>#private #research<\/p>/);

  const unpinned = setDocumentSystemTag({
    content: pinned,
    title: "Test",
    format: "html",
    enabled: false,
  });
  assert.equal(documentHasSystemTag(unpinned, "pinned", "html"), false);
  assert.deepEqual(getFlatnotesMetaTags(unpinned), ["private", "research"]);
});

test("legacy markdown can still be pinned", () => {
  const pinned = setDocumentSystemTag({
    content: "# Title\n\nText\n",
    format: "markdown",
    enabled: true,
  });
  assert.match(pinned, /#pinned\n$/);
  const unpinned = setDocumentSystemTag({
    content: pinned,
    format: "markdown",
    enabled: false,
  });
  assert.doesNotMatch(unpinned, /#pinned/);
});

test("visible HTML tags replace stale non-system metadata on save", () => {
  const stale = `<!doctype html>
<html><head><meta name="flatnotes-tags" content="private,pinned,robotics"></head>
<body><article><footer class="tags" data-flatnotes-component="tags">
  <span>#private</span><span>#nirv-bot</span>
</footer></article></body></html>`;

  const synchronized = synchronizeDocumentTags({
    content: stale,
    previousContent: stale,
  });

  assert.deepEqual(getFlatnotesMetaTags(synchronized), [
    "private",
    "nirv-bot",
    "pinned",
  ]);
  assert.doesNotMatch(synchronized, /content="[^"]*robotics/);
});

test("removing the final visible HTML tag clears non-system metadata", () => {
  const previous = `<!doctype html>
<html><head><meta name="flatnotes-tags" content="private,pinned"></head>
<body><article><p>#private</p></article></body></html>`;
  const content = previous.replace("<p>#private</p>", "");

  const synchronized = synchronizeDocumentTags({
    content,
    previousContent: previous,
  });

  assert.deepEqual(getFlatnotesMetaTags(synchronized), ["pinned"]);
});
