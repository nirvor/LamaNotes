const tagUsageStorageKey = "lamanotes:tag-usage";
const tagUsageEventName = "lamanotes:tag-usage";
const maxStoredTags = 80;

export function normalizeTagName(tag = "") {
  return String(tag).replace(/^#/, "").trim().toLowerCase();
}

function readTagUsage() {
  try {
    const parsed = JSON.parse(localStorage.getItem(tagUsageStorageKey) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeTagUsage(usage) {
  const compactUsage = Object.fromEntries(
    Object.entries(usage)
      .sort((left, right) => {
        const leftLastUsed = left[1]?.lastUsed || 0;
        const rightLastUsed = right[1]?.lastUsed || 0;
        return rightLastUsed - leftLastUsed;
      })
      .slice(0, maxStoredTags),
  );

  try {
    localStorage.setItem(tagUsageStorageKey, JSON.stringify(compactUsage));
  } catch {
    // Local storage can fail in private contexts. Tag ranking simply falls back
    // to note frequency then.
  }
}

export function getTagUsage() {
  return readTagUsage();
}

export function getTagUsageEntry(tag) {
  return readTagUsage()[normalizeTagName(tag)] || { count: 0, lastUsed: 0 };
}

export function recordTagUse(tags) {
  const normalizedTags = [...new Set([tags].flat().map(normalizeTagName))]
    .filter(Boolean)
    .filter((tag) => /^[a-z0-9_-]+$/.test(tag));

  if (!normalizedTags.length) {
    return;
  }

  const now = Date.now();
  const usage = readTagUsage();
  normalizedTags.forEach((tag) => {
    const existing = usage[tag] || { count: 0, lastUsed: 0 };
    usage[tag] = {
      count: Math.min((Number(existing.count) || 0) + 1, 999),
      lastUsed: now,
    };
  });

  writeTagUsage(usage);
  window.dispatchEvent(
    new CustomEvent(tagUsageEventName, { detail: { tags: normalizedTags } }),
  );
}

export function onTagUsageChange(callback) {
  const handler = () => callback();
  window.addEventListener(tagUsageEventName, handler);
  window.addEventListener("storage", handler);
  return () => {
    window.removeEventListener(tagUsageEventName, handler);
    window.removeEventListener("storage", handler);
  };
}
