<template>
  <section class="flatnotes-work-viewer">
    <ToastViewer
      :initialValue="markdown"
      :enhance-note-lead="false"
      :note-title="noteTitle"
      :task-checkboxes-disabled="taskCheckboxesDisabled"
      :task-checkbox-toggle-handler="taskCheckboxToggleHandler"
      class="toast-viewer min-w-0 max-w-full pb-4"
    />
  </section>
</template>

<script setup>
import { computed } from "vue";

import ToastViewer from "../toastui/ToastViewer.vue";
import { extractWorkMarkdown } from "./workNote.js";

const props = defineProps({
  initialValue: String,
  noteTitle: String,
  taskCheckboxToggleHandler: Function,
  taskCheckboxesDisabled: Boolean,
});

const markdown = computed(() => extractWorkMarkdown(props.initialValue || ""));
</script>

<style lang="scss" scoped>
.flatnotes-work-viewer {
  position: relative;
  min-width: 0;
  max-width: 100%;
}
</style>
