import assert from "node:assert/strict";
import test from "node:test";

import {
  isFileTransfer,
  isPlainTextTransfer,
  normalizeDroppedText,
  readPlainTextTransfer,
} from "./textDrop.js";

function transfer(types, values = {}) {
  return {
    types,
    getData(type) {
      return values[type] || "";
    },
  };
}

test("recognizes selected plain text from another application", () => {
  const dataTransfer = transfer(["text/plain", "text/html"]);

  assert.equal(isPlainTextTransfer(dataTransfer), true);
  assert.equal(isFileTransfer(dataTransfer), false);
});

test("file drops stay on the native file-opening path", () => {
  const dataTransfer = transfer(["Files", "text/plain"]);

  assert.equal(isFileTransfer(dataTransfer), true);
  assert.equal(isPlainTextTransfer(dataTransfer), false);
});

test("reads raw text and normalizes Windows line endings", () => {
  const dataTransfer = transfer(["text/plain"], {
    "text/plain": "first\r\nsecond\rthird",
  });

  assert.equal(readPlainTextTransfer(dataTransfer), "first\nsecond\nthird");
  assert.equal(normalizeDroppedText(null), "");
});

test("empty or unrelated transfers are ignored", () => {
  assert.equal(isPlainTextTransfer(null), false);
  assert.equal(readPlainTextTransfer(transfer(["text/uri-list"])), "");
});
