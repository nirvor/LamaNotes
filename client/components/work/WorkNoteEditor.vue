<template>
  <div class="flatnotes-work-editor">
    <div class="flatnotes-work-editor-toolbar" aria-label="Work note tools">
      <NoteKindSwitch
        v-if="showKindSwitch"
        :current-kind="currentKind"
        @set-kind="setKind"
      />
      <button
        type="button"
        class="flatnotes-work-icon-button"
        title="Insert code block"
        aria-label="Insert code block"
        @click="insertCodeBlock"
      >
        <SvgIcon type="mdi" :path="mdiCodeTags" size="0.84rem" />
      </button>
      <button
        type="button"
        class="flatnotes-work-icon-button"
        title="Insert checklist item"
        aria-label="Insert checklist item"
        @click="insertChecklist"
      >
        <SvgIcon type="mdi" :path="mdiFormatListChecks" size="0.84rem" />
      </button>
      <button
        type="button"
        class="flatnotes-work-icon-button"
        :class="{ 'flatnotes-work-icon-button-active': previewVisible }"
        :title="previewVisible ? 'Hide preview' : 'Show preview'"
        :aria-label="previewVisible ? 'Hide preview' : 'Show preview'"
        :aria-pressed="previewVisible"
        @click="togglePreview"
      >
        <SvgIcon
          type="mdi"
          :path="previewVisible ? mdiEyeOffOutline : mdiEyeOutline"
          size="0.84rem"
        />
      </button>
      <button
        type="button"
        class="flatnotes-work-icon-button flatnotes-work-copy-button"
        :class="{ 'flatnotes-work-icon-button-active': copied }"
        :title="copied ? 'Copied' : 'Copy markdown'"
        :aria-label="copied ? 'Copied' : 'Copy markdown'"
        @click="copyMarkdown"
      >
        <SvgIcon
          type="mdi"
          :path="copied ? mdiCheck : mdiContentCopy"
          size="0.84rem"
        />
      </button>
    </div>

    <textarea
      v-show="!previewVisible"
      ref="textarea"
      v-model="markdown"
      class="flatnotes-work-editor-source"
      rows="1"
      spellcheck="false"
      @input="contentInputHandler"
      @keydown="keydownHandler"
      @paste="pasteHandler"
    ></textarea>

    <div v-if="previewVisible" class="flatnotes-work-editor-preview">
      <ToastViewer
        :key="previewKey"
        :initialValue="markdown"
        :enhance-note-lead="false"
        :note-title="noteTitle"
        :task-checkboxes-disabled="true"
      />
    </div>
  </div>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import {
  mdiCheck,
  mdiCodeTags,
  mdiContentCopy,
  mdiEyeOffOutline,
  mdiEyeOutline,
  mdiFormatListChecks,
} from "@mdi/js";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

import NoteKindSwitch from "../NoteKindSwitch.vue";
import { writeMarkdownToClipboard } from "../../clipboard.js";
import {
  classifyPastedText,
  getClipboardImageFile,
  markdownForPaste,
  markdownImageSnippet,
} from "../paste/mediaPaste.js";
import ToastViewer from "../toastui/ToastViewer.vue";
import {
  buildWorkNoteHtml,
  extractWorkMarkdown,
  normalizeWorkMarkdownTags,
} from "./workNote.js";

const props = defineProps({
  currentKind: {
    type: String,
    default: "work",
  },
  initialValue: String,
  noteTitle: String,
  addImageBlobHook: Function,
  showKindSwitch: Boolean,
});

const emit = defineEmits(["change", "keydown", "ready", "set-kind"]);

const copied = ref(false);
const markdown = ref(initialMarkdown());
const previewVisible = ref(false);
const textarea = ref();
let tagNormalizeTimeout = null;
let lastTagNormalizationUndo = null;

const previewKey = computed(() => `${previewVisible.value}-${markdown.value}`);

function initialMarkdown() {
  const raw = extractWorkMarkdown(props.initialValue || "");
  return raw.trim() ? raw : "";
}

function resizeTextarea() {
  const element = textarea.value;
  if (!element) {
    return;
  }

  element.style.height = "auto";
  element.style.height = `${element.scrollHeight}px`;
}

function selectedRange() {
  const element = textarea.value;
  if (!element) {
    return { start: markdown.value.length, end: markdown.value.length };
  }

  return {
    start: element.selectionStart,
    end: element.selectionEnd,
  };
}

function insertAtCursor(snippet) {
  const element = textarea.value;
  const { start, end } = selectedRange();
  markdown.value = `${markdown.value.slice(0, start)}${snippet}${markdown.value.slice(end)}`;
  requestAnimationFrame(() => {
    resizeTextarea();
    const nextPosition = start + snippet.length;
    element?.focus();
    element?.setSelectionRange(nextPosition, nextPosition);
  });
  emit("change");
}

function insertCodeBlock() {
  const { start, end } = selectedRange();
  const selectedText = markdown.value.slice(start, end);
  insertAtCursor(`\n\`\`\`text\n${selectedText}\n\`\`\`\n`);
}

function insertChecklist() {
  insertAtCursor("\n- [ ] \n");
}

