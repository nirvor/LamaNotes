import assert from "node:assert/strict";
import test from "node:test";

import {
  createDebouncedWork,
  scheduleIdleWork,
} from "./performanceScheduling.js";

function fakeHost() {
  let nextId = 0;
  const callbacks = new Map();
  return {
    callbacks,
    setTimeout(callback) {
      nextId += 1;
      callbacks.set(nextId, callback);
      return nextId;
    },
    clearTimeout(id) {
      callbacks.delete(id);
    },
    runLatest() {
      const [id, callback] = [...callbacks.entries()].at(-1) || [];
      if (callback) {
        callbacks.delete(id);
        callback();
      }
    },
  };
}

test("debounced work keeps only the latest arguments and can flush", () => {
  const host = fakeHost();
  const calls = [];
  const work = createDebouncedWork((value) => calls.push(value), 220, host);

  work.schedule("first");
  work.schedule("latest");

  assert.equal(host.callbacks.size, 1);
  assert.equal(work.pending(), true);
  assert.equal(work.flush(), true);
  assert.deepEqual(calls, ["latest"]);
  assert.equal(work.pending(), false);
});

test("cancelled idle work never runs", () => {
  const host = fakeHost();
  let calls = 0;
  const cancel = scheduleIdleWork(
    () => {
      calls += 1;
    },
    { host },
  );

  cancel();
  host.runLatest();

  assert.equal(calls, 0);
});
