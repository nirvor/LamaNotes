<template>
  <section
    :class="[
      'lamanotes-open-file min-w-0 max-w-full',
      { 'lamanotes-document-find-open': findVisible },
    ]"
    @dblclick="openFileDblClickHandler"
    @pointerup="openFilePointerUpHandler"
  >
    <DocumentFindBar
      v-if="findVisible"
      ref="findBar"
      v-model="findQuery"
      :current="findCurrent"
      :total="findTotal"
      @previous="findMove(-1)"
      @next="findMove(1)"
      @close="closeFind"
    />

    <DocumentAutomationModal
      v-if="automationVisible"
      v-model="automationVisible"
      :source="automationSource"
      :language="editorLanguage"
      @apply="applyDocumentAutomation"
    />

    <div
      class="lamanotes-open-file-heading"
      :class="{
        'lamanotes-open-file-heading-desktop': desktopShell.enabled,
      }"
    >
      <div class="min-w-0">
        <div class="lamanotes-open-file-kicker-line">
          <span class="lamanotes-open-file-kicker">
            <SvgIcon type="mdi" :path="mdiHarddisk" size="0.68rem" />
            Local
          </span>
          <span
            v-for="item in metadataItems"
            :key="item.label"
            class="lamanotes-open-file-meta"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </span>
        </div>
        <h1 v-if="!desktopShell.enabled" class="lamanotes-open-file-title">
          {{ activeFile ? activeFile.name : "Open a local file" }}
        </h1>
      </div>
    </div>

    <input
      ref="fileInput"
      type="file"
      class="hidden"
      accept=".md,.txt,.cfg,.ini,.json,.yaml,.yml,.toml,.xml,.log,.csv,.tex,text/markdown,text/plain,text/csv,application/json,application/yaml,application/xml,application/x-tex"
      multiple
      @change="fileInputChanged"
    />

    <div v-if="visibleStatusMessage" class="lamanotes-open-file-strip">
      <span
        class="lamanotes-open-file-status"
        :class="{ 'lamanotes-open-file-status-error': statusTone === 'error' }"
      >
        <SvgIcon type="mdi" :path="statusIcon" size="0.76rem" />
        {{ visibleStatusMessage }}
      </span>
    </div>

    <div
      v-if="activeFile?.externalState"
      class="lamanotes-open-file-conflict print:hidden"
      role="status"
    >
      <SvgIcon
        type="mdi"
        :path="
          activeFile.externalState === 'deleted'
            ? mdiFileAlertOutline
            : mdiAlertOutline
        "
        size="0.88rem"
      />
      <span class="min-w-0 grow">
        {{ externalStateMessage }}
      </span>
      <button
        v-if="activeFile.externalState === 'conflict'"
        type="button"
        title="Compare versions"
        aria-label="Compare versions"
        @click="compareOpen = true"
      >
        <SvgIcon type="mdi" :path="mdiFileCompare" size="0.92rem" />
      </button>
      <button
        v-if="activeFile.externalState === 'conflict'"
        type="button"
        title="Reload file from disk"
        aria-label="Reload file from disk"
        @click="reloadActiveFromDisk"
      >
        <SvgIcon type="mdi" :path="mdiReload" size="0.92rem" />
      </button>
      <button
        v-if="activeFile.externalState === 'conflict'"
        type="button"
        title="Keep my version and overwrite disk"
        aria-label="Keep my version and overwrite disk"
        @click="overwriteExternalVersion"
      >
        <SvgIcon type="mdi" :path="mdiContentSaveAlertOutline" size="0.92rem" />
      </button>
    </div>

    <div
      v-if="files.length > 1"
      class="mb-3 flex flex-wrap gap-1.5 print:hidden"
    >
      <button
        v-for="file in files"
        :key="file.key"
        type="button"
        class="rounded-full border border-theme-border px-2 py-0.5 text-xs hover:border-theme-brand hover:text-theme-brand"
        :class="{
          'border-theme-brand text-theme-brand': activeFile?.key === file.key,
        }"
        @click="activateFile(file.key)"
      >
        {{ file.name }}
      </button>
    </div>

    <div ref="openFileContent" class="lamanotes-open-file-content">
      <SourceEditor
        v-if="activeFile && editMode"
        ref="editorTextarea"
        v-model="activeFile.draftContent"
        :language="editorLanguage"
        :wrap="editorWrap"
        :show-line-numbers="globalStore.showLineNumbers"
        :structured-paste="editorLanguage === 'markdown'"
        :session-key="editorSessionKey"
        :aria-label="`Edit ${activeFile.name}`"
        @change="activeFileChangedHandler"
        @keydown="documentKeydownHandler"
        @ready="openFileEditorReadyHandler"
      />

      <CsvTablePreview
        v-else-if="activeFile && activeFile.previewMode === 'csv'"
        :source="activeFile.draftContent"
      />

      <pre
        v-else-if="activeFile && activeFile.previewMode === 'plain'"
        class="lamanotes-open-file-plain-preview"
        >{{ activeFile.previewContent }}</pre
      >
      <p
        v-if="activeFile?.largeFile && activeFile.previewTruncated && !editMode"
        class="lamanotes-large-file-note"
      >
        Fast preview shortened. Edit opens the complete file.
      </p>

      <ToastViewer
        v-else-if="activeFile && !editMode"
        :key="`${activeFile.key}:${activeFile.previewRevision}`"
        :initialValue="activeFile.previewMarkdown"
        :enhance-note-lead="false"
        :note-title="noteTitleForFile(activeFile)"
        class="toast-viewer min-w-0 max-w-full pb-4"
      />
    </div>

    <div
      v-if="!activeFile"
      class="rounded-md border border-dashed border-theme-border px-3 py-4 text-center text-sm text-theme-text-muted"
    >
      <IconLabel
        :iconPath="mdiFileDocumentOutline"
        iconSize="1.35rem"
        class="mb-2 justify-center"
      />
      <p>
        Open a local text or configuration file through Windows, or choose one
        here. Nothing is saved into the Library.
      </p>
    </div>

    <div
      v-if="compareOpen && activeFile?.externalChange"
      class="lamanotes-file-compare-backdrop print:hidden"
      role="presentation"
      @click.self="compareOpen = false"
    >
      <section
        class="lamanotes-file-compare"
        role="dialog"
        aria-modal="true"
        aria-label="Compare local file versions"
      >
        <header>
          <strong>File changed outside LamaNotes</strong>
          <button
            type="button"
            title="Close comparison"
            aria-label="Close comparison"
            @click="compareOpen = false"
          >
            <SvgIcon type="mdi" :path="mdiClose" size="0.95rem" />
          </button>
        </header>
        <div class="lamanotes-file-compare-grid">
          <div>
            <span>My version</span>
            <pre>{{ activeFile.draftContent }}</pre>
          </div>
          <div>
            <span>On disk</span>
            <pre>{{ activeFile.externalChange.content }}</pre>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import {
  mdiAlertCircleOutline,
  mdiAlertOutline,
  mdiCheck,
  mdiCheckCircleOutline,
  mdiClose,
  mdiCloudUploadOutline,
  mdiContentSaveAlertOutline,
  mdiContentSaveOutline,
  mdiContentCopy,
  mdiCogOutline,
  mdiFileAlertOutline,
  mdiFileCompare,
  mdiFileDocumentOutline,
  mdiFolderOpenOutline,
  mdiHarddisk,
  mdiPencilOutline,
  mdiReload,
} from "@mdi/js";
import {
  computed,
  defineAsyncComponent,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  watch,
  watchEffect,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import { useToast } from "primevue/usetoast";

import { apiErrorHandler, createNote } from "../api.js";
import DocumentFindBar from "../components/DocumentFindBar.vue";
import CsvTablePreview from "../components/CsvTablePreview.vue";
import IconLabel from "../components/IconLabel.vue";
import { useDocumentFind } from "../documentFind.js";
import { useDocumentSession } from "../documents/documentSession.js";
import { createLocalFileStorageAdapter } from "../documents/storageAdapters.js";
import {
  clearDesktopFileSession,
  saveDesktopFileSession,
} from "../desktopSession.js";
import { desktopShell, setDesktopWindowTitle } from "../desktopShell.js";
import {
  externalFileLaunch,
  fileFromNativePayload,
  supportsFileHandlingLaunchQueue,
  supportsNativeFileBridge,
} from "../externalFiles.js";
import { useGlobalStore } from "../globalStore.js";
import { getToastOptions } from "../helpers.js";
import {
  buildLargeFilePreview,
  shouldUseLargeFileMode,
} from "../largeFileMode.js";
import { buildLocalLibraryNote } from "../localNotePromotion.js";
import { reportNativeReady } from "../nativeTelemetry.js";
import { createDebouncedWork } from "../performanceScheduling.js";

const ToastViewer = defineAsyncComponent(
  () => import("../components/toastui/ToastViewer.vue"),
);
const loadSourceEditor = () => import("../components/editor/SourceEditor.vue");
const SourceEditor = defineAsyncComponent(loadSourceEditor);
const DocumentAutomationModal = defineAsyncComponent(
  () => import("../components/DocumentAutomationModal.vue"),
);

const editorTextarea = ref();
const openFileContent = ref();
const fileInput = ref();
const files = ref([]);
const activeKey = ref(null);
const lastConsumedLaunchId = ref(null);
const statusMessage = ref("");
const statusTone = ref("info");
const compareOpen = ref(false);
const keepingFile = ref(false);
const automationVisible = ref(false);
const automationSource = ref("");
const route = useRoute();
const router = useRouter();
const toast = useToast();
const globalStore = useGlobalStore();
const localFileStorageAdapter = createLocalFileStorageAdapter();

if (desktopShell.enabled) {
  // Overlap the editor chunk with native file handoff instead of waiting for it.
  void loadSourceEditor();
}

const activeFile = computed(
  () => files.value.find((file) => file.key === activeKey.value) || null,
);
const documentSession = useDocumentSession({
  canEdit: () => Boolean(activeFile.value),
  hasDocument: () => Boolean(activeFile.value),
  requestClose: finishEditing,
  focusEditor: () => editorTextarea.value?.focusEditor?.(),
  beforeLeaveEdit: () => {
    if (activeFile.value) {
      refreshPreview(activeFile.value);
    }
  },
  draftKey: () => activeFile.value?.draftStorageKey || "",
  persistDraft: true,
  saveDocument: persistActiveFile,
  copyDocument: getActiveFileCopyPayload,
  afterSave: () => showStatus("Saved to original file."),
  onSaveError: handleActiveFileSaveError,
  afterCopy: () => showStatus("Copied raw source to clipboard."),
  onCopyError: () => showStatus("Could not copy this file.", "error"),
});
const editMode = documentSession.editMode;
const copied = documentSession.copied;
const openFileDblClickHandler = documentSession.contentDblClickHandler;
const openFilePointerUpHandler = documentSession.contentPointerUpHandler;
const {
  close: closeFind,
  contentChanged: documentFindContentChanged,
  current: findCurrent,
  findBar,
  move: findMove,
  query: findQuery,
  refresh: refreshDocumentFind,
  total: findTotal,
  visible: findVisible,
} = useDocumentFind({
  isEditing: () => editMode.value,
  getEditorText: () =>
    editorTextarea.value?.getSearchText?.() ||
    activeFile.value?.draftContent ||
    "",
  selectEditorRange: (from, to) =>
    editorTextarea.value?.selectSearchRange?.(from, to),
  setEditorMatches: (matches, currentIndex) =>
    editorTextarea.value?.setSearchMatches?.(matches, currentIndex),
  getViewRoot: () => openFileContent.value,
});
const canSaveActiveFile = computed(
  () =>
    Boolean(
      activeFile.value?.isNewDraft ||
        (activeFile.value?.handle && activeFile.value?.dirty),
    ) && !documentSession.saving.value,
);
const editorLanguage = computed(() => {
  const extension = activeFile.value?.extension || "text";
  return extension === "md" ? "markdown" : extension;
});
const editorWrap = computed(
  () =>
    !activeFile.value?.largeFile &&
    ["md", "txt", "log", "tex"].includes(activeFile.value?.extension),
);
const editorSessionKey = computed(() =>
  activeFile.value ? `local:${activeFile.value.draftStorageKey}` : "",
);
const canAutomateActiveFile = computed(() =>
  ["md", "txt", "log", "json"].includes(activeFile.value?.extension),
);
const metadataItems = computed(() => {
  if (!activeFile.value) {
    return [];
  }

  const items = desktopShell.enabled
    ? [{ label: "size", value: formatBytes(activeFile.value.size) }]
    : [
        { label: "type", value: activeFile.value.extension || "text" },
        { label: "size", value: formatBytes(activeFile.value.size) },
      ];
  if (activeFile.value.encoding) {
    items.push({ label: "encoding", value: activeFile.value.encoding });
  }
  if (activeFile.value.lineEnding) {
    items.push({ label: "lines", value: activeFile.value.lineEnding });
  }
  if (activeFile.value.largeFile) {
    items.push({ label: "view", value: "fast" });
  }
  return items;
});
const externalStateMessage = computed(() => {
  if (activeFile.value?.externalState === "deleted") {
    return "The original file was deleted outside LamaNotes.";
  }
  return "The file changed on disk while this version has unsaved edits.";
});
const visibleStatusMessage = computed(() =>
  statusTone.value === "error" ? statusMessage.value : "",
);
const statusIcon = computed(() =>
  statusTone.value === "error" ? mdiAlertCircleOutline : mdiCheckCircleOutline,
);
let nativeWatcherTimer = null;
let nativeWatcherBusy = false;
let scrollSaveTimer = null;
let localLoadStartedAt = performance.now();
let localLoadGeneration = 0;
let lastEditorReadyGeneration = -1;
let lastFileReadyGeneration = -1;
let textDropActivatedEditMode = false;
let textDropEditorReady = null;
let latestTextDropPosition = null;
let textDropPreviewActive = false;
const draftPersistence = createDebouncedWork(persistDraftState, 240);

onMounted(() => {
  if (!supportsFileHandlingLaunchQueue() && !supportsNativeFileBridge()) {
    showStatus(
      "This browser can preview files here, but Windows file opening needs the installed LamaNotes app.",
    );
  }
  startNativeWatcher();
  window.addEventListener("scroll", scheduleActiveScrollSave, {
    passive: true,
  });
  window.addEventListener("lamanotes:text-drop", insertExternalDroppedText);
  window.addEventListener(
    "lamanotes:text-drag-position",
    previewExternalTextDrop,
  );
  window.addEventListener("lamanotes:text-drag-end", endExternalTextDrop);
  window.addEventListener("visibilitychange", nativeWatcherVisibilityChanged);
  window.addEventListener("pagehide", flushDraftPersistence);
});

watch(externalFileLaunch, consumeExternalLaunch, { immediate: true });
watch(
  () => [route.query.new, route.query.draft],
  ([newDraft, draftId]) => {
    if (newDraft === "1") {
      createLocalDraft(String(draftId || "new"));
    }
  },
  { immediate: true },
);
watch(editMode, () => {
  if (findVisible.value) {
    nextTick(refreshDocumentFind);
  }
});
watch(editorTextarea, () => {
  if (findVisible.value && editorTextarea.value) {
    nextTick(refreshDocumentFind);
  }
});
watchEffect(updateOpenFileActions);
watchEffect(persistDesktopFiles);
watchEffect(() => {
  setDesktopWindowTitle(activeFile.value?.name || "Open File");
});
watchEffect(() => {
  document.body.classList.toggle(
    "lamanotes-text-drop-enabled",
    Boolean(activeFile.value),
  );
});

onUnmounted(() => {
  textDropPreviewActive = false;
  flushDraftPersistence();
  draftPersistence.cancel();
  window.clearInterval(nativeWatcherTimer);
  window.clearTimeout(scrollSaveTimer);
  saveActiveScroll();
  window.removeEventListener("scroll", scheduleActiveScrollSave);
  window.removeEventListener("lamanotes:text-drop", insertExternalDroppedText);
  window.removeEventListener(
    "lamanotes:text-drag-position",
    previewExternalTextDrop,
  );
  window.removeEventListener("lamanotes:text-drag-end", endExternalTextDrop);
  window.removeEventListener(
    "visibilitychange",
    nativeWatcherVisibilityChanged,
  );
  window.removeEventListener("pagehide", flushDraftPersistence);
  document.body.classList.remove(
    "lamanotes-text-drop-enabled",
    "lamanotes-native-text-drag-active",
  );
  delete document.body.dataset.lamanotesTextDropLabel;
  globalStore.clearNoteActions();
});

async function ensureTextDropEditor() {
  if (editMode.value && editorTextarea.value) {
    return;
  }
  if (!textDropEditorReady) {
    if (!editMode.value) {
      textDropActivatedEditMode = true;
      setEditMode(true);
    }
    textDropEditorReady = (async () => {
      await nextTick();
      await new Promise((resolve) => window.requestAnimationFrame(resolve));
    })().finally(() => {
      textDropEditorReady = null;
    });
  }
  await textDropEditorReady;
}

async function previewExternalTextDrop(event) {
  if (!activeFile.value) {
    return;
  }
  textDropPreviewActive = true;
  latestTextDropPosition = {
    clientX: event.detail?.clientX,
    clientY: event.detail?.clientY,
  };
  await ensureTextDropEditor();
  if (!textDropPreviewActive || !latestTextDropPosition) {
    return;
  }
  const target = editorTextarea.value?.previewDroppedTextPosition?.({
    ...latestTextDropPosition,
    fallback: textDropActivatedEditMode ? "end" : "selection",
  });
  if (target?.lineNumber) {
    document.body.dataset.lamanotesTextDropLabel = `Insert - line ${target.lineNumber}`;
  }
}

function clearExternalTextDropPreview() {
  editorTextarea.value?.clearDroppedTextPosition?.();
  latestTextDropPosition = null;
  delete document.body.dataset.lamanotesTextDropLabel;
}

function endExternalTextDrop(event) {
  textDropPreviewActive = false;
  clearExternalTextDropPreview();
  if (
    !event.detail?.dropped &&
    textDropActivatedEditMode &&
    !activeFile.value?.dirty
  ) {
    documentSession.leaveEdit();
  }
  if (!event.detail?.dropped) {
    textDropActivatedEditMode = false;
  }
}

async function insertExternalDroppedText(event) {
  const text = String(event.detail?.text || "");
  if (!activeFile.value || !text) {
    return;
  }

  const startedInViewMode = textDropActivatedEditMode || !editMode.value;
  await ensureTextDropEditor();
  const inserted = editorTextarea.value?.insertDroppedText?.(text, {
    clientX: event.detail?.clientX,
    clientY: event.detail?.clientY,
    fallback: startedInViewMode ? "end" : "selection",
  });
  clearExternalTextDropPreview();
  textDropActivatedEditMode = false;
  if (inserted) {
    showStatus("Dropped text inserted. Save when ready.");
  }
}

function updateOpenFileActions() {
  const file = activeFile.value;
  globalStore.setNoteActions([
    {
      key: "external-tools",
      label: "Note tools",
      iconPath: mdiCogOutline,
      badge: "A",
      visible: Boolean(file && editMode.value && canAutomateActiveFile.value),
      iconOnly: true,
      handler: () => {
        automationSource.value =
          editorTextarea.value?.getValue?.() || file?.draftContent || "";
        automationVisible.value = true;
      },
    },
    {
      key: "external-edit",
      label: editMode.value ? "Done" : "Edit",
      iconPath: editMode.value ? mdiCheck : mdiPencilOutline,
      visible: Boolean(file),
      iconOnly: true,
      handler: editMode.value ? finishEditing : () => setEditMode(true),
    },
    {
      key: "external-save",
      label: "Save",
      iconPath: mdiContentSaveOutline,
      visible: Boolean(file?.isNewDraft || (file?.handle && file?.dirty)),
      disabled: !canSaveActiveFile.value,
      unsaved: Boolean(file?.dirty),
      iconOnly: true,
      handler: () => {
        if (canSaveActiveFile.value) {
          saveActiveFile(false);
        }
      },
    },
    {
      key: "external-copy",
      label: copied.value ? "Copied" : "Copy",
      iconPath: copied.value ? mdiCheck : mdiContentCopy,
      visible: Boolean(file),
      iconOnly: true,
      handler: copyActiveFile,
    },
    {
      key: "external-keep",
      label: keepingFile.value ? "Keeping..." : "Keep as note",
      iconPath: mdiCloudUploadOutline,
      visible: Boolean(file),
      disabled: keepingFile.value,
      iconOnly: true,
      handler: keepActiveFileAsNote,
    },
    {
      key: "external-choose",
      label: "Open",
      iconPath: mdiFolderOpenOutline,
      iconOnly: true,
      handler: chooseFile,
    },
    {
      key: "external-close",
      label: "Close",
      iconPath: mdiClose,
      visible: Boolean(file),
      iconOnly: true,
      handler: closeExternalFile,
    },
  ]);
  globalStore.setNoteMenuItems([]);
  globalStore.setNoteLayout({ kind: "markdown" });
}

function applyDocumentAutomation(content) {
  editorTextarea.value?.replaceContent?.(content);
}

async function keepActiveFileAsNote() {
  const file = activeFile.value;
  if (!file || keepingFile.value) {
    return;
  }

  const snapshot = buildLocalLibraryNote(file);
  keepingFile.value = true;
  try {
    const created = await createNote(
      snapshot.title,
      snapshot.content,
      snapshot.format,
    );
    toast.add(
      getToastOptions(
        "Local snapshot added to the LamaNotes library.",
        "Note Kept",
        "success",
      ),
    );
    if (file.isNewDraft) {
      clearLocalDraftState(file);
    }
    await router.push({
      name: "note",
      params: { title: created.title },
    });
  } catch (error) {
    if (error.response?.status === 409) {
      toast.add(
        getToastOptions(
          `A note named "${snapshot.title}" already exists. Nothing was overwritten.`,
          "Already Exists",
          "error",
        ),
      );
    } else {
      apiErrorHandler(error, toast);
    }
  } finally {
    keepingFile.value = false;
  }
}

async function chooseFile() {
  if (!confirmDiscardUnsavedChanges()) {
    return;
  }

  if (supportsNativeFileBridge()) {
    window.dispatchEvent(new CustomEvent("lamanotes:open-native-file-dialog"));
    return;
  }

  if (window.showOpenFilePicker) {
    try {
      const handles = await window.showOpenFilePicker({
        multiple: true,
        types: [
          {
            description: "Text and configuration files",
            accept: {
              "text/markdown": [".md"],
              "text/plain": [".txt", ".cfg", ".ini", ".log"],
              "text/csv": [".csv"],
              "application/x-tex": [".tex"],
              "application/json": [".json"],
              "application/yaml": [".yaml", ".yml"],
              "application/toml": [".toml"],
              "application/xml": [".xml"],
            },
          },
        ],
      });
      const selectedFiles = [];
      for (const handle of handles) {
        selectedFiles.push({
          file: await handle.getFile(),
          handle,
        });
      }
      await loadFiles(selectedFiles, "Loaded from local file picker.");
    } catch (error) {
      if (error?.name !== "AbortError") {
        showStatus("Could not open the local file.", "error");
        console.error(error);
      }
    }
    return;
  }

  fileInput.value?.click();
}

function closeExternalFile() {
  if (!confirmDiscardUnsavedChanges()) {
    return;
  }

  draftPersistence.cancel();
  closeFind({ restoreFocus: false });

  files.value.forEach((file) => {
    documentSession.clearDraft(file.draftStorageKey);
    if (file.isNewDraft) {
      localStorage.removeItem(localDraftNameKey(file.draftId));
    }
  });
  files.value = [];
  activeKey.value = null;
  compareOpen.value = false;
  statusMessage.value = "";
  clearDesktopFileSession();
  documentSession.leaveEdit();
  documentSession.setDirty(false);
  router.push({ name: "home" });
}

function activateFile(key) {
  if (key === activeKey.value) {
    return;
  }
  flushDraftPersistence();
  beginLocalLoad();
  closeFind({ restoreFocus: false });
  saveActiveScroll();
  documentSession.leaveEdit();
  activeKey.value = key;
  restoreActiveDraft();
  documentSession.setDirty(Boolean(activeFile.value?.dirty));
  restoreActiveScroll();
}

async function fileInputChanged(event) {
  if (!confirmDiscardUnsavedChanges()) {
    event.target.value = "";
    return;
  }

  await loadFiles([...event.target.files], "Loaded from local file picker.");
  event.target.value = "";
}

async function loadFiles(selectedFiles, message) {
  flushDraftPersistence();
  beginLocalLoad();
  closeFind({ restoreFocus: false });
  saveActiveScroll();
  const readableFiles = await Promise.all(selectedFiles.map(fileToPreview));

  files.value = readableFiles;
  activeKey.value = readableFiles[0]?.key || null;
  documentSession.leaveEdit();
  documentSession.setDirty(false);
  if (readableFiles.length) {
    restoreActiveDraft();
    showStatus(message);
    restoreActiveScroll();
    reportFileReady();
  }
}

function createLocalDraft(draftId) {
  const storageKey = `local:new:${draftId}`;
  if (activeFile.value?.draftStorageKey === storageKey) {
    return;
  }
  if (!confirmDiscardUnsavedChanges()) {
    return;
  }

  flushDraftPersistence();
  beginLocalLoad();
  closeFind({ restoreFocus: false });
  saveActiveScroll();
  const storedContent = documentSession.loadDraft(storageKey) || "";
  const storedName = localStorage.getItem(localDraftNameKey(draftId));
  const name = storedName || suggestedDraftName(storedContent);
  const file = {
    key: `draft:${draftId}`,
    name,
    path: "",
    size: new Blob([storedContent]).size,
    type: "text/markdown",
    extension: "md",
    handle: null,
    draftStorageKey: storageKey,
    content: "",
    draftContent: storedContent,
    largeFile: false,
    previewMode: "markdown",
    previewContent: storedContent,
    previewTruncated: false,
    previewMarkdown: storedContent,
    lastModified: Date.now(),
    encoding: "UTF-8",
    lineEnding: "LF",
    bom: false,
    version: "",
    dirty: Boolean(storedContent),
    draftRestored: true,
    externalState: "",
    externalChange: null,
    previewRevision: 0,
    isNewDraft: true,
    draftId,
  };

  files.value = [file];
  activeKey.value = file.key;
  clearDesktopFileSession();
  documentSession.setDirty(file.dirty);
  documentSession.enterEdit();
  showStatus("Local draft. Save to choose its Windows file.");
}

function localDraftNameKey(draftId) {
  return `lamanotes:local-draft-name:${draftId}`;
}

function suggestedDraftName(content = "") {
  const heading = String(content).match(
    /^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$/m,
  )?.[1];
  const title = String(heading || "New Note")
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 96);
  return `${title || "New Note"}.md`;
}

