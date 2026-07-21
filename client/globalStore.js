import { defineStore } from "pinia";
import { ref } from "vue";

export const useGlobalStore = defineStore("global", () => {
  const config = ref({});
  const noteActions = ref([]);
  const noteLayoutKind = ref("default");
  const noteMenuItems = ref([]);
  const showLineNumbers = ref(
    localStorage.getItem("nirvnotes:show-line-numbers") === "true",
  );

  function setNoteActions(actions = []) {
    noteActions.value = actions;
  }

  function setNoteMenuItems(items = []) {
    noteMenuItems.value = items;
  }

  function setNoteLayout({ kind = "default" } = {}) {
    noteLayoutKind.value = kind;
  }

  function clearNoteActions() {
    noteActions.value = [];
    noteMenuItems.value = [];
    noteLayoutKind.value = "default";
  }

  function toggleLineNumbers() {
    showLineNumbers.value = !showLineNumbers.value;
    localStorage.setItem(
      "nirvnotes:show-line-numbers",
      String(showLineNumbers.value),
    );
  }

  return {
    config,
    noteActions,
    noteLayoutKind,
    noteMenuItems,
    showLineNumbers,
    setNoteActions,
    setNoteLayout,
    setNoteMenuItems,
    toggleLineNumbers,
    clearNoteActions,
  };
});
