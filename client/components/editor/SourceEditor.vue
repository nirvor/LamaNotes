<template>
  <div
    ref="editorHost"
    class="flatnotes-source-editor"
    :class="{
      'flatnotes-source-editor-wrap': wrap,
      'flatnotes-source-editor-no-gutter': !showLineNumbers,
    }"
  ></div>
</template>

<script setup>
import {
  defaultKeymap,
  history,
  historyKeymap,
  indentWithTab,
} from "@codemirror/commands";
import { markdownKeymap, markdownLanguage } from "@codemirror/lang-markdown";
import {
  bracketMatching,
  HighlightStyle,
  indentOnInput,
  StreamLanguage,
  syntaxHighlighting,
} from "@codemirror/language";
import { json } from "@codemirror/legacy-modes/mode/javascript";
import { properties } from "@codemirror/legacy-modes/mode/properties";
import { toml } from "@codemirror/legacy-modes/mode/toml";
import { xml } from "@codemirror/legacy-modes/mode/xml";
import { yaml } from "@codemirror/legacy-modes/mode/yaml";
import { highlightSelectionMatches, searchKeymap } from "@codemirror/search";
import { Annotation, Compartment, EditorState } from "@codemirror/state";
import {
  drawSelection,
  dropCursor,
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  highlightSpecialChars,
  keymap,
  lineNumbers,
} from "@codemirror/view";
import { tags } from "@lezer/highlight";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { normalizeWorkMarkdownTags } from "../work/workNote.js";

const props = defineProps({
  modelValue: { type: String, default: "" },
  initialValue: { type: String, default: "" },
  language: { type: String, default: "text" },
  wrap: { type: Boolean, default: true },
  showLineNumbers: { type: Boolean, default: true },
  normalizeTags: Boolean,
  sessionKey: { type: String, default: "" },
  ariaLabel: { type: String, default: "Source editor" },
  addImageBlobHook: Function,
});

const emit = defineEmits(["update:modelValue", "change", "keydown", "ready"]);
const editorHost = ref();
const languageCompartment = new Compartment();
const wrappingCompartment = new Compartment();
const externalUpdate = Annotation.define();
let editorView = null;
let tagNormalizeTimer = null;
let sessionSaveTimer = null;

const sourceTheme = EditorView.theme({
  "&": {
    minHeight: "min(68vh, 48rem)",
    color: "rgb(var(--theme-text))",
    backgroundColor: "transparent",
    fontSize: "0.88rem",
  },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": {
    minHeight: "min(68vh, 48rem)",
    overflowY: "visible",
    fontFamily:
      'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
    lineHeight: "1.58",
  },
  ".cm-content": {
    minHeight: "min(68vh, 48rem)",
    padding: "0.72rem 0.2rem 1.1rem",
    caretColor: "rgb(var(--theme-brand))",
  },
  ".cm-line": { padding: "0 0.48rem" },
  ".cm-cursor, .cm-dropCursor": {
    borderLeftColor: "rgb(var(--theme-brand))",
  },
  ".cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection":
    {
      backgroundColor: "rgb(var(--theme-link) / 0.24)",
    },
  ".cm-activeLine": {
    backgroundColor: "rgb(var(--theme-background-elevated) / 0.34)",
  },
  ".cm-gutters": {
    border: "0",
    color: "rgb(var(--theme-text-very-muted))",
    backgroundColor: "transparent",
  },
  ".cm-activeLineGutter": {
    color: "rgb(var(--theme-text-muted))",
    backgroundColor: "transparent",
  },
  ".cm-lineNumbers .cm-gutterElement": {
    minWidth: "2.15rem",
    padding: "0 0.48rem 0 0.2rem",
    fontSize: "0.7rem",
  },
  ".cm-foldGutter": { display: "none" },
  ".cm-panels": {
    border: "0",
    color: "rgb(var(--theme-text))",
    backgroundColor: "rgb(var(--theme-background-elevated))",
  },
  ".cm-panels.cm-panels-top": {
    borderBottom: "1px solid rgb(var(--theme-border))",
  },
  ".cm-search": {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    gap: "0.3rem",
    padding: "0.38rem 0.46rem",
    fontFamily: '"Poppins", system-ui, sans-serif',
    fontSize: "0.72rem",
  },
  ".cm-search input": {
    minHeight: "1.7rem",
    border: "1px solid rgb(var(--theme-border))",
    borderRadius: "4px",
    padding: "0 0.4rem",
    color: "rgb(var(--theme-text))",
    backgroundColor: "rgb(var(--theme-background))",
    outline: "none",
  },
  ".cm-search button": {
    minHeight: "1.7rem",
    border: "1px solid rgb(var(--theme-border))",
    borderRadius: "4px",
    padding: "0 0.4rem",
    color: "rgb(var(--theme-text-muted))",
    backgroundColor: "transparent",
  },
  ".cm-search button:hover": {
    color: "rgb(var(--theme-text))",
    borderColor: "rgb(var(--theme-text-muted))",
  },
});

