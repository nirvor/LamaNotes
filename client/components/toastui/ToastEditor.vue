<template>
  <div ref="editorElement"></div>
</template>

<script setup>
import Editor from "@toast-ui/editor";
import { onBeforeUnmount, onMounted, ref } from "vue";

import baseOptions from "./baseOptions.js";
import {
  hasMovableWorkMarkdownTags,
  normalizeWorkMarkdownTags,
} from "../work/workNote.js";

const props = defineProps({
  initialValue: String,
  initialEditType: {
    type: String,
    default: "markdown",
  },
  addImageBlobHook: Function,
});

const emit = defineEmits(["change", "keydown"]);

const editorElement = ref();
let toastEditor;
let tagNormalizeTimeout = null;
let applyingTagNormalization = false;
let lastTagNormalizationUndo = null;

function clearTagNormalizeTimeout() {
  if (tagNormalizeTimeout != null) {
    window.clearTimeout(tagNormalizeTimeout);
    tagNormalizeTimeout = null;
  }
}

function markdownContainsTag(markdown = "") {
  return hasMovableWorkMarkdownTags(markdown);
}

function normalizeMarkdownTagsLive() {
  if (
    !toastEditor ||
    applyingTagNormalization ||
    !toastEditor.isMarkdownMode()
  ) {
    return;
  }

  const markdown = toastEditor.getMarkdown();
  if (!markdownContainsTag(markdown)) {
    return;
  }

  const normalized = normalizeWorkMarkdownTags(markdown);
  if (!normalized.changed || normalized.markdown === markdown) {
    return;
  }

  lastTagNormalizationUndo = {
    before: markdown,
    after: normalized.markdown,
  };
  applyingTagNormalization = true;
  toastEditor.setMarkdown(normalized.markdown, false);
  window.setTimeout(() => {
    applyingTagNormalization = false;
  }, 0);
}

function scheduleTagNormalization() {
  clearTagNormalizeTimeout();
  if (!toastEditor || !toastEditor.isMarkdownMode()) {
    return;
  }

  tagNormalizeTimeout = window.setTimeout(normalizeMarkdownTagsLive, 320);
}

function undoTagNormalization() {
  if (!toastEditor || !lastTagNormalizationUndo) {
    return false;
  }

  const currentMarkdown = toastEditor.getMarkdown();
  if (currentMarkdown !== lastTagNormalizationUndo.after) {
    lastTagNormalizationUndo = null;
    return false;
  }

  applyingTagNormalization = true;
  toastEditor.setMarkdown(lastTagNormalizationUndo.before, false);
  lastTagNormalizationUndo = null;
  window.setTimeout(() => {
    applyingTagNormalization = false;
  }, 0);
  emit("change");
  return true;
}

onMounted(() => {
  toastEditor = new Editor({
    ...baseOptions,
    el: editorElement.value,
    initialValue: props.initialValue,
    initialEditType: props.initialEditType,
    events: {
      change: () => {
        if (
          lastTagNormalizationUndo &&
          toastEditor?.getMarkdown() !== lastTagNormalizationUndo.after
        ) {
          lastTagNormalizationUndo = null;
        }
        if (!applyingTagNormalization) {
          scheduleTagNormalization();
        }
        emit("change");
      },
      keydown: (_, event) => {
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
      },
    },
    hooks: props.addImageBlobHook
      ? { addImageBlobHook: props.addImageBlobHook }
      : {},
  });
});

function getMarkdown() {
  if (!toastEditor) {
    return props.initialValue || "";
  }

  return normalizeWorkMarkdownTags(toastEditor.getMarkdown()).markdown;
}

function isWysiwygMode() {
  return toastEditor.isWysiwygMode();
}

function focusEditor() {
  if (!toastEditor) {
    return null;
  }

  toastEditor.focus();
  return editorElement.value?.querySelector(
    "textarea, [contenteditable='true']",
  );
}

onBeforeUnmount(clearTagNormalizeTimeout);

defineExpose({ focusEditor, getMarkdown, isWysiwygMode });
</script>

<style>
@import "@toast-ui/editor/dist/toastui-editor.css";
@import "prismjs/themes/prism.css";
@import "@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight.css";
@import "./toastui-editor-overrides.scss";
</style>
