import assert from "node:assert/strict";
import test from "node:test";

import {
  buildWorkNoteHtml,
  isChecklistNoteHtml,
  isWorkNoteHtml,
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
