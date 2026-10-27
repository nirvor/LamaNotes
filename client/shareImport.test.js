import assert from "node:assert/strict";
import test from "node:test";
import {
  clearShareTicket,
  importSharedItem,
  pendingShareTicket,
  retainShareTicket,
} from "./shareImport.js";

function fixture() {
  const data = new Map();
  const storage = {
    getItem: (key) => data.get(key) || null,
    setItem: (key, value) => data.set(key, value),
    removeItem: (key) => data.delete(key),
  };
  let url;
  const host = {
    sessionStorage: storage,
    location: { pathname: "/share-import", search: "" },
    history: {
      state: {},
      replaceState(_state, _title, value) {
        url = value;
      },
    },
  };
  return {
    host,
    storage,
    data,
    get url() {
      return url;
    },
  };
}

test("a fragment ticket is removed before login and survives a same-tab Google return", () => {
  const state = fixture();
  const ticket = "lst_" + "t".repeat(43);
  retainShareTicket("#ticket=" + ticket, state.host, 1000);
  assert.equal(state.url, "/share-import");
  assert.equal(pendingShareTicket(state.storage, 1200), ticket);
  assert.equal(pendingShareTicket(state.storage, 601001), null);
  assert.equal(state.data.size, 0);
});

test("malformed or duplicate tickets cannot revive an earlier pending import", () => {
  const state = fixture();
  retainShareTicket("#ticket=lst_" + "t".repeat(43), state.host, 1000);
  retainShareTicket("#ticket=bad&ticket=also-bad", state.host, 1100);
  assert.equal(state.url, "/share-import");
  assert.equal(pendingShareTicket(state.storage, 1200), null);
});

test("import posts only to the owner Notes endpoint and waits for a real receipt", async () => {
  const ticket = "lst_" + "t".repeat(43);
  let call;
  const note = { noteId: "ln-" + "a".repeat(32), title: "Saved item" };
  const result = await importSharedItem(ticket, {
    fetcher: async (url, options) => {
      call = { url, ...options };
      return { ok: true, json: async () => note };
    },
  });
  assert.deepEqual(result, note);
  assert.equal(call.url, "/api/private/v1/share-import");
  assert.equal(call.headers["X-LamaNotes-Share"], "1");
  assert.equal(call.credentials, "same-origin");
  assert.deepEqual(JSON.parse(call.body), { ticket });
  await assert.rejects(
    importSharedItem(ticket, {
      fetcher: async () => ({
        ok: false,
        status: 502,
        json: async () => ({ detail: "Retry later" }),
      }),
    }),
    /Retry later/,
  );
});

test("success clears only the tab's Share ticket", () => {
  const state = fixture();
  state.storage.setItem("other-draft", "keep");
  retainShareTicket("#ticket=lst_" + "t".repeat(43), state.host, 1000);
  clearShareTicket(state.storage);
  assert.equal(pendingShareTicket(state.storage, 1200), null);
  assert.equal(state.storage.getItem("other-draft"), "keep");
});
