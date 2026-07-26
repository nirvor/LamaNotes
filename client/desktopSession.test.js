import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  clearDesktopFileSession,
  loadDesktopFileSession,
  loadHostDesktopFileSession,
  saveDesktopFileSession,
} from "./desktopSession.js";

class MemoryStorage {
  constructor() {
    this.values = new Map();
  }

  getItem(key) {
    return this.values.has(key) ? this.values.get(key) : null;
  }

  setItem(key, value) {
    this.values.set(key, String(value));
  }

  removeItem(key) {
    this.values.delete(key);
  }
}

function installDesktopHost(api = {}) {
  globalThis.localStorage = new MemoryStorage();
  globalThis.window = {
    location: { origin: "http://127.0.0.1:31992" },
    pywebview: { api },
  };
}

test("desktop boot restores through the shared host session", async () => {
  const indexSource = await readFile(
    new URL("./index.js", import.meta.url),
    "utf8",
  );

  assert.match(indexSource, /loadHostDesktopFileSession/);
  assert.doesNotMatch(indexSource, /\bloadDesktopFileSession\b/);
});

test("the native session wins over a stale port-local session", async () => {
  installDesktopHost({
    load_desktop_file_session: async () => ({
      paths: ["C:/work/newest.md"],
      activePath: "C:/work/newest.md",
      editMode: false,
      savedAt: 200,
    }),
  });
  localStorage.setItem(
    "lamanotes:desktop-files:v1",
    JSON.stringify({
      paths: ["C:/work/prompts-collection.md"],
      activePath: "C:/work/prompts-collection.md",
      editMode: false,
      savedAt: 100,
    }),
  );

  const session = await loadHostDesktopFileSession();

  assert.equal(session.activePath, "C:/work/newest.md");
  assert.deepEqual(loadDesktopFileSession(), session);
});

test("an empty native session does not revive stale port-local state", async () => {
  installDesktopHost({
    load_desktop_file_session: async () => null,
  });
  localStorage.setItem(
    "lamanotes:desktop-files:v1",
    JSON.stringify({
      paths: ["C:/work/prompts-collection.md"],
      activePath: "C:/work/prompts-collection.md",
      savedAt: 100,
    }),
  );

  assert.equal(await loadHostDesktopFileSession(), null);
  assert.equal(loadDesktopFileSession(), null);
});

test("an older native host can still use its port-local session", async () => {
  installDesktopHost();
  localStorage.setItem(
    "lamanotes:desktop-files:v1",
    JSON.stringify({
      paths: ["C:/work/compatible.md"],
      activePath: "C:/work/compatible.md",
      savedAt: 100,
    }),
  );

  const session = await loadHostDesktopFileSession();

  assert.equal(session.activePath, "C:/work/compatible.md");
});

test("saving mirrors one normalized session into native state", async () => {
  const saved = [];
  installDesktopHost({
    save_desktop_file_session: async (session) => saved.push(session),
  });

  const mirrored = await saveDesktopFileSession({
    files: [{ path: "C:/work/latest.md" }, { path: "C:/work/latest.md" }],
    activePath: "C:/work/latest.md",
    editMode: true,
  });

  assert.equal(mirrored, true);
  assert.equal(saved.length, 1);
  assert.deepEqual(saved[0].paths, ["C:/work/latest.md"]);
  assert.equal(saved[0].activePath, "C:/work/latest.md");
  assert.equal(saved[0].editMode, true);
  assert.deepEqual(loadDesktopFileSession(), saved[0]);
});

test("clearing removes both local and native session state", async () => {
  let nativeClears = 0;
  installDesktopHost({
    clear_desktop_file_session: async () => {
      nativeClears += 1;
    },
  });
  localStorage.setItem("lamanotes:desktop-files:v1", "{}");

  const cleared = await clearDesktopFileSession();

  assert.equal(cleared, true);
  assert.equal(nativeClears, 1);
  assert.equal(localStorage.getItem("lamanotes:desktop-files:v1"), null);
});
