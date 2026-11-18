<template>
  <div
    ref="viewerElement"
    @click="editCell"
    @keydown.enter="editCell"
    @keydown.space="editCell"
  ></div>
</template>

<script setup>
import Viewer from "@toast-ui/editor/dist/toastui-editor-viewer";
import { onMounted, ref, watch } from "vue";

import baseOptions from "./baseOptions.js";
import { editableTableCell, startCellEdit } from "./editableTableCells.js";
import extendedAutolinks from "./extendedAutolinks.js";

let renderEnhancementsPromise = null;

const props = defineProps({
  initialValue: String,
  enhanceNoteLead: {
    type: Boolean,
    default: true,
  },
  noteTitle: String,
  editableTableCells: Boolean,
  taskCheckboxToggleHandler: Function,
  taskItemAddHandler: Function,
  taskSectionEditHandler: Function,
  taskCheckboxesDisabled: Boolean,
});

const viewerElement = ref();
const emit = defineEmits(["rendered", "cell-input", "cell-finish"]);
let viewer = null;
let enhancementRun = 0;
let refocusCell = "";

function editCell(event) {
  if (
    !props.editableTableCells ||
    event.altKey ||
    event.ctrlKey ||
    event.metaKey
  )
    return;
  startCellEdit(
    event,
    props.initialValue,
    (change) => emit("cell-input", change),
    (location, focus, change) => {
      refocusCell = focus
        ? location.split(":").slice(0, 2).join(":") + ":"
        : "";
      emit("cell-finish", change);
    },
  );
}

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
  if (run === enhancementRun) {
    if (refocusCell) {
      viewerElement.value
        .querySelector('[data-ln-cell^="' + refocusCell + '"]')
        ?.focus({ preventScroll: true });
      refocusCell = "";
    }
    emit("rendered");
  }
}

onMounted(async () => {
  viewer = new Viewer({
    ...baseOptions,
    customHTMLRenderer: props.editableTableCells
      ? { ...baseOptions.customHTMLRenderer, tableCell: editableTableCell }
      : baseOptions.customHTMLRenderer,
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
    onAdd: props.taskItemAddHandler,
    onEdit: props.taskSectionEditHandler,
    source: props.initialValue || "",
    format: "markdown",
    noteTitle: props.noteTitle,
  };
}

watch(
  () => props.noteTitle,
  () => {
    if (viewerElement.value) {
      viewerElement.value.lamanotesHiddenTaskLists = new Set();
      viewerElement.value.lamanotesSectionDrafts = new Map();
      viewerElement.value.lamanotesChecklistSections = new Set();
    }
  },
);

watch(
  () => props.initialValue,
  async (value) => {
    if (!viewer) {
      return;
    }
    const { resetChecklistGroups } = await loadRenderEnhancements();
    resetChecklistGroups(viewerElement.value);
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

[data-ln-cell]:hover {
  background-color: rgb(var(--theme-background-elevated));
}
[data-ln-cell]:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: -2px;
}
.lamanotes-cell-input {
  width: 100%;
  min-width: 2ch;
  color: inherit;
  font: inherit;
  background: rgb(var(--theme-background));
}
</style>
