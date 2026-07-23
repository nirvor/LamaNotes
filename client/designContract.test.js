import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const clientFile = (path) => new URL(path, import.meta.url);

const [
  appSource,
  automationModalSource,
  htmlEditorSource,
  modalSource,
  noteSource,
  renderSource,
  styleSource,
  viewerCss,
] = await Promise.all([
  readFile(clientFile("App.vue"), "utf8"),
  readFile(clientFile("components/DocumentAutomationModal.vue"), "utf8"),
  readFile(clientFile("components/html/HtmlEditor.vue"), "utf8"),
  readFile(clientFile("components/Modal.vue"), "utf8"),
  readFile(clientFile("views/Note.vue"), "utf8"),
  readFile(clientFile("components/toastui/renderEnhancements.js"), "utf8"),
  readFile(clientFile("style.css"), "utf8"),
  readFile(
    clientFile("components/toastui/toastui-editor-overrides.scss"),
    "utf8",
  ),
]);

test("all non-work HTML uses the shared article presentation", () => {
  assert.match(noteSource, /return "article";/);
  assert.match(noteSource, /lamanotes-note-shell-article/);
  assert.match(appSource, /lamanotes-app-shell-note-article/);
  assert.doesNotMatch(noteSource, /note-shell-research/);
  assert.doesNotMatch(appSource, /app-shell-note-research/);
  for (const action of ["delete", "save", "edit"]) {
    assert.match(
      noteSource,
      new RegExp(`key: "${action}"[\\s\\S]*?iconOnly: true`),
    );
  }
});

test("HTML source and preview share the production viewer", () => {
  assert.match(
    htmlEditorSource,
    /import HtmlViewer from "\.\/HtmlViewer\.vue"/,
  );
  assert.match(htmlEditorSource, /aria-label="HTML note preview"/);
  assert.match(htmlEditorSource, /findHtmlPlaceholderWarnings/);
});

test("V2 tokens and legacy aliases stay in one design contract", () => {
  assert.match(styleSource, /--ln-touch-target: 2\.65rem/);
  assert.match(styleSource, /--ln-content-max: 68rem/);
  assert.match(styleSource, /prefers-reduced-motion: reduce/);
  assert.match(viewerCss, /\.lamanote-article,/);
  assert.match(
    viewerCss,
    /\.lamanote-section,\s*\n\.toastui-editor-contents \.lamanote-research-section/,
  );
  assert.match(viewerCss, /\.lamanote blockquote \{\s*\n  border: var/);
  assert.match(viewerCss, /min-width: var\(--ln-wide-min\)/);
});

test("media preview is a modal keyboard boundary", () => {
  assert.match(renderSource, /const structuredArticle = contentRoot\.matches/);
  assert.match(
    renderSource,
    /const heroImage = structuredArticle \? null : getFirstLeadImage/,
  );
  assert.match(renderSource, /trapImageLightboxFocus/);
  assert.match(renderSource, /setImageLightboxBackgroundInert\(true\)/);
  assert.match(renderSource, /element\.inert = true/);
  assert.match(renderSource, /mediaLightboxLastFocusedElement\.focus\(\)/);
});

test("wide visuals expose bounded keyboard panning", () => {
  assert.match(renderSource, /enhanceWideVisualPanning/);
  assert.match(
    renderSource,
    /"aria-roledescription",\s*"horizontally scrollable visual"/,
  );
  assert.match(renderSource, /"ArrowLeft ArrowRight Home End"/);
  assert.match(renderSource, /visual\.scrollLeft = visual\.scrollWidth/);
  assert.match(viewerCss, /\.lamanote-visual-wide:focus-visible/);
});

test("shared application modals trap and restore keyboard focus", () => {
  assert.match(modalSource, /role="dialog"/);
  assert.match(modalSource, /aria-modal="true"/);
  assert.match(modalSource, /@keydown\.tab="trapFocus"/);
  assert.match(modalSource, /function trapFocus/);
  assert.match(modalSource, /returnFocusTarget\?\.focus/);
  assert.doesNotMatch(modalSource, /backdrop-blur/);
  assert.match(automationModalSource, /@keydown\.tab="trapFocus"/);
  assert.match(automationModalSource, /returnFocusTarget\?\.focus/);
  assert.doesNotMatch(automationModalSource, /backdrop-filter/);
});
