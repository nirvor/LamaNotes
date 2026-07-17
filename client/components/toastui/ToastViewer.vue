<template>
  <div ref="viewerElement"></div>
</template>

<script setup>
import Viewer from "@toast-ui/editor/dist/toastui-editor-viewer";
import { onMounted, ref, watch } from "vue";

import baseOptions from "./baseOptions.js";
import extendedAutolinks from "./extendedAutolinks.js";

let renderEnhancementsPromise = null;

const props = defineProps({
  initialValue: String,
  enhanceNoteLead: {
    type: Boolean,
    default: true,
  },
  noteTitle: String,
  taskCheckboxToggleHandler: Function,
  taskCheckboxesDisabled: Boolean,
});

const viewerElement = ref();
let viewer = null;
let enhancementRun = 0;

function loadRenderEnhancements() {
  if (!renderEnhancementsPromise) {
    renderEnhancementsPromise = import("./renderEnhancements.js");
  }

  return renderEnhancementsPromise;
}

async function enhance() {
  const run = ++enhancementRun;
  const { enhanceRenderedMarkdown } = await loadRenderEnhancements();
  if (run !== enhancementRun || !viewerElement.value) {
    return;
  }
  await enhanceRenderedMarkdown(viewerElement.value, {
    noteLead: props.enhanceNoteLead,
    noteTitle: props.noteTitle,
    taskList: getTaskListOptions(),
  });
}

onMounted(async () => {
  viewer = new Viewer({
    ...baseOptions,
    extendedAutolinks,
    el: viewerElement.value,
    initialValue: props.initialValue,
  });
  await enhance();
});

function getTaskListOptions() {
  return {
    disabled: props.taskCheckboxesDisabled,
    onToggle: props.taskCheckboxToggleHandler,
  };
}

watch(
  () => props.initialValue,
  async (value) => {
    if (!viewer) {
      return;
    }
    viewer.setMarkdown(value || "");
    await enhance();
  },
);

watch(
  () => props.taskCheckboxesDisabled,
  async () => {
    const { enhanceTaskListCheckboxes } = await loadRenderEnhancements();
    enhanceTaskListCheckboxes(viewerElement.value, getTaskListOptions());
  },
);
</script>

<style>
@import "@toast-ui/editor/dist/toastui-editor-viewer.css";
@import "katex/dist/katex.min.css";
@import "prismjs/themes/prism.css";
@import "@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight.css";
@import "./toastui-editor-overrides.scss";
</style>
