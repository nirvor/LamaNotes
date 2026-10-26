import test from "node:test";
import assert from "node:assert/strict";
import { createQuicknotesCapture } from "./quicknotesCapture.js";

const target = { noteId: `ln-${"a".repeat(32)}`, title: "Quicknotes" };
function fixture() {
  const values = new Map([["target", target]]);
  const entries = new Map();
  const store = {
    get: async (key) => values.get(key),
    set: async (key, value) => {
      if (value == null) values.delete(key);
      else values.set(key, value);
    },
    list: async () => [...entries.values()],
    enqueue: async (entry, text) => {
      entries.set(entry.entryId, entry);
      if (values.get("draft") === text) values.delete("draft");
    },
    remove: async (id) => {
      entries.delete(id);
    },
  };
  let online = false;
  let nextId = 0;
  const options = {
    store,
    getTarget: async () => target,
    sendEntry: async (entry) => ({ ...target, entryId: entry.entryId }),
    online: () => online,
    uuid: () => `entry-${++nextId}`,
    now: () => new Date("2026-10-26T08:00:00Z"),
  };
  return {
    store,
    entries,
    values,
    options,
    connect: () => {
      online = true;
    },
  };
}
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

test("offline submission acknowledges only a durable local enqueue and preserves the exact text", async () => {
  const f = fixture();
  let commit;
  const enqueue = f.store.enqueue;
  f.store.enqueue = async (...args) => {
    await new Promise((resolve) => {
      commit = resolve;
    });
    await enqueue(...args);
  };
  const capture = createQuicknotesCapture(f.options);
  await capture.initialize();
  capture.editDraft("Idee unterwegs.\n#123 bleibt Text.");
  const sending = capture.submit();
  await tick();
  assert.equal(capture.getState().draft, "Idee unterwegs.\n#123 bleibt Text.");
  assert.equal(capture.getState().busy, true);
  commit();
  assert.equal(await sending, true);
  assert.equal(capture.getState().draft, "");
  assert.equal(capture.getState().pendingCount, 1);
  assert.equal(
    [...f.entries.values()][0].text,
    "Idee unterwegs.\n#123 bleibt Text.",
  );
  assert.equal(f.values.has("draft"), false);
});

test("pending entries survive a new page controller and reconnect to the same note", async () => {
  const f = fixture();
  const first = createQuicknotesCapture(f.options);
  await first.initialize();
  first.editDraft("Erster Gedanke");
  await first.submit();
  const saved = [];
  const second = createQuicknotesCapture({
    ...f.options,
    sendEntry: async (entry) => {
      saved.push(entry);
      return { ...target, entryId: entry.entryId };
    },
  });
  await second.initialize();
  assert.equal(second.getState().pendingCount, 1);
  f.connect();
  await second.flush();
  assert.equal(saved.length, 1);
  assert.equal(saved[0].noteId, target.noteId);
  assert.equal(saved[0].entryId, "entry-1");
  assert.equal(second.getState().pendingCount, 0);
  assert.equal(second.getState().status, "saved");
});

test("a lost response retries the identical receipt ID after a reload", async () => {
  const f = fixture();
  const persisted = new Map();
  const ids = [];
  let loseReply = true;
  f.options.sendEntry = async (entry) => {
    ids.push(entry.entryId);
    persisted.set(entry.entryId, entry.text);
    if (loseReply) {
      loseReply = false;
      throw new Error("Connection lost after save");
    }
    return { ...target, entryId: entry.entryId, duplicate: true };
  };
  const capture = createQuicknotesCapture(f.options);
  await capture.initialize();
  capture.editDraft("Exactly once");
  await capture.submit();
  f.connect();
  await capture.flush();
  assert.equal(capture.getState().pendingCount, 1);
  const resumed = createQuicknotesCapture(f.options);
  await resumed.initialize();
  await resumed.flush();
  assert.deepEqual(new Set(ids), new Set(["entry-1"]));
  assert.equal(persisted.size, 1);
  assert.equal(resumed.getState().pendingCount, 0);
});

test("storage failure never clears the writing field or claims success", async () => {
  const f = fixture();
  f.store.enqueue = async () => {
    throw new Error("Quota exhausted");
  };
  const capture = createQuicknotesCapture(f.options);
  await capture.initialize();
  capture.editDraft("Keep this thought");
  assert.equal(await capture.submit(), false);
  assert.equal(capture.getState().draft, "Keep this thought");
  assert.equal(capture.getState().status, "error");
  assert.equal(capture.getState().busy, false);
  assert.equal(f.entries.size, 0);
});

test("authentication failure keeps pending content until the same owner returns", async () => {
  const f = fixture();
  const capture = createQuicknotesCapture(f.options);
  await capture.initialize();
  capture.editDraft("Private thought");
  await capture.submit();
  f.connect();
  let allowed = false;
  f.options.getTarget = async () => {
    if (!allowed) throw { response: { status: 401 } };
    return target;
  };
  const resumed = createQuicknotesCapture(f.options);
  await resumed.initialize();
  await resumed.flush();
  assert.equal(resumed.getState().status, "blocked");
  assert.equal(f.entries.size, 1);
  allowed = true;
  await resumed.flush();
  assert.equal(f.entries.size, 0);
});

test("a changed source never redirects already captured private text to another note", async () => {
  const f = fixture();
  const capture = createQuicknotesCapture(f.options);
  await capture.initialize();
  capture.editDraft("For the original note");
  await capture.submit();
  f.connect();
  let sent = false;
  const resumed = createQuicknotesCapture({
    ...f.options,
    getTarget: async () => ({ noteId: `ln-${"b".repeat(32)}`, title: "Other" }),
    sendEntry: async () => {
      sent = true;
    },
  });
  await resumed.initialize();
  await resumed.flush();
  assert.equal(sent, false);
  assert.equal(resumed.getState().status, "blocked");
  assert.equal([...f.entries.values()][0].noteId, target.noteId);
});

test("new input during a background send is retained and every submitted entry is sent", async () => {
  const f = fixture();
  const sent = [];
  let release;
  f.options.sendEntry = async (entry) => {
    if (!sent.length)
      await new Promise((resolve) => {
        release = resolve;
      });
    sent.push(entry);
    return { ...target, entryId: entry.entryId };
  };
  const capture = createQuicknotesCapture(f.options);
  await capture.initialize();
  capture.editDraft("First");
  await capture.submit();
  f.connect();
  const firstFlush = capture.flush();
  await tick();
  capture.editDraft("Second");
  await capture.submit();
  capture.editDraft("Still typing a third");
  release();
  await firstFlush;
  await tick();
  await capture.flush();
  assert.deepEqual(
    sent.map((entry) => entry.text),
    ["First", "Second"],
  );
  assert.equal(capture.getState().draft, "Still typing a third");
  assert.equal(f.values.get("draft"), "Still typing a third");
  assert.equal(capture.getState().pendingCount, 0);
});
