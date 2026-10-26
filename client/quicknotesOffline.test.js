import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const version = "a".repeat(16);
const source = readFileSync(
  new URL("./public/sw.js", import.meta.url),
  "utf8",
).replace("__LAMANOTES_SHELL_VERSION__", version);
function worker({ valid = true } = {}) {
  const handlers = new Map();
  const records = new Map([
    ["unrelated-cache", new Map()],
    ["lamanotes-shell-old", new Map()],
  ]);
  let network = true;
  let skipped = false;
  let claimed = false;
  const context = {
    self: {
      location: { origin: "https://notes.example" },
      addEventListener: (name, handler) => handlers.set(name, handler),
      skipWaiting: async () => {
        skipped = true;
      },
      clients: {
        claim: async () => {
          claimed = true;
        },
      },
    },
    URL,
    Response,
    AbortController,
    setTimeout,
    clearTimeout,
    fetch: async (request) => {
      if (!network) throw new Error("Offline");
      if (request === "/offline-shell.json")
        return Response.json({
          version: valid ? version : "other",
          resources: ["/", "/index.html", "/assets/home.js"],
        });
      return new Response("Online");
    },
    caches: {
      open: async (name) => ({
        addAll: async (resources) => {
          records.set(
            name,
            new Map(
              resources.map((path) => [
                path,
                new Response(
                  path === "/index.html" ? "<html>Home</html>" : "Static",
                ),
              ]),
            ),
          );
        },
      }),
      keys: async () => [...records.keys()],
      delete: async (name) => records.delete(name),
      match: async (request) => {
        const path =
          typeof request === "string" ? request : new URL(request.url).pathname;
        for (const cache of records.values())
          if (cache.has(path)) return cache.get(path).clone();
      },
    },
  };
  vm.runInNewContext(source, context);
  const lifecycle = (name) => {
    let result;
    handlers.get(name)({
      waitUntil: (promise) => {
        result = promise;
      },
    });
    return result;
  };
  const request = (path, mode = "cors", method = "GET") => {
    let result;
    handlers.get("fetch")({
      request: { url: `https://notes.example${path}`, mode, method },
      respondWith: (promise) => {
        result = promise;
      },
    });
    return result;
  };
  return {
    records,
    lifecycle,
    request,
    disconnect: () => {
      network = false;
    },
    state: () => ({ skipped, claimed }),
  };
}

test("the complete shell installs before activation and activation works without a network", async () => {
  const app = worker();
  await app.lifecycle("install");
  assert.equal(app.state().skipped, true);
  app.disconnect();
  await app.lifecycle("activate");
  assert.equal(app.state().claimed, true);
  assert.equal(app.records.has("unrelated-cache"), true);
  assert.equal(app.records.has("lamanotes-shell-old"), false);
  assert.equal(
    await (await app.request("/", "navigate")).text(),
    "<html>Home</html>",
  );
  const redirect = await app.request("/note/Quicknotes", "navigate");
  assert.equal(redirect.status, 303);
  assert.equal(redirect.headers.get("location"), "https://notes.example/");
});

test("a mismatched release never replaces the existing offline shell", async () => {
  const app = worker({ valid: false });
  await assert.rejects(app.lifecycle("install"), /Invalid offline shell/);
  assert.equal(app.state().skipped, false);
  assert.equal(app.records.has("lamanotes-shell-old"), true);
});

test("the worker never intercepts private API reads or queued writing requests", () => {
  const app = worker();
  assert.equal(app.request("/api/index"), undefined);
  assert.equal(app.request("/api/notes/Quicknotes", "navigate"), undefined);
  assert.equal(
    app.request("/api/quicknotes/entries", "cors", "POST"),
    undefined,
  );
  assert.equal(
    app.request("/api/private/v1/assets/private/content"),
    undefined,
  );
});
