<template>
  <!-- Confirm Deletion Modal -->
  <ConfirmModal
    v-model="isDeleteModalVisible"
    title="Confirm Deletion"
    :message="`Are you sure you want to delete the note '${note.title}'?`"
    confirmButtonText="Delete"
    confirmButtonStyle="danger"
    @confirm="deleteConfirmedHandler"
  />

  <PublishNoteModal
    v-model="isPublishModalVisible"
    :suggested-slug="publication?.suggestedSlug || ''"
    :busy="publishBusy"
    :problem-message="publishProblemMessage"
    :quality-warning="publicationQualityWarning"
    @publish="publishConfirmedHandler"
  />

  <ConfirmModal
    v-model="conflictVisible"
    title="Note changed elsewhere"
    message="Your edits are still here. Use latest replaces them with the current Library version. Keep mine overwrites the version just loaded from the Library."
    confirmButtonText="Keep mine"
    confirmButtonStyle="danger"
    rejectButtonText="Use latest"
    rejectButtonStyle="subtle"
    cancelButtonText="Keep editing"
    @confirm="keepConflictEdits"
    @reject="useLatestVersion"
  />

  <ConfirmModal
    v-model="isUpdateModalVisible"
    title="Update online"
    :message="publicationUpdateMessage"
    confirmButtonText="Update"
    confirmButtonStyle="cta"
    @confirm="startPublication()"
  />

  <!-- Save Changes Modal -->
  <ConfirmModal
    v-model="isSaveChangesModalVisible"
    title="Save Changes"
    message="Do you want to save your changes?"
    confirmButtonText="Save"
    confirmButtonStyle="success"
    rejectButtonText="Discard"
    rejectButtonStyle="danger"
    @confirm="saveNoteDecision"
    @reject="discardNoteDecision"
    @cancel="cancelNoteDecision"
  />

  <!-- Draft Modal -->
  <ConfirmModal
    v-model="isDraftModalVisible"
    title="Draft Detected"
    message="There is an unsaved draft of this note stored in this browser. Do you want to resume the draft version or delete it?"
    confirmButtonText="Resume Draft"
    confirmButtonStyle="cta"
    rejectButtonText="Delete Draft"
    rejectButtonStyle="danger"
    @confirm="setEditMode()"
    @reject="
      documentSession.clearDraft();
      setEditMode();
    "
  />

  <LoadingIndicator
    ref="loadingIndicator"
    :class="[
      'lamanotes-note-shell flex h-full min-w-0 max-w-full flex-col',
      {
        'lamanotes-document-find-open': findVisible,
        'lamanotes-note-shell-wide': isWideDashboardNote,
        'lamanotes-note-shell-work': noteLayoutKind === 'work',
        'lamanotes-note-shell-article': noteLayoutKind === 'article',
        'lamanotes-note-shell-markdown': noteLayoutKind === 'markdown',
      },
    ]"
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
      :language="automationLanguage"
      @apply="applyDocumentAutomation"
    />

    <!-- Header -->
    <div class="min-w-0 max-w-full">
      <!-- Title -->
      <div
        v-if="editMode || !desktopShell.enabled"
        class="lamanotes-note-title-row"
      >
        <div class="lamanotes-note-title-text">
          <span v-show="!editMode" :title="note.title">{{ note.title }}</span>
          <input
            v-show="editMode"
            v-model.trim="newTitle"
            class="w-full bg-theme-background outline-none"
            placeholder="Title"
          />
        </div>
      </div>
    </div>

    <hr
      v-if="!editMode && !desktopShell.enabled"
      class="lamanotes-note-title-rule border-theme-border"
    />

    <!-- Content -->
    <div
      ref="noteContent"
      class="lamanotes-note-content min-w-0 max-w-full flex-1"
      @dblclick="noteContentDblClickHandler"
      @pointerup="noteContentPointerUpHandler"
    >
      <ToastViewer
        v-if="!editMode && (!isHtmlFormat || isTextNote)"
        :initialValue="
          isTextNote
            ? extractTextMarkdown(note.content, note.title)
            : note.content
        "
        :enhance-note-lead="!isTextNote"
        :class="{
          'lamanotes-share-quicknotes':
            isTextNote && hasSharedQuicknotes(note.content),
        }"
        :note-title="note.title"
        :task-checkboxes-disabled="!canModify"
        :task-checkbox-toggle-handler="toggleTaskCheckbox"
        :task-item-add-handler="addTaskItem"
        :task-section-edit-handler="editTaskSection"
        class="toast-viewer min-w-0 max-w-full pb-4"
      />
      <WorkNoteViewer
        v-else-if="!editMode && isWorkNote"
        :initialValue="note.content"
        :note-title="note.title"
        :task-checkboxes-disabled="!canModify"
        :task-checkbox-toggle-handler="toggleTaskCheckbox"
        :task-item-add-handler="addTaskItem"
        :task-section-edit-handler="editTaskSection"
      />
      <HtmlViewer
        v-else-if="!editMode && isHtmlFormat && !isWorkNote"
        :initialValue="note.content"
        :note-title="note.title"
        :task-checkboxes-disabled="!canModify"
        :task-checkbox-toggle-handler="toggleTaskCheckbox"
        :task-item-add-handler="addTaskItem"
        :task-section-edit-handler="editTaskSection"
        class="toast-viewer min-w-0 max-w-full pb-4"
      />
      <SourceEditor
        v-else-if="editMode && editorFormat === 'markdown'"
        ref="contentEditor"
        :initialValue="editorInitialValue"
        language="markdown"
        :show-line-numbers="globalStore.showLineNumbers"
        :normalize-tags="true"
        :structured-paste="true"
        :session-key="`cloud:${newTitle || note.title || 'new'}`"
        :session-state="editorMemory"
        :aria-label="`Edit ${newTitle || note.title || 'note'}`"
        :addImageBlobHook="addImageBlobHook"
        @change="editorContentChangedHandler"
        @keydown="keydownHandler"
        @ready="editorReadyHandler"
      />
      <WorkNoteEditor
        v-else-if="editMode && editorFormat === 'html' && editorKind === 'work'"
        :key="editorKey"
        ref="contentEditor"
        :current-kind="editorKind"
        :session-state="editorMemory"
        :initialValue="editorInitialValue"
        :note-title="newTitle"
        :addImageBlobHook="addImageBlobHook"
        :show-line-numbers="globalStore.showLineNumbers"
        :show-kind-switch="isNewNote"
        @change="editorContentChangedHandler"
        @keydown="keydownHandler"
        @ready="editorReadyHandler"
        @set-kind="setNewNoteKind"
      />
      <TextNoteEditor
        v-else-if="editMode && editorFormat === 'html' && editorKind === 'text'"
        :key="editorKey"
        ref="contentEditor"
        :session-state="editorMemory"
        :initial-value="editorInitialValue"
        :note-title="newTitle"
        :add-image-blob-hook="addImageBlobHook"
        @change="editorContentChangedHandler"
        @keydown="keydownHandler"
        @ready="editorReadyHandler"
      />
      <HtmlEditor
        v-else-if="
          editMode && editorFormat === 'html' && editorKind === 'article'
        "
        :key="editorKey"
        ref="contentEditor"
        :current-kind="editorKind"
        :session-state="editorMemory"
        :initialValue="editorInitialValue"
        :note-title="newTitle"
        :addImageBlobHook="addImageBlobHook"
        :show-kind-switch="isNewNote"
        @change="editorContentChangedHandler"
        @keydown="keydownHandler"
        @ready="editorReadyHandler"
        @set-kind="setNewNoteKind"
      />
    </div>
  </LoadingIndicator>
