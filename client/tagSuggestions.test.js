import assert from "node:assert/strict";
import test from "node:test";
import { buildTagSuggestions } from "./tagSuggestions.js";

test("routine suggestions are limited without removing technical tags from the full list", () => {
  const names = [
    "private",
    "research",
    "infra",
    "work",
    "stamsried",
    "auto",
    "backup",
    "codex",
    "dots",
    "finn",
    "lamanotes",
  ];
  const notes = names.map((name) => ({ tags: [name] }));
  notes.push(
    ...Array.from({ length: 30 }, () => ({
      tags: ["r-fixture", "r-acceptance", "design-reference", "pinned"],
    })),
  );
  const result = buildTagSuggestions(notes);
  assert.equal(result.suggested.length, 9);
  assert.equal(
    result.suggested.some((tag) => tag.name === "r-fixture"),
    false,
  );
  assert.equal(
    result.all.some((tag) => tag.name === "r-fixture"),
    true,
  );
  assert.equal(
    result.all.some((tag) => tag.name === "pinned"),
    false,
  );
  assert.equal(result.all.length, names.length + 3);
});

test("one note counts once per normalized tag", () => {
  const result = buildTagSuggestions([
    { tags: ["Private", "#private", " #PRIVATE "] },
  ]);
  assert.deepEqual(result.all, [{ name: "private", count: 1 }]);
});

test("recently used topics can rise without changing their display weight", () => {
  const now = Date.UTC(2026, 9, 25);
  const result = buildTagSuggestions(
    [{ tags: ["research"] }, { tags: ["research"] }, { tags: ["wandern"] }],
    { wandern: { count: 2, lastUsed: now } },
    9,
    now,
  );
  assert.equal(result.suggested[0].name, "wandern");
  assert.equal(result.suggested[0].count, 1);
  assert.equal("prominence" in result.suggested[0], false);
});

test("technical-only libraries still have a full selectable tag list", () => {
  const result = buildTagSuggestions([
    { tags: ["r-fixture", "publisher-demo"] },
  ]);
  assert.deepEqual(result.suggested, []);
  assert.deepEqual(
    result.all.map((tag) => tag.name),
    ["publisher-demo", "r-fixture"],
  );
});
