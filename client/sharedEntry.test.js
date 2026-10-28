import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";
import {
  sharedAnchorRanges,
  sharedEntryAnchor,
  sharedEntryPosition,
  sharedEntryRequest,
  stableNoteDestination,
} from "./sharedEntry.js";
import {
  buildTextNoteHtml,
  extractTextMarkdown,
} from "./components/text/textNote.js";

globalThis.DOMParser = new JSDOM().window.DOMParser;
const id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const head = `<meta name="lamanotes-share-quicknote" content="${id}:${"b".repeat(64)}">`;
const anchor = sharedEntryAnchor(id);

test("entry routes accept only UUIDs and preserve query through stable note resolution", () => {
  assert.deepEqual(sharedEntryRequest({ entry: id, edit: "1" }), {
    id,
    edit: true,
  });
  for (const entry of ["../other", "javascript:alert(1)", [id], "", null])
    assert.equal(sharedEntryRequest({ entry }), null);
  assert.deepEqual(
    stableNoteDestination("Renamed Quicknotes", {
      query: { entry: id, edit: "1" },
      hash: "",
    }),
    {
      name: "note",
      params: { title: "Renamed Quicknotes" },
      query: { entry: id, edit: "1" },
      hash: "",
    },
  );
});

test("an exact entry survives edits, a title rename and repeated Markdown saves", () => {
  let markdown = `Prior writing.\n\n${anchor}\n\n---\n\nShared content.\n\n\`\`\`python\nprint("hello")\n\`\`\``;
  let html = buildTextNoteHtml(
    "Quicknotes",
    markdown,
    `<html><head>${head}</head><body></body></html>`,
  );
  for (let count = 0; count < 2; count++) {
    markdown = extractTextMarkdown(html).replace(
      "Shared content.",
      "Edited content.",
    );
    html = buildTextNoteHtml("Renamed Quicknotes", markdown, html);
  }
  const position = sharedEntryPosition(html, markdown, id);
  assert.ok(position);
  assert.equal(
    markdown.slice(position.caret).startsWith("Edited content."),
    true,
  );
  const doc = new DOMParser().parseFromString(html, "text/html");
  assert.equal(doc.querySelectorAll(`#quicknote-${id}`).length, 1);
  assert.equal(doc.querySelector("code").textContent, 'print("hello")');
  assert.equal(
    sharedEntryPosition(html, markdown.replace(anchor, ""), id),
    null,
  );
  assert.equal(sharedEntryPosition(html, markdown + "\n" + anchor, id), null);
  assert.equal(sharedEntryPosition(html.replace(head, ""), markdown, id), null);
});

test("legacy share fragments acquire their stable anchor on the normal text adapter", () => {
  const html = `<html><head>${head}</head><body><article class="flatnote-migrated"><p class="flatnote-kicker">Pinned Scratch Note</p><section data-lamanotes-share-entry="${id}"><p>Shared text.</p><template data-lamanotes-share-markdown>---\n\nShared text.</template></section></article></body></html>`;
  const markdown = extractTextMarkdown(html, "Quicknotes");
  assert.equal(markdown.split(anchor).length - 1, 1);
  assert.ok(sharedEntryPosition(html, markdown, id));
});

test("anchor-looking code remains visible code and cannot redirect an entry", () => {
  const markdown = `\`\`\`\`text\n${anchor}\n\`\`\`\`\n\n${anchor}\n\n---\n\nReal entry`;
  const ranges = sharedAnchorRanges(markdown);
  assert.equal(ranges.length, 1);
  assert.equal(ranges[0].from, markdown.lastIndexOf(anchor));
  assert.ok(
    sharedEntryPosition(`<html><head>${head}</head></html>`, markdown, id),
  );
  const inline = buildTextNoteHtml(
    "Quicknotes",
    "`" + anchor + "`",
    `<html><head>${head}</head></html>`,
  );
  const doc = new DOMParser().parseFromString(inline, "text/html");
  assert.equal(doc.querySelector("code").textContent, anchor);
  assert.equal(doc.querySelectorAll("[data-lamanotes-share-anchor]").length, 0);
});
