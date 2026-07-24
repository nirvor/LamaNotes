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
