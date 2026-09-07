<template>
  <div class="lamanotes-html-editor">
    <SourceEditor
      v-show="!previewVisible"
      ref="sourceEditor"
      v-model="content"
      language="html"
      :session-state="sessionState"
      :add-image-blob-hook="addImageBlobHook"
      :transform-pasted-text="transformPastedText"
      aria-label="Edit HTML note"
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
        <button
          type="button"
          class="lamanotes-format-button"
          title="Insert selected component"
          aria-label="Insert selected component"
          @click="insertSelectedSnippet"
        >
          <SvgIcon type="mdi" :path="mdiPlus" size="0.92rem" />
        </button>
        <button
          type="button"
          class="lamanotes-format-button"
          title="Insert media"
          aria-label="Insert media"
          @click="fileInput?.click()"
        >
          <SvgIcon type="mdi" :path="mdiImageOutline" size="0.92rem" />
        </button>
        <button
          type="button"
          class="lamanotes-format-button"
          title="Show note preview"
          aria-label="Show note preview"
          @click="togglePreview"
        >
          <SvgIcon type="mdi" :path="mdiEyeOutline" size="0.92rem" />
        </button>
      </template>
    </SourceEditor>
    <div
      v-if="placeholderWarnings.length"
      class="lamanotes-html-editor-quality-warning"
      role="status"
      :title="placeholderWarningTitle"
    >
      <SvgIcon type="mdi" :path="mdiAlertOutline" size="0.88rem" /><span
        >Template placeholders ({{ placeholderWarnings.length }})</span
      >
    </div>
    <input
      ref="fileInput"
      type="file"
      accept="image/*"
      class="hidden"
      @change="imageChosen"
    />
    <div
      v-if="previewVisible"
      class="lamanotes-html-editor-preview"
      role="region"
      aria-label="HTML note preview"
    >
      <div class="lamanotes-format-toolbar">
        <button
          type="button"
          class="lamanotes-format-button"
          title="Show HTML source"
          aria-label="Show HTML source"
          @click="togglePreview"
        >
          <SvgIcon type="mdi" :path="mdiCodeTags" size="0.92rem" />
        </button>
      </div>
      <HtmlViewer
        :initial-value="content"
        :note-title="noteTitle"
        :task-checkboxes-disabled="true"
      />
    </div>
  </div>
</template>
<script setup>
import { computed, nextTick, ref, watch } from "vue";
import SvgIcon from "@jamescoyle/vue-icon";
import {
  mdiAlertOutline,
  mdiCodeTags,
  mdiEyeOutline,
  mdiImageOutline,
  mdiPlus,
} from "@mdi/js";
import SourceEditor from "../editor/SourceEditor.vue";
import NoteKindSwitch from "../NoteKindSwitch.vue";
import HtmlViewer from "./HtmlViewer.vue";
import {
  createCodeBlockSnippet,
  createLinkCardSnippet,
  createMediaFigureSnippet,
  findHtmlPlaceholderWarnings,
  getHtmlSnippet,
  htmlComponentSnippets,
} from "./componentKit.js";
import { classifyPastedText } from "../paste/mediaPaste.js";
const props = defineProps({
  currentKind: { type: String, default: "article" },
  initialValue: String,
  noteTitle: String,
  addImageBlobHook: Function,
  showKindSwitch: Boolean,
  sessionState: Object,
});
defineEmits(["change", "keydown", "ready", "set-kind"]);
const content = ref(props.initialValue || "");
const sourceEditor = ref();
const fileInput = ref();
const previewVisible = ref(false);
const selectedSnippet = ref(htmlComponentSnippets[0]?.id || "");
const placeholderWarnings = computed(() =>
  findHtmlPlaceholderWarnings(content.value),
);
const placeholderWarningTitle = computed(
  () =>
    "Review before publishing: " +
    placeholderWarnings.value.map(({ label }) => label).join(", "),
);
watch(
  () => props.initialValue,
  (value) => {
    content.value = value || "";
  },
);
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
function insertSelectedSnippet() {
  const snippet = getHtmlSnippet(
    selectedSnippet.value,
    sourceEditor.value?.getSelectedText() || "",
  );
  if (snippet) sourceEditor.value?.replaceSelection(snippet);
}
function transformPastedText(text) {
  const paste = classifyPastedText(text);
  if (paste.type === "image-url")
    return createMediaFigureSnippet(paste.url, "Image");
  if (paste.type === "url")
    return createLinkCardSnippet(paste.url, paste.label);
  if (paste.type === "code")
    return createCodeBlockSnippet(paste.text, paste.language);
  return null;
}
function imageChosen(event) {
  const file = event.target.files?.[0];
  if (file && props.addImageBlobHook)
    props.addImageBlobHook(file, (url, alt, metadata = {}) =>
      sourceEditor.value?.replaceSelection(
        createMediaFigureSnippet(url, alt || file.name, metadata),
      ),
    );
  event.target.value = "";
}
defineExpose({
  focusEditor,
  getContent: () => content.value,
  getSearchText: () => content.value,
  selectSearchRange: (...args) =>
    sourceEditor.value?.selectSearchRange(...args),
  setSearchMatches: (...args) => sourceEditor.value?.setSearchMatches(...args),
  replaceContent: (...args) => sourceEditor.value?.replaceContent(...args),
  isWysiwygMode: () => false,
});
</script>
<style scoped>
.lamanotes-html-editor-select {
  min-width: 0;
  max-width: 9rem;
  padding: 0.15rem;
  border: 1px solid rgb(var(--theme-border));
  border-radius: var(--ln-radius-control);
  background: rgb(var(--theme-background));
  font-size: 0.75rem;
}
.lamanotes-html-editor-quality-warning {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem;
  color: rgb(var(--theme-warning));
  font-size: 0.75rem;
}
</style>
