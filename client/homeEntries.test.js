import assert from "node:assert/strict";
import test from "node:test";
import { buildHomeEntries, noteRoute } from "./homeEntries.js";

const index = [
  { title: "Work-Projects", tags: ["work", "pinned"], lastModified: 30 },
  { title: "Quicknotes", tags: ["private", "pinned"], lastModified: 20 },
  { title: "Einkaufszettel", tags: ["private", "pinned"], lastModified: 10 },
  { title: "A shared photo", tags: ["shared"], lastModified: 40 },
];

test("daily entries are direct notes, with shared capture available independently of pinning", () => {
  const home = buildHomeEntries(index);
  assert.deepEqual(
    home.daily.map((entry) => entry.title),
    ["Einkaufszettel", "Quicknotes"],
  );
  assert.deepEqual(
    home.pinned.map((entry) => entry.title),
    ["Work-Projects"],
  );
  assert.equal(home.shared.count, 1);
  assert.equal(home.shared.to.query.term, "#shared");
  assert.equal(home.more, false);
  assert.deepEqual(index[1].tags, ["private", "pinned"]);
});

test("shared remains reachable with an empty inbox and no named daily notes", () => {
  const home = buildHomeEntries([]);
  assert.deepEqual(home.daily, []);
  assert.deepEqual(home.pinned, []);
  assert.equal(home.shared.count, 0);
  assert.equal(home.shared.to.name, "search");
});

test("a custom quick-access query, sorting and limit keep their meaning", () => {
  const entries = [
    ...index,
    { title: "Another work note", tags: ["work"], lastModified: 5 },
  ];
  const home = buildHomeEntries(entries, {
    quickAccessTerm: "#work",
    quickAccessSort: "title",
    quickAccessLimit: 1,
  });
  assert.deepEqual(
    home.pinned.map((note) => note.title),
    ["Another work note"],
  );
  assert.equal(home.more, true);
  assert.equal(home.moreLabel, "More notes");
  assert.equal(home.allPinnedRoute.query.term, "#work");
  assert.equal(home.allPinnedRoute.query.sortBy, 1);
  assert.deepEqual(
    home.daily.map((entry) => entry.title),
    ["Einkaufszettel", "Quicknotes"],
  );
});

test("hidden quick-access notes stay hidden without disabling the shared inbox", () => {
  const home = buildHomeEntries(index, { quickAccessHide: true });
  assert.deepEqual(home.daily, []);
  assert.deepEqual(home.pinned, []);
  assert.equal(home.more, false);
  assert.equal(home.shared.count, 1);
});

test("named daily notes need not acquire the pinned tag", () => {
  const entries = index.map((entry) => ({
    ...entry,
    tags: entry.tags.filter((tag) => tag !== "pinned"),
  }));
  const home = buildHomeEntries(entries);
  assert.equal(home.daily.length, 2);
  assert.deepEqual(home.pinned, []);
  assert.deepEqual(entries[1].tags, ["private"]);
});

test("stable identities are used when present, with legacy title routes preserved", () => {
  const noteId = "ln-" + "a".repeat(32);
  assert.deepEqual(noteRoute({ title: "Renamed Quicknotes", noteId }), {
    name: "stableNote",
    params: { noteId },
  });
  assert.deepEqual(noteRoute({ title: "Quicknotes" }), {
    name: "note",
    params: { title: "Quicknotes" },
  });
});
