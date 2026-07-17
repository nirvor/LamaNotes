import { defineStore } from "pinia";
import { ref } from "vue";

export const useGlobalStore = defineStore("global", () => {
  const config = ref({});
  const noteActions = ref([]);
  const noteLayoutKind = ref("default");
  const noteMenuItems = ref([]);

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

  return {
    config,
    noteActions,
    noteLayoutKind,
    noteMenuItems,
    setNoteActions,
    setNoteLayout,
    setNoteMenuItems,
    clearNoteActions,
  };
});