</template>

<script setup>
import {
  mdiCloudUploadOutline,
  mdiImageMultipleOutline,
  mdiCodeTags,
  mdiCogOutline,
  mdiContentCopy,
  mdiLanguageHtml5,
  mdiLinkVariant,
  mdiNoteOffOutline,
  mdiOpenInNew,
  mdiStar,
  mdiStarOutline,
  mdiSync,
  mdiTextBoxOutline,
  mdiWeb,
} from "@mdi/js";
import {
  mdilCheck,
  mdilContentSave,
  mdilDelete,
  mdilPencil,
} from "@mdi/light-js";
import { useToast } from "../toastStore.js";
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
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRouter } from "vue-router";

import {
  apiErrorHandler,
  createAttachment,
  createNote,
  deleteNote,
  getNote,
  getNotePublication,
  libraryNoteDeletedEvent,
  libraryNoteUpdatedEvent,
  publishNote,
  updateNote,
} from "../api.js";
import { Note } from "../classes.js";
import ConfirmModal from "../components/ConfirmModal.vue";
import DocumentFindBar from "../components/DocumentFindBar.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import PublishNoteModal from "../components/PublishNoteModal.vue";
import { findHtmlPlaceholderWarnings } from "../components/html/componentKit.js";
import {
  buildWorkNoteHtml,
  extractWorkMarkdown,
  htmlChecklistToWorkMarkdown,
  isChecklistNoteHtml,
  isWorkNoteHtml,
} from "../components/work/workNote.js";
import { authTypes } from "../constants.js";
import { useDocumentSession } from "../documents/documentSession.js";
import { appendMarkdownTask, toggleMarkdownTask } from "../checklists.js";
import {
  appendChecklistSectionItem,
  readChecklistSection,
  replaceChecklistSection,
} from "../checklistSections.js";
import {
  buildTextNoteHtml,
  extractTextMarkdown,
  hasSharedQuicknotes,
  isTextNoteHtml,
} from "../components/text/textNote.js";
import { createVpsNoteStorageAdapter } from "../documents/storageAdapters.js";
import { useDocumentFind } from "../documentFind.js";
import { desktopShell, setDesktopWindowTitle } from "../desktopShell.js";
import { useGlobalStore } from "../globalStore.js";
import { getToastOptions } from "../helpers.js";
import { isEditableShortcutTarget, isPlainKey } from "../keyboardShortcuts.js";
import { isCurrentTokenStored } from "../tokenStorage.js";
import {
  isPublicationPending,
  publicationPollDelay,
  publicationProblemMessage,
  publicationToolbarMode,
} from "../publicationState.js";
import {
  documentHasSystemTag,
  getLamaNotesMetaTags,
  isSystemTag,
  setDocumentSystemTag,
  synchronizeDocumentTags,
} from "../noteSystemTags.js";

const HtmlEditor = defineAsyncComponent(
  () => import("../components/html/HtmlEditor.vue"),
);
const DocumentAutomationModal = defineAsyncComponent(
  () => import("../components/DocumentAutomationModal.vue"),
);
const HtmlViewer = defineAsyncComponent(
  () => import("../components/html/HtmlViewer.vue"),
);
const SourceEditor = defineAsyncComponent(
  () => import("../components/editor/SourceEditor.vue"),
);
const ToastViewer = defineAsyncComponent(
  () => import("../components/toastui/ToastViewer.vue"),
);
const WorkNoteEditor = defineAsyncComponent(
  () => import("../components/work/WorkNoteEditor.vue"),
);
const WorkNoteViewer = defineAsyncComponent(
  () => import("../components/work/WorkNoteViewer.vue"),
);
const TextNoteEditor = defineAsyncComponent(
  () => import("../components/text/TextNoteEditor.vue"),
);

const props = defineProps({
  title: String,
  initialTitle: String,
});

