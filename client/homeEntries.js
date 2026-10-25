import { searchSortOptions } from "./constants.js";

const dailyTitles = ["Einkaufszettel", "Quicknotes"];
const normalized = (value) =>
  String(value || "")
    .trim()
    .toLowerCase();

export function noteRoute(note) {
  return /^ln-[a-f0-9]{32}$/.test(note.noteId || "")
    ? { name: "stableNote", params: { noteId: note.noteId } }
    : { name: "note", params: { title: note.title } };
}

export function buildHomeEntries(index = [], config = {}) {
  const entries = Array.isArray(index) ? index : [];
  const sharedCount = entries.filter((note) =>
    (note.tags || []).some(
      (tag) => normalized(tag).replace(/^#/, "") === "shared",
    ),
  ).length;
  const daily = config.quickAccessHide
    ? []
    : dailyTitles.flatMap((title, position) => {
        const note = entries.find(
          (entry) => normalized(entry.title) === normalized(title),
        );
        return note
          ? [
              {
                ...note,
                key: position === 0 ? "shopping" : "quicknotes",
                to: noteRoute(note),
              },
            ]
          : [];
      });
  const dailyNames = new Set(daily.map((note) => normalized(note.title)));
  const tag = normalized(config.quickAccessTerm || "#pinned").replace(/^#/, "");
  const matching = (config.quickAccessHide ? [] : entries)
    .filter((note) =>
      (note.tags || []).some(
        (value) => normalized(value).replace(/^#/, "") === tag,
      ),
    )
    .filter((note) => !dailyNames.has(normalized(note.title)))
    .sort((left, right) =>
      config.quickAccessSort === "title"
        ? left.title.localeCompare(right.title)
        : Number(right.lastModified || 0) - Number(left.lastModified || 0),
    );
  const rawLimit = Number(config.quickAccessLimit ?? 7);
  const limit = Number.isFinite(rawLimit)
    ? Math.max(0, Math.floor(rawLimit))
    : 7;
  return {
    daily,
    shared: {
      key: "shared",
      title: "Shared to LamaNotes",
      count: sharedCount,
      to: {
        name: "search",
        query: { term: "#shared", sortBy: searchSortOptions.lastModified },
      },
    },
    pinned: matching
      .slice(0, limit)
      .map((note) => ({ ...note, to: noteRoute(note) })),
    more: matching.length > limit,
    moreLabel: tag === "pinned" ? "All pinned notes" : "More notes",
    allPinnedRoute: {
      name: "search",
      query: {
        term: config.quickAccessTerm || "#pinned",
        sortBy:
          searchSortOptions[config.quickAccessSort] ??
          searchSortOptions.lastModified,
      },
    },
  };
}
