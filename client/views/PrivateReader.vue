<template>
  <main
    ref="root"
    class="lamanotes-private-reader lamanotes-app-shell lamanotes-app-shell-note"
    :class="
      work
        ? 'lamanotes-app-shell-note-work'
        : 'lamanotes-app-shell-note-article'
    "
    :data-private-reader-ready="ready ? 'true' : 'false'"
    :data-note-id="note?.noteId"
    :data-note-version="note?.version"
  >
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="!note" role="status">Loading note...</p>
    <article
      v-else
      class="lamanotes-note-shell"
      :class="
        work ? 'lamanotes-note-shell-work' : 'lamanotes-note-shell-article'
      "
    >
      <div class="lamanotes-note-title-row">
        <span class="lamanotes-note-title-text">{{ note.title }}</span>
      </div>
      <hr class="lamanotes-note-title-rule border-theme-border" />
      <div class="lamanotes-note-content">
        <WorkNoteViewer
          v-if="work"
          :initial-value="content"
          :note-title="note.title"
          :task-checkboxes-disabled="true"
          @rendered="rendered"
        />
        <HtmlViewer
          v-else
          :initial-value="content"
          :note-title="note.title"
          :task-checkboxes-disabled="true"
          @rendered="rendered"
          class="toast-viewer min-w-0 max-w-full pb-4"
        />
      </div>
    </article>
  </main>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from "vue";
import HtmlViewer from "../components/html/HtmlViewer.vue";
import WorkNoteViewer from "../components/work/WorkNoteViewer.vue";
import { isWorkNoteHtml } from "../components/work/workNote.js";

const note = ref(null),
  error = ref("");
const root = ref(null),
  ready = ref(false);
const path = window.location.pathname.replace(/\/$/, "");
const work = computed(() => isWorkNoteHtml(note.value?.content || ""));
const content = computed(() =>
  (note.value?.content || "").replaceAll(
    /\/api\/private\/v1\/assets\/(la-[a-f0-9]{32})\/content/g,
    (_, id) => `${path}/assets/${id}/content`,
  ),
);
async function rendered() {
  try {
    await nextTick();
    if (root.value.querySelector("pre code.language-mermaid"))
      throw new Error("Diagram rendering did not complete.");
    await document.fonts.ready;
    await Promise.all(
      [...root.value.querySelectorAll("img")].map(async (image) => {
        if (image.loading === "lazy") image.loading = "eager";
        await image.decode();
      }),
    );
    await new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve)),
    );
    ready.value = true;
  } catch {
    error.value =
      "Note media could not be rendered. Do not accept this capture.";
  }
}
onMounted(async () => {
  document.body.classList.toggle(
    "dark",
    window.matchMedia("(prefers-color-scheme: dark)").matches,
  );
  try {
    const response = await fetch(`${path}/document`, {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok)
      throw new Error(
        "This note is unavailable. Request a fresh reader session.",
      );
    note.value = await response.json();
    document.title = `LamaNotes - ${note.value.title}`;
  } catch (problem) {
    error.value = problem.message;
  }
});
</script>

<style scoped src="../appShell.css"></style>
<style scoped src="../noteShell.css"></style>
<style scoped>
.lamanotes-private-reader {
  min-width: 0;
  margin-inline: auto;
  padding-top: 0.75rem;
}
</style>
