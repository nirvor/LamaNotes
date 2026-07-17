<template>
  <form
    class="flatnotes-document-find print:hidden"
    role="search"
    aria-label="Find in document"
    @submit.prevent="$emit('next')"
    @dblclick.stop
    @pointerup.stop
  >
    <SvgIcon
      type="mdi"
      :path="mdiMagnify"
      size="0.9rem"
      class="flatnotes-document-find-icon"
    />
    <input
      ref="input"
      :value="modelValue"
      type="search"
      autocomplete="off"
      spellcheck="false"
      aria-label="Find in document"
      placeholder="Find"
      @input="$emit('update:modelValue', $event.target.value)"
      @keydown.enter.prevent="enterHandler"
      @keydown.esc.prevent.stop="$emit('close')"
    />
    <span class="flatnotes-document-find-count" aria-live="polite">
      {{ current }}/{{ total }}
    </span>
    <button
      type="button"
      title="Previous match"
      aria-label="Previous match"
      :disabled="!total"
      @click="$emit('previous')"
    >
      <SvgIcon type="mdi" :path="mdiChevronUp" size="0.92rem" />
    </button>
    <button
      type="button"
      title="Next match"
      aria-label="Next match"
      :disabled="!total"
      @click="$emit('next')"
    >
      <SvgIcon type="mdi" :path="mdiChevronDown" size="0.92rem" />
    </button>
    <button
      type="button"
      title="Close find"
      aria-label="Close find"
      @click="$emit('close')"
    >
      <SvgIcon type="mdi" :path="mdiClose" size="0.86rem" />
    </button>
  </form>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import { mdiChevronDown, mdiChevronUp, mdiClose, mdiMagnify } from "@mdi/js";
import { ref } from "vue";

defineProps({
  current: { type: Number, default: 0 },
  modelValue: { type: String, default: "" },
  total: { type: Number, default: 0 },
});

const emit = defineEmits(["close", "next", "previous", "update:modelValue"]);
const input = ref();

function enterHandler(event) {
  emit(event.shiftKey ? "previous" : "next");
}

function focusSelect() {
  input.value?.focus({ preventScroll: true });
  input.value?.select();
}

defineExpose({ focusSelect });
</script>

<style scoped>
.flatnotes-document-find {
  position: fixed;
  z-index: 70;
  top: 3.15rem;
  right: max(0.55rem, env(safe-area-inset-right));
  display: grid;
  width: min(21rem, calc(100vw - 1.1rem));
  min-height: 2.15rem;
  grid-template-columns: auto minmax(5rem, 1fr) auto repeat(3, 1.9rem);
  align-items: stretch;
  overflow: hidden;
  border: 1px solid rgb(var(--theme-border));
  border-radius: 5px;
  color: rgb(var(--theme-text));
  background: rgb(var(--theme-background));
  box-shadow: 0 0.45rem 1.25rem rgb(var(--theme-shadow) / 0.34);
}

.flatnotes-document-find-icon {
  align-self: center;
  margin-left: 0.58rem;
  color: rgb(var(--theme-text-muted));
}

.flatnotes-document-find input {
  min-width: 0;
  border: 0;
  padding: 0.35rem 0.5rem;
  outline: 0;
  color: rgb(var(--theme-text));
  background: transparent;
  font-size: 0.82rem;
}

.flatnotes-document-find input::-webkit-search-cancel-button {
  display: none;
}

.flatnotes-document-find-count {
  min-width: 2.7rem;
  align-self: center;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.67rem;
  font-variant-numeric: tabular-nums;
  text-align: center;
}

.flatnotes-document-find button {
  display: inline-grid;
  min-width: 0;
  place-items: center;
  border: 0;
  border-left: 1px solid rgb(var(--theme-border) / 0.58);
  color: rgb(var(--theme-text-muted));
  background: transparent;
}

.flatnotes-document-find button:hover,
.flatnotes-document-find button:focus-visible {
  color: rgb(var(--theme-text));
  background: rgb(var(--theme-background-elevated) / 0.74);
  outline: 0;
}

.flatnotes-document-find button:disabled {
  opacity: 0.34;
}

@media (max-width: 520px) {
  .flatnotes-document-find {
    top: 3rem;
    min-height: 2.35rem;
    grid-template-columns: auto minmax(4rem, 1fr) auto repeat(3, 2rem);
  }
}
</style>

<style>
::highlight(nirvnotes-find-matches) {
  color: inherit;
  background-color: rgb(var(--theme-brand) / 0.3);
}

::highlight(nirvnotes-find-active) {
  color: rgb(var(--theme-background));
  background-color: rgb(var(--theme-brand));
}

@media (max-width: 520px) {
  .flatnotes-document-find-open {
    padding-top: 2.6rem;
  }
}
</style>