const canModify = computed(
  () => globalStore.config.authType != authTypes.readOnly,
);
const isHtmlFormat = computed(() => (note.value.format || "html") === "html");
const isWorkNote = computed(
  () => isHtmlFormat.value && isWorkNoteHtml(note.value.content || ""),
);
const isTextNote = computed(
  () => isHtmlFormat.value && isTextNoteHtml(note.value.content || ""),
);
const isWideDashboardNote = computed(
  () =>
    isHtmlFormat.value &&
    /class=["'][^"']*\b(?:nirv-dashboard-v[345]|nirv-board)\b/.test(
      note.value.content || "",
    ),
);
const noteLayoutKind = computed(() => {
  if (isWideDashboardNote.value) {
    return "dashboard";
  }
  if (editMode.value) {
    return "editor";
  }
  if (isWorkNote.value) {
    return "work";
  }
  if (isTextNote.value) return "markdown";
  if (isHtmlFormat.value) {
    return "article";
  }
  return "markdown";
});
let contentChangedTimeout = null;
let noteLoadStartedAt = performance.now();
const contentEditor = ref();
const automationVisible = ref(false);
const automationSource = ref("");
const editorKey = ref(0);
const editorFormat = ref("html");
const editorKind = ref("work");
const globalStore = useGlobalStore();
const isSaveChangesModalVisible = ref(false);
const isDeleteModalVisible = ref(false);
const isDraftModalVisible = ref(false);
const isNewNote = computed(() => !props.title);
const loadingIndicator = ref();
const note = ref({});
const noteContent = ref();
const pinBusy = ref(false);
const publication = ref(null);
const isPublishModalVisible = ref(false);
const isUpdateModalVisible = ref(false);
const publishBusy = ref(false);
const publishProblem = ref(null);
const publishProblemMessage = computed(() =>
  publishProblem.value ? publicationProblemMessage(publishProblem.value) : "",
);
const publicationMode = computed(() =>
  publicationToolbarMode(publication.value),
);
const publicationQualityWarning = computed(() => {
  if (!isHtmlFormat.value || isWorkNote.value) {
    return "";
  }
  const warnings = findHtmlPlaceholderWarnings(note.value.content || "");
  return warnings.length
    ? `Likely template placeholders remain: ${warnings
        .map(({ label }) => label)
        .join(", ")}.`
    : "";
});
const publicationUpdateMessage = computed(() => {
  const message = `Replace ${
    publication.value?.canonicalUrl || "the public page"
  } with the current saved note?`;
  return publicationQualityWarning.value
    ? `${message} ${publicationQualityWarning.value}`
    : message;
});
let publicationPollTimer = null;
let publicationPollAttempt = 0;
let publicationRequestSequence = 0;
let pendingNoteDecision = null;
let updatingSavedRoute = false;
const isPinned = computed(() =>
  documentHasSystemTag(
    note.value.content || "",
    "pinned",
    note.value.format || "html",
  ),
);
const canAutomateNote = computed(
  () =>
    editMode.value &&
    (editorFormat.value === "markdown" ||
      (editorFormat.value === "html" &&
        ["work", "text"].includes(editorKind.value))),
);
const automationLanguage = computed(() =>
  canAutomateNote.value ? "markdown" : "text",
);
const reservedFilenameCharacters = /[<>:"/\\|?*]/;
const router = useRouter();
const newTitle = ref();
const editorMemory = {};
const editorInitialValue = ref("");
const conflictVisible = ref(false);
let conflictLatest = null;
let conflictContent = null;
const toast = useToast();
const noteStorageAdapter = createVpsNoteStorageAdapter({
  create: createNote,
  update: updateNote,
});
const documentSession = useDocumentSession({
  canEdit: () => canModify.value,
  hasDocument: true,
  requestEdit: editHandler,
  requestClose: closeHandler,
  focusEditor,
  draftKey: () =>
    isNewNote.value
      ? "vps:new"
      : `vps:${note.value.title || props.title || "note"}`,
  legacyDraftKeys: () => [note.value.title],
  persistDraft: () => isCurrentTokenStored(),
  saveDocument: persistNote,
  getSnapshot: () =>
    JSON.stringify([newTitle.value, editorFormat.value, getEditorContent()]),
  onPendingEdits: contentChangedHandler,
  copyDocument: getCopyPayload,
  afterSave: noteSaveSuccess,
  onSaveError: noteSaveFailure,
  afterCopy: ({ kind }) => {
    const copyKind = kind === "default" ? getDefaultCopyKind() : kind;
    toast.add(getToastOptions(getCopyLabel(copyKind), "Copied", "success"));
  },
  onCopyError: () => {
    toast.add(
      getToastOptions("Could not copy this note.", "Copy Failed", "error"),
    );
  },
});
const editMode = documentSession.editMode;
const unsavedChanges = documentSession.dirty;
const noteContentDblClickHandler = documentSession.contentDblClickHandler;
const noteContentPointerUpHandler = documentSession.contentPointerUpHandler;

onBeforeRouteLeave(confirmNoteNavigation);
onBeforeRouteUpdate(confirmNoteNavigation);
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
  getEditorText: () => contentEditor.value?.getSearchText?.() || "",
  selectEditorRange: (from, to) =>
    contentEditor.value?.selectSearchRange?.(from, to),
  setEditorMatches: (matches, currentIndex) =>
    contentEditor.value?.setSearchMatches?.(matches, currentIndex),
  getViewRoot: () => noteContent.value,
});

function init() {
  // Return if we already have the note e.g. When we rename a note, the route prop would change but we’d already have the note.
  if (props.title && props.title == note.value.title) {
    return;
  }

  resetPublicationState();
  editorMemory.snapshot = null;
  noteLoadStartedAt = performance.now();
  loadingIndicator.value.setLoading();
  if (props.title) {
    getNote(props.title)
      .then((data) => {
        note.value = data;
        loadingIndicator.value.setLoaded();
        markNoteReady();
        void loadPublicationState();
      })
      .catch((error) => {
        if (error.response?.status === 404) {
          loadingIndicator.value.setFailed("Note not found", mdiNoteOffOutline);
        } else {
          loadingIndicator.value.setFailed();
          apiErrorHandler(error, toast);
        }
      });
  } else {
    newTitle.value = getInitialNewTitle();
    note.value = new Note();
    editorFormat.value = "html";
    editorKind.value = loadNewNoteKind();
    // Set the editMode to false to close any existing editors.
    // This ensures the editor is cleanly reinitialised in an empty state.
    // Simple fix for #266 without requiring a full re-work of the logic.
    editMode.value = false;
    nextTick(() => {
      editHandler();
      loadingIndicator.value.setLoaded();
    });
  }
}

function cachedNoteUpdatedHandler(event) {
  const updated = event.detail;
  if (
    !updated?.title ||
    updated.title !== props.title ||
    editMode.value ||
    unsavedChanges.value
  ) {
    return;
  }
  if (
    updated.lastModified === note.value.lastModified &&
    updated.content === note.value.content
  ) {
    return;
  }
  note.value = new Note(updated);
  void loadPublicationState();
}

function cachedNoteDeletedHandler(event) {
  if (
    event.detail?.title !== props.title ||
    editMode.value ||
    unsavedChanges.value
  ) {
    return;
  }
  loadingIndicator.value?.setFailed("Note not found", mdiNoteOffOutline);
}

function markNoteReady() {
  nextTick(() => {
    window.requestAnimationFrame(() => {
      performance.mark("lamanotes-note-ready");
      const reporter = window.pywebview?.api?.report_client_ready;
      if (!reporter) {
        return;
      }
      Promise.resolve(
        reporter({
          phase: "note",
          route: router.currentRoute.value.fullPath,
          browserMs: Math.round(performance.now()),
          routeMs: Math.round(performance.now() - noteLoadStartedAt),
        }),
      ).catch(() => {});
    });
  });
}

function getInitialNewTitle() {
  const title = Array.isArray(props.initialTitle)
    ? props.initialTitle[0]
    : props.initialTitle;
  return String(title || "").trim();
}

// Note Editing
function toggleEditModeHandler() {
  if (editMode.value) {
    closeHandler();
  } else {
    editHandler();
  }
}

function editHandler() {
  const draftContent = documentSession.loadDraft();
  if (draftContent != null) {
    isDraftModalVisible.value = true;
  } else {
    setEditMode();
  }
}

function setEditMode() {
  newTitle.value = isNewNote.value
    ? newTitle.value || getInitialNewTitle()
    : note.value.title;
  editorFormat.value = note.value.format || "html";
  if (editorFormat.value === "html") {
    editorKind.value = isTextNoteHtml(note.value.content || "")
      ? "text"
      : isWorkNoteHtml(note.value.content || "") ||
          isChecklistNoteHtml(note.value.content || "")
        ? "work"
        : isNewNote.value
          ? loadNewNoteKind()
          : "article";
  } else {
    editorKind.value = "markdown";
  }
  documentSession.setDirty(false);
  editorInitialValue.value = getInitialEditorValue();
  documentSession.enterEdit();
}

function focusEditor() {
  const editorElement =
    contentEditor.value?.focusEditor?.() ||
    document.querySelector(
      ".lamanotes-note-content textarea, .lamanotes-note-content .toastui-editor-md-container textarea, .lamanotes-note-content [contenteditable='true']",
    );

  if (editorElement instanceof HTMLElement) {
    editorElement.focus({ preventScroll: true });
  }
}

