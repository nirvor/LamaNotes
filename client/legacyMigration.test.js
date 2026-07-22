import assert from "node:assert/strict";
import test from "node:test";

import { migrateStorage } from "./legacyMigration.js";

function fakeStorage(entries = {}) {
  const values = new Map(Object.entries(entries));
  return {
    get length() {
      return values.size;
    },
    key: (index) => [...values.keys()][index] ?? null,
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

test("legacy product settings move once to LamaNotes keys", () => {
  const storage = fakeStorage({
    "nirvnotes:show-line-numbers": "true",
    nirvNotesTagUsage: '{"work":{"count":4}}',
    nirvNotesNewNoteKind: "research",
  });

  migrateStorage(storage);

  assert.equal(storage.getItem("lamanotes:show-line-numbers"), "true");
  assert.equal(storage.getItem("lamanotes:tag-usage"), '{"work":{"count":4}}');
  assert.equal(storage.getItem("lamanotes:new-note-kind"), "research");
  assert.equal(storage.getItem("nirvnotes:show-line-numbers"), null);
});

test("warm cache keeps index but drops legacy note bodies", () => {
  const storage = fakeStorage({
    "nirvnotes:library-cache:v1": JSON.stringify({
      version: 1,
      config: { data: { authType: "google" } },
      index: { data: [{ title: "One" }] },
      notes: [{ title: "One", content: "old contract" }],
    }),
  });

  migrateStorage(storage);

  const cache = JSON.parse(storage.getItem("lamanotes:library-cache:v1"));
  assert.deepEqual(cache.index.data, [{ title: "One" }]);
  assert.deepEqual(cache.notes, []);
});
