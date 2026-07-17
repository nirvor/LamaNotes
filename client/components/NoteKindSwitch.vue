<template>
  <div class="flatnotes-note-kind-switch" aria-label="New note kind">
    <button
      type="button"
      title="Work note"
      aria-label="Work note"
      :class="{ 'flatnotes-note-kind-switch-active': currentKind === 'work' }"
      @click="setKind('work')"
    >
      <SvgIcon type="mdi" :path="mdiBriefcaseOutline" size="0.92rem" />
    </button>
    <button
      type="button"
      title="Research note"
      aria-label="Research note"
      :class="{ 'flatnotes-note-kind-switch-active': currentKind === 'research' }"
      @click="setKind('research')"
    >
      <SvgIcon type="mdi" :path="mdiTextBoxSearchOutline" size="0.92rem" />
    </button>
  </div>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import { mdiBriefcaseOutline, mdiTextBoxSearchOutline } from "@mdi/js";

defineProps({
  currentKind: {
    type: String,
    default: "work",
  },
});

const emit = defineEmits(["set-kind"]);

function setKind(kind) {
  emit("set-kind", kind);
}
</script>

<style lang="scss" scoped>
.flatnotes-note-kind-switch {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 0.1rem;
  margin-right: 0.2rem;
  padding: 0.06rem;
  border: 1px solid rgb(var(--theme-border));
  border-radius: 6px;
  background-color: rgb(var(--theme-background));
}

.flatnotes-note-kind-switch button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.55rem;
  height: 1.34rem;
  border-radius: 5px;
  padding: 0;
  color: rgb(var(--theme-text-muted));
  touch-action: manipulation;
}

.flatnotes-note-kind-switch button:hover,
.flatnotes-note-kind-switch button:focus-visible,
.flatnotes-note-kind-switch-active {
  color: rgb(var(--theme-text)) !important;
  background-color: rgb(var(--theme-background-elevated));
}

@media (max-width: 640px) and (pointer: coarse), (max-width: 640px) and (hover: none) {
  .flatnotes-note-kind-switch {
    gap: 0.12rem;
    margin-right: 0.25rem;
    padding: 0.1rem;
  }

  .flatnotes-note-kind-switch button {
    width: 1.86rem;
    height: 1.86rem;
  }
}
</style>
