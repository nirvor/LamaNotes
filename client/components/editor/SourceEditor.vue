<template>
  <div class="lamanotes-source-editor-shell">
    <div
      v-if="hasFormatting || $slots.tools"
      class="lamanotes-format-toolbar"
      role="toolbar"
      aria-label="Formatting"
    >
      <FormattingTools v-if="hasFormatting" @format="formatSelection" />
      <slot name="tools" />
    </div>
    <form
      v-if="linkVisible"
      class="lamanotes-editor-link"
      @submit.prevent="insertLink"
    >
      <input
        ref="linkInput"
        v-model="linkUrl"
        aria-label="Link URL"
        placeholder="https://"
        required
        @input="linkInput?.setCustomValidity('')"
        @keydown.esc.stop.prevent="closeLink"
      />
      <button
        type="submit"
        class="lamanotes-format-button"
        title="Insert link"
        aria-label="Insert link"
      >
        <SvgIcon type="mdi" :path="mdiCheck" size="0.92rem" />
      </button>
      <button
        type="button"
        class="lamanotes-format-button"
        title="Cancel link"
        aria-label="Cancel link"
        @click="closeLink"
      >
        <SvgIcon type="mdi" :path="mdiClose" size="0.92rem" />
      </button>
    </form>
    <div
      ref="editorHost"
      class="lamanotes-source-editor"
      :class="{
        'lamanotes-source-editor-wrap': wrap,
        'lamanotes-source-editor-no-gutter': !showLineNumbers,
        'lamanotes-source-editor-prose': prose,
      }"
    ></div>
    <div
      v-if="pendingStructuredPaste"
      class="lamanotes-structured-paste"
      role="toolbar"
      aria-label="Paste as"
    >
      <button
        type="button"
        class="lamanotes-structured-paste-active"
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
        class="lamanotes-structured-paste-close"
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
  historyField,
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
  mdiCheck,
  mdiCodeTags,
  mdiFormatQuoteClose,
  mdiTable,
  mdiText,
} from "@mdi/js";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import FormattingTools from "./FormattingTools.vue";
import { sharedAnchorRanges } from "../../sharedEntry.js";
import { formattingEdit, safeEditorLink } from "./formatting.js";

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
  sessionState: Object,
  formatting: { type: Boolean, default: true },
  prose: Boolean,
  hideShareAnchors: Boolean,
});

