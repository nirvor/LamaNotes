import assert from "node:assert/strict";
import test from "node:test";

import { isEditableShortcutTarget, isPlainKey } from "./keyboardShortcuts.js";

test("plain reading shortcuts stay outside editors and modified keys", () => {
  assert.equal(isPlainKey({ key: "e" }, "e"), true);
  assert.equal(isPlainKey({ key: "e", ctrlKey: true }, "e"), false);
  assert.equal(isEditableShortcutTarget({ tagName: "TEXTAREA" }), true);
  assert.equal(isEditableShortcutTarget({ tagName: "DIV" }), false);
  assert.equal(
    isEditableShortcutTarget({
      tagName: "DIV",
      closest: (selector) => selector.includes("contenteditable"),
    }),
    true,
  );
});
