import { isSuggestedTag, normalizeTagName } from "./tagPolicy.js";
import { isSystemTag } from "./systemTags.js";

export function buildTagSuggestions(
  index = [],
  usage = {},
  limit = 9,
  now = Date.now(),
) {
  const counts = new Map();
  for (const note of Array.isArray(index) ? index : []) {
    const names = new Set(
      (Array.isArray(note.tags) ? note.tags : []).map(normalizeTagName),
    );
    for (const name of names) {
      if (name && !isSystemTag(name))
        counts.set(name, (counts.get(name) || 0) + 1);
    }
  }
  const all = [...counts]
    .map(([name, count]) => ({ name, count }))
    .sort((left, right) => left.name.localeCompare(right.name));
  const suggested = all
    .filter((tag) => isSuggestedTag(tag.name))
    .map((tag) => {
      const entry = usage[tag.name] || {};
      const age = entry.lastUsed
        ? Math.max(0, (now - Number(entry.lastUsed)) / 86400000)
        : Infinity;
      return {
        ...tag,
        score:
          tag.count * 10 +
          Math.min(Number(entry.count) || 0, 20) * 14 +
          Math.max(0, 18 - age),
      };
    })
    .sort(
      (left, right) =>
        right.score - left.score ||
        right.count - left.count ||
        left.name.localeCompare(right.name),
    );
  return { all, suggested: suggested.slice(0, limit) };
}
