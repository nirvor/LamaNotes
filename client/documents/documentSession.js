import { nextTick, onBeforeUnmount, ref } from "vue";

import {
  writeHtmlToClipboard,
  writeMarkdownToClipboard,
  writePlainTextToClipboard,
} from "../clipboard.js";

const ignoredEditTriggerSelector = [
  "a",
  "button",
  "input",
  "textarea",
  "select",
  "label",
  "summary",
  "[role='button']",
  "pre",
  "code",
  ".lamanotes-code-block-wrapper",
  ".lamanotes-bottom-tags",
  ".lamanotes-media-button",
  ".lamanotes-media-lightbox",
  ".katex",
].join(",");

const editDoubleTapDelayMs = 420;
const editDoubleTapDistancePx = 28;

export function useDocumentSession(options = {}) {
  const editMode = ref(false);
  const dirty = ref(false);
  const saving = ref(false);
  const copied = ref(false);
  let lastContentTap = null;
  let copiedTimer = null;

  function getOptionValue(name, fallback = null) {
    const option = options[name];
    return typeof option === "function" ? option() : (option ?? fallback);
  }

  function draftKey(overrideKey = null) {
    const key = String(overrideKey ?? getOptionValue("draftKey", "")).trim();
    return key ? `lamanotes:draft:${key}` : "";
  }

  function legacyDraftKeys() {
    return (getOptionValue("legacyDraftKeys", []) || [])
      .map((key) => String(key || "").trim())
      .filter(Boolean);
  }

  function preferredDraftStorage() {
    return getOptionValue("persistDraft", false)
      ? window.localStorage
      : window.sessionStorage;
  }

  function loadDraft(overrideKey = null) {
    const key = draftKey(overrideKey);
    const keys = key ? [key, ...legacyDraftKeys()] : legacyDraftKeys();
    for (const storage of [window.localStorage, window.sessionStorage]) {
      for (const candidate of keys) {
        const value = storage.getItem(candidate);
        if (value != null) {
          return value;
        }
      }
    }
    return null;
  }

  function saveDraft(content, overrideKey = null) {
    const key = draftKey(overrideKey);
    if (!key) {
      return;
    }

    const value = String(content ?? "");
    if (!value) {
      clearDraft(overrideKey);
      return;
    }

    const storage = preferredDraftStorage();
    const otherStorage =
      storage === window.localStorage
        ? window.sessionStorage
        : window.localStorage;
    storage.setItem(key, value);
    otherStorage.removeItem(key);
  }

  function clearDraft(overrideKey = null) {
    const key = draftKey(overrideKey);
    const keys = key ? [key, ...legacyDraftKeys()] : legacyDraftKeys();
    clearStoredDraftKeys(keys);
  }

  function clearStoredDraftKeys(keys) {
    for (const storage of [window.localStorage, window.sessionStorage]) {
      keys.forEach((candidate) => storage.removeItem(candidate));
    }
  }

  function setDirty(value = true) {
    dirty.value = Boolean(value);
  }

  function focusEditorSoon() {
    nextTick(() => options.focusEditor?.());
  }

  function enterEdit() {
    if (
      !getOptionValue("canEdit", true) ||
      !getOptionValue("hasDocument", true)
    ) {
      return false;
    }

    options.beforeEnterEdit?.();
    editMode.value = true;
    focusEditorSoon();
    return true;
  }

  function leaveEdit() {
    options.beforeLeaveEdit?.();
    editMode.value = false;
    lastContentTap = null;
    options.afterLeaveEdit?.();
  }

  function requestEdit() {
    if (
      !getOptionValue("canEdit", true) ||
      !getOptionValue("hasDocument", true)
    ) {
      return false;
    }
    if (options.requestEdit) {
      return options.requestEdit();
    }
    return enterEdit();
  }

  function contentSelectionHasText() {
    const selection = window.getSelection?.();
    return Boolean(selection && !selection.isCollapsed && selection.toString());
  }

  function isIgnoredEditTriggerTarget(target) {
    return (
      target instanceof Element &&
      Boolean(target.closest(ignoredEditTriggerSelector))
    );
  }

  function canStartEditFromContent(event, { allowSelection = false } = {}) {
    return (
      !editMode.value &&
      getOptionValue("canEdit", true) &&
      getOptionValue("hasDocument", true) &&
      !event.defaultPrevented &&
      (event.button == null || event.button === 0) &&
      (allowSelection || !contentSelectionHasText()) &&
      !isIgnoredEditTriggerTarget(event.target)
    );
  }

  function startEditFromContent(event, options = {}) {
    if (!canStartEditFromContent(event, options)) {
      return false;
    }

    event.preventDefault();
    requestEdit();
    return true;
  }

  function contentDblClickHandler(event) {
    lastContentTap = null;
    startEditFromContent(event, { allowSelection: true });
  }

  function contentPointerUpHandler(event) {
    const previousTap = lastContentTap;
    if (
      !canStartEditFromContent(event, {
        allowSelection: Boolean(previousTap),
      })
    ) {
      lastContentTap = null;
      return;
    }

    const now = window.performance?.now?.() || Date.now();
    const nextTap = {
      time: now,
      x: event.clientX,
      y: event.clientY,
    };

    lastContentTap = nextTap;
    window.setTimeout(() => {
      if (lastContentTap === nextTap) {
        lastContentTap = null;
      }
    }, editDoubleTapDelayMs + 40);

    if (!previousTap || now - previousTap.time > editDoubleTapDelayMs) {
      return;
    }

    const distance = Math.hypot(
      event.clientX - previousTap.x,
      event.clientY - previousTap.y,
    );
    if (distance > editDoubleTapDistancePx) {
      return;
    }

    lastContentTap = null;
    startEditFromContent(event, { allowSelection: true });
  }

  async function save(saveOptions = {}) {
    const { close = false } = saveOptions;
    if (saving.value || !options.saveDocument) {
      return false;
    }

    const savedDraftKeys = [draftKey(), ...legacyDraftKeys()].filter(Boolean);
    saving.value = true;
    try {
      const saved = await options.saveDocument({ ...saveOptions, close });
      if (saved === false) {
        return false;
      }
      setDirty(false);
      clearStoredDraftKeys(savedDraftKeys);
      options.afterSave?.({ close, result: saved });
      if (close) {
        leaveEdit();
      }
      return saved;
    } catch (error) {
      options.onSaveError?.(error);
      return false;
    } finally {
      saving.value = false;
    }
  }

  async function copy(kind = "default") {
    if (!options.copyDocument) {
      return false;
    }

    try {
      const payload = await options.copyDocument(kind);
      if (!payload) {
        return false;
      }
      if (payload.type === "markdown") {
        await writeMarkdownToClipboard(payload.content || "");
      } else if (payload.type === "html") {
        await writeHtmlToClipboard(
          payload.content || "",
          payload.plainText || "",
        );
      } else {
        await writePlainTextToClipboard(payload.content || "");
      }

      copied.value = true;
      window.clearTimeout(copiedTimer);
      copiedTimer = window.setTimeout(() => {
        copied.value = false;
      }, 1400);
      options.afterCopy?.({ kind, payload });
      return true;
    } catch (error) {
      options.onCopyError?.(error);
      return false;
    }
  }

  function keydownHandler(event) {
    const saveShortcut =
      (event.ctrlKey || event.metaKey) &&
      (event.key.toLowerCase() === "s" || event.key === "Enter");
    if (saveShortcut) {
      event.preventDefault();
      save({ close: false });
      return true;
    }

    if (event.key === "Escape") {
      options.requestClose?.();
      return true;
    }
    return false;
  }

  function beforeUnloadHandler(event) {
    if (!dirty.value) {
      return;
    }
    event.preventDefault();
    event.returnValue = "";
  }

  window.addEventListener("beforeunload", beforeUnloadHandler);
  onBeforeUnmount(() => {
    window.removeEventListener("beforeunload", beforeUnloadHandler);
    window.clearTimeout(copiedTimer);
  });

  return {
    editMode,
    dirty,
    saving,
    copied,
    clearDraft,
    contentDblClickHandler,
    contentPointerUpHandler,
    copy,
    enterEdit,
    keydownHandler,
    leaveEdit,
    loadDraft,
    requestEdit,
    save,
    saveDraft,
    setDirty,
  };
}