function selectedText() {
  const { start, end } = selectedRange();
  return markdown.value.slice(start, end);
}

function insertImageFile(file) {
  if (!file || !props.addImageBlobHook) {
    return false;
  }

  props.addImageBlobHook(file, (url, altText) => {
    insertAtCursor(markdownImageSnippet(url, altText));
  });
  return true;
}

function pasteHandler(event) {
  const file = getClipboardImageFile(event.clipboardData);
  if (file && insertImageFile(file)) {
    event.preventDefault();
    return;
  }

  const text = event.clipboardData?.getData("text/plain") || "";
  const snippet = markdownForPaste(classifyPastedText(text), selectedText());
  if (!snippet) {
    return;
  }

  event.preventDefault();
  insertAtCursor(snippet);
}

function setKind(kind) {
  emit("set-kind", kind);
}

async function togglePreview() {
  previewVisible.value = !previewVisible.value;
  if (!previewVisible.value) {
    await nextTick();
    resizeTextarea();
    textarea.value?.focus();
  }
}

function cursorIsInCodeFence(value, position) {
  const beforeCursor = value.slice(0, position);
  return (beforeCursor.match(/```/g) || []).length % 2 === 1;
}

function textContainsTag(value) {
  return /(^|\s)#[a-zA-Z0-9][a-zA-Z0-9_-]*(?=\s|$)/.test(value);
}

function cursorJustClosedTag(value, position) {
  const beforeCursor = value.slice(0, position);
  return /(^|\s)#[a-zA-Z0-9][a-zA-Z0-9_-]*\s+$/.test(beforeCursor);
}

function shouldNormalizeTags(event) {
  const element = event?.target;
  const value = element?.value || markdown.value;
  const position = element?.selectionStart ?? value.length;
  if (cursorIsInCodeFence(value, position)) {
    return false;
  }

  if (["insertFromPaste", "insertReplacementText"].includes(event?.inputType)) {
    return textContainsTag(value);
  }

  if (
    event?.data === " " ||
    event?.data === "\n" ||
    ["insertLineBreak", "insertParagraph"].includes(event?.inputType)
  ) {
    return cursorJustClosedTag(value, position);
  }

  return false;
}

function clearTagNormalizeTimeout() {
  if (tagNormalizeTimeout != null) {
    window.clearTimeout(tagNormalizeTimeout);
    tagNormalizeTimeout = null;
  }
}

function clearStaleTagUndo() {
  if (
    lastTagNormalizationUndo &&
    markdown.value !== lastTagNormalizationUndo.after
  ) {
    lastTagNormalizationUndo = null;
  }
}

function mapCursorAfterTagNormalization(value, position) {
  const tagPattern = /(^|[ \t])#([a-zA-Z0-9][a-zA-Z0-9_-]*)([ \t]?)/g;
  const tagOnlyLinePattern = /^\s*(?:#[a-zA-Z0-9][a-zA-Z0-9_-]*\s*)+$/;
  const lines = value.slice(0, position).split("\n");
  let inCodeFence = false;
  const mappedLines = [];

  for (const line of lines) {
    const trimmed = line.trim();
    const fenceLine = trimmed.startsWith("```");
    if (fenceLine) {
      mappedLines.push(line);
      inCodeFence = !inCodeFence;
      continue;
    }

    if (inCodeFence) {
      mappedLines.push(line);
      continue;
    }

    if (tagOnlyLinePattern.test(line)) {
      continue;
    }

    mappedLines.push(
      line.replace(tagPattern, (match, prefix) => {
        return prefix;
      }),
    );
  }

  return mappedLines.join("\n").length;
}

function normalizeEditorTags({
  restoreSelection = true,
  recordUndo = false,
} = {}) {
  const element = textarea.value;
  const selectionStart = element?.selectionStart ?? markdown.value.length;
  const selectionEnd = element?.selectionEnd ?? selectionStart;
  const before = markdown.value;
  const normalized = normalizeWorkMarkdownTags(before);
  if (!normalized.changed || normalized.markdown === markdown.value) {
    return normalized.markdown;
  }

  if (recordUndo) {
    lastTagNormalizationUndo = {
      before,
      after: normalized.markdown,
      selectionStart,
      selectionEnd,
    };
  }

  markdown.value = normalized.markdown;
  nextTick(() => {
    resizeTextarea();
    if (restoreSelection && element) {
      const nextStart = Math.min(
        mapCursorAfterTagNormalization(before, selectionStart),
        markdown.value.length,
      );
      const nextEnd = Math.min(
        mapCursorAfterTagNormalization(before, selectionEnd),
        markdown.value.length,
      );
      element.setSelectionRange(nextStart, nextEnd);
    }
  });

  return normalized.markdown;
}

function undoTagNormalization() {
  const undo = lastTagNormalizationUndo;
  if (!undo || markdown.value !== undo.after) {
    return false;
  }

  markdown.value = undo.before;
  lastTagNormalizationUndo = null;
  nextTick(() => {
    resizeTextarea();
    textarea.value?.focus();
    textarea.value?.setSelectionRange(undo.selectionStart, undo.selectionEnd);
  });
  emit("change");
  return true;
}

async function copyMarkdown() {
  try {
    const normalizedMarkdown = normalizeEditorTags();
    await writeMarkdownToClipboard(normalizedMarkdown);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 1400);
  } catch {
    copied.value = false;
  }
}