const sourceHighlightStyle = HighlightStyle.define([
  {
    tag: [tags.heading, tags.heading1, tags.heading2, tags.heading3],
    color: "rgb(var(--theme-heading))",
    fontWeight: "650",
  },
  {
    tag: [tags.link, tags.url],
    color: "rgb(var(--theme-link))",
    textDecoration: "none",
  },
  {
    tag: [tags.keyword, tags.atom, tags.bool],
    color: "rgb(var(--theme-heading))",
  },
  {
    tag: [tags.propertyName, tags.labelName, tags.definitionKeyword],
    color: "rgb(var(--theme-link))",
  },
  {
    tag: [tags.string, tags.inserted],
    color: "rgb(var(--theme-brand))",
  },
  {
    tag: [tags.comment, tags.meta, tags.processingInstruction],
    color: "rgb(var(--theme-text-muted))",
    fontStyle: "italic",
  },
  {
    tag: [tags.monospace, tags.number],
    color: "rgb(var(--theme-text))",
  },
  {
    tag: [tags.emphasis],
    fontStyle: "italic",
  },
  {
    tag: [tags.strong],
    fontWeight: "650",
  },
]);

function initialContent() {
  return props.modelValue || props.initialValue || "";
}

function languageExtension(language = props.language) {
  if (language === "markdown" || language === "md") {
    return [markdownLanguage, keymap.of(markdownKeymap)];
  }
  if (language === "ini" || language === "cfg" || language === "properties") {
    return StreamLanguage.define(properties);
  }
  if (language === "json") {
    return StreamLanguage.define(json);
  }
  if (language === "yaml" || language === "yml") {
    return StreamLanguage.define(yaml);
  }
  if (language === "toml") {
    return StreamLanguage.define(toml);
  }
  if (language === "xml") {
    return StreamLanguage.define(xml);
  }
  return [];
}

function wrappingExtension(value = props.wrap) {
  return value ? EditorView.lineWrapping : [];
}

function editorExtensions() {
  return [
    lineNumbers(),
    highlightActiveLineGutter(),
    highlightSpecialChars(),
    history(),
    drawSelection(),
    dropCursor(),
    EditorState.allowMultipleSelections.of(true),
    indentOnInput(),
    bracketMatching(),
    highlightActiveLine(),
    highlightSelectionMatches(),
    keymap.of([
      indentWithTab,
      ...defaultKeymap,
      ...searchKeymap,
      ...historyKeymap,
    ]),
    languageCompartment.of(languageExtension()),
    wrappingCompartment.of(wrappingExtension()),
    sourceTheme,
    syntaxHighlighting(sourceHighlightStyle),
    EditorView.contentAttributes.of({
      "aria-label": props.ariaLabel,
      spellcheck: props.language === "markdown" || props.language === "text",
    }),
    EditorView.updateListener.of((update) => {
      if (update.docChanged && !isExternalUpdate(update)) {
        const content = update.state.doc.toString();
        emit("update:modelValue", content);
        emit("change", content);
        scheduleTagNormalization();
      }
      if (update.docChanged || update.selectionSet) {
        scheduleSessionSave();
      }
    }),
    EditorView.domEventHandlers({
      keydown(event) {
        emit("keydown", event);
        return event.defaultPrevented;
      },
      paste(event) {
        return handleImageFiles(event.clipboardData?.files, event);
      },
      drop(event) {
        return handleImageFiles(event.dataTransfer?.files, event);
      },
    }),
  ];
}

function isExternalUpdate(update) {
  return update.transactions.some((transaction) =>
    transaction.annotation(externalUpdate),
  );
}

function scheduleTagNormalization() {
  window.clearTimeout(tagNormalizeTimer);
  if (!props.normalizeTags || !editorView) {
    return;
  }
  tagNormalizeTimer = window.setTimeout(normalizeTagsNow, 320);
}

function normalizeTagsNow() {
  if (!editorView || !props.normalizeTags) {
    return;
  }
  const content = editorView.state.doc.toString();
  const normalized = normalizeWorkMarkdownTags(content);
  if (!normalized.changed || normalized.markdown === content) {
    return;
  }

  const change = minimalTextChange(content, normalized.markdown);
  editorView.dispatch({ changes: change });
}

function minimalTextChange(before, after) {
  let prefix = 0;
  const maxPrefix = Math.min(before.length, after.length);
  while (prefix < maxPrefix && before[prefix] === after[prefix]) {
    prefix += 1;
  }

  let beforeSuffix = before.length;
  let afterSuffix = after.length;
  while (
    beforeSuffix > prefix &&
    afterSuffix > prefix &&
    before[beforeSuffix - 1] === after[afterSuffix - 1]
  ) {
    beforeSuffix -= 1;
    afterSuffix -= 1;
  }

  return {
    from: prefix,
    to: beforeSuffix,
    insert: after.slice(prefix, afterSuffix),
  };
}

function handleImageFiles(fileList, event) {
  if (!props.addImageBlobHook || !fileList?.length) {
    return false;
  }
  const images = [...fileList].filter((file) => file.type.startsWith("image/"));
  if (!images.length) {
    return false;
  }

  event.preventDefault();
  images.forEach((file) => {
    props.addImageBlobHook(file, (url, altText = file.name) => {
      insertText(`![${escapeMarkdownLabel(altText)}](${url})`);
    });
  });
  return true;
}

