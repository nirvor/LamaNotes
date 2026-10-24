import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const clientFile = (path) => new URL(path, import.meta.url);

const [
  appSource,
  automationModalSource,
  homeSource,
  htmlEditorSource,
  indexSource,
  modalSource,
  navBarSource,
  noteSource,
  openFileSource,
  popupMenuSource,
  renderSource,
  searchInputSource,
  styleSource,
  viewerCss,
] = await Promise.all([
  readFile(clientFile("App.vue"), "utf8"),
  readFile(clientFile("components/DocumentAutomationModal.vue"), "utf8"),
  readFile(clientFile("views/Home.vue"), "utf8"),
  readFile(clientFile("components/html/HtmlEditor.vue"), "utf8"),
  readFile(clientFile("index.js"), "utf8"),
  readFile(clientFile("components/Modal.vue"), "utf8"),
  readFile(clientFile("partials/NavBar.vue"), "utf8"),
  readFile(clientFile("views/Note.vue"), "utf8"),
  readFile(clientFile("views/OpenFile.vue"), "utf8"),
  readFile(clientFile("components/PopupMenu.vue"), "utf8"),
  readFile(clientFile("components/toastui/renderEnhancements.js"), "utf8"),
  readFile(clientFile("partials/SearchInput.vue"), "utf8"),
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
  assert.match(styleSource, /--theme-background: 239 244 249/);
  assert.match(styleSource, /--theme-title-accent: 151 85 25/);
  assert.match(styleSource, /--ln-font-body: 1rem/);
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
  assert.match(viewerCss, /\.lamanote-research-header \{/);
  assert.match(viewerCss, /\.lamanote-section-eyebrow \{/);
  assert.match(viewerCss, /\.lamanote-result \{/);
  assert.match(viewerCss, /\.lamanote-comparison \{/);
  assert.match(viewerCss, /\.lamanote-steps \{/);
  assert.match(viewerCss, /\.lamanote-tags \{/);
  assert.match(viewerCss, /\.lamanote-section-card:has\(\s*> :is\(/);
  assert.match(viewerCss, /\.lamanote-diagram\.lamanote-flow \{/);
  assert.match(viewerCss, /\.lamanote-flow \.lamanote-flow-node \{/);
  assert.match(viewerCss, /\.lamanote-research[\s\S]*?border-radius: 0;/);
  assert.match(viewerCss, /\.lamanote-plot-pair \{/);
  assert.match(renderSource, /tertiaryTextColor: heading/);
  assert.match(
    viewerCss,
    /\.lamanote-plot\.lamanote-visual-wide[\s\S]*?\.lamanote-plot-pair[\s\S]*?min-width: var\(--ln-wide-min\)/,
  );
  assert.match(
    viewerCss,
    /\.lamanote-flow\.lamanote-visual-wide[\s\S]*?\.lamanotes-mermaid-wrapper[\s\S]*?min-width: var\(--ln-wide-min\)/,
  );
  assert.match(renderSource, /graphRoot\.getBBox\(\)/);
  assert.match(renderSource, /svgElement\.setAttribute\(\s*"viewBox"/);
  assert.match(renderSource, /defaultRenderer: "dagre-wrapper"/);
  assert.match(renderSource, /wrappingWidth: 160/);
  assert.match(
    viewerCss,
    /\.lamanote-comparison tbody th \{[\s\S]*?background: transparent;/,
  );
});

test("scientific figures retain authored geometry, fill and typography", () => {
  assert.doesNotMatch(viewerCss, /r[xy]: 0 !important/);
  const mermaidCss = viewerCss.slice(
    viewerCss.indexOf("// Mermaid diagrams"),
    viewerCss.indexOf("// Bottom tag assistant"),
  );
  assert.doesNotMatch(mermaidCss, /!important|font-size:|fill:/);
  assert.match(mermaidCss, /color: inherit/);
  assert.doesNotMatch(renderSource, /rectangle\.setAttribute\("r[xy]"/);
  assert.match(renderSource, /securityLevel: "strict"/);
  assert.match(renderSource, /flowchartTitleText/);
  assert.match(
    viewerCss,
    /:is\(img, svg\)\.lamanote-figure-paper,[\s\S]*?\.lamanotes-media-lightbox-image\.lamanote-figure-paper \{[\s\S]*?background-color: #fff/,
  );
  assert.match(
    renderSource,
    /image\.classList\.toggle\(\s*"lamanote-figure-paper"/,
  );
  assert.match(
    viewerCss,
    /body\.dark[\s\S]*?lamanote-plot-image--dark[\s\S]*?display: block !important/,
  );
});

test("Home uses quiet navigation surfaces instead of an empty landing page", () => {
  assert.match(homeSource, /lamanotes-home-mark\.webp/);
  assert.match(homeSource, /decoding="async"/);
  assert.match(homeSource, /fetchpriority="low"/);
  assert.match(homeSource, /prominent-tag-cloud/);
  assert.match(homeSource, /lamanotes-home-pinned-section/);
  assert.match(homeSource, /pinnedNoteContext\(note\)/);
  assert.doesNotMatch(homeSource, /lamanotes-home-pinned-title/);
  assert.doesNotMatch(homeSource, /visiblePinnedLabel|mdiStar/);
  assert.match(
    homeSource,
    /\.lamanotes-home-pinned-list \{[\s\S]*?grid-template-columns: minmax\(0, 1fr\)/,
  );
  assert.match(
    homeSource,
    /\.lamanotes-home-pinned-link \{[\s\S]*?min-height: 2\.15rem/,
  );
  assert.match(homeSource, /width: clamp\(18rem, 42vw, 25\.5rem\)/);
  assert.match(
    homeSource,
    /lamanotes-home-pinned-section bg-theme-background dark:bg-theme-background-elevated/,
  );
  assert.match(
    homeSource,
    /\.lamanotes-home-pinned-section \{[\s\S]*?border: 1px solid rgb\(var\(--theme-border\)\);[\s\S]*?border-radius: 0\.375rem;[\s\S]*?box-shadow: none;/,
  );
  assert.match(searchInputSource, /prominentTagCloud: Boolean/);
  assert.match(searchInputSource, /lamanotes-tag-cloud-item-high/);
  assert.match(searchInputSource, /props\.prominentTagCloud \? 18/);
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
  assert.match(viewerCss, /figure\.lamanote-visual-wide:focus-visible/);
});

test("comparison tables expose bounded keyboard panning", () => {
  assert.match(renderSource, /enhanceComparisonTablePanning/);
  assert.match(
    renderSource,
    /"aria-roledescription",\s*"horizontally scrollable comparison table"/,
  );
  assert.match(
    renderSource,
    /Scrollable comparison table\. Use Left and Right Arrow, Home, and End to pan\./,
  );
  assert.match(renderSource, /table\.scrollLeft = table\.scrollWidth/);
  assert.match(viewerCss, /\.lamanote-comparison:focus-visible/);
  assert.match(viewerCss, /overscroll-behavior-inline: contain/);
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

test("all routes share stable global toolbar anchors and a row-based menu", () => {
  const actionsIndex = navBarSource.indexOf('v-for="action in noteActions"');
  const homeIndex = navBarSource.indexOf("<!-- Stable global anchors -->");
  const menuIndex = navBarSource.indexOf("<!-- Menu -->");
  assert.ok(actionsIndex >= 0 && actionsIndex < homeIndex);
  assert.ok(homeIndex < menuIndex);
  assert.match(navBarSource, /label: "New Note"[\s\S]*?command: createNewNote/);
  assert.doesNotMatch(navBarSource, /New Window|openNewWindow|mdilPlusBox/);
  assert.doesNotMatch(navBarSource, /<!-- New Note -->/);
  assert.match(navBarSource, /label: "Toggle theme"/);
  assert.match(
    navBarSource,
    /label: globalStore\.showLineNumbers[\s\S]*?toggle: true/,
  );
  assert.match(navBarSource, /var\(--ln-toolbar-max\)/);
  assert.match(styleSource, /--ln-toolbar-max: 68rem/);
  assert.match(popupMenuSource, /lamanotes-menu-action/);
  assert.doesNotMatch(popupMenuSource, /item\.controls/);
  assert.match(
    popupMenuSource,
    /:role="item\.toggle \? 'menuitemcheckbox' : 'menuitem'"/,
  );
  assert.match(popupMenuSource, /event\.key === "ArrowDown"/);
  assert.match(popupMenuSource, /event\.key === "Escape"/);
  assert.match(popupMenuSource, /anchor\.value\.focus/);
});

test("local file promotion and opening live in the menu", () => {
  const actionsStart = openFileSource.indexOf("globalStore.setNoteActions([");
  const menuStart = openFileSource.indexOf(
    "globalStore.setNoteMenuItems([",
    actionsStart,
  );
  const layoutStart = openFileSource.indexOf(
    "globalStore.setNoteLayout",
    menuStart,
  );
  const actionsBlock = openFileSource.slice(actionsStart, menuStart);
  const menuBlock = openFileSource.slice(menuStart, layoutStart);
  assert.doesNotMatch(actionsBlock, /external-keep|external-choose/);
  assert.match(
    menuBlock,
    /label: keepingFile\.value \? "Keeping\.\.\." : "Keep as note"/,
  );
  assert.match(menuBlock, /label: "Open local file"/);
  assert.match(openFileSource, /actions: \[[\s\S]*?key: "copy-path"/);
  assert.match(openFileSource, /key: "open-folder"/);
  assert.match(
    openFileSource,
    /nativeFileId: nativePayload\?\.id \|\| handle\?\.id/,
  );
  assert.match(openFileSource, /open_containing_folder/);
});

test("one document replaces the current one through Save or Discard", () => {
  assert.doesNotMatch(openFileSource, /\s+multiple\s*\n/);
  assert.match(openFileSource, /multiple: false/);
  assert.doesNotMatch(openFileSource, /function activateFile/);
  assert.match(openFileSource, /title="Unsaved Changes"/);
  assert.match(openFileSource, /@confirm="saveBeforeFileDecision"/);
  assert.match(openFileSource, /@reject="discardBeforeFileDecision"/);
  assert.match(openFileSource, /onBeforeRouteLeave\(confirmFileNavigation\)/);
  assert.match(openFileSource, /fileReplacementQueue/);
  assert.match(openFileSource, /complete_file_handoff/);
  assert.match(indexSource, /payloads\?\.\[0\]\?\._handoffId/);
  assert.match(noteSource, /onBeforeRouteLeave\(confirmNoteNavigation\)/);
  assert.match(noteSource, /onBeforeRouteUpdate\(confirmNoteNavigation\)/);
});

test("local metadata is one compact uniform pill row", () => {
  assert.match(
    openFileSource,
    /lamanotes-open-file-meta lamanotes-open-file-local/,
  );
  assert.doesNotMatch(openFileSource, /class="lamanotes-open-file-kicker"/);
  assert.match(openFileSource, /var\(--theme-title-accent\)/);
});

test("local and Library documents use one reading or editing surface", () => {
  assert.match(
    openFileSource,
    /v-else-if="activeFile && activeFile\.largeFile"/,
  );
  assert.match(openFileSource, /<ToastViewer\s+v-else-if="activeFile"/);
  assert.doesNotMatch(
    openFileSource,
    /activeFile && activeFile\.previewMode === 'plain'/,
  );
  assert.match(
    noteSource,
    /<ToastViewer[\s\S]*?<WorkNoteViewer\s+v-else-if="!editMode && isWorkNote"[\s\S]*?<HtmlViewer\s+v-else-if="!editMode && isHtmlFormat && !isWorkNote"[\s\S]*?<SourceEditor\s+v-else-if="editMode && editorFormat === 'markdown'"/,
  );
});

test("task enhancement reuses and deduplicates source checkboxes", () => {
  assert.match(
    renderSource,
    /querySelectorAll\(":scope > input\[type='checkbox'\]"\)/,
  );
  assert.match(renderSource, /candidate\.remove\(\)/);
  assert.match(renderSource, /taskItem\.dataset\.taskChecked === "true"/);
  assert.match(noteSource, /isChecklistNoteHtml\(note\.value\.content/);
  assert.match(noteSource, /htmlChecklistToWorkMarkdown\(content/);
});
