<template>
  <div class="lamanotes-work-editor">
    <SourceEditor
      v-show="!previewVisible"
      ref="sourceEditor"
      v-model="markdown"
      language="markdown"
      :normalize-tags="true"
      :show-line-numbers="showLineNumbers"
      :session-state="sessionState"
      :add-image-blob-hook="addImageBlobHook"
      :transform-pasted-text="transformPastedText"
      :structured-paste="true"
      aria-label="Edit work note"
      @change="$emit('change')"
      @keydown="$emit('keydown', $event)"
      @ready="$emit('ready')"
    >
      <template #tools>
        <NoteKindSwitch
          v-if="showKindSwitch"
          :current-kind="currentKind"
          @set-kind="$emit('set-kind', $event)"
        />
        <button
          type="button"
          class="lamanotes-format-button"
          title="Show preview"
          aria-label="Show preview"
          @click="togglePreview"
        >
          <SvgIcon type="mdi" :path="mdiEyeOutline" size="0.92rem" />
        </button>
        <button
          type="button"
          class="lamanotes-format-button"
          :title="copied ? 'Copied' : 'Copy markdown'"
          :aria-label="copied ? 'Copied' : 'Copy markdown'"
          @click="copyMarkdown"
        >
          <SvgIcon
            type="mdi"
            :path="copied ? mdiCheck : mdiContentCopy"
            size="0.92rem"
          />
        </button>
      </template>
    </SourceEditor>
    <div v-if="previewVisible" class="lamanotes-work-editor-preview">
      <div class="lamanotes-format-toolbar">
        <button
          type="button"
          class="lamanotes-format-button"
          title="Back to writing"
          aria-label="Back to writing"
          @click="togglePreview"
        >
          <SvgIcon type="mdi" :path="mdiPencilOutline" size="0.92rem" />
        </button>
      </div>
      <ToastViewer
        :initialValue="markdown"
        :enhance-note-lead="false"
        :note-title="noteTitle"
        :task-checkboxes-disabled="true"
      />
    </div>
  </div>
</template>
<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import SvgIcon from "@jamescoyle/vue-icon";
import {
  mdiCheck,
  mdiContentCopy,
  mdiEyeOutline,
  mdiPencilOutline,
} from "@mdi/js";
import SourceEditor from "../editor/SourceEditor.vue";
import NoteKindSwitch from "../NoteKindSwitch.vue";
import ToastViewer from "../toastui/ToastViewer.vue";
import {
  buildWorkNoteHtml,
  extractWorkMarkdown,
  normalizeWorkMarkdownTags,
} from "./workNote.js";
import { classifyPastedText, markdownForPaste } from "../paste/mediaPaste.js";
import { writeMarkdownToClipboard } from "../../clipboard.js";

const props = defineProps({
  currentKind: { type: String, default: "work" },
  initialValue: String,
  noteTitle: String,
  addImageBlobHook: Function,
  showLineNumbers: Boolean,
  showKindSwitch: Boolean,
  sessionState: Object,
});
defineEmits(["change", "keydown", "ready", "set-kind"]);
const markdown = ref(extractWorkMarkdown(props.initialValue || ""));
const sourceEditor = ref();
const previewVisible = ref(false);
const copied = ref(false);
let copyTimer;
watch(
  () => props.initialValue,
  (value) => {
    markdown.value = extractWorkMarkdown(value || "");
  },
);
function getMarkdown() {
  return normalizeWorkMarkdownTags(markdown.value).markdown;
}
function transformPastedText(text) {
  return (
    markdownForPaste(
      classifyPastedText(text),
      sourceEditor.value?.getSelectedText?.() || "",
    ) || null
  );
}
async function togglePreview() {
  previewVisible.value = !previewVisible.value;
  if (!previewVisible.value) {
    await nextTick();
    sourceEditor.value?.focusEditor();
  }
}
function focusEditor() {
  previewVisible.value = false;
  nextTick(() => sourceEditor.value?.focusEditor());
  return sourceEditor.value?.focusEditor();
}
async function copyMarkdown() {
  try {
    await writeMarkdownToClipboard(getMarkdown());
    copied.value = true;
    clearTimeout(copyTimer);
    copyTimer = setTimeout(() => {
      copied.value = false;
    }, 1400);
  } catch {
    copied.value = false;
  }
}
onBeforeUnmount(() => clearTimeout(copyTimer));
defineExpose({
  focusEditor,
  getMarkdown,
  getContent: (title) =>
    buildWorkNoteHtml(title || props.noteTitle || "Untitled", getMarkdown()),
  getSearchText: () => markdown.value,
  selectSearchRange: (...args) =>
    sourceEditor.value?.selectSearchRange(...args),
  setSearchMatches: (...args) => sourceEditor.value?.setSearchMatches(...args),
  replaceContent: (...args) => sourceEditor.value?.replaceContent(...args),
});
</script>