function clearLocalDraftState(file) {
  if (!file?.isNewDraft) {
    return;
  }
  documentSession.clearDraft(file.draftStorageKey);
  localStorage.removeItem(localDraftNameKey(file.draftId));
}

async function fileToPreview(selectedFile) {
  const { file, handle, nativePayload } = normalizeSelectedFile(selectedFile);
  const content =
    typeof nativePayload?.content === "string"
      ? nativePayload.content
      : await file.text();
  const nativeMetadata = nativePayload || handle?.metadata || {};
  const extension = getExtension(file.name);
  const largeFile = shouldUseLargeFileMode(content, file.size);
  const largePreview = largeFile
    ? buildLargeFilePreview(content)
    : { content, truncated: false };
  const previewMarkdown = largeFile
    ? ""
    : contentToPreviewMarkdown(content, extension, file.type);
  const previewMode = largeFile
    ? "plain"
    : extension === "csv"
      ? "csv"
      : isMarkdownFile(extension, file.type)
        ? "markdown"
        : "plain";

  return {
    key:
      handle?.id ||
      `${file.name}-${file.size}-${file.lastModified}-${Math.random()
        .toString(36)
        .slice(2)}`,
    name: file.name,
    path: nativeMetadata.path || handle?.path || "",
    size: file.size,
    type: file.type,
    extension,
    handle,
    draftStorageKey: localDraftStorageKey(file, handle),
    content,
    draftContent: content,
    largeFile,
    previewMode,
    previewContent: largePreview.content,
    previewTruncated: largePreview.truncated,
    previewMarkdown,
    lastModified: file.lastModified,
    encoding: nativeMetadata.encoding || "",
    lineEnding: nativeMetadata.lineEnding || "",
    bom: Boolean(nativeMetadata.bom),
    version: nativeMetadata.version || "",
    dirty: false,
    draftRestored: false,
    externalState: "",
    externalChange: null,
    previewRevision: 0,
  };
}

