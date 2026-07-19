import assert from "node:assert/strict";
import test from "node:test";

import { getSearchSuggestions } from "./searchSuggestions.js";

const index = [
  {
    title: "Notiz aus dem Labor",
    tags: ["drei", "hardware"],
    summary: "Drei Hardware-Systeme werden verglichen.",
    last_modified: 30,
  },
  {
    title: "Drei Hardware-Systeme",
    tags: ["infra", "vergleich"],
    summary: "PC, Mini-PC und Laptop.",
    last_modified: 10,
  },
  {
    title: "Hardware-Archiv",
    tags: ["backup"],
    summary: "Aeltere Systeme.",
    last_modified: 20,
  },
];

test('"drei" prioritizes the matching note title', () => {
  const suggestions = getSearchSuggestions(index, "drei");

  assert.equal(suggestions[0].title, "Drei Hardware-Systeme");
  assert.equal(suggestions[0].matchKind, "title");
});

test('"drei hardw" matches the title "Drei Hardware-Systeme"', () => {
  const suggestions = getSearchSuggestions(index, "drei hardw");

  assert.equal(suggestions[0].title, "Drei Hardware-Systeme");
  assert.equal(suggestions[0].matchKind, "title");
  assert.equal(
    suggestions.some((suggestion) => suggestion.title === "Hardware-Archiv"),
    false,
  );
});

test("empty input has no suggestions", () => {
  assert.deepEqual(getSearchSuggestions(index, "  "), []);
});