function escapeMarkdownLabel(value = "") {
  return String(value).replace(/[\[\]\\]/g, "\\$&");
}

function insertText(text) {
  if (!editorView) {
    return;
  }
  const selection = editorView.state.selection.main;
  editorView.dispatch({
    changes: { from: selection.from, to: selection.to, insert: text },
    selection: { anchor: selection.from + text.length },
    scrollIntoView: true,
  });
  editorView.focus();
}

function sessionStorageKey() {
  const key = String(props.sessionKey || "").trim();
  return key ? `nirvnotes:editor-session:${key}` : "";
}

function scheduleSessionSave() {
  window.clearTimeout(sessionSaveTimer);
  if (!sessionStorageKey()) {
    return;
  }
  sessionSaveTimer = window.setTimeout(saveSessionState, 180);
}

function saveSessionState() {
  const key = sessionStorageKey();
  if (!key || !editorView) {
    return;
  }
  const selection = editorView.state.selection.main;
  localStorage.setItem(
    key,
    JSON.stringify({
      anchor: selection.anchor,
      head: selection.head,
      scrollTop: editorView.scrollDOM.scrollTop,
    }),
  );
}

function restoreSessionState() {
  const key = sessionStorageKey();
  if (!key || !editorView) {
    return;
  }
  try {
    const saved = JSON.parse(localStorage.getItem(key) || "null");
    if (!saved) {
      return;
    }
    const length = editorView.state.doc.length;
    const anchor = Math.max(0, Math.min(Number(saved.anchor) || 0, length));
    const head = Math.max(0, Math.min(Number(saved.head) || anchor, length));
    editorView.dispatch({ selection: { anchor, head } });
    nextTick(() => {
      editorView.scrollDOM.scrollTop = Math.max(
        0,
        Number(saved.scrollTop) || 0,
      );
    });
  } catch {
    localStorage.removeItem(key);
  }
}

function focusEditor() {
  editorView?.focus();
  return editorView?.contentDOM || null;
}

function getValue() {
  return editorView?.state.doc.toString() || initialContent();
}

function getSearchText() {
  return getValue();
}

function selectSearchRange(from, to) {
  if (!editorView) {
    return;
  }
  const length = editorView.state.doc.length;
  const start = Math.max(0, Math.min(Number(from) || 0, length));
  const end = Math.max(start, Math.min(Number(to) || start, length));
  editorView.dispatch({
    selection: { anchor: start, head: end },
    effects: EditorView.scrollIntoView(start, { y: "center" }),
  });
}

function getMarkdown() {
  const content = getValue();
  return props.normalizeTags
    ? normalizeWorkMarkdownTags(content).markdown
    : content;
}

function isWysiwygMode() {
  return false;
}

onMounted(() => {
  editorView = new EditorView({
    state: EditorState.create({
      doc: initialContent(),
      extensions: editorExtensions(),
    }),
    parent: editorHost.value,
  });
  editorView.scrollDOM.addEventListener("scroll", scheduleSessionSave, {
    passive: true,
  });
  restoreSessionState();
  emit("ready");
});

watch(
  () => props.modelValue,
  (value) => {
    if (!editorView) {
      return;
    }
    const nextValue = String(value ?? "");
    const currentValue = editorView.state.doc.toString();
    if (nextValue === currentValue) {
      return;
    }
    editorView.dispatch({
      changes: { from: 0, to: currentValue.length, insert: nextValue },
      annotations: externalUpdate.of(true),
    });
  },
);

watch(
  () => props.language,
  (language) => {
    editorView?.dispatch({
      effects: languageCompartment.reconfigure(languageExtension(language)),
    });
  },
);

watch(
  () => props.wrap,
  (wrap) => {
    editorView?.dispatch({
      effects: wrappingCompartment.reconfigure(wrappingExtension(wrap)),
    });
  },
);

onBeforeUnmount(() => {
  window.clearTimeout(tagNormalizeTimer);
  window.clearTimeout(sessionSaveTimer);
  saveSessionState();
  editorView?.destroy();
  editorView = null;
});

defineExpose({
  focusEditor,
  getMarkdown,
  getSearchText,
  getValue,
  isWysiwygMode,
  selectSearchRange,
});
</script>

<style scoped>
.flatnotes-source-editor {
  width: 100%;
  min-width: 0;
  border-top: 1px solid rgb(var(--theme-border));
  border-bottom: 1px solid rgb(var(--theme-border));
}

.flatnotes-source-editor :deep(.cm-editor) {
  width: 100%;
  min-width: 0;
}

.flatnotes-source-editor :deep(.cm-scroller) {
  scrollbar-width: thin;
  scrollbar-color: rgb(var(--theme-border)) transparent;
}

.flatnotes-source-editor-no-gutter :deep(.cm-gutters) {
  display: none;
}

@media (max-width: 440px) {
  .flatnotes-source-editor :deep(.cm-lineNumbers) {
    display: none;
  }

  .flatnotes-source-editor :deep(.cm-line) {
    padding-inline: 0.22rem;
  }
}
</style>
