<template>
  <div class="flatnotes-source-editor-shell">
    <div
      ref="editorHost"
      class="flatnotes-source-editor"
      :class="{
        'flatnotes-source-editor-wrap': wrap,
        'flatnotes-source-editor-no-gutter': !showLineNumbers,
      }"
    ></div>
    <div
      v-if="pendingStructuredPaste"
      class="flatnotes-structured-paste"
      role="toolbar"
      aria-label="Paste as"
    >
      <button
        type="button"
        class="flatnotes-structured-paste-active"
        title="Keep raw text"
        aria-label="Keep raw text"
        @click="clearStructuredPaste"
      >
        <SvgIcon type="mdi" :path="mdiText" size="0.78rem" />
        Raw
      </button>
      <button
        v-for="option in pendingStructuredPaste.options"
        :key="option.id"
        type="button"
        :title="`Paste as ${option.label.toLowerCase()}`"
        :aria-label="`Paste as ${option.label.toLowerCase()}`"
        @click="applyStructuredPaste(option)"
      >
        <SvgIcon
          type="mdi"
          :path="structuredPasteIcon(option.id)"
          size="0.78rem"
        />
        {{ option.label }}
      </button>
      <button
        type="button"
        class="flatnotes-structured-paste-close"
        title="Dismiss paste options"
        aria-label="Dismiss paste options"
        @click="clearStructuredPaste"
      >
        <SvgIcon type="mdi" :path="mdiClose" size="0.76rem" />
      </button>
    </div>
  </div>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
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
import { highlightSelectionMatches, searchKeymap } from "@codemirror/search";
import {
  Annotation,
  Compartment,
  EditorState,
  StateEffect,
  StateField,
} from "@codemirror/state";
import {
  Decoration,
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
import {
  mdiClose,
  mdiCodeTags,
  mdiFormatQuoteClose,
  mdiTable,
  mdiText,
} from "@mdi/js";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import {
  fitStructuredPasteToContext,
  structuredPasteOptions,
} from "../../structuredPaste.js";
import { normalizeWorkMarkdownTags } from "../work/workNote.js";

const props = defineProps({
  modelValue: { type: String, default: "" },
  initialValue: { type: String, default: "" },
  language: { type: String, default: "text" },
  wrap: { type: Boolean, default: true },
  showLineNumbers: { type: Boolean, default: false },
  normalizeTags: Boolean,
  sessionKey: { type: String, default: "" },
  ariaLabel: { type: String, default: "Source editor" },
  addImageBlobHook: Function,
  transformPastedText: Function,
  structuredPaste: Boolean,
});

const emit = defineEmits(["update:modelValue", "change", "keydown", "ready"]);
const editorHost = ref();
const languageCompartment = new Compartment();
const wrappingCompartment = new Compartment();
const externalUpdate = Annotation.define();
let editorView = null;
let languageLoadGeneration = 0;
let tagNormalizeTimer = null;
let sessionSaveTimer = null;
let structuredPasteTimer = null;
let structuredPasteApplying = false;
let textDropLineFrom = null;
const pendingStructuredPaste = ref(null);
const setTextDropPosition = StateEffect.define();
const setDocumentFindMatches = StateEffect.define();
const textDropPositionField = StateField.define({
  create() {
    return Decoration.none;
  },
  update(value, transaction) {
    value = value.map(transaction.changes);
    for (const effect of transaction.effects) {
      if (!effect.is(setTextDropPosition)) {
        continue;
      }
      if (effect.value == null) {
        return Decoration.none;
      }
      const position = Math.max(
        0,
        Math.min(Number(effect.value) || 0, transaction.state.doc.length),
      );
      const line = transaction.state.doc.lineAt(position);
      return Decoration.set([
        Decoration.line({ class: "cm-textDropTarget" }).range(line.from),
      ]);
    }
    return value;
  },
  provide(field) {
    return EditorView.decorations.from(field);
  },
});

const documentFindMatchesField = StateField.define({
  create() {
    return Decoration.none;
  },
  update(value, transaction) {
    value = value.map(transaction.changes);
    for (const effect of transaction.effects) {
      if (!effect.is(setDocumentFindMatches)) {
        continue;
      }
      const matches = Array.isArray(effect.value?.matches)
        ? effect.value.matches
        : [];
      const currentIndex = Number(effect.value?.currentIndex);
      const length = transaction.state.doc.length;
      const decorations = matches
        .map((match, index) => {
          const from = Math.max(0, Math.min(Number(match?.start) || 0, length));
          const to = Math.max(
            from,
            Math.min(Number(match?.end) || from, length),
          );
          if (to <= from) {
            return null;
          }
          const classes = ["cm-documentFindMatch"];
          if (index === currentIndex) {
            classes.push("cm-documentFindMatchActive");
          }
          return Decoration.mark({ class: classes.join(" ") }).range(from, to);
        })
        .filter(Boolean);
      return Decoration.set(decorations, true);
    }
    return value;
  },
  provide(field) {
    return EditorView.decorations.from(field);
  },
});

const csvLanguage = {
  startState: () => ({ quoted: false }),
  token(stream, state) {
    if (state.quoted) {
      while (!stream.eol()) {
        if (stream.next() !== '"') {
          continue;
        }
        if (stream.peek() === '"') {
          stream.next();
        } else {
          state.quoted = false;
          break;
        }
      }
      return "string";
    }
    if (stream.peek() === '"') {
      state.quoted = true;
      stream.next();
      return "string";
    }
    if (stream.match(/^[,;\t]/)) {
      return "punctuation";
    }
    if (stream.match(/^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)/)) {
      return "number";
    }
    stream.match(/^[^,;\t"]+/);
    return null;
  },
};

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
  ".cm-textDropTarget": {
    backgroundColor: "rgb(var(--theme-link) / 0.1)",
    boxShadow: "inset 2px 0 0 rgb(var(--theme-heading) / 0.9)",
  },
  ".cm-documentFindMatch": {
    borderRadius: "2px",
    color: "rgb(var(--theme-heading))",
    backgroundColor: "rgb(var(--theme-link) / 0.13)",
  },
  ".cm-documentFindMatchActive": {
    color: "rgb(var(--theme-background))",
    backgroundColor: "rgb(var(--theme-heading) / 0.94)",
  },
  ".cm-selectionMatch": {
    color: "inherit",
    backgroundColor: "rgb(var(--theme-link) / 0.13)",
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

function immediateLanguageExtension(language = props.language) {
  if (language === "markdown" || language === "md") {
    return [markdownLanguage, keymap.of(markdownKeymap)];
  }
  if (language === "csv") {
    return StreamLanguage.define(csvLanguage);
  }
  return [];
}

function usesLazyLanguageMode(language = props.language) {
  return [
    "ini",
    "cfg",
    "properties",
    "json",
    "yaml",
    "yml",
    "toml",
    "xml",
    "tex",
    "latex",
  ].includes(language);
}

async function loadLazyLanguageExtension(language) {
  if (language === "ini" || language === "cfg" || language === "properties") {
    const { properties } = await import(
      "@codemirror/legacy-modes/mode/properties"
    );
    return StreamLanguage.define(properties);
  }
  if (language === "json") {
    const { json } = await import("@codemirror/legacy-modes/mode/javascript");
    return StreamLanguage.define(json);
  }
  if (language === "yaml" || language === "yml") {
    const { yaml } = await import("@codemirror/legacy-modes/mode/yaml");
    return StreamLanguage.define(yaml);
  }
  if (language === "toml") {
    const { toml } = await import("@codemirror/legacy-modes/mode/toml");
    return StreamLanguage.define(toml);
  }
  if (language === "xml") {
    const { xml } = await import("@codemirror/legacy-modes/mode/xml");
    return StreamLanguage.define(xml);
  }
  if (language === "tex" || language === "latex") {
    const { stex } = await import("@codemirror/legacy-modes/mode/stex");
    return StreamLanguage.define(stex);
  }
  return [];
}

async function applyLanguageExtension(language) {
  const generation = ++languageLoadGeneration;
  editorView?.dispatch({
    effects: languageCompartment.reconfigure(
      immediateLanguageExtension(language),
    ),
  });
  if (!usesLazyLanguageMode(language)) {
    return;
  }
  try {
    const extension = await loadLazyLanguageExtension(language);
    if (generation === languageLoadGeneration && editorView) {
      editorView.dispatch({
        effects: languageCompartment.reconfigure(extension),
      });
    }
  } catch (error) {
    console.debug(`Could not load ${language} syntax mode`, error);
  }
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
    textDropPositionField,
    documentFindMatchesField,
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
    languageCompartment.of(immediateLanguageExtension()),
    wrappingCompartment.of(wrappingExtension()),
    sourceTheme,
    syntaxHighlighting(sourceHighlightStyle),
    EditorView.contentAttributes.of({
      "aria-label": props.ariaLabel,
      spellcheck: props.language === "markdown" || props.language === "text",
    }),
    EditorView.updateListener.of((update) => {
      if (
        update.docChanged &&
        pendingStructuredPaste.value &&
        !structuredPasteApplying
      ) {
        clearStructuredPaste();
      }
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
        if (handleImageFiles(event.clipboardData, event)) {
          return true;
        }
        const rawText = event.clipboardData?.getData("text/plain") || "";
        if (
          props.structuredPaste &&
          ["markdown", "md"].includes(props.language) &&
          insertStructuredPaste(rawText, event)
        ) {
          return true;
        }
        if (!props.transformPastedText) {
          return false;
        }
        const transformed = props.transformPastedText(
          rawText,
          getSelectedText(),
        );
        if (typeof transformed !== "string") {
          return false;
        }
        event.preventDefault();
        replaceSelection(transformed);
        return true;
      },
      drop(event) {
        return handleImageFiles(event.dataTransfer, event);
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

function handleImageFiles(dataTransfer, event) {
  if (!props.addImageBlobHook || !dataTransfer) {
    return false;
  }
  const files = [...(dataTransfer.files || [])];
  const itemFiles = [...(dataTransfer.items || [])]
    .filter((item) => item.type?.startsWith("image/"))
    .map((item) => item.getAsFile?.())
    .filter(Boolean);
  const images = [...new Set([...files, ...itemFiles])].filter((file) =>
    file.type?.startsWith("image/"),
  );
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

function getSelectionRange() {
  const selection = editorView?.state.selection.main;
  const length = editorView?.state.doc.length ?? initialContent().length;
  return selection
    ? { start: selection.from, end: selection.to }
    : { start: length, end: length };
}

function getSelectedText() {
  if (!editorView) {
    return "";
  }
  const { start, end } = getSelectionRange();
  return editorView.state.doc.sliceString(start, end);
}

function replaceSelection(text, options = {}) {
  if (!editorView) {
    return false;
  }
  const value = String(text ?? "");
  const selection = editorView.state.selection.main;
  const anchorOffset = Number.isFinite(options.anchorOffset)
    ? options.anchorOffset
    : value.length;
  const headOffset = Number.isFinite(options.headOffset)
    ? options.headOffset
    : anchorOffset;
  editorView.dispatch({
    changes: { from: selection.from, to: selection.to, insert: value },
    selection: {
      anchor:
        selection.from + Math.max(0, Math.min(anchorOffset, value.length)),
      head: selection.from + Math.max(0, Math.min(headOffset, value.length)),
    },
    scrollIntoView: true,
  });
  editorView.focus();
  return true;
}

function replaceContent(text) {
  if (!editorView) {
    return false;
  }
  const value = String(text ?? "");
  const current = editorView.state.doc.toString();
  if (value === current) {
    return false;
  }
  const selection = editorView.state.selection.main;
  const anchor = Math.min(selection.anchor, value.length);
  const head = Math.min(selection.head, value.length);
  editorView.dispatch({
    changes: { from: 0, to: current.length, insert: value },
    selection: { anchor, head },
    scrollIntoView: true,
  });
  editorView.focus();
  return true;
}

function insertStructuredPaste(text, event) {
  const options = structuredPasteOptions(text);
  if (!editorView || !options.length) {
    return false;
  }

  event.preventDefault();
  clearStructuredPaste();
  const selection = editorView.state.selection.main;
  const value = String(text);
  editorView.dispatch({
    changes: { from: selection.from, to: selection.to, insert: value },
    selection: { anchor: selection.from + value.length },
    scrollIntoView: true,
  });
  pendingStructuredPaste.value = {
    from: selection.from,
    to: selection.from + value.length,
    raw: value,
    options,
  };
  structuredPasteTimer = window.setTimeout(clearStructuredPaste, 7000);
  return true;
}

function applyStructuredPaste(option) {
  const pending = pendingStructuredPaste.value;
  if (!editorView || !pending) {
    return;
  }
  const current = editorView.state.doc.sliceString(pending.from, pending.to);
  if (current !== pending.raw) {
    clearStructuredPaste();
    return;
  }

  structuredPasteApplying = true;
  const value = fitStructuredPasteToContext(
    editorView.state.doc.toString(),
    pending.from,
    pending.to,
    option.content || "",
  );
  editorView.dispatch({
    changes: { from: pending.from, to: pending.to, insert: value },
    selection: { anchor: pending.from + value.length },
    scrollIntoView: true,
  });
  structuredPasteApplying = false;
  clearStructuredPaste();
  editorView.focus();
}

function clearStructuredPaste() {
  window.clearTimeout(structuredPasteTimer);
  pendingStructuredPaste.value = null;
}

function structuredPasteIcon(kind) {
  return {
    code: mdiCodeTags,
    quote: mdiFormatQuoteClose,
    table: mdiTable,
  }[kind];
}

function insertDroppedText(text, options = {}) {
  if (!editorView || !text) {
    return false;
  }

  const { from, to } = droppedTextRange(options);
  textDropLineFrom = null;
  editorView.dispatch({
    changes: { from, to, insert: text },
    selection: { anchor: from + text.length },
    scrollIntoView: true,
    effects: setTextDropPosition.of(null),
  });
  editorView.focus();
  return true;
}

function droppedTextRange(options = {}) {
  const selection = editorView.state.selection.main;
  const coordinatePosition =
    Number.isFinite(options.clientX) && Number.isFinite(options.clientY)
      ? editorView.posAtCoords(
          { x: options.clientX, y: options.clientY },
          false,
        )
      : null;
  const useSelection = options.fallback !== "end" && coordinatePosition == null;
  const from =
    coordinatePosition ??
    (useSelection ? selection.from : editorView.state.doc.length);
  return {
    from,
    to: coordinatePosition ?? (useSelection ? selection.to : from),
  };
}

function previewDroppedTextPosition(options = {}) {
  if (!editorView) {
    return null;
  }
  const { from } = droppedTextRange(options);
  const line = editorView.state.doc.lineAt(from);
  if (line.from !== textDropLineFrom) {
    textDropLineFrom = line.from;
    editorView.dispatch({ effects: setTextDropPosition.of(from) });
  }
  return { position: from, lineNumber: line.number };
}

function clearDroppedTextPosition() {
  textDropLineFrom = null;
  editorView?.dispatch({ effects: setTextDropPosition.of(null) });
}

function setSearchMatches(matches = [], currentIndex = -1) {
  editorView?.dispatch({
    effects: setDocumentFindMatches.of({ matches, currentIndex }),
  });
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
  if (usesLazyLanguageMode(props.language)) {
    void applyLanguageExtension(props.language);
  }
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
    void applyLanguageExtension(language);
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
  languageLoadGeneration += 1;
  window.clearTimeout(tagNormalizeTimer);
  window.clearTimeout(sessionSaveTimer);
  window.clearTimeout(structuredPasteTimer);
  saveSessionState();
  editorView?.destroy();
  editorView = null;
});

defineExpose({
  clearDroppedTextPosition,
  focusEditor,
  getMarkdown,
  getSelectedText,
  getSelectionRange,
  getSearchText,
  getValue,
  isWysiwygMode,
  insertDroppedText,
  previewDroppedTextPosition,
  replaceContent,
  replaceSelection,
  selectSearchRange,
  setSearchMatches,
});
</script>

<style scoped>
.flatnotes-source-editor-shell {
  position: relative;
  width: 100%;
  min-width: 0;
}

.flatnotes-source-editor {
  width: 100%;
  min-width: 0;
  border-top: 1px solid rgb(var(--theme-border));
  border-bottom: 1px solid rgb(var(--theme-border));
}

.flatnotes-structured-paste {
  position: sticky;
  z-index: 12;
  bottom: 0.42rem;
  display: flex;
  width: max-content;
  max-width: calc(100% - 0.8rem);
  min-height: 1.8rem;
  align-items: center;
  gap: 0.12rem;
  margin: -2.25rem 0.4rem 0 auto;
  padding: 0.16rem;
  overflow-x: auto;
  border: 1px solid rgb(var(--theme-border));
  border-radius: 5px;
  color: rgb(var(--theme-text-muted));
  background: rgb(var(--theme-background-elevated) / 0.97);
  box-shadow: 0 8px 22px rgb(0 0 0 / 0.18);
  backdrop-filter: blur(6px);
}

.flatnotes-structured-paste button {
  display: inline-flex;
  min-width: 1.55rem;
  min-height: 1.42rem;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 0.22rem;
  padding: 0.08rem 0.32rem;
  border: 1px solid transparent;
  border-radius: 3px;
  font-size: 0.68rem;
}

.flatnotes-structured-paste button:hover,
.flatnotes-structured-paste button:focus-visible,
.flatnotes-structured-paste-active {
  border-color: rgb(var(--theme-border));
  color: rgb(var(--theme-heading));
  background: rgb(var(--theme-background));
  outline: none;
}

.flatnotes-structured-paste .flatnotes-structured-paste-close {
  padding-inline: 0.2rem;
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
