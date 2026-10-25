import { normalizeTagName } from "./tagPolicy.js";

const systemTags = new Set(["pinned"]);

export function normalizeSystemTag(tag = "") {
  return normalizeTagName(tag);
}

export function isSystemTag(tag = "") {
  return systemTags.has(normalizeSystemTag(tag));
}
