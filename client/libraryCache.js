const cacheKey = "lamanotes:library-cache:v1";
const cacheVersion = 1;
const maxCachedNotes = 4;
const maxCachedNoteCharacters = 600_000;
const maxCacheAgeMs = 30 * 24 * 60 * 60 * 1000;

function defaultStorage() {
  return typeof window !== "undefined" ? window.localStorage : null;
}

function emptyCache() {
  return {
    version: cacheVersion,
    config: null,
    index: null,
    notes: [],
  };
}

function readCache(storage = defaultStorage()) {
  if (!storage) {
    return emptyCache();
  }

  try {
    const parsed = JSON.parse(storage.getItem(cacheKey) || "null");
    if (!parsed || parsed.version !== cacheVersion) {
      return emptyCache();
    }
    return {
      version: cacheVersion,
      config: parsed.config || null,
      index: parsed.index || null,
      notes: Array.isArray(parsed.notes) ? parsed.notes : [],
    };
  } catch {
    storage.removeItem(cacheKey);
    return emptyCache();
  }
}

function writeCache(cache, storage = defaultStorage()) {
  if (!storage) {
    return;
  }

  try {
    storage.setItem(cacheKey, JSON.stringify(cache));
  } catch {
    // Keep the small config/index cache even if large note content hits quota.
    try {
      storage.setItem(cacheKey, JSON.stringify({ ...cache, notes: [] }));
    } catch {
      storage.removeItem(cacheKey);
    }
  }
}

function isFresh(entry, now = Date.now()) {
  return Boolean(
    entry?.savedAt && now - Number(entry.savedAt) <= maxCacheAgeMs,
  );
}

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

export function getWarmConfig(storage = defaultStorage()) {
  const entry = readCache(storage).config;
  return isFresh(entry) && entry.data && typeof entry.data === "object"
    ? clone(entry.data)
    : null;
}

export function setWarmConfig(config, storage = defaultStorage()) {
  if (!config || typeof config !== "object") {
    return;
  }
  const cache = readCache(storage);
  cache.config = { savedAt: Date.now(), data: clone(config) };
  writeCache(cache, storage);
}

export function getWarmIndex(storage = defaultStorage()) {
  const entry = readCache(storage).index;
  return isFresh(entry) && Array.isArray(entry.data) ? clone(entry.data) : null;
}

export function setWarmIndex(index, storage = defaultStorage()) {
  if (!Array.isArray(index)) {
    return;
  }
  const cache = readCache(storage);
  cache.index = { savedAt: Date.now(), data: clone(index) };
  writeCache(cache, storage);
}

export function getWarmNote(title, storage = defaultStorage()) {
  const normalizedTitle = String(title || "");
  const entry = readCache(storage).notes.find(
    (note) => note.title === normalizedTitle,
  );
  return isFresh(entry) && entry.data ? clone(entry.data) : null;
}

export function setWarmNote(note, storage = defaultStorage()) {
  if (!note?.title || typeof note.content !== "string") {
    return;
  }
  if (note.content.length > maxCachedNoteCharacters) {
    removeWarmNote(note.title, storage);
    return;
  }

  const cache = readCache(storage);
  cache.notes = [
    {
      title: String(note.title),
      savedAt: Date.now(),
      data: clone(note),
    },
    ...cache.notes.filter((entry) => entry.title !== String(note.title)),
  ].slice(0, maxCachedNotes);
  writeCache(cache, storage);
}

export function removeWarmNote(title, storage = defaultStorage()) {
  const cache = readCache(storage);
  const nextNotes = cache.notes.filter(
    (entry) => entry.title !== String(title || ""),
  );
  if (nextNotes.length === cache.notes.length) {
    return;
  }
  cache.notes = nextNotes;
  writeCache(cache, storage);
}

export function removeWarmIndexTitles(titles, storage = defaultStorage()) {
  const removedTitles = new Set(
    (Array.isArray(titles) ? titles : [titles]).map((title) =>
      String(title || ""),
    ),
  );
  const cache = readCache(storage);
  if (!Array.isArray(cache.index?.data)) {
    return;
  }
  cache.index = {
    savedAt: Date.now(),
    data: cache.index.data.filter((note) => !removedTitles.has(note.title)),
  };
  writeCache(cache, storage);
}

export function clearWarmLibraryCache(storage = defaultStorage()) {
  storage?.removeItem(cacheKey);
}

export { cacheKey as warmLibraryCacheKey };
