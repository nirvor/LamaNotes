import { defineStore } from "pinia";
import { ref } from "vue";

export const useGlobalStore = defineStore("global", () => {
  const config = ref({});
  const noteActions = ref([]);
  const noteToolbarContext = ref(null);
  const noteLayoutKind = ref("default");
  const noteMenuItems = ref([]);
  const showLineNumbers = ref(
    localStorage.getItem("lamanotes:show-line-numbers") === "true",
  );

  function setNoteActions(actions = []) {
    noteActions.value = actions;
  }

  function setNoteToolbarContext(context = null) {
    noteToolbarContext.value = context;
  }

  function setNoteMenuItems(items = []) {
    noteMenuItems.value = items;
  }

  function setNoteLayout({ kind = "default" } = {}) {
    noteLayoutKind.value = kind;
  }

  function clearNoteActions() {
    noteActions.value = [];
    noteToolbarContext.value = null;
    noteMenuItems.value = [];
    noteLayoutKind.value = "default";
  }

  function toggleLineNumbers() {
    showLineNumbers.value = !showLineNumbers.value;
    localStorage.setItem(
      "lamanotes:show-line-numbers",
      String(showLineNumbers.value),
    );
  }

  return {
    config,
    noteActions,
    noteToolbarContext,
    noteLayoutKind,
    noteMenuItems,
    showLineNumbers,
    setNoteActions,
    setNoteToolbarContext,
    setNoteLayout,
    setNoteMenuItems,
    toggleLineNumbers,
    clearNoteActions,
  };
});