function localDraftStorageKey(file, handle) {
  const identity = handle?.id || `${file.name}:${file.lastModified}`;
  return `local:${identity}`;
}

function restoreActiveDraft() {
  const file = activeFile.value;
  if (!file || file.draftRestored) {
    return;
  }

  file.draftRestored = true;
  const draft = documentSession.loadDraft(file.draftStorageKey);
  if (draft == null || draft === file.content) {
    return;
  }

  file.draftContent = draft;
  file.dirty = true;
  refreshPreview(file);
  documentSession.setDirty(true);
  showStatus("Unsaved local draft restored.");
}

function normalizeSelectedFile(selectedFile) {
  if (selectedFile?.file) {
    return {
      file: selectedFile.file,
      handle: selectedFile.handle || null,
      nativePayload: selectedFile.nativePayload || null,
    };
  }

  return {
    file: selectedFile,
    handle: null,
    nativePayload: null,
  };
}

function contentToPreviewMarkdown(content, extension, type) {
  return isMarkdownFile(extension, type)
    ? compactLeadingMarkdownMetadata(content)
    : fencedCode(content, codeLanguageForExtension(extension));
}

function isMarkdownFile(extension, type) {
  return extension === "md" || type === "text/markdown";
}

function getExtension(filename = "") {
  const match = filename.toLowerCase().match(/\.([^.]+)$/);
  return match ? match[1] : "";
}