function getInitialEditorValue() {
  const draftContent = documentSession.loadDraft();
  const content = draftContent != null ? draftContent : note.value.content;
  if (editorFormat.value === "html" && editorKind.value === "text") {
    try {
      return extractTextMarkdown(content, note.value.title);
    } catch {
      editorKind.value = "article";
      return content;
    }
  }
  if (editorFormat.value === "html" && editorKind.value === "work") {
    if (isWorkNoteHtml(content)) {
      return extractWorkMarkdown(content);
    }
    return htmlChecklistToWorkMarkdown(content, note.value.title);
  }

  return content;
}

// Note Deletion
function deleteHandler() {
  isDeleteModalVisible.value = true;
}

function deleteConfirmedHandler() {
  deleteNote(note.value.title)
    .then(() => {
      toast.add(getToastOptions("Note deleted ✓", "Success", "success"));
      router.push({ name: "home" });
    })
    .catch((error) => {
      apiErrorHandler(error, toast);
    });
}

// Note Saving
function saveHandler(close = false) {
  return documentSession.save({ close });
}

async function persistNote() {
  saveDefaultEditorMode();

  if (!newTitle.value) {
    toast.add(
      getToastOptions("Cannot save note without a title.", "Invalid", "error"),
    );
    return false;
  }

  // Invalid Character Validation
  if (reservedFilenameCharacters.test(newTitle.value)) {
    badFilenameToast("Title");
    return false;
  }

  const newContent = getEditorContent();
  if (
    !isNewNote.value &&
    newTitle.value === note.value.title &&
    newContent === note.value.content &&
    editorFormat.value === (note.value.format || "html")
  ) {
    return note.value;
  }

  const wasNew = isNewNote.value;
  const data = await noteStorageAdapter.save({
    isNew: wasNew,
    sourceTitle: note.value.title,
    title: newTitle.value,
    content: newContent,
    format: editorFormat.value,
    expectedVersion: wasNew ? "" : await currentNoteVersion(),
  });
  note.value = data;
  if (!pendingNoteDecision) {
    updatingSavedRoute = true;
    try {
      await router.replace({
        name: "note",
        params: { title: note.value.title },
      });
    } finally {
      updatingSavedRoute = false;
    }
  }
  return data;
}

function updateTaskCheckboxMarkdown(content, taskIndex, checked) {
  return toggleMarkdownTask(content, taskIndex, checked);
}

function updateTaskCheckboxHtml(content, taskIndex, checked) {
  const isFullDocument = /<(?:!doctype|html|head|body)\b/i.test(content || "");
  const parsedDocument = new DOMParser().parseFromString(
    content || "",
    "text/html",
  );
  const taskItems = [
    ...parsedDocument.body.querySelectorAll("li.task-list-item"),
  ];
  const taskItem = taskItems[taskIndex];
  if (!taskItem) {
    return null;
  }

  let checkbox = taskItem.querySelector(":scope > input[type='checkbox']");
  if (!checkbox) {
    checkbox = parsedDocument.createElement("input");
    checkbox.type = "checkbox";
    taskItem.insertBefore(checkbox, taskItem.firstChild);
  }

  if (checked) {
    checkbox.setAttribute("checked", "");
    taskItem.classList.add("checked");
    taskItem.setAttribute("data-task-checked", "true");
  } else {
    checkbox.removeAttribute("checked");
    taskItem.classList.remove("checked");
    taskItem.removeAttribute("data-task-checked");
  }

  if (isFullDocument) {
    return `<!doctype html>\n${parsedDocument.documentElement.outerHTML}`;
  }

  return parsedDocument.body.innerHTML;
}

function updateTaskCheckboxWorkHtml(content, taskIndex, checked) {
  const markdown = extractWorkMarkdown(content || "");
  const updatedMarkdown = updateTaskCheckboxMarkdown(
    markdown,
    taskIndex,
    checked,
  );
  if (updatedMarkdown == null) {
    return null;
  }

  return buildWorkNoteHtml(note.value.title, updatedMarkdown, {
    systemTags: getLamaNotesMetaTags(content).filter(isSystemTag),
  });
}

async function toggleTaskCheckbox({ index, checked }) {
  if (!canModify.value || isNewNote.value || !note.value.title) {
    throw new Error("Task checkbox changes are not available here.");
  }

  const newContent = isTextNote.value
    ? (() => {
        const updated = toggleMarkdownTask(
          extractTextMarkdown(note.value.content, note.value.title),
          index,
          checked,
        );
        return updated == null
          ? null
          : buildTextNoteHtml(note.value.title, updated, note.value.content);
      })()
    : isWorkNote.value
      ? updateTaskCheckboxWorkHtml(note.value.content || "", index, checked)
      : isHtmlFormat.value
        ? updateTaskCheckboxHtml(note.value.content || "", index, checked)
        : updateTaskCheckboxMarkdown(note.value.content || "", index, checked);

  if (newContent == null) {
    toast.add(
      getToastOptions(
        "Could not match this checkbox to the note source.",
        "Not Saved",
        "error",
      ),
    );
    throw new Error("Task checkbox source line not found.");
  }

  if (newContent === note.value.content) {
    return;
  }

  try {
    note.value = await updateNote(
      note.value.title,
      note.value.title,
      newContent,
      note.value.format || "html",
      await currentNoteVersion(),
    );
    documentSession.clearDraft();
  } catch (error) {
    await noteSaveFailure(error, newContent);
    throw error;
  }
}

async function togglePinned() {
  if (
    pinBusy.value ||
    !canModify.value ||
    isNewNote.value ||
    !note.value.title
  ) {
    return;
  }

  const nextPinned = !isPinned.value;
  const newContent = setDocumentSystemTag({
    content: note.value.content || "",
    title: note.value.title,
    format: note.value.format || "html",
    tag: "pinned",
    enabled: nextPinned,
  });

  pinBusy.value = true;
  try {
    note.value = await updateNote(
      note.value.title,
      note.value.title,
      newContent,
      note.value.format || "html",
      await currentNoteVersion(),
    );
    documentSession.clearDraft();
    toast.add(
      getToastOptions(
        nextPinned ? "Added to favorites." : "Removed from favorites.",
        nextPinned ? "Pinned" : "Unpinned",
        "success",
      ),
    );
  } catch (error) {
    await noteSaveFailure(error, newContent);
  } finally {
    pinBusy.value = false;
  }
}

async function currentNoteVersion() {
  if (note.value.version) return note.value.version;
  const original = note.value;
  const latest = await getNote(original.title, { force: true });
  if (
    latest.content !== original.content ||
    latest.format !== original.format
  ) {
    throw {
      response: { status: 409, data: { detail: { code: "note-conflict" } } },
    };
  }
  if (!latest.version)
    throw new Error(
      "The Library needs an update before safe editing is available.",
    );
  return latest.version;
}

function checklistSource() {
  const content = note.value.content || "";
  return isTextNote.value
    ? {
        content: extractTextMarkdown(content, note.value.title),
        format: "markdown",
        serialize: (updated) =>
          buildTextNoteHtml(note.value.title, updated, content),
      }
    : {
        content,
        format: note.value.format || "html",
        serialize: (updated) => updated,
      };
}

