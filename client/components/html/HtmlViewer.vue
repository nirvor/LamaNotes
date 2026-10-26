<template>
  <div
    ref="viewerElement"
    class="lamanotes-html-viewer"
    @click="openNativeReaderLink"
  >
    <div
      class="toastui-editor-contents lamanotes-html-contents"
      v-html="html"
    ></div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { enhanceReaderLinks, openNativeReaderLink } from "../../readerLinks.js";

let renderEnhancementsPromise = null;
const renderedHtmlCache = new Map();
const renderedHtmlCacheLimit = 8;

const props = defineProps({
  initialValue: String,
  noteTitle: String,
  taskCheckboxToggleHandler: Function,
  taskItemAddHandler: Function,
  taskSectionEditHandler: Function,
  taskCheckboxesDisabled: Boolean,
});

const viewerElement = ref();
const emit = defineEmits(["rendered"]);
let enhancementRun = 0;

const html = computed(() =>
  cachedRenderableHtml(props.initialValue || "", props.noteTitle),
);

function cachedRenderableHtml(value, noteTitle) {
  const page = new URL(window.location.href);
  page.hash = "";
  const key = page.href + "\0" + (noteTitle || "") + "\0" + value;
  if (renderedHtmlCache.has(key)) {
    const cached = renderedHtmlCache.get(key);
    renderedHtmlCache.delete(key);
    renderedHtmlCache.set(key, cached);
    return cached;
  }

  const rendered = renderSafeHtml(value, page.href);
  renderedHtmlCache.set(key, rendered);
  if (renderedHtmlCache.size > renderedHtmlCacheLimit) {
    renderedHtmlCache.delete(renderedHtmlCache.keys().next().value);
  }
  return rendered;
}

function loadRenderEnhancements() {
  if (!renderEnhancementsPromise) {
    renderEnhancementsPromise = import("../toastui/renderEnhancements.js");
  }

  return renderEnhancementsPromise;
}

function renderSafeHtml(value, documentUrl) {
  const documentValue = new DOMParser().parseFromString(value, "text/html");
  const body = documentValue.body;

  body
    .querySelectorAll("script, iframe[src^='javascript:']")
    .forEach((element) => element.remove());

  body.querySelectorAll("*").forEach((element) => {
    [...element.attributes].forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      const rawValue = attribute.value.trim().toLowerCase();

      if (name.startsWith("on")) {
        element.removeAttribute(attribute.name);
      }

      if (
        (name === "href" || name === "src") &&
        rawValue.startsWith("javascript:")
      ) {
        element.removeAttribute(attribute.name);
      }
    });
  });

  enhanceReaderLinks(body, documentUrl);
  return body.innerHTML;
}

function getTaskListOptions() {
  return {
    disabled: props.taskCheckboxesDisabled,
    onToggle: props.taskCheckboxToggleHandler,
    onAdd: props.taskItemAddHandler,
    onEdit: props.taskSectionEditHandler,
    source: props.initialValue || "",
    format: "html",
    noteTitle: props.noteTitle,
  };
}

async function enhance() {
  const run = ++enhancementRun;
  await nextTick();
  const { enhanceRenderedMarkdown } = await loadRenderEnhancements();
  if (run !== enhancementRun || !viewerElement.value) {
    return;
  }
  await enhanceRenderedMarkdown(viewerElement.value, {
    noteTitle: props.noteTitle,
    taskList: getTaskListOptions(),
  });
  if (run === enhancementRun) emit("rendered");
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
watch(() => props.initialValue, enhance);
watch(() => props.taskCheckboxesDisabled, enhance);
onMounted(enhance);
</script>

<style>
@import "@toast-ui/editor/dist/toastui-editor-viewer.css";
@import "katex/dist/katex.min.css";
@import "prismjs/themes/prism.css";
@import "@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight.css";
@import "../toastui/toastui-editor-overrides.scss";
</style>
