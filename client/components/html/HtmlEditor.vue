<template>
  <div class="lamanotes-html-editor">
    <div class="lamanotes-html-editor-toolbar">
      <NoteKindSwitch
        v-if="showKindSwitch"
        :current-kind="currentKind"
        @set-kind="setKind"
      />
      <div class="lamanotes-html-editor-toolbar-group">
        <span class="lamanotes-html-editor-label">HTML</span>
        <select
          v-model="selectedSnippet"
          class="lamanotes-html-editor-select"
          aria-label="HTML component"
        >
          <option
            v-for="snippet in htmlComponentSnippets"
            :key="snippet.id"
            :value="snippet.id"
          >
            {{ snippet.label }}
          </option>
        </select>
        <button type="button" @click="insertSelectedSnippet">Insert</button>
      </div>
      <div class="lamanotes-html-editor-toolbar-group">
        <button type="button" @click="chooseImage">Media</button>
      </div>
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        class="hidden"
        @change="imageChosen"
      />
    </div>
    <textarea
      ref="textarea"
      v-model="content"
      class="lamanotes-html-editor-source"
      rows="1"
      spellcheck="false"
      @input="contentInputHandler"
      @keydown="keydownHandler"
      @paste="pasteHandler"
      @drop="dropHandler"
      @dragover.prevent
    ></textarea>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from "vue";

import NoteKindSwitch from "../NoteKindSwitch.vue";
import {
  createCodeBlockSnippet,
  createLinkCardSnippet,
  createMediaFigureSnippet,
  getHtmlSnippet,
  htmlComponentSnippets,
} from "./componentKit.js";
import {
  classifyPastedText,
  getClipboardImageFile,
} from "../paste/mediaPaste.js";

const props = defineProps({
  currentKind: {
    type: String,
    default: "research",
  },
  initialValue: String,
  addImageBlobHook: Function,
  showKindSwitch: Boolean,
});

const emit = defineEmits(["change", "keydown", "ready", "set-kind"]);

const content = ref(props.initialValue || "");
const fileInput = ref();
const selectedSnippet = ref(htmlComponentSnippets[0]?.id || "");
const textarea = ref();
let lastTagNormalizationUndo = null;

