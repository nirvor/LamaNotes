<template>
  <section class="lamanotes-work-viewer">
    <ToastViewer
      :initialValue="markdown"
      :enhance-note-lead="false"
      :note-title="noteTitle"
      :task-checkboxes-disabled="taskCheckboxesDisabled"
      :task-checkbox-toggle-handler="taskCheckboxToggleHandler"
      :task-item-add-handler="taskItemAddHandler"
      :task-section-edit-handler="taskSectionEditHandler"
      class="toast-viewer min-w-0 max-w-full pb-4"
      @rendered="$emit('rendered')"
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
  taskItemAddHandler: Function,
  taskSectionEditHandler: Function,
  taskCheckboxesDisabled: Boolean,
});
defineEmits(["rendered"]);

const markdown = computed(() => extractWorkMarkdown(props.initialValue || ""));
</script>

<style lang="scss" scoped>
.lamanotes-work-viewer {
  position: relative;
  min-width: 0;
  max-width: 100%;
}
</style>
