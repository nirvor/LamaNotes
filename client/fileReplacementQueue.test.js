import assert from "node:assert/strict";
import test from "node:test";

import { createFileReplacementQueue } from "./fileReplacementQueue.js";

test("file replacements remain ordered while one decision is open", async () => {
  const decisions = [];
  const opened = [];
  let dirty = true;
  const replace = createFileReplacementQueue({
    hasUnsavedChanges: () => dirty,
    requestDecision: (proceed, cancel) => decisions.push({ proceed, cancel }),
  });

  const first = replace(async () => {
    opened.push("first");
    dirty = false;
  });
  const second = replace(async () => {
    opened.push("second");
  });

  await Promise.resolve();
  assert.equal(decisions.length, 1);
  assert.deepEqual(opened, []);

  await decisions[0].proceed();
  assert.equal(await first, true);
  assert.equal(await second, true);
  assert.deepEqual(opened, ["first", "second"]);
});

test("Cancel keeps the current file and resolves the handoff", async () => {
  let decision;
  let opened = false;
  const replace = createFileReplacementQueue({
    hasUnsavedChanges: () => true,
    requestDecision: (proceed, cancel) => {
      decision = { proceed, cancel };
    },
  });

  const replacement = replace(async () => {
    opened = true;
  });
  await Promise.resolve();
  decision.cancel();

  assert.equal(await replacement, false);
  assert.equal(opened, false);
});

test("a failed replacement releases the next queued file", async () => {
  const opened = [];
  const replace = createFileReplacementQueue({
    hasUnsavedChanges: () => false,
    requestDecision: () => {},
  });

  const failed = replace(async () => {
    throw new Error("broken file");
  });
  const next = replace(async () => {
    opened.push("next");
  });

  await assert.rejects(failed, /broken file/);
  assert.equal(await next, true);
  assert.deepEqual(opened, ["next"]);
});
