import assert from "node:assert/strict";
import test from "node:test";
import { isSuggestedTag, normalizeTagName } from "./tagPolicy.js";
import { normalizeTagName as normalizeUsageTag } from "./tagUsage.js";
import { isSystemTag } from "./systemTags.js";
import { setWorkMarkdownTag } from "./components/work/workNote.js";

test("home suggestions omit exact technical tags without hiding topic families", () => {
  for (const tag of ["pinned", "r-acceptance", "r-fixture", "design-reference", "publisher-demo"]) {
    assert.equal(isSuggestedTag(` #${tag.toUpperCase()} `), false);
  }
  for (const tag of ["private", "research", "work", "r-games", "r-acceptance-methods", "fixture-design"]) {
    assert.equal(isSuggestedTag(tag), true);
  }
  assert.equal(isSuggestedTag(""), false);
  assert.equal(normalizeTagName("  #Research "), "research");
});

test("tag producers share trim-before-hash normalization", () => {
  assert.equal(normalizeUsageTag(" #RESEARCH "), "research");
  assert.equal(isSystemTag(" #PINNED "), true);
  assert.match(setWorkMarkdownTag("Task\n", " #PRIVATE "), /\n#private\n$/);
  assert.doesNotMatch(setWorkMarkdownTag("Task\n", " #PRIVATE "), /##/);
});
