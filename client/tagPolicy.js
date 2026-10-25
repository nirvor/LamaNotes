export const technicalTagNames = Object.freeze([
  "r-acceptance",
  "r-fixture",
  "design-reference",
  "publisher-demo",
]);

const hiddenSuggestions = new Set(["pinned", ...technicalTagNames]);

export function normalizeTagName(value = "") {
  return String(value).trim().replace(/^#+/, "").trim().toLowerCase();
}

export function isSuggestedTag(value = "") {
  const tag = normalizeTagName(value);
  return Boolean(tag) && !hiddenSuggestions.has(tag);
}
