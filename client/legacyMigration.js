const migrations = [
  ["nirvnotes:", "lamanotes:"],
  ["nirvNotesTagUsage", "lamanotes:tag-usage"],
  ["nirvNotesNewNoteKind", "lamanotes:new-note-kind"],
  ["lamanotesNewNoteKind", "lamanotes:new-note-kind"],
  ["flatnotesNewNoteKind", "lamanotes:new-note-kind"],
];

function sanitizeMigratedValue(nextKey, value) {
  if (nextKey !== "lamanotes:library-cache:v1") {
    return value;
  }

  try {
    const cache = JSON.parse(value || "null");
    if (!cache || typeof cache !== "object") {
      return value;
    }
    return JSON.stringify({ ...cache, notes: [] });
  } catch {
    return value;
  }
}

export function migrateStorage(storage) {
  if (!storage) {
    return;
  }

  const keys = Array.from({ length: storage.length }, (_, index) =>
    storage.key(index),
  ).filter(Boolean);

  for (const key of keys) {
    const migration = migrations.find(([legacy]) =>
      legacy.endsWith(":") ? key.startsWith(legacy) : key === legacy,
    );
    if (!migration) {
      continue;
    }
    const [legacy, current] = migration;
    const nextKey = legacy.endsWith(":")
      ? `${current}${key.slice(legacy.length)}`
      : current;
    if (storage.getItem(nextKey) == null) {
      storage.setItem(
        nextKey,
        sanitizeMigratedValue(nextKey, storage.getItem(key)),
      );
    }
    storage.removeItem(key);
  }
}

if (typeof window !== "undefined") {
  try {
    migrateStorage(window.localStorage);
    migrateStorage(window.sessionStorage);
  } catch {
    // Private browsing policies may block storage. LamaNotes remains usable.
  }
}