async function editTaskSection({ section, markdown, originalMarkdown }) {
  if (!canModify.value || editMode.value)
    throw new Error("Section editing is not available here.");
  const source = checklistSource();
  const current = readChecklistSection(source.content, section, source);
  if (!current || current.markdown !== originalMarkdown) {
    throw {
      response: { status: 409 },
      message: "This section changed elsewhere.",
    };
  }
  const updated = replaceChecklistSection(
    source.content,
    section,
    markdown,
    source,
  );
  if (updated == null) throw new Error("Checklist source not found.");
  note.value = await updateNote(
    note.value.title,
    note.value.title,
    source.serialize(updated),
    note.value.format || "html",
    await currentNoteVersion(),
  );
}

async function addTaskItem({ afterIndex, text, section }) {
  if (!canModify.value || editMode.value) return;
  if (section) {
    const source = checklistSource();
    const updated = appendChecklistSectionItem(
      source.content,
      section,
      text,
      source,
    );
    if (updated == null) throw new Error("Checklist source not found.");
    note.value = await updateNote(
      note.value.title,
      note.value.title,
      source.serialize(updated),
      note.value.format || "html",
      await currentNoteVersion(),
    );
    return;
  }
  const original = note.value.content || "";
  let content;
  if (isWorkNote.value || isTextNote.value || !isHtmlFormat.value) {
    const markdown = isTextNote.value
      ? extractTextMarkdown(original, note.value.title)
      : isWorkNote.value
        ? extractWorkMarkdown(original)
        : original;
    const updated = appendMarkdownTask(markdown, afterIndex, text);
    if (updated == null) throw new Error("Checklist source not found.");
    content = isTextNote.value
      ? buildTextNoteHtml(note.value.title, updated, original)
      : isWorkNote.value
        ? buildWorkNoteHtml(note.value.title, updated, {
            systemTags: getLamaNotesMetaTags(original).filter(isSystemTag),
          })
        : updated;
  } else {
    const doc = new DOMParser().parseFromString(original, "text/html");
    const item = doc.body.querySelectorAll("li.task-list-item")[afterIndex];
    if (!item) throw new Error("Checklist source not found.");
    const added = doc.createElement("li");
    added.className = "task-list-item";
    const checkbox = doc.createElement("input");
    checkbox.type = "checkbox";
    added.append(checkbox, doc.createTextNode(String(text).trim()));
    item.after(added);
    content = /<(?:!doctype|html|body)\b/i.test(original)
      ? `<!doctype html>\n${doc.documentElement.outerHTML}`
      : doc.body.innerHTML;
  }
  try {
    note.value = await updateNote(
      note.value.title,
      note.value.title,
      content,
      note.value.format,
      await currentNoteVersion(),
    );
  } catch (error) {
    await noteSaveFailure(error, content);
    throw error;
  }
}

async function noteSaveFailure(error, pendingContent = null) {
  if (error.response?.data?.detail?.code === "note-conflict") {
    const original = note.value;
    conflictContent = null;
    try {
      conflictLatest = await getNote(note.value.title, { force: true });
      if (pendingContent != null && !editMode.value) {
        note.value = original;
        documentSession.saveDraft(pendingContent);
        setEditMode();
        documentSession.setDirty(true);
        await nextTick();
      }
      conflictVisible.value = true;
    } catch (loadError) {
      apiErrorHandler(loadError, toast);
    }
  } else if (error.response?.status === 409) {
    toast.add(
      getToastOptions(
        "A note with this title already exists. Please try again with a new title.",
        "Duplicate",
        "error",
      ),
    );
  } else if (error.response?.status === 413) {
    entityTooLargeToast("note");
  } else {
    apiErrorHandler(error, toast);
  }
}

async function keepConflictEdits() {
  if (!conflictLatest) return;
  const content = conflictContent ?? getEditorContent();
  const title = editMode.value ? newTitle.value : note.value.title;
  const snapshot = JSON.stringify([title, editorFormat.value, content]);
  try {
    const saved = await updateNote(
      note.value.title,
      title,
      content,
      editorFormat.value,
      conflictLatest.version,
    );
    note.value = saved;
    if (
      !editMode.value ||
      JSON.stringify([
        newTitle.value,
        editorFormat.value,
        getEditorContent(),
      ]) === snapshot
    ) {
      documentSession.setDirty(false);
      documentSession.clearDraft();
    } else contentChangedHandler();
    noteSaveSuccess({ pendingEdits: documentSession.dirty.value });
    updatingSavedRoute = true;
    try {
      await router.replace({ name: "note", params: { title: saved.title } });
    } finally {
      updatingSavedRoute = false;
    }
  } catch (error) {
    await noteSaveFailure(error, editMode.value ? null : content);
  }
}

function useLatestVersion() {
  if (!conflictLatest) return;
  documentSession.clearDraft();
  editorMemory.snapshot = null;
  const editing = editMode.value;
  documentSession.leaveEdit();
  note.value = conflictLatest;
  newTitle.value = note.value.title;
  documentSession.setDirty(false);
  if (editing) nextTick(setEditMode);
}

function noteSaveSuccess({ pendingEdits = false } = {}) {
  if (!pendingEdits) clearContentChangedTimeout();
  toast.add(
    getToastOptions(
      pendingEdits
        ? "Saved. Newer edits are still unsaved."
        : "Note saved successfully ✓",
      "Success",
      "success",
    ),
  );
  void loadPublicationState();
}

function resetPublicationState() {
  publicationRequestSequence += 1;
  window.clearTimeout(publicationPollTimer);
  publicationPollTimer = null;
  publicationPollAttempt = 0;
  publication.value = null;
  publishProblem.value = null;
  publishBusy.value = false;
  isPublishModalVisible.value = false;
  isUpdateModalVisible.value = false;
}

function canLoadPublicationState() {
  return !isNewNote.value && isHtmlFormat.value && Boolean(note.value.title);
}

async function loadPublicationState({ polling = false } = {}) {
  window.clearTimeout(publicationPollTimer);
  publicationPollTimer = null;
  if (!canLoadPublicationState()) {
    publication.value = null;
    return;
  }

  const requestSequence = ++publicationRequestSequence;
  try {
    const state = await getNotePublication(note.value.title);
    if (requestSequence !== publicationRequestSequence) {
      return;
    }
    publication.value = state;
    publishProblem.value = state.error || null;
    if (isPublicationPending(state.state)) {
      schedulePublicationPoll(state);
    } else {
      publicationPollAttempt = 0;
    }
  } catch (error) {
    if (requestSequence !== publicationRequestSequence) {
      return;
    }
    if (error.response?.status === 401) {
      apiErrorHandler(error, toast);
    } else if (!polling) {
      console.error(error);
    }
  }
}

function schedulePublicationPoll(state) {
  const delay = publicationPollDelay(
    publicationPollAttempt,
    state.operation?.retryAfterMs,
  );
  publicationPollAttempt += 1;
  publicationPollTimer = window.setTimeout(
    () => loadPublicationState({ polling: true }),
    delay,
  );
}

function publicationProblemFromError(error) {
  const data = error?.response?.data;
  return data && typeof data === "object"
    ? data
    : {
        code: "consumer_unavailable",
        detail: "Publishing is temporarily unavailable.",
        retryable: true,
      };
}

