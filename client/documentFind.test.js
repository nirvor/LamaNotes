import assert from "node:assert/strict";
import test from "node:test";

import { findTextMatches, nextDocumentMatchIndex } from "./documentFind.js";

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
