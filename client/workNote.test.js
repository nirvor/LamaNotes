import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import {
  buildWorkNoteHtml,
  createSmallTextEdit,
  isChecklistNoteHtml,
  isWorkNoteHtml,
  normalizeSmallTextMarkdown,
  renderMarkdownToHtml,
} from "./components/work/workNote.js";

test("work task lists render exactly one shared checkbox per item", () => {
  const rendered = renderMarkdownToHtml(
    "- [x] Milk\n- [ ] Apples\n- Ordinary item",
  );

  assert.equal(
    (rendered.match(/class="lamanotes-task-checkbox"/g) || []).length,
    2,
  );
  assert.equal((rendered.match(/type="checkbox"/g) || []).length, 2);
  assert.equal((rendered.match(/ checked/g) || []).length, 2);
});

test("work notes render small Markdown text without opening raw HTML", () => {
  const rendered = renderMarkdownToHtml(
    "- <small>**Paused/stopped**</small>\n- <script>unsafe</script>",
  );

  assert.match(rendered, /<small><strong>Paused\/stopped<\/strong><\/small>/);
  assert.match(rendered, /&lt;script&gt;unsafe&lt;\/script&gt;/);
  assert.doesNotMatch(rendered, /<script>/);
});

test("backslash-escaped ASCII punctuation renders as literal text", () => {
  const punctuation = Array.from({ length: 94 }, (_, index) =>
    String.fromCharCode(index + 33),
  )
    .filter((character) => !/[a-zA-Z0-9]/.test(character))
    .join("");
  const markdown = [...punctuation]
    .map((character) => `\\${character}`)
    .join("");
  const paragraph = new JSDOM(
    renderMarkdownToHtml(markdown),
  ).window.document.querySelector("p");

  assert.equal(paragraph.textContent, punctuation);
  assert.equal(paragraph.children.length, 0);
});

test("escaped capture syntax stays literal beside ordinary Markdown", () => {
  const rendered = renderMarkdownToHtml(
    String.raw`\#tag \*bold\* \[link\]\(https\:\/\/example\.org\) \<small\>text\<\/small\> and **real bold**`,
  );
  const paragraph = new JSDOM(rendered).window.document.querySelector("p");

  assert.equal(
    paragraph.textContent,
    "#tag *bold* [link](https://example.org) <small>text</small> and real bold",
  );
  assert.equal(paragraph.querySelector("strong").textContent, "real bold");
  assert.equal(paragraph.querySelectorAll("em,a,small").length, 0);
});

test("inline and fenced code retain escapes and literal small tags", () => {
  const source = [
    "Literal `\\*bold\\* <small>#tag</small> $&` and <small>\\*small\\*</small>.",
    "",
    "```text",
    "\\*bold\\* <small>#tag</small>  ",
    "next line",
    "```",
  ].join("\n");
  const doc = new JSDOM(renderMarkdownToHtml(source)).window.document;

  assert.equal(
    doc.querySelector("p code").textContent,
    "\\*bold\\* <small>#tag</small> $&",
  );
  assert.equal(doc.querySelector("p small").textContent, "*small*");
  assert.equal(
    doc.querySelector("pre code").textContent,
    "\\*bold\\* <small>#tag</small>  \nnext line",
  );
  assert.equal(doc.querySelectorAll("code small,code em,pre br").length, 0);
});

test("two trailing spaces keep hard line breaks outside code", () => {
  assert.equal(
    renderMarkdownToHtml("First  \nSecond\nThird  \n**Fourth**"),
    "<p>First<br>\nSecond Third<br>\n<strong>Fourth</strong></p>",
  );
  assert.equal(
    renderMarkdownToHtml("A `code  \ntext`  \nB"),
    "<p>A <code>code  \ntext</code><br>\nB</p>",
  );
});

test("legacy HTML checklists are eligible for the simple work editor", () => {
  const checklist =
    '<ul><li class="task-list-item"><input type="checkbox"> Apples</li><li class="task-list-item"><input type="checkbox"> Pears</li></ul>';

  assert.equal(isChecklistNoteHtml(checklist), true);
  assert.equal(isChecklistNoteHtml("<p>Ordinary article</p>"), false);
  assert.equal(
    isChecklistNoteHtml(
      `<article class="lamanote-article">${checklist}<figure>Chart</figure></article>`,
    ),
    false,
  );
});

test("work notes keep the simple Markdown source used by the editor", () => {
  const markdown = "# Shopping\n\n- [ ] Apples\n\n#private";
  const note = buildWorkNoteHtml("Shopping", markdown, {
    systemTags: ["pinned"],
  });

  assert.equal(isWorkNoteHtml(note), true);
  assert.match(note, /data-lamanotes-work-markdown/);
  assert.match(note, /# Shopping/);
  assert.match(note, /- \[ \] Apples/);
});

test("work note snapshots keep compact secondary text in source and HTML", () => {
  const note = buildWorkNoteHtml(
    "Status",
    "- <small>**Paused/stopped**</small>",
  );

  assert.match(note, /<small><strong>Paused\/stopped<\/strong><\/small>/);
  assert.match(note, /&lt;small&gt;\*\*Paused\/stopped\*\*&lt;\/small&gt;/);
});

test("smaller text keeps Markdown structure outside the semantic tag", () => {
  const markdown =
    "- **Paused/stopped**\n- [ ] Follow up\n1. Review\n> Context";
  const edit = createSmallTextEdit(markdown, {
    start: 0,
    end: markdown.length,
  });

  assert.equal(
    edit.text,
    "- <small>**Paused/stopped**</small>\n- [ ] <small>Follow up</small>\n1. <small>Review</small>\n> <small>Context</small>",
  );
  assert.match(
    renderMarkdownToHtml(edit.text),
    /<ul><li><small><strong>Paused\/stopped<\/strong><\/small><\/li>/,
  );
});

test("smaller text toggles off while keeping the useful selection", () => {
  const markdown = "- **<small>Paused/stopped</small>**";
  const start = markdown.indexOf("Paused");
  const end = start + "Paused/stopped".length;
  const edit = createSmallTextEdit(markdown, { start, end });
  const updated = `${markdown.slice(0, edit.from)}${edit.text}${markdown.slice(edit.to)}`;

  assert.equal(updated, "- **Paused/stopped**");
  assert.equal(edit.mode, "remove");
  assert.equal(edit.headOffset - edit.anchorOffset, "Paused/stopped".length);
});

test("legacy full-line small tags recover list structure outside code", () => {
  const markdown = [
    "<small>- All challenges done</small>",
    "",
    "```html",
    "<small>- keep literal</small>",
    "```",
  ].join("\n");

  assert.equal(
    normalizeSmallTextMarkdown(markdown),
    [
      "- <small>All challenges done</small>",
      "",
      "```html",
      "<small>- keep literal</small>",
      "```",
    ].join("\n"),
  );
});

test("smaller text inserts a compact span at an empty cursor", () => {
  const edit = createSmallTextEdit("Status", { start: 6, end: 6 });

  assert.equal(edit.text, "<small></small>");
  assert.equal(edit.anchorOffset, 7);
  assert.equal(edit.headOffset, 7);
});