function publicationActionHandler() {
  if (publicationMode.value === "show") {
    openPublicPublication();
    return;
  }
  if (publicationMode.value === "update") {
    isUpdateModalVisible.value = true;
    return;
  }
  if (publicationMode.value === "publish") {
    publishProblem.value = publication.value?.error || null;
    isPublishModalVisible.value = true;
  }
}

function publishConfirmedHandler(slug) {
  void startPublication(slug);
}

async function startPublication(requestedSlug = null) {
  if (publishBusy.value || !publication.value?.lastModified) {
    return;
  }
  const wasFirstPublish = !publication.value.canonicalUrl;
  publishBusy.value = true;
  publishProblem.value = null;
  publication.value = {
    ...publication.value,
    state: "preparing",
  };
  try {
    const state = await publishNote(note.value.title, {
      ...(requestedSlug ? { requestedSlug } : {}),
      expectedLastModified: publication.value.lastModified,
    });
    publication.value = state;
    isPublishModalVisible.value = false;
    isUpdateModalVisible.value = false;
    if (isPublicationPending(state.state)) {
      publicationPollAttempt = 0;
      schedulePublicationPoll(state);
    } else if (state.state === "current") {
      toast.add(
        getToastOptions("Public page is online.", "Published", "success"),
      );
    }
  } catch (error) {
    const problem = publicationProblemFromError(error);
    publishProblem.value = problem;
    publication.value = {
      ...publication.value,
      state: wasFirstPublish ? "failed-unpublished" : "failed-update",
      error: problem,
    };
    if (!wasFirstPublish) {
      toast.add(
        getToastOptions(
          publicationProblemMessage(problem),
          "Publish Failed",
          "error",
        ),
      );
    }
  } finally {
    publishBusy.value = false;
  }
}

function openPublicPublication() {
  const url = publication.value?.canonicalUrl;
  if (!url) {
    return;
  }
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:") {
      throw new Error("Invalid public URL");
    }
  } catch (_error) {
    toast.add(
      getToastOptions("The public URL is invalid.", "Open Failed", "error"),
    );
    return;
  }

  if (window.pywebview?.api?.open_external_url) {
    Promise.resolve(window.pywebview.api.open_external_url(url))
      .then((result) => {
        if (!result?.opened) {
          throw new Error(result?.error || "Could not open the public page.");
        }
      })
      .catch((error) => {
        toast.add(getToastOptions(error.message, "Open Failed", "error"));
      });
    return;
  }

  const opened = window.open(url, "_blank", "noopener,noreferrer");
  if (!opened) {
    toast.add(
      getToastOptions(
        "Could not open the public page.",
        "Open Failed",
        "error",
      ),
    );
  }
}

// Note Closure
function closeHandler() {
  if (isContentChanged()) {
    isSaveChangesModalVisible.value = true;
  } else {
    closeNote();
  }
}

function confirmNoteNavigation() {
  if (updatingSavedRoute) return true;
  if (!editMode.value || !isContentChanged()) {
    return true;
  }

  return new Promise((resolve) => {
    pendingNoteDecision = {
      proceed: () => resolve(true),
      cancel: () => resolve(false),
    };
    isSaveChangesModalVisible.value = true;
  });
}

async function saveNoteDecision() {
  const decision = pendingNoteDecision;
  const saved = await saveHandler(true);
  pendingNoteDecision = null;
  if (!saved) {
    decision?.cancel();
    return;
  }
  decision?.proceed();
}

function discardNoteDecision() {
  const decision = pendingNoteDecision;
  pendingNoteDecision = null;
  closeNote({ navigateHome: !decision });
  decision?.proceed();
}

function cancelNoteDecision() {
  const decision = pendingNoteDecision;
  pendingNoteDecision = null;
  decision?.cancel();
}

function closeNote({ navigateHome = true } = {}) {
  clearContentChangedTimeout();
  documentSession.clearDraft();
  documentSession.setDirty(false);
  documentSession.leaveEdit();
  if (navigateHome && isNewNote.value) {
    router.push({ name: "home" });
  }
}

// Image Upload
function addImageBlobHook(file, callback) {
  const altTextInputValue = document.getElementById(
    "toastuiAltTextInput",
  )?.value;

  // Upload the image then use the callback to insert the URL into the editor
  postAttachment(file).then(function (data) {
    if (data) {
      // If the user has entered an alt text, use it. Otherwise, use the filename returned by the API.
      const altText = altTextInputValue
        ? altTextInputValue
        : data.originalFilename || data.filename;
      callback(data.url, altText, data);
    }
  });
}

function postAttachment(file) {
  // Uploading Toast
  toast.add(getToastOptions("Uploading attachment..."));

  // Upload the attachment
  return createAttachment(file)
    .then((data) => {
      // Success Toast
      toast.add(
        getToastOptions(
          data.reused
            ? "Existing media asset reused ✓"
            : "Attachment uploaded successfully ✓",
          "Success",
          "success",
        ),
      );
      return data;
    })
    .catch((error) => {
      if (error.response?.status === 409) {
        // Note: The current implementation will append a datetime to the filename if it already exists.
        // Error Toast
        toast.add(
          getToastOptions(
            "An attachment with this filename already exists.",
            "Duplicate",
            "error",
          ),
        );
      } else if (error.response?.status == 413) {
        entityTooLargeToast("attachment");
      } else {
        apiErrorHandler(error, toast);
      }
    });
}

// Content Change Watcher
function startContentChangedTimeout() {
  clearContentChangedTimeout();
  contentChangedTimeout = setTimeout(contentChangedHandler, 1000);
}

function editorContentChangedHandler() {
  documentSession.setDirty(true);
  startContentChangedTimeout();
  documentFindContentChanged();
}

function editorReadyHandler() {
  nextTick(() => {
    focusEditor();
    documentSession.restoreEditorPosition(contentEditor.value);
  });
  if (!findVisible.value) {
    return;
  }
  window.requestAnimationFrame(() => {
    refreshDocumentFind();
    nextTick(() => findBar.value?.focusSelect?.());
  });
}

function clearContentChangedTimeout() {
  if (contentChangedTimeout != null) {
    clearTimeout(contentChangedTimeout);
  }
}

function contentChangedHandler() {
  if (isContentChanged()) {
    documentSession.setDirty(true);
    documentSession.saveDraft(getEditorContent());
  } else {
    documentSession.setDirty(false);
    documentSession.clearDraft();
  }
}

function noteShortcutHandler(event) {
  if (
    isPlainKey(event, "e") &&
    !isEditableShortcutTarget(event.target) &&
    editMode.value === false &&
    canModify.value
  ) {
    event.preventDefault();
    editHandler();
  }
}

function keydownHandler(event) {
  documentSession.keydownHandler(event);
}

// Helpers
function entityTooLargeToast(entityName) {
  toast.add(
    getToastOptions(
      `This ${entityName} is too large. Please try again with a smaller ${entityName} or adjust your server configuration.`,
      "Failure",
      "error",
    ),
  );
}