const htmlTagTokenPattern = /(^|[ \t])#([a-zA-Z0-9][a-zA-Z0-9_-]*)([ \t]?)/g;
const htmlBottomTagParagraphPattern =
  /^\s*<p>\s*(#[a-zA-Z0-9][a-zA-Z0-9_-]*(?:\s+#[a-zA-Z0-9][a-zA-Z0-9_-]*)*)\s*<\/p>\s*$/i;

function chooseImage() {
  fileInput.value?.click();
}

function setKind(kind) {
  emit("set-kind", kind);
}

function getSelectionText() {
  const element = textarea.value;
  if (!element) {
    return "";
  }

  return content.value.slice(element.selectionStart, element.selectionEnd);
}

function insertAtCursor(snippet) {
  const element = textarea.value;
  if (!element) {
    content.value += snippet;
    emit("change");
    nextTick(resizeTextarea);
    return;
  }

  const start = element.selectionStart;
  const end = element.selectionEnd;
  content.value = `${content.value.slice(0, start)}${snippet}${content.value.slice(end)}`;

  requestAnimationFrame(() => {
    const nextPosition = start + snippet.length;
    resizeTextarea();
    element.focus();
    element.setSelectionRange(nextPosition, nextPosition);
  });
  emit("change");
}

function resizeTextarea() {
  const element = textarea.value;
  if (!element) {
    return;
  }

  element.style.height = "auto";
  element.style.height = `${element.scrollHeight}px`;
}

function normalizeTagName(tag = "") {
  return tag.replace(/^#/, "").trim().toLowerCase();
}

function sortTags(tags = []) {
  return [...tags].sort((left, right) => left.localeCompare(right));
}

function collectTagsFromText(value = "", addTag) {
  [...String(value).matchAll(/#[a-zA-Z0-9][a-zA-Z0-9_-]*/g)].forEach((match) =>
    addTag(match[0]),
  );
}

function removeInlineTagsFromHtmlLine(line, addTag) {
  let removed = false;
  const cleanedLine = line.replace(
    htmlTagTokenPattern,
    (match, prefix, tag) => {
      addTag(tag);
      removed = true;
      return prefix;
    },
  );

  return { line: cleanedLine, removed };
}

function insertBeforeLastClosingTag(markup, insertion, tagName) {
  const closingTag = `</${tagName}>`;
  const index = markup.toLowerCase().lastIndexOf(closingTag);
  if (index < 0) {
    return null;
  }

  return `${markup.slice(0, index).trimEnd()}\n${insertion}\n${markup.slice(index)}`;
}

function appendBottomTagParagraph(markup, tags) {
  if (!tags.length) {
    return markup;
  }

  const tagParagraph = `<p>${tags.map((tag) => `#${tag}`).join(" ")}</p>`;
  return (
    insertBeforeLastClosingTag(markup, tagParagraph, "article") ||
    insertBeforeLastClosingTag(markup, tagParagraph, "body") ||
    insertBeforeLastClosingTag(markup, tagParagraph, "html") ||
    `${markup.trimEnd()}\n\n${tagParagraph}\n`
  );
}

function normalizeHtmlBottomTags(html = "") {
  const lines = String(html || "")
    .replace(/\r\n?/g, "\n")
    .split("\n");
  const bodyLines = [];
  const tags = new Set();
  let removedTag = false;

  const addTag = (tag) => {
    const normalizedTag = normalizeTagName(tag);
    if (normalizedTag) {
      tags.add(normalizedTag);
    }
  };

  for (const line of lines) {
    const bottomTagMatch = line.match(htmlBottomTagParagraphPattern);
    if (bottomTagMatch) {
      collectTagsFromText(bottomTagMatch[1], addTag);
      removedTag = true;
      continue;
    }

    const cleaned = removeInlineTagsFromHtmlLine(line, addTag);
    if (cleaned.removed) {
      removedTag = true;
    }
    bodyLines.push(cleaned.line);
  }

  const normalized = appendBottomTagParagraph(
    bodyLines.join("\n").trimEnd(),
    sortTags([...tags]),
  );

  return {
    changed: removedTag && normalized !== html,
    html: normalized,
  };
}

function contentHasTagsOutsideBottomParagraph(html = "") {
  return normalizeHtmlBottomTags(html).changed;
}

function cursorJustClosedTag(value, position) {
  const beforeCursor = value.slice(0, position);
  return /(^|[\s>])#[a-zA-Z0-9][a-zA-Z0-9_-]*\s+$/.test(beforeCursor);
}

function shouldNormalizeTags(event) {
  const element = event?.target;
  const value = element?.value || content.value;
  const position = element?.selectionStart ?? value.length;

  if (["insertFromPaste", "insertReplacementText"].includes(event?.inputType)) {
    return contentHasTagsOutsideBottomParagraph(value);
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

function normalizeEditorTags({ recordUndo = false } = {}) {
  const element = textarea.value;
  const selectionStart = element?.selectionStart ?? content.value.length;
  const selectionEnd = element?.selectionEnd ?? selectionStart;
  const before = content.value;
  const normalized = normalizeHtmlBottomTags(before);
  if (!normalized.changed || normalized.html === before) {
    return before;
  }

  if (recordUndo) {
    lastTagNormalizationUndo = {
      before,
      after: normalized.html,
      selectionStart,
      selectionEnd,
    };
  }

  content.value = normalized.html;
  nextTick(() => {
    resizeTextarea();
    const nextPosition = Math.min(selectionStart, content.value.length);
    element?.setSelectionRange(nextPosition, nextPosition);
  });

  return normalized.html;
}

function clearStaleTagUndo() {
  if (
    lastTagNormalizationUndo &&
    content.value !== lastTagNormalizationUndo.after
  ) {
    lastTagNormalizationUndo = null;
  }
}

function undoTagNormalization() {
  const undo = lastTagNormalizationUndo;
  if (!undo || content.value !== undo.after) {
    return false;
  }

  content.value = undo.before;
  lastTagNormalizationUndo = null;
  nextTick(() => {
    resizeTextarea();
    textarea.value?.focus();
    textarea.value?.setSelectionRange(undo.selectionStart, undo.selectionEnd);
  });
  emit("change");
  return true;
}

function contentInputHandler(event) {
  content.value = event.target.value;
  clearStaleTagUndo();
  if (shouldNormalizeTags(event)) {
    normalizeEditorTags({ recordUndo: true });
  }
  resizeTextarea();
  emit("change");
}

function insertSelectedSnippet() {
  const snippet = getHtmlSnippet(selectedSnippet.value, getSelectionText());
  if (snippet) {
    insertAtCursor(snippet);
  }
}

function insertImageFile(file) {
  if (!file || !props.addImageBlobHook) {
    return;
  }

  props.addImageBlobHook(file, (url, altText, metadata = {}) => {
    insertAtCursor(createMediaFigureSnippet(url, altText, metadata));
  });
}

function imageChosen(event) {
  const [file] = event.target.files || [];
  event.target.value = "";
  insertImageFile(file);
}

function getImageFiles(dataTransfer) {
  return [...(dataTransfer?.files || [])].filter((file) =>
    file.type?.startsWith("image/"),
  );
}

function insertClassifiedPaste(classification) {
  if (classification.type === "image-url") {
    insertAtCursor(createMediaFigureSnippet(classification.url, "Image"));
    return true;
  }

  if (classification.type === "url") {
    insertAtCursor(
      createLinkCardSnippet(classification.url, classification.label),
    );
    return true;
  }

  if (classification.type === "code") {
    insertAtCursor(
      createCodeBlockSnippet(classification.text, classification.language),
    );
    return true;
  }

  return false;
}

function pasteHandler(event) {
  const file = getClipboardImageFile(event.clipboardData);
  if (file) {
    event.preventDefault();
    insertImageFile(file);
    return;
  }

  const text = event.clipboardData?.getData("text/plain") || "";
  const classification = classifyPastedText(text);
  if (insertClassifiedPaste(classification)) {
    event.preventDefault();
  }
}

function dropHandler(event) {
  const [file] = getImageFiles(event.dataTransfer);
  if (!file) {
    return;
  }

  event.preventDefault();
  insertImageFile(file);
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

  emit("keydown", event);
}

function getContent() {
  return normalizeEditorTags();
}

function getSearchText() {
  return content.value;
}

function selectSearchRange(from, to) {
  const element = textarea.value;
  if (!element) {
    return;
  }
  const start = Math.max(0, Math.min(Number(from) || 0, content.value.length));
  const end = Math.max(
    start,
    Math.min(Number(to) || start, content.value.length),
  );
  element.setSelectionRange(start, end);
  const lineCount = content.value.slice(0, start).split("\n").length - 1;
  const styles = getComputedStyle(element);
  const lineHeight =
    Number.parseFloat(styles.lineHeight) ||
    Number.parseFloat(styles.fontSize) * 1.45;
  element.scrollTop = Math.max(
    0,
    lineCount * lineHeight - element.clientHeight / 2,
  );
}

function isWysiwygMode() {
  return false;
}

function focusEditor() {
  nextTick(() => textarea.value?.focus({ preventScroll: true }));
  return textarea.value;
}

onMounted(async () => {
  await nextTick();
  resizeTextarea();
  textarea.value?.focus();
  emit("ready");
});

defineExpose({
  focusEditor,
  getContent,
  getSearchText,
  isWysiwygMode,
  selectSearchRange,
});
</script>

<style lang="scss" scoped>
.lamanotes-html-editor {
  display: flex;
  min-height: 65vh;
  flex-direction: column;
  border: 1px solid rgb(var(--theme-border));
  border-radius: 6px;
  overflow: visible;
  background-color: rgb(var(--theme-background));
}

.lamanotes-html-editor-toolbar {
  display: flex;
  min-height: 1.82rem;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 0.28rem;
  padding: 0.16rem 0.5rem;
  border-bottom: 1px solid rgb(var(--theme-border));
  color: rgb(var(--theme-text-muted));
  background-color: rgb(var(--theme-background-elevated));
  font-size: 0.82rem;
  font-weight: 600;
}

.lamanotes-html-editor-toolbar-group {
  display: flex;
  align-items: center;
  gap: 0.32rem;
  min-width: 0;
}

.lamanotes-html-editor-label {
  flex: 0 0 auto;
}

.lamanotes-html-editor-select,
.lamanotes-html-editor-toolbar button {
  min-height: 1.42rem;
  border: 1px solid rgb(var(--theme-border));
  border-radius: 5px;
  padding: 0 0.45rem;
  color: rgb(var(--theme-text));
  background-color: rgb(var(--theme-background));
  font-size: 0.78rem;
  touch-action: manipulation;
}

.lamanotes-html-editor-select {
  min-width: min(11rem, 48vw);
  max-width: 100%;
  outline: none;
}

.lamanotes-html-editor-select:focus-visible,
.lamanotes-html-editor-toolbar button:hover,
.lamanotes-html-editor-toolbar button:focus-visible {
  border-color: rgb(var(--theme-brand));
}

.lamanotes-html-editor-source {
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

@media (max-width: 640px) and (pointer: coarse),
  (max-width: 640px) and (hover: none) {
  .lamanotes-html-editor-toolbar {
    min-height: 2.35rem;
    gap: 0.4rem;
    padding: 0.26rem;
  }

  .lamanotes-html-editor-toolbar-group {
    gap: 0.45rem;
  }

  .lamanotes-html-editor-select,
  .lamanotes-html-editor-toolbar button {
    min-height: 2rem;
    padding: 0 0.65rem;
  }
}
</style>
