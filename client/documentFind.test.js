import assert from "node:assert/strict";
import test from "node:test";

import { findTextMatches, nextDocumentMatchIndex, replacementEdits } from "./documentFind.js";

test("document find is case insensitive and non-overlapping", () => {
  assert.deepEqual(findTextMatches("Alpha alpha ALPHA", "alpha"), [
    { start: 0, end: 5 },
    { start: 6, end: 11 },
    { start: 12, end: 17 },
  ]);
  assert.deepEqual(findTextMatches("aaaa", "aa"), [
    { start: 0, end: 2 },
    { start: 2, end: 4 },
  ]);
  assert.deepEqual(
    findTextMatches(
      "Required workflow and REQUIRED WORKFLOW",
      "rEqUiReD WoRkFlOw",
    ),
    [
      { start: 0, end: 17 },
      { start: 22, end: 39 },
    ],
  );
});

test("document find wraps in both directions", () => {
  assert.equal(nextDocumentMatchIndex(3, 2, 1), 0);
  assert.equal(nextDocumentMatchIndex(3, 0, -1), 2);
  assert.equal(nextDocumentMatchIndex(0, 0, 1), -1);
});

test("literal search keeps original UTF-16 offsets and supports exact case", () => {
  assert.deepEqual(findTextMatches("İx 😀x X", "x"), [
    { start: 1, end: 2 }, { start: 5, end: 6 }, { start: 7, end: 8 },
  ]);
  assert.deepEqual(findTextMatches("İx 😀x X", "x", true), [
    { start: 1, end: 2 }, { start: 5, end: 6 },
  ]);
  assert.deepEqual(findTextMatches("[a].* [a]", "[a]"), [
    { start: 0, end: 3 }, { start: 6, end: 9 },
  ]);
});

test("replacement changes are non-overlapping and keep dollar text literal", () => {
  const matches = findTextMatches("one ONE one", "one");
  assert.deepEqual(replacementEdits(matches, "$&"), [
    { from: 0, to: 3, insert: "$&" }, { from: 4, to: 7, insert: "$&" }, { from: 8, to: 11, insert: "$&" },
  ]);
  assert.deepEqual(replacementEdits(matches, "", 1), [{ from: 4, to: 7, insert: "" }]);
});