function badFilenameToast(entityName) {
  toast.add(
    getToastOptions(
      'Due to filename restrictions, the following characters are not allowed: <>:"/\\|?*',
      `Invalid ${entityName}`,
      "error",
    ),
  );
}

function saveDefaultEditorMode() {
  if (
    editorFormat.value !== "markdown" ||
    !contentEditor.value?.isWysiwygMode
  ) {
    return;
  }

  const isWysiwygMode = contentEditor.value.isWysiwygMode();
  localStorage.setItem(
    "defaultEditorMode",
    isWysiwygMode ? "wysiwyg" : "markdown",
  );
}

function loadDefaultEditorMode() {
  const defaultWysiwygMode = localStorage.getItem("defaultEditorMode");
  return defaultWysiwygMode || "markdown";
}

function loadNewNoteKind() {
  const key = "lamanotes:new-note-kind";
  const storedKind = localStorage.getItem(key);
  const kind = storedKind === "research" ? "article" : storedKind;
  if (storedKind && kind !== storedKind) {
    localStorage.setItem(key, kind);
  }
  return ["work", "article"].includes(kind) ? kind : "work";
}

function currentNewEditorContentLooksEdited() {
  if (!contentEditor.value) {
    return false;
  }

  if (editorKind.value === "work" && contentEditor.value.getMarkdown) {
    const markdown = contentEditor.value.getMarkdown().trim();
    return Boolean(markdown);
  }

  if (editorKind.value === "article" && contentEditor.value.getContent) {
    return Boolean(contentEditor.value.getContent().trim());
  }

  return false;
}

function setNewNoteKind(kind) {
  if (kind === editorKind.value) {
    return;
  }

  if (
    currentNewEditorContentLooksEdited() &&
    !window.confirm("Switch editor mode and reset this unsaved note?")
  ) {
    return;
  }

  editorKind.value = kind;
  localStorage.setItem("lamanotes:new-note-kind", kind);
  note.value.content =
    kind === "work" ? buildWorkNoteHtml(newTitle.value || "Untitled", "") : "";
  documentSession.clearDraft();
  unsavedChanges.value = false;
  editorMemory.snapshot = null;
  editorInitialValue.value = getInitialEditorValue();
  editorKey.value += 1;
}

function getNoteSourceContent() {
  return note.value.content || "";
}

function extractBodyHtml(html) {
  if (!/<(?:!doctype|html|head|body)\b/i.test(html || "")) {
    return html || "";
  }

  const parsedDocument = new DOMParser().parseFromString(
    html || "",
    "text/html",
  );
  return parsedDocument.body?.innerHTML || html || "";
}

function htmlToPlainText(html) {
  const parsedDocument = new DOMParser().parseFromString(
    extractBodyHtml(html),
    "text/html",
  );
  parsedDocument
    .querySelectorAll("script, style, template, .lamanotes-note-hidden-title")
    .forEach((element) => element.remove());

  const rawText =
    parsedDocument.body?.innerText || parsedDocument.body?.textContent || "";
  return normalizeCopiedText(rawText);
}

function removeAbstractLikeLead(documentRoot) {
  documentRoot
    .querySelectorAll(
      [
        ".lamanotes-note-lead",
        ".lamanotes-note-lead-abstract",
        ".lamanote-summary",
        "[data-lamanotes-component='summary']",
      ].join(","),
    )
    .forEach((element) => element.remove());

  const headings = [...documentRoot.querySelectorAll("h1,h2,h3,h4,h5,h6")];
  for (const heading of headings) {
    const text = heading.textContent.trim().toLowerCase();
    if (
      ![
        "abstract",
        "summary",
        "kurzfassung",
        "kurzantwort",
        "tl;dr",
        "tldr",
        "key points",
        "takeaways",
      ].includes(text)
    ) {
      continue;
    }

    const toRemove = [heading];
    let next = heading.nextElementSibling;
    while (next && !/^H[1-6]$/.test(next.tagName) && toRemove.length < 4) {
      toRemove.push(next);
      next = next.nextElementSibling;
    }
    toRemove.forEach((element) => element.remove());
    break;
  }
}

function getCleanNoteTextContent() {
  if (!isHtmlFormat.value) {
    return normalizeCopiedText(getNoteSourceContent());
  }

  if (isWorkNote.value) {
    return normalizeCopiedText(extractWorkMarkdown(getNoteSourceContent()));
  }

  const parsedDocument = new DOMParser().parseFromString(
    extractBodyHtml(getNoteSourceContent()),
    "text/html",
  );
  parsedDocument
    .querySelectorAll("script, style, template, .lamanotes-note-hidden-title")
    .forEach((element) => element.remove());
  removeAbstractLikeLead(parsedDocument);

  const rawText =
    parsedDocument.body?.innerText || parsedDocument.body?.textContent || "";
  return normalizeCopiedText(rawText);
}

