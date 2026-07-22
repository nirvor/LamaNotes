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

    <SourceEditor
      v-show="!previewVisible"
      ref="sourceEditor"
      v-model="markdown"
      class="flatnotes-work-editor-source"
      language="markdown"
      :normalize-tags="true"
      :show-line-numbers="showLineNumbers"
      :add-image-blob-hook="addImageBlobHook"
      :transform-pasted-text="transformPastedText"
      aria-label="Edit work note"
      @change="contentChangedHandler"
      @keydown="keydownHandler"
      @ready="editorReadyHandler"
    />

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
import { computed, nextTick, ref, watch } from "vue";

import NoteKindSwitch from "../NoteKindSwitch.vue";
import SourceEditor from "../editor/SourceEditor.vue";
import { writeMarkdownToClipboard } from "../../clipboard.js";
import { classifyPastedText, markdownForPaste } from "../paste/mediaPaste.js";
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
  showLineNumbers: Boolean,
  showKindSwitch: Boolean,
});

const emit = defineEmits(["change", "keydown", "ready", "set-kind"]);

const copied = ref(false);
const markdown = ref(initialMarkdown());
const previewVisible = ref(false);
const sourceEditor = ref();

const previewKey = computed(() => `${previewVisible.value}-${markdown.value}`);

function initialMarkdown() {
  const raw = extractWorkMarkdown(props.initialValue || "");
  return raw.trim() ? raw : "";
}

function insertAtCursor(snippet, options = {}) {
  sourceEditor.value?.replaceSelection?.(snippet, options);
}

function insertCodeBlock() {
  const selectedText = sourceEditor.value?.getSelectedText?.() || "";
  insertAtCursor(`\n\`\`\`text\n${selectedText}\n\`\`\`\n`);
}

function insertChecklist() {
  insertAtCursor("\n- [ ] \n");
}

function selectedText() {
  return sourceEditor.value?.getSelectedText?.() || "";
}

function transformPastedText(text) {
  const snippet = markdownForPaste(classifyPastedText(text), selectedText());
  return snippet || null;
}

function setKind(kind) {
  emit("set-kind", kind);
}

async function togglePreview() {
  previewVisible.value = !previewVisible.value;
  if (!previewVisible.value) {
    await nextTick();
    sourceEditor.value?.focusEditor?.();
  }
}

function normalizedMarkdown() {
  return normalizeWorkMarkdownTags(markdown.value).markdown;
}

async function copyMarkdown() {
  try {
    await writeMarkdownToClipboard(normalizedMarkdown());
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 1400);
  } catch {
    copied.value = false;
  }
}

function contentChangedHandler() {
  emit("change");
}

function keydownHandler(event) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "b") {
    event.preventDefault();
    const selected = selectedText();
    const snippet = `**${selected}**`;
    insertAtCursor(snippet, {
      anchorOffset: 2,
      headOffset: 2 + selected.length,
    });
    return;
  }

  emit("keydown", event);
}

function getMarkdown() {
  return normalizedMarkdown();
}

function getSearchText() {
  return markdown.value;
}

function selectSearchRange(from, to) {
  sourceEditor.value?.selectSearchRange?.(from, to);
}

function setSearchMatches(matches, currentIndex) {
  sourceEditor.value?.setSearchMatches?.(matches, currentIndex);
}

function getContent(title) {
  return buildWorkNoteHtml(
    title || props.noteTitle || "Untitled",
    normalizedMarkdown(),
  );
}

function focusEditor() {
  previewVisible.value = false;
  nextTick(() => sourceEditor.value?.focusEditor?.());
  return sourceEditor.value?.focusEditor?.();
}

watch(
  () => props.initialValue,
  () => {
    markdown.value = initialMarkdown();
  },
);

function editorReadyHandler() {
  sourceEditor.value?.focusEditor?.();
  emit("ready");
}

defineExpose({
  focusEditor,
  getContent,
  getMarkdown,
  getSearchText,
  selectSearchRange,
  setSearchMatches,
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
  border: 0;
}

.flatnotes-work-editor-source :deep(.cm-editor),
.flatnotes-work-editor-source :deep(.cm-scroller),
.flatnotes-work-editor-source :deep(.cm-content) {
  min-height: 65vh;
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