function escapeHtml(value = "") {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function stripInlineMarkdown(value = "") {
  return String(value)
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .trim();
}

function normalizeMetadataKey(key = "") {
  return stripInlineMarkdown(key)
    .replace(/[*_`]+/g, "")
    .replace(/^[-*\s]+/, "")
    .replace(/\s*\/\s*/g, "/")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function compactMetadataValue(key, value) {
  const normalizedKey = normalizeMetadataKey(key);
  const cleaned = stripInlineMarkdown(value);
  if (
    !cleaned ||
    normalizedKey === "original writer" ||
    normalizedKey === "writer"
  ) {
    return "";
  }

  if (normalizedKey === "domain") {
    return cleaned;
  }

  if (normalizedKey === "topic/subdomain") {
    return cleaned;
  }

  if (normalizedKey === "difficulty level") {
    return `difficulty ${cleaned}`;
  }

  if (normalizedKey === "tool use") {
    return `tools ${cleaned}`;
  }

  return "";
}

function compactLeadingMarkdownMetadata(markdown = "") {
  const normalized = String(markdown).replace(/\r\n?/g, "\n");
  const lines = normalized.split("\n");
  const firstHeadingIndex = lines.findIndex((line) => /^#{1,6}\s+/.test(line));
  if (firstHeadingIndex <= 0) {
    return markdown;
  }

  const leadingLines = lines.slice(0, firstHeadingIndex);
  const fieldPattern = /^\s*(?:[-*]\s+)?([^:\n]{2,48}):\s*(.+?)\s*$/;
  const fields = [];

  for (const line of leadingLines) {
    if (!line.trim()) {
      continue;
    }

    const match = line.match(fieldPattern);
    if (!match) {
      return markdown;
    }

    fields.push({ key: match[1], value: match[2] });
  }

  if (!fields.length) {
    return markdown;
  }

  const metaValues = fields
    .map((field) => compactMetadataValue(field.key, field.value))
    .filter(Boolean);
  const rest = lines.slice(firstHeadingIndex).join("\n").trimStart();
  if (!metaValues.length) {
    return rest;
  }

  const metaLine = metaValues.map(escapeHtml).join(" | ");
  return `<p class="lamanotes-external-meta-line"><strong>Meta</strong> ${metaLine}</p>\n\n${rest}`;
}

function fencedCode(content = "", language = "") {
  const fence = "```";
  const safeContent = String(content).replace(/```/g, "`` `");
  return `${fence}${language}\n${safeContent}\n${fence}\n`;
}

function noteTitleForFile(file) {
  const stem = file.name.replace(/\.[^.]+$/, "").trim() || "External file";
  return sanitizeTitle(stem);
}

function sanitizeTitle(value = "") {
  const title = value
    .replace(/[<>:"/\\|?*]/g, "-")
    .replace(/\s+/g, " ")
    .trim();
  return title || "External file";
}

function codeLanguageForExtension(extension = "") {
  if (extension === "ini" || extension === "cfg") {
    return "ini";
  }

  if (
    ["json", "yaml", "yml", "toml", "xml", "csv", "tex"].includes(extension)
  ) {
    return extension === "yml" ? "yaml" : extension;
  }

  return "";
}

function markActiveFileDirty() {
  const file = activeFile.value;
  if (!file) {
    return;
  }

  file.dirty = file.isNewDraft
    ? Boolean(file.draftContent)
    : file.draftContent !== file.content;
  documentSession.setDirty(file.dirty);
  draftPersistence.schedule(file);
}

function persistDraftState(file) {
  if (!file) {
    return;
  }
  if (file.isNewDraft) {
    const nextName = suggestedDraftName(file.draftContent);
    file.name = nextName;
    file.size = new Blob([file.draftContent]).size;
    localStorage.setItem(localDraftNameKey(file.draftId), nextName);
  }
  if (file.dirty) {
    documentSession.saveDraft(file.draftContent, file.draftStorageKey);
  } else {
    documentSession.clearDraft(file.draftStorageKey);
  }
}

function flushDraftPersistence() {
  draftPersistence.flush();
}

function activeFileChangedHandler() {
  markActiveFileDirty();
  documentFindContentChanged();
}

function openFileEditorReadyHandler() {
  reportEditorReady();
  if (!findVisible.value) {
    return;
  }
  window.requestAnimationFrame(() => {
    refreshDocumentFind();
    nextTick(() => findBar.value?.focusSelect?.());
  });
}

function refreshPreview(file) {
  file.largeFile = shouldUseLargeFileMode(file.draftContent, file.size);
  const largePreview = file.largeFile
    ? buildLargeFilePreview(file.draftContent)
    : { content: file.draftContent, truncated: false };
  file.previewMode = file.largeFile
    ? "plain"
    : file.extension === "csv"
      ? "csv"
      : isMarkdownFile(file.extension, file.type)
        ? "markdown"
        : "plain";
  file.previewContent = largePreview.content;
  file.previewTruncated = largePreview.truncated;
  file.previewMarkdown = file.largeFile
    ? ""
    : contentToPreviewMarkdown(file.draftContent, file.extension, file.type);
  file.previewRevision += 1;
}

function setEditMode(value) {
  if (value) {
    documentSession.enterEdit();
  } else {
    documentSession.leaveEdit();
  }
}

function finishEditing() {
  if (!activeFile.value) {
    return;
  }
  if (activeFile.value.dirty) {
    saveActiveFile(true);
  } else {
    documentSession.leaveEdit();
  }
}

function saveActiveFile(close = false, options = {}) {
  return documentSession.save({ close, ...options });
}

async function persistActiveFile({ force = false } = {}) {
  flushDraftPersistence();
  const file = activeFile.value;
  if (!file) {
    return false;
  }

  if (!file.handle && file.isNewDraft && supportsNativeFileBridge()) {
    const payload = await window.pywebview.api.create_native_file(
      file.name,
      file.draftContent,
    );
    if (payload?.cancelled) {
      return false;
    }
    if (!payload?.ok) {
      throw new Error(payload?.error || "The local file could not be created.");
    }
    const selectedFile = fileFromNativePayload(payload);
    if (!selectedFile) {
      throw new Error("The created local file could not be reopened.");
    }
    const savedFile = await fileToPreview(selectedFile);
    clearLocalDraftState(file);
    files.value = files.value.map((candidate) =>
      candidate.key === file.key ? savedFile : candidate,
    );
    activeKey.value = savedFile.key;
    refreshPreview(savedFile);
    return selectedFile.file;
  }

  if (!file.handle) {
    const error = new Error("Read-only: no writable file handle.");
    error.code = "read-only";
    throw error;
  }

  const savedFile = await localFileStorageAdapter.save({
    handle: file.handle,
    content: file.draftContent,
    force,
  });
  const nativeMetadata = file.handle?.metadata || {};
  file.content = file.draftContent;
  file.size = savedFile.size;
  file.lastModified = savedFile.lastModified;
  file.encoding = nativeMetadata.encoding || file.encoding;
  file.lineEnding = nativeMetadata.lineEnding || file.lineEnding;
  file.version = nativeMetadata.version || file.version;
  file.dirty = false;
  file.externalState = "";
  file.externalChange = null;
  compareOpen.value = false;
  refreshPreview(file);
  return savedFile;
}

function handleActiveFileSaveError(error) {
  if (error?.code === "external-conflict" && activeFile.value) {
    activeFile.value.externalState = "conflict";
    activeFile.value.externalChange = error.external;
    statusMessage.value = "";
  } else if (error?.code === "external-deleted" && activeFile.value) {
    activeFile.value.externalState = "deleted";
    statusMessage.value = "";
  } else if (error?.code === "permission-denied") {
    showStatus("Save permission denied.", "error");
  } else if (error?.code === "read-only") {
    showStatus(error.message, "error");
  } else {
    showStatus("Could not save to the original file.", "error");
  }
  console.error(error);
}

function confirmDiscardUnsavedChanges() {
  if (!files.value.some((file) => file.dirty)) {
    return true;
  }

  return window.confirm("Discard unsaved external file changes?");
}

function persistDesktopFiles() {
  const nativeFiles = files.value.filter((file) => file.path);
  if (!nativeFiles.length) {
    if (files.value.some((file) => file.isNewDraft)) {
      clearDesktopFileSession();
    }
    return;
  }
  saveDesktopFileSession({
    files: nativeFiles,
    activePath: activeFile.value?.path,
    editMode: editMode.value,
  });
}

function restoreLaunchSession(session) {
  if (!session) {
    return;
  }
  const restoredActive = files.value.find(
    (file) => file.path === session.activePath,
  );
  if (restoredActive) {
    activeKey.value = restoredActive.key;
    restoreActiveDraft();
    documentSession.setDirty(Boolean(restoredActive.dirty));
  }
  if (session.editMode && activeFile.value) {
    documentSession.enterEdit();
  }
  restoreActiveScroll();
}

function activeScrollStorageKey() {
  const identity = activeFile.value?.path || activeFile.value?.draftStorageKey;
  return identity ? `lamanotes:document-scroll:${identity}` : "";
}

function scheduleActiveScrollSave() {
  window.clearTimeout(scrollSaveTimer);
  scrollSaveTimer = window.setTimeout(saveActiveScroll, 120);
}

function saveActiveScroll() {
  const key = activeScrollStorageKey();
  if (key) {
    localStorage.setItem(key, String(Math.max(0, window.scrollY || 0)));
  }
}

function restoreActiveScroll() {
  const key = activeScrollStorageKey();
  const position = key ? Number(localStorage.getItem(key)) || 0 : 0;
  nextTick(() => window.scrollTo({ top: position, behavior: "instant" }));
}

function startNativeWatcher() {
  if (!supportsNativeFileBridge() || nativeWatcherTimer) {
    return;
  }
  nativeWatcherTimer = window.setInterval(pollNativeFileChanges, 1200);
}

async function pollNativeFileChanges() {
  if (
    document.hidden ||
    nativeWatcherBusy ||
    !files.value.some((file) => file.handle?.id)
  ) {
    return;
  }
  nativeWatcherBusy = true;
  try {
    const changes = await window.pywebview.api.poll_native_file_changes();
    for (const change of changes || []) {
      const file = files.value.find((item) => item.handle?.id === change.id);
      if (!file) {
        continue;
      }
      if (change.deleted) {
        file.externalState = "deleted";
        file.externalChange = null;
        continue;
      }
      if (file.dirty) {
        file.externalState = "conflict";
        file.externalChange = change;
        continue;
      }
      applyNativePayload(file, change);
    }
  } catch (error) {
    console.debug("Native file watcher unavailable", error);
  } finally {
    nativeWatcherBusy = false;
  }
}

function nativeWatcherVisibilityChanged() {
  if (!document.hidden) {
    void pollNativeFileChanges();
  }
}

function applyNativePayload(file, payload) {
  if (!file || !payload || typeof payload.content !== "string") {
    return;
  }
  file.handle?.applyPayload?.(payload);
  file.name = payload.name || file.name;
  file.path = payload.path || file.path;
  file.size = payload.size ?? file.size;
  file.type = payload.type || file.type;
  file.extension = payload.extension || file.extension;
  file.lastModified = payload.lastModified || file.lastModified;
  file.encoding = payload.encoding || file.encoding;
  file.lineEnding = payload.lineEnding || file.lineEnding;
  file.bom = Boolean(payload.bom);
  file.version = payload.version || file.version;
  file.content = payload.content;
  file.draftContent = payload.content;
  file.dirty = false;
  file.externalState = "";
  file.externalChange = null;
  documentSession.clearDraft(file.draftStorageKey);
  if (file === activeFile.value) {
    documentSession.setDirty(false);
  }
  refreshPreview(file);
}

async function reloadActiveFromDisk() {
  const file = activeFile.value;
  if (!file?.path) {
    return;
  }
  let payload = file.externalChange;
  if (!payload) {
    const payloads = await window.pywebview.api.restore_native_files([
      file.path,
    ]);
    payload = payloads?.[0];
  }
  if (!payload) {
    file.externalState = "deleted";
    return;
  }
  applyNativePayload(file, payload);
  compareOpen.value = false;
  showStatus("Reloaded current file from disk.");
}

async function overwriteExternalVersion() {
  const saved = await saveActiveFile(false, { force: true });
  if (saved) {
    compareOpen.value = false;
  }
}

async function consumeExternalLaunch(launch) {
  if (!launch || lastConsumedLaunchId.value === launch.id) {
    return;
  }

  lastConsumedLaunchId.value = launch.id;
  if (launch.files?.length) {
    if (!confirmDiscardUnsavedChanges()) {
      return;
    }

    await loadFiles(launch.files, launch.message || "Opened from Windows.");
    restoreLaunchSession(launch.restoreSession);
    return;
  }

  showStatus(
    launch.message || "Could not open the file.",
    launch.tone || "error",
  );
}

function getActiveFileCopyPayload() {
  if (!activeFile.value) {
    return null;
  }

  const file = activeFile.value;
  const isMarkdown = file.extension === "md" || file.type === "text/markdown";
  const content = file.draftContent ?? file.content;
  return { type: isMarkdown ? "markdown" : "text", content };
}

function copyActiveFile() {
  return documentSession.copy("source");
}

function documentKeydownHandler(event) {
  documentSession.keydownHandler(event);
}

function reportEditorReady() {
  if (lastEditorReadyGeneration === localLoadGeneration) {
    return;
  }
  lastEditorReadyGeneration = localLoadGeneration;
  performance.mark("lamanotes-editor-ready");
  reportLocalReady("editor");
}

function beginLocalLoad() {
  localLoadStartedAt = performance.now();
  localLoadGeneration += 1;
}

function reportFileReady() {
  const generation = localLoadGeneration;
  nextTick(() => {
    window.requestAnimationFrame(() => {
      if (
        generation !== localLoadGeneration ||
        lastFileReadyGeneration === generation
      ) {
        return;
      }
      lastFileReadyGeneration = generation;
      performance.mark("lamanotes-file-ready");
      reportLocalReady("file");
    });
  });
}

function reportLocalReady(phase) {
  reportNativeReady({
    phase,
    route: router.currentRoute.value.fullPath,
    browserMs: Math.round(performance.now()),
    routeMs: Math.round(performance.now() - localLoadStartedAt),
    fileBytes: activeFile.value?.size || 0,
    loadId: localLoadGeneration,
  });
}

function formatBytes(bytes = 0) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function showStatus(message, tone = "info") {
  statusMessage.value = message;
  statusTone.value = tone;
}
</script>

<style scoped>
.lamanotes-open-file {
  width: min(100%, 68rem);
  margin-inline: auto;
}

.lamanotes-open-file-heading {
  min-width: 0;
  max-width: 100%;
  margin-bottom: 0.68rem;
}

.lamanotes-open-file-heading-desktop {
  margin-bottom: 0.38rem;
}

.lamanotes-open-file-heading-desktop .lamanotes-open-file-kicker-line {
  margin-bottom: 0;
}

.lamanotes-open-file-kicker-line {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.32rem;
  margin-bottom: 0.22rem;
}

.lamanotes-open-file-kicker {
  display: inline-flex;
  align-items: center;
  gap: 0.18rem;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 1;
  text-transform: uppercase;
}

.lamanotes-open-file-title {
  display: block;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgb(var(--theme-text));
  font-size: clamp(1.18rem, 4.2vw, 1.5rem);
  line-height: 1.15;
}

.lamanotes-large-file-note {
  margin: 0;
  border-top: 1px solid rgb(var(--theme-border) / 0.72);
  padding: 0.42rem 0.1rem;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.68rem;
  line-height: 1.3;
}

.lamanotes-open-file-strip {
  display: flex;
  min-height: 1.42rem;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.28rem;
  margin-bottom: 0.58rem;
  color: rgb(var(--theme-text-muted));
  font-size: 0.76rem;
  line-height: 1.1;
}

.lamanotes-open-file-status,
.lamanotes-open-file-meta {
  display: inline-flex;
  min-height: 1.18rem;
  align-items: center;
  gap: 0.22rem;
  border-radius: 999px;
  padding: 0 0.38rem;
  line-height: 1;
}

.lamanotes-open-file-status {
  color: rgb(var(--theme-text));
}

.lamanotes-open-file-status-error {
  color: rgb(var(--theme-danger));
}

.lamanotes-open-file-conflict {
  display: flex;
  min-height: 1.82rem;
  align-items: center;
  gap: 0.42rem;
  margin: 0 0 0.62rem;
  border-block: 1px solid rgb(var(--theme-danger) / 0.46);
  padding: 0.3rem 0.08rem;
  color: rgb(var(--theme-danger));
  font-size: 0.72rem;
  line-height: 1.25;
}

.lamanotes-open-file-conflict button,
.lamanotes-file-compare button {
  display: inline-grid;
  width: 1.65rem;
  height: 1.65rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgb(var(--theme-border));
  border-radius: 4px;
  color: rgb(var(--theme-text-muted));
  background: transparent;
}

.lamanotes-open-file-conflict button:hover,
.lamanotes-file-compare button:hover {
  border-color: rgb(var(--theme-text-muted));
  color: rgb(var(--theme-text));
}

.lamanotes-open-file-meta {
  border: 1px solid rgb(var(--theme-border));
  background-color: rgb(var(--theme-background-elevated) / 0.45);
  font-size: 0.72rem;
}

.lamanotes-open-file-meta span {
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.62rem;
  font-weight: 700;
  text-transform: uppercase;
}

.lamanotes-open-file-meta strong {
  color: rgb(var(--theme-text));
  font-weight: 600;
}

.lamanotes-open-file-plain-preview {
  margin: 0;
  min-height: min(58vh, 38rem);
  overflow-x: auto;
  white-space: pre-wrap;
  border-top: 1px solid rgb(var(--theme-border));
  border-bottom: 1px solid rgb(var(--theme-border));
  padding: 0.7rem 0;
  color: rgb(var(--theme-text));
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace;
  font-size: 0.86rem;
  line-height: 1.5;
}

:deep(.lamanotes-external-meta-line) {
  max-width: 100%;
  margin: 0 0 0.7rem 0 !important;
  color: rgb(var(--theme-text-muted));
  font-size: 0.8rem;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.lamanotes-external-meta-line strong) {
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.lamanotes-open-file
  :deep(.toastui-editor-contents:not(.lamanotes-html-contents) h1) {
  font-size: 1.42rem;
}

.lamanotes-open-file
  :deep(.toastui-editor-contents:not(.lamanotes-html-contents) h2) {
  font-size: 1.22rem;
}

.lamanotes-open-file
  :deep(.toastui-editor-contents:not(.lamanotes-html-contents) h3) {
  font-size: 1.08rem;
}

.lamanotes-file-compare-backdrop {
  position: fixed;
  z-index: 80;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: rgb(0 0 0 / 0.62);
}

.lamanotes-file-compare {
  display: grid;
  width: min(64rem, 100%);
  max-height: min(84vh, 50rem);
  overflow: hidden;
  border: 1px solid rgb(var(--theme-border));
  border-radius: 6px;
  color: rgb(var(--theme-text));
  background: rgb(var(--theme-background));
  box-shadow: 0 1rem 3rem rgb(0 0 0 / 0.32);
}

.lamanotes-file-compare header {
  display: flex;
  min-height: 2.4rem;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  border-bottom: 1px solid rgb(var(--theme-border));
  padding: 0.35rem 0.55rem 0.35rem 0.75rem;
  font-size: 0.82rem;
}

.lamanotes-file-compare-grid {
  display: grid;
  min-height: 0;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.lamanotes-file-compare-grid > div {
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-rows: auto 1fr;
}

.lamanotes-file-compare-grid > div + div {
  border-left: 1px solid rgb(var(--theme-border));
}

.lamanotes-file-compare-grid span {
  padding: 0.35rem 0.65rem;
  color: rgb(var(--theme-text-muted));
  background: rgb(var(--theme-background-elevated) / 0.52);
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
}

.lamanotes-file-compare-grid pre {
  min-width: 0;
  overflow: auto;
  margin: 0;
  padding: 0.7rem;
  color: rgb(var(--theme-text));
  background: transparent;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace;
  font-size: 0.74rem;
  line-height: 1.48;
  white-space: pre-wrap;
}

@media (max-width: 720px) {
  .lamanotes-file-compare-grid {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }

  .lamanotes-file-compare-grid > div + div {
    border-top: 1px solid rgb(var(--theme-border));
    border-left: 0;
  }

  .lamanotes-file-compare-grid pre {
    max-height: 34vh;
  }
}
</style>
