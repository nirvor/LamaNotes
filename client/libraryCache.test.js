import assert from "node:assert/strict";
import test from "node:test";

import {
  clearWarmLibraryCache,
  getWarmConfig,
  getWarmIndex,
  getWarmNote,
  removeWarmIndexTitles,
  removeWarmNote,
  setWarmConfig,
  setWarmIndex,
  setWarmNote,
  warmLibraryCacheKey,
} from "./libraryCache.js";

function fakeStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

test("warm config, index, and recent notes survive a new reader", () => {
  const storage = fakeStorage();
  setWarmConfig({ authType: "password" }, storage);
  setWarmIndex([{ title: "One", tags: ["private"] }], storage);
  setWarmNote({ title: "One", content: "hello", format: "html" }, storage);

  assert.deepEqual(getWarmConfig(storage), { authType: "password" });
  assert.deepEqual(getWarmIndex(storage), [
    { title: "One", tags: ["private"] },
  ]);
  assert.equal(getWarmNote("One", storage).content, "hello");
});

test("deleted titles leave both warm note and semantic index", () => {
  const storage = fakeStorage();
  setWarmIndex(
    [
      { title: "Keep", tags: ["private"] },
      { title: "Delete", tags: ["lamanotes"] },
    ],
    storage,
  );
  setWarmNote({ title: "Delete", content: "old", format: "html" }, storage);

  removeWarmNote("Delete", storage);
  removeWarmIndexTitles("Delete", storage);

  assert.equal(getWarmNote("Delete", storage), null);
  assert.deepEqual(getWarmIndex(storage), [
    { title: "Keep", tags: ["private"] },
  ]);
});

test("oversized note content is not persisted", () => {
  const storage = fakeStorage();
  setWarmNote(
    { title: "Huge", content: "x".repeat(600_001), format: "html" },
    storage,
  );
  assert.equal(getWarmNote("Huge", storage), null);
});

test("cache can be cleared on logout", () => {
  const storage = fakeStorage();
  setWarmConfig({ authType: "password" }, storage);
  clearWarmLibraryCache(storage);
  assert.equal(storage.getItem(warmLibraryCacheKey), null);
});
