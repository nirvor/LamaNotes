import test from "node:test";
import assert from "node:assert/strict";
import {
  createSaveCheckpoint,
  acceptFileSave,
} from "./documents/saveCheckpoint.js";
import {
  formattingEdit,
  safeEditorLink,
} from "./components/editor/formatting.js";
import {
  appendMarkdownTask,
  markdownTasks,
  toggleMarkdownTask,
} from "./checklists.js";
import { findEditAnchor } from "./documents/editorPosition.js";
import { EditorState } from "@codemirror/state";
import { history, historyField, undoDepth } from "@codemirror/commands";

test("a delayed save confirms only the submitted local content", async () => {
  const file = { content: "old", draftContent: "submitted", dirty: true };
  const current = createSaveCheckpoint(() => file.draftContent);
  const submitted = file.draftContent;
  await Promise.resolve();
  file.draftContent = "submitted plus newer typing";
  assert.equal(acceptFileSave(file, submitted), false);
  assert.equal(file.content, "submitted");
  assert.equal(file.dirty, true);
  assert.equal(current(), false);
});

test("unchanged and deliberately emptied edits can be saved", () => {
  const file = { content: "old", draftContent: "", dirty: true };
  const current = createSaveCheckpoint(() => file.draftContent);
  assert.equal(acceptFileSave(file, ""), true);
  assert.equal(file.content, "");
  assert.equal(current(), true);
});

for (const language of ["markdown", "html"]) {
  for (const kind of ["bold", "italic", "small", "code"]) {
    test(`${language} ${kind} toggles and preserves the selection`, () => {
      const source = "a status z";
      const edit = formattingEdit(source, { start: 2, end: 8 }, kind, language);
      const formatted =
        source.slice(0, edit.from) + edit.text + source.slice(edit.to);
      const removed = formattingEdit(
        formatted,
        {
          start: edit.from + edit.anchorOffset,
          end: edit.from + edit.headOffset,
        },
        kind,
        language,
      );
      assert.equal(
        formatted.slice(0, removed.from) +
          removed.text +
          formatted.slice(removed.to),
        source,
      );
    });
  }
}

test("lists preserve selected rows and do not consume the following row", () => {
  const edit = formattingEdit(
    "one\ntwo\nthree",
    { start: 0, end: 8 },
    "checklist",
  );
  assert.equal(edit.text, "- [ ] one\n- [ ] two");
  assert.equal(edit.to, 7);
  assert.equal(
    formattingEdit(edit.text, { start: 0, end: edit.text.length }, "checklist")
      .text,
    "one\ntwo",
  );
});

test("link insertion rejects executable URLs and escapes HTML attributes", () => {
  assert.equal(safeEditorLink("javascript:alert(1)"), "");
  assert.equal(safeEditorLink("//other.example"), "");
  assert.equal(
    formattingEdit(
      "label",
      { start: 0, end: 5 },
      "link",
      "html",
      'https://example.org/?q="',
    ).text,
    '<a href="https://example.org/?q=&quot;">label</a>',
  );
});

test("HTML lists toggle without nested wrappers and Markdown keeps the caret", () => {
  for (const kind of ["list", "checklist"]) {
    const added = formattingEdit(
      "one\ntwo",
      { start: 0, end: 7 },
      kind,
      "html",
    );
    assert.equal(
      formattingEdit(
        added.text,
        { start: 0, end: added.text.length },
        kind,
        "html",
      ).text,
      "one\ntwo",
    );
  }
  assert.equal(
    formattingEdit("hello", { start: 5, end: 5 }, "list").anchorOffset,
    7,
  );
  assert.equal(
    formattingEdit("- hello", { start: 7, end: 7 }, "list").anchorOffset,
    5,
  );
});

test("checklists ignore fenced examples and keep item order", () => {
  const source = "```md\n- [ ] Example\n```\n- [x] One\n- [ ] Two\n\n#work";
  assert.equal(markdownTasks(source).length, 2);
  assert.equal(
    toggleMarkdownTask(source, 1, true),
    source.replace("[ ] Two", "[x] Two"),
  );
  assert.equal(
    appendMarkdownTask(source, 1, "Three"),
    source.replace("Two", "Two\n- [ ] Three"),
  );
});

test("reading anchors only move the caret when the source match is unambiguous", () => {
  assert.equal(findEditAnchor("# Title\n\nMy paragraph", "My paragraph"), 9);
  assert.equal(findEditAnchor("Repeat Repeat", "Repeat"), null);
});

test("editor state keeps undo and selection through an in-memory roundtrip", () => {
  let state = EditorState.create({ doc: "first", extensions: [history()] });
  state = state.update({
    changes: { from: 5, insert: " next" },
    selection: { anchor: 10 },
  }).state;
  const saved = state.toJSON({ history: historyField });
  const restored = EditorState.fromJSON(
    saved,
    { extensions: [history()] },
    { history: historyField },
  );
  assert.equal(restored.doc.toString(), "first next");
  assert.equal(restored.selection.main.head, 10);
  assert.equal(undoDepth(restored), 1);
});