const emit = defineEmits(["update:modelValue", "change", "keydown", "ready"]);
const editorHost = ref();
const hasFormatting = computed(
  () =>
    props.formatting &&
    ["markdown", "md", "text", "txt", "html"].includes(props.language),
);
const linkVisible = ref(false);
const linkUrl = ref("");
const linkInput = ref();
let linkSelection = null;
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
  const anchors = (state) =>
    Decoration.set(
      sharedAnchorRanges(state.doc.toString()).map((range) =>
        Decoration.replace({ block: true }).range(range.from, range.to),
      ),
    );
  const anchorField = StateField.define({
    create: anchors,
    update: (value, transaction) =>
      transaction.docChanged ? anchors(transaction.state) : value,
    provide: (field) => [
      EditorView.decorations.from(field),
      EditorView.atomicRanges.of((view) => view.state.field(field)),
    ],
  });
  return [
    props.hideShareAnchors ? anchorField : [],
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
      ...(props.prose
        ? { autocapitalize: "sentences", autocorrect: "on" }
        : {}),
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
        if (
          hasFormatting.value &&
          (event.ctrlKey || event.metaKey) &&
          !event.altKey
        ) {
          const kind = { b: "bold", i: "italic", k: "link" }[
            event.key.toLowerCase()
          ];
          if (kind) {
            event.preventDefault();
            formatSelection(kind);
            return true;
          }
        }
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
    props.addImageBlobHook(
      file,
      async (url, altText = file.name, metadata = {}) => {
        if (props.language === "html") {
          const { createMediaFigureSnippet } = await import(
            "../html/componentKit.js"
          );
          insertText(createMediaFigureSnippet(url, altText, metadata));
        } else {
          insertText(`![${escapeMarkdownLabel(altText)}](${url})`);
        }
      },
    );
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

function formatSelection(kind) {
  if (!editorView) return;
  if (kind === "link") {
    linkSelection = getSelectionRange();
    linkVisible.value = true;
    nextTick(() => linkInput.value?.focus());
    return;
  }
  const edit = formattingEdit(
    getValue(),
    getSelectionRange(),
    kind,
    props.language,
  );
  if (edit) replaceRange(edit.from, edit.to, edit.text, edit);
}

function closeLink() {
  linkVisible.value = false;
  linkUrl.value = "";
  focusEditor();
}

function insertLink() {
  if (!safeEditorLink(linkUrl.value)) {
    linkInput.value?.setCustomValidity(
      "Use an https, http, mailto or relative link.",
    );
    linkInput.value?.reportValidity();
    return;
  }
  linkInput.value?.setCustomValidity("");
  const edit = formattingEdit(
    getValue(),
    linkSelection,
    "link",
    props.language,
    linkUrl.value,
  );
  if (edit) replaceRange(edit.from, edit.to, edit.text, edit);
  closeLink();
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
  const selection = editorView.state.selection.main;
  return replaceRange(selection.from, selection.to, text, options);
}

function replaceRange(start, end, text, options = {}) {
  if (!editorView) {
    return false;
  }
  const value = String(text ?? "");
  const documentLength = editorView.state.doc.length;
  const from = Math.max(0, Math.min(Number(start) || 0, documentLength));
  const to = Math.max(from, Math.min(Number(end) || from, documentLength));
  const anchorOffset = Number.isFinite(options.anchorOffset)
    ? options.anchorOffset
    : value.length;
  const headOffset = Number.isFinite(options.headOffset)
    ? options.headOffset
    : anchorOffset;
  editorView.dispatch({
    changes: { from, to, insert: value },
    selection: {
      anchor: from + Math.max(0, Math.min(anchorOffset, value.length)),
      head: from + Math.max(0, Math.min(headOffset, value.length)),
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
  return key ? `lamanotes:editor-session:${key}` : "";
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
  return editorView ? editorView.state.doc.toString() : initialContent();
}

function getSearchText() {
  return getValue();
}

function selectSearchRange(from, to, { centerInPage = false } = {}) {
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
  if (centerInPage)
    editorView.requestMeasure({
      read: (view) => view.domAtPos(start).node,
      write: (node) =>
        requestAnimationFrame(() =>
          (node.nodeType === 1 ? node : node.parentElement)
            ?.closest(".cm-line")
            ?.scrollIntoView({ block: "center" }),
        ),
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
  const saved = props.sessionState?.snapshot;
  const config = { doc: initialContent(), extensions: editorExtensions() };
  const state =
    saved?.state?.doc === initialContent()
      ? EditorState.fromJSON(saved.state, config, { history: historyField })
      : EditorState.create(config);
  editorView = new EditorView({
    state,
    parent: editorHost.value,
  });
  editorView.scrollDOM.addEventListener("scroll", scheduleSessionSave, {
    passive: true,
  });
  if (saved?.state?.doc === initialContent()) {
    requestAnimationFrame(() => {
      window.scrollTo(0, saved.pageScroll || 0);
      editorView?.requestMeasure();
    });
  } else {
    restoreSessionState();
  }
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
  if (props.sessionState && editorView) {
    props.sessionState.snapshot = {
      state: editorView.state.toJSON({ history: historyField }),
      pageScroll: window.scrollY,
    };
  }
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
  replaceRange,
  replaceSelection,
  selectSearchRange,
  setSearchMatches,
});
</script>

<style scoped>
.lamanotes-source-editor-shell {
  position: relative;
  width: 100%;
  min-width: 0;
}

.lamanotes-source-editor {
  width: 100%;
  min-width: 0;
  border-top: 1px solid rgb(var(--theme-border));
  border-bottom: 1px solid rgb(var(--theme-border));
}

.lamanotes-structured-paste {
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
  background: rgb(var(--theme-background-elevated));
  box-shadow: 0 8px 22px rgb(0 0 0 / 0.18);
}

.lamanotes-structured-paste button {
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

.lamanotes-structured-paste button:hover,
.lamanotes-structured-paste button:focus-visible,
.lamanotes-structured-paste-active {
  border-color: rgb(var(--theme-border));
  color: rgb(var(--theme-heading));
  background: rgb(var(--theme-background));
}

.lamanotes-structured-paste button:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: 2px;
}

.lamanotes-structured-paste .lamanotes-structured-paste-close {
  padding-inline: 0.2rem;
}

.lamanotes-source-editor :deep(.cm-editor) {
  width: 100%;
  min-width: 0;
}

.lamanotes-source-editor :deep(.cm-scroller) {
  scrollbar-width: thin;
  scrollbar-color: rgb(var(--theme-border)) transparent;
}

.lamanotes-source-editor-no-gutter :deep(.cm-gutters) {
  display: none;
}

.lamanotes-source-editor-prose :deep(.cm-editor) {
  font-size: 0.95rem;
}
.lamanotes-source-editor-prose :deep(.cm-scroller) {
  font-family: "Poppins", system-ui, sans-serif;
  line-height: 1.5;
}
@media (pointer: coarse), (hover: none) {
  .lamanotes-source-editor-prose :deep(.cm-editor) {
    font-size: 16px;
  }
}

@media (max-width: 440px) {
  .lamanotes-source-editor :deep(.cm-lineNumbers) {
    display: none;
  }

  .lamanotes-source-editor :deep(.cm-line) {
    padding-inline: 0.22rem;
  }
}
</style>
