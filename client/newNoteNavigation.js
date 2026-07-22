export function createLocalDraftId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function newNoteLocation(options = {}) {
  const desktopEnabled = options.desktopEnabled ?? isDesktopHost();
  if (!desktopEnabled) {
    return { name: "new" };
  }

  return {
    name: "openFile",
    query: {
      new: "1",
      draft: options.draftId || createLocalDraftId(),
    },
  };
}

export function openNewNote(router, options = {}) {
  return router.push(newNoteLocation(options));
}
import { isDesktopHost } from "./brand.js";
