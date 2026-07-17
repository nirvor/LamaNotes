const systemTags = new Set(["pinned"]);

export function normalizeSystemTag(tag = "") {
  return String(tag).replace(/^#/, "").trim().toLowerCase();
}

export function isSystemTag(tag = "") {
  return systemTags.has(normalizeSystemTag(tag));
}