function contentInputHandler(event) {
  markdown.value = event.target.value;
  clearStaleTagUndo();
  if (shouldNormalizeTags(event)) {
    clearTagNormalizeTimeout();
    normalizeEditorTags({ recordUndo: true });
  }
  resizeTextarea();
  emit("change");
}

function keydownHandler(event) {
  if (
    (event.ctrlKey || event.metaKey) &&
    event.key.toLowerCase() === "z" &&
    !event.shiftKey &&
    undoTagNormalization()
  ) {
    event.preventDefault();
    return;
  }

  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "b") {
    event.preventDefault();
    insertAtCursor("****");
    const element = textarea.value;
    const position = selectedRange().start - 2;
    requestAnimationFrame(() => element?.setSelectionRange(position, position));
    return;
  }

  emit("keydown", event);
}

function getMarkdown() {
  return normalizeEditorTags({ restoreSelection: false });
}

function getSearchText() {
  return markdown.value;
}

function selectSearchRange(from, to) {
  const element = textarea.value;
  if (!element) {
    return;
  }
  const start = Math.max(0, Math.min(Number(from) || 0, markdown.value.length));
  const end = Math.max(
    start,
    Math.min(Number(to) || start, markdown.value.length),
  );
  element.setSelectionRange(start, end);
  const lineCount = markdown.value.slice(0, start).split("\n").length - 1;
  const styles = getComputedStyle(element);
  const lineHeight =
    Number.parseFloat(styles.lineHeight) ||
    Number.parseFloat(styles.fontSize) * 1.45;
  element.scrollTop = Math.max(
    0,
    lineCount * lineHeight - element.clientHeight / 2,
  );
}

function getContent(title) {
  return buildWorkNoteHtml(
    title || props.noteTitle || "Untitled",
    normalizeEditorTags({ restoreSelection: false }),
  );
}

function focusEditor() {
  previewVisible.value = false;
  nextTick(() => textarea.value?.focus({ preventScroll: true }));
  return textarea.value;
}

watch(
  () => props.initialValue,
  async () => {
    markdown.value = initialMarkdown();
    await nextTick();
    resizeTextarea();
  },
);

onMounted(async () => {
  await nextTick();
  resizeTextarea();
  textarea.value?.focus();
  emit("ready");
});

onBeforeUnmount(clearTagNormalizeTimeout);

defineExpose({
  focusEditor,
  getContent,
  getMarkdown,
  getSearchText,
  selectSearchRange,
});
</script>

<style lang="scss" scoped>
.flatnotes-work-editor {
  display: flex;
  min-height: 65vh;
  flex-direction: column;
  border: 1px solid rgb(var(--theme-border));
  border-radius: 6px;
  overflow: visible;
  background-color: rgb(var(--theme-background));
}

.flatnotes-work-editor-toolbar {
  display: flex;
  min-height: 1.42rem;
  align-items: center;
  justify-content: flex-start;
  gap: 0.14rem;
  padding: 0.06rem 0.2rem;
  border-bottom: 1px solid rgb(var(--theme-border));
  color: rgb(var(--theme-text-muted));
  background-color: rgb(var(--theme-background-elevated));
}

.flatnotes-work-icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.48rem;
  height: 1.34rem;
  border: 1px solid rgb(var(--theme-border));
  border-radius: 5px;
  padding: 0;
  color: rgb(var(--theme-text));
  background-color: rgb(var(--theme-background));
  touch-action: manipulation;
}

.flatnotes-work-copy-button {
  margin-left: auto;
}

.flatnotes-work-icon-button:hover,
.flatnotes-work-icon-button:focus-visible,
.flatnotes-work-icon-button-active {
  border-color: rgb(var(--theme-brand));
  color: rgb(var(--theme-brand));
  background-color: rgb(var(--theme-background-elevated));
}

.flatnotes-work-editor-source {
  min-height: 65vh;
  flex: 0 0 auto;
  resize: none;
  overflow-y: hidden;
  padding: 0.68rem 0.82rem;
  border: 0;
  color: rgb(var(--theme-text));
  background-color: rgb(var(--theme-background));
  font-family: Consolas, "Lucida Console", Monaco, "Andale Mono", monospace;
  font-size: 0.9rem;
  line-height: 1.45;
  outline: none;
  tab-size: 2;
}

.flatnotes-work-editor-preview {
  min-height: 65vh;
  padding: 1.05rem 1.2rem;
  background-color: rgb(var(--theme-background));
}

@media (max-width: 640px) and (pointer: coarse),
  (max-width: 640px) and (hover: none) {
  .flatnotes-work-editor-toolbar {
    gap: 0.22rem;
    min-height: 2.35rem;
    padding: 0.26rem;
  }

  .flatnotes-work-icon-button {
    width: 2rem;
    height: 2rem;
  }
}
</style>
