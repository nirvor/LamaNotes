<template>
  <div class="lamanotes-note-kind-switch" aria-label="New note kind">
    <button
      type="button"
      title="Work note"
      aria-label="Work note"
      :class="{ 'lamanotes-note-kind-switch-active': currentKind === 'work' }"
      @click="setKind('work')"
    >
      <SvgIcon type="mdi" :path="mdiBriefcaseOutline" size="0.92rem" />
    </button>
    <button
      type="button"
      title="HTML article"
      aria-label="HTML article"
      :class="{
        'lamanotes-note-kind-switch-active': currentKind === 'article',
      }"
      @click="setKind('article')"
    >
      <SvgIcon type="mdi" :path="mdiLanguageHtml5" size="0.92rem" />
    </button>
  </div>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import { mdiBriefcaseOutline, mdiLanguageHtml5 } from "@mdi/js";

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
.lamanotes-note-kind-switch {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 0.1rem;
  margin-right: 0.2rem;
  padding: 0.06rem;
  border: 1px solid rgb(var(--theme-border));
  border-radius: var(--ln-radius-control);
  background-color: rgb(var(--theme-background));
}

.lamanotes-note-kind-switch button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--ln-control-size);
  height: var(--ln-control-size);
  border-radius: var(--ln-radius-control);
  padding: 0;
  color: rgb(var(--theme-text-muted));
  touch-action: manipulation;
}

.lamanotes-note-kind-switch button:hover,
.lamanotes-note-kind-switch button:focus-visible,
.lamanotes-note-kind-switch-active {
  color: rgb(var(--theme-text)) !important;
  background-color: rgb(var(--theme-background-elevated));
}

@media (pointer: coarse), (hover: none) {
  .lamanotes-note-kind-switch {
    gap: 0.12rem;
    margin-right: 0.25rem;
    padding: 0.1rem;
  }

  .lamanotes-note-kind-switch button {
    width: var(--ln-touch-target);
    height: var(--ln-touch-target);
  }
}
</style>