function normalizeCopiedText(text) {
  return String(text || "")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function getMarkdownSource() {
  return isTextNote.value
    ? extractTextMarkdown(getNoteSourceContent(), note.value.title)
    : isWorkNote.value
      ? extractWorkMarkdown(getNoteSourceContent())
      : getNoteSourceContent();
}

function getDefaultCopyKind() {
  return "text";
}

function getCopyLabel(kind) {
  if (kind === "link") {
    return "Link copied ✓";
  }
  if (kind === "html") {
    return "HTML copied ✓";
  }
  if (kind === "source") {
    return isHtmlFormat.value && !isWorkNote.value && !isTextNote.value
      ? "Source copied ✓"
      : "Markdown copied ✓";
  }
  return "Text copied ✓";
}

function getNoteLink() {
  const resolved = router.resolve({
    name: "note",
    params: { title: note.value.title },
  });
  return `${window.location.origin}${resolved.href}`;
}

function getCopyPayload(kind = "default") {
  const copyKind = kind === "default" ? getDefaultCopyKind() : kind;
  if (copyKind === "link") {
    return { type: "text", content: getNoteLink() };
  }
  if (copyKind === "html") {
    const html = extractBodyHtml(getNoteSourceContent());
    return { type: "html", content: html, plainText: htmlToPlainText(html) };
  }
  if (copyKind === "source") {
    return {
      type:
        isWorkNote.value || isTextNote.value || !isHtmlFormat.value
          ? "markdown"
          : "text",
      content: getMarkdownSource(),
    };
  }
  return { type: "text", content: getCleanNoteTextContent() };
}

function copyNote(kind = "default") {
  return documentSession.copy(kind);
}

function getCopyMenuItems() {
  if (editMode.value || isNewNote.value || !note.value.title) {
    return [];
  }

  const items = [
    {
      label:
        isWorkNote.value || isTextNote.value || !isHtmlFormat.value
          ? "Copy Markdown"
          : "Copy Text",
      icon:
        isWorkNote.value || isTextNote.value || !isHtmlFormat.value
          ? mdiCodeTags
          : mdiTextBoxOutline,
      command: () =>
        copyNote(
          isWorkNote.value || isTextNote.value || !isHtmlFormat.value
            ? "source"
            : "text",
        ),
    },
  ];

  if (publication.value?.canonicalUrl) {
    items.unshift({
      label: "Show online",
      icon: mdiOpenInNew,
      command: openPublicPublication,
    });
  }

  if (isHtmlFormat.value && !isWorkNote.value) {
    items.push({
      label: "Copy HTML",
      icon: mdiLanguageHtml5,
      command: () => copyNote("html"),
    });
  }

  items.push({
    label: "Copy Link",
    icon: mdiLinkVariant,
    command: () => copyNote("link"),
  });

  return items;
}

function getPublicationMenuItem() {
  if (
    !canModify.value ||
    editMode.value ||
    isNewNote.value ||
    !isHtmlFormat.value
  ) {
    return null;
  }

  return {
    publish: {
      label: "Publish",
      icon: mdiCloudUploadOutline,
    },
    publishing: {
      label: "Publishing...",
      icon: mdiCloudUploadOutline,
      disabled: true,
    },
    show: {
      label: "Show online",
      icon: mdiWeb,
    },
    update: {
      label: "Update online",
      icon: mdiSync,
    },
  }[publicationMode.value];
}

function getNoteMenuItems() {
  const publicationItem = getPublicationMenuItem();
  const copyItems = getCopyMenuItems();
  if (note.value.noteId && !editMode.value && !isNewNote.value) {
    copyItems.push({
      label: "Note media",
      icon: mdiImageMultipleOutline,
      command: () => router.push(`/n/${note.value.noteId}/media`),
    });
  }
  if (!publicationItem) {
    return copyItems;
  }

  return [
    {
      ...publicationItem,
      disabled: publicationItem.disabled || publishBusy.value,
      command: publicationActionHandler,
    },
    ...(copyItems.length ? [{ separator: true }, ...copyItems] : []),
  ];
}

function updateNoteActions() {
  globalStore.setNoteActions([
    {
      key: "tools",
      label: "Note tools",
      iconPath: mdiCogOutline,
      badge: "A",
      visible: canAutomateNote.value,
      iconOnly: true,
      handler: () => {
        automationSource.value = contentEditor.value?.getMarkdown?.() || "";
        automationVisible.value = true;
      },
    },
    {
      key: "copy",
      label: "Copy",
      iconPath: mdiContentCopy,
      visible: !editMode.value && !isNewNote.value && Boolean(note.value.title),
      iconOnly: true,
      handler: () => copyNote(),
    },
    {
      key: "pin",
      label: isPinned.value ? "Unpin" : "Pin",
      iconPath: isPinned.value ? mdiStar : mdiStarOutline,
      visible:
        canModify.value &&
        !editMode.value &&
        !isNewNote.value &&
        Boolean(note.value.title),
      disabled: pinBusy.value,
      iconOnly: true,
      active: isPinned.value,
      handler: togglePinned,
    },
    {
      key: "delete",
      label: "Delete",
      iconPath: mdilDelete,
      visible: canModify.value && !isNewNote.value && Boolean(note.value.title),
      iconOnly: true,
      handler: deleteHandler,
    },
    {
      key: "save",
      label: "Save",
      iconPath: mdilContentSave,
      visible: editMode.value,
      iconOnly: true,
      handler: () => saveHandler(false),
      unsaved: unsavedChanges.value,
    },
    {
      key: "edit",
      label: editMode.value ? "Done" : "Edit",
      iconPath: editMode.value ? mdilCheck : mdilPencil,
      visible: canModify.value,
      iconOnly: true,
      handler: editMode.value ? () => saveHandler(true) : toggleEditModeHandler,
    },
  ]);
  globalStore.setNoteMenuItems(getNoteMenuItems());
  globalStore.setNoteLayout({
    kind: noteLayoutKind.value,
  });
}

function applyDocumentAutomation(content) {
  contentEditor.value?.replaceContent?.(content);
}

function libraryFilename() {
  const title = editMode.value ? newTitle.value : note.value.title;
  if (!title) {
    return isNewNote.value ? "New Note.html" : "LamaNotes";
  }
  const extension = editorFormat.value || note.value.format || "html";
  return String(title).toLowerCase().endsWith(`.${extension}`)
    ? String(title)
    : `${title}.${extension}`;
}

function isContentChanged() {
  return (
    newTitle.value != note.value.title ||
    getEditorContent() != note.value.content ||
    editorFormat.value != (note.value.format || "html")
  );
}

function getEditorContent() {
  if (!contentEditor.value) {
    return "";
  }

  if (editorFormat.value === "markdown") {
    return contentEditor.value.getMarkdown();
  }

  if (editorKind.value === "text") {
    const markdown = contentEditor.value.getMarkdown();
    if (
      newTitle.value === note.value.title &&
      markdown === extractTextMarkdown(note.value.content, note.value.title)
    )
      return note.value.content;
    return buildTextNoteHtml(
      newTitle.value || note.value.title,
      markdown,
      note.value.content,
    );
  }

  if (editorKind.value === "work") {
    const systemTags = getLamaNotesMetaTags(note.value.content || "").filter(
      isSystemTag,
    );
    return buildWorkNoteHtml(
      newTitle.value || note.value.title,
      contentEditor.value.getMarkdown(),
      { systemTags },
    );
  }

  const content = contentEditor.value.getContent(
    newTitle.value || note.value.title,
  );
  if (editorKind.value !== "article") {
    return content;
  }

  return synchronizeDocumentTags({
    content,
    previousContent: note.value.content || "",
    format: editorFormat.value,
  });
}

watchEffect(updateNoteActions);
watchEffect(() => setDesktopWindowTitle(libraryFilename()));
watch(
  () => props.title,
  () => {
    closeFind({ restoreFocus: false });
    init();
  },
);
watch(editMode, () => {
  if (findVisible.value) {
    nextTick(refreshDocumentFind);
  }
});
watch(contentEditor, () => {
  if (findVisible.value && contentEditor.value) {
    nextTick(refreshDocumentFind);
  }
});
watch(newTitle, () => {
  if (editMode.value) {
    startContentChangedTimeout();
  }
});
watch(
  () => props.initialTitle,
  () => {
    if (!isNewNote.value || unsavedChanges.value) {
      return;
    }
    newTitle.value = getInitialNewTitle();
  },
);
onMounted(() => {
  window.addEventListener("keydown", noteShortcutHandler);
  window.addEventListener(libraryNoteUpdatedEvent, cachedNoteUpdatedHandler);
  window.addEventListener(libraryNoteDeletedEvent, cachedNoteDeletedHandler);
  init();
});
onUnmounted(() => {
  editorMemory.snapshot = null;
  clearContentChangedTimeout();
  publicationRequestSequence += 1;
  window.clearTimeout(publicationPollTimer);
  window.removeEventListener("keydown", noteShortcutHandler);
  window.removeEventListener(libraryNoteUpdatedEvent, cachedNoteUpdatedHandler);
  window.removeEventListener(libraryNoteDeletedEvent, cachedNoteDeletedHandler);
  globalStore.clearNoteActions();
});
</script>

<style scoped src="../noteShell.css"></style>
