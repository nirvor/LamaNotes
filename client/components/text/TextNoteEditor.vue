<template>
  <SourceEditor
    ref="sourceEditor"
    v-model="markdown"
    language="markdown"
    prose
    :session-state="sessionState"
    :structured-paste="true"
    :hide-share-anchors="true"
    :aria-label="`Edit ${noteTitle || 'note'}`"
    :add-image-blob-hook="addImageBlobHook"
    @change="$emit('change')"
    @keydown="$emit('keydown', $event)"
    @ready="$emit('ready')"
  />
</template>

<script setup>
import { ref, watch } from "vue";
import SourceEditor from "../editor/SourceEditor.vue";
import { normalizeTextMarkdown } from "./textNote.js";

const props = defineProps({
  initialValue: String,
  noteTitle: String,
  sessionState: Object,
  addImageBlobHook: Function,
});
defineEmits(["change", "keydown", "ready"]);
const sourceEditor = ref();
const markdown = ref(normalizeTextMarkdown(props.initialValue));
watch(
  () => props.initialValue,
  (value) => {
    markdown.value = normalizeTextMarkdown(value);
  },
);
defineExpose({
  getMarkdown: () => normalizeTextMarkdown(markdown.value),
  getSearchText: () => markdown.value,
  focusEditor: (...args) => sourceEditor.value?.focusEditor(...args),
  selectSearchRange: (...args) =>
    sourceEditor.value?.selectSearchRange(...args),
  setSearchMatches: (...args) => sourceEditor.value?.setSearchMatches(...args),
  replaceContent: (...args) => sourceEditor.value?.replaceContent(...args),
});
</script>
