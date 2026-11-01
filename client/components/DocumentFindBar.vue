<template>
  <form
    class="lamanotes-document-find print:hidden"
    role="search"
    aria-label="Find in document"
    @submit.prevent="$emit('next')"
    @dblclick.stop
    @pointerup.stop
  >
    <div class="lamanotes-document-find-row">
      <SvgIcon
        type="mdi"
        :path="mdiMagnify"
        size="0.9rem"
        class="lamanotes-document-find-icon"
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
      <span class="lamanotes-document-find-count" aria-live="polite">
        {{ current }}/{{ total }}
      </span>
      <button
        type="button"
        title="Match case"
        aria-label="Match case"
        :aria-pressed="caseSensitive"
        @click="$emit('update:caseSensitive', !caseSensitive)"
      >
        <SvgIcon type="mdi" :path="mdiFormatLetterCase" size="1rem" />
      </button>
      <button
        type="button"
        title="Show or hide replacement (Ctrl+H)"
        aria-label="Show or hide replacement"
        :aria-expanded="replaceVisible"
        :disabled="!replaceAllowed"
        @click="$emit('toggle-replace')"
      >
        <SvgIcon type="mdi" :path="mdiFindReplace" size="1rem" />
      </button>
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
    </div>
    <div
      v-if="replaceVisible"
      class="lamanotes-document-find-row lamanotes-document-find-replace"
    >
      <SvgIcon
        type="mdi"
        :path="mdiSubdirectoryArrowRight"
        size="0.9rem"
        class="lamanotes-document-find-icon"
      />
      <input
        ref="replacementInput"
        :value="replacement"
        type="text"
        autocomplete="off"
        spellcheck="false"
        aria-label="Replacement text"
        placeholder="Replace with"
        @input="$emit('update:replacement', $event.target.value)"
        @keydown.enter.prevent="
          $emit($event.ctrlKey || $event.metaKey ? 'replace-all' : 'replace')
        "
        @keydown.esc.prevent.stop="$emit('close')"
      />
      <span
        class="lamanotes-document-find-count"
        aria-live="polite"
        :aria-label="`${replacedCount} matches replaced`"
      >
        {{ replacedCount || "" }}
      </span>
      <button
        type="button"
        title="Replace current match (Enter)"
        aria-label="Replace current match"
        :disabled="!canReplace || !total"
        @click="$emit('replace')"
      >
        <SvgIcon type="mdi" :path="mdiFindReplace" size="1rem" />
      </button>
      <button
        type="button"
        :title="`Replace all ${total} matches (Ctrl+Enter)`"
        aria-label="Replace all matches"
        :disabled="!canReplace || !total"
        @click="$emit('replace-all')"
      >
        <SvgIcon type="mdi" :path="mdiTextBoxMultipleOutline" size="0.95rem" />
      </button>
    </div>
  </form>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import {
  mdiChevronDown,
  mdiChevronUp,
  mdiClose,
  mdiMagnify,
  mdiFindReplace,
  mdiFormatLetterCase,
  mdiSubdirectoryArrowRight,
  mdiTextBoxMultipleOutline,
} from "@mdi/js";
import { ref } from "vue";

defineProps({
  current: { type: Number, default: 0 },
  modelValue: { type: String, default: "" },
  total: { type: Number, default: 0 },
  replacement: { type: String, default: "" },
  caseSensitive: { type: Boolean, default: false },
  replaceVisible: { type: Boolean, default: false },
  replaceAllowed: { type: Boolean, default: false },
  canReplace: { type: Boolean, default: false },
  replacedCount: { type: Number, default: 0 },
});

const emit = defineEmits([
  "close",
  "next",
  "previous",
  "update:modelValue",
  "update:replacement",
  "update:caseSensitive",
  "toggle-replace",
  "replace",
  "replace-all",
]);
const input = ref();
const replacementInput = ref();

function enterHandler(event) {
  emit(event.shiftKey ? "previous" : "next");
}

function focusSelect() {
  input.value?.focus({ preventScroll: true });
  input.value?.select();
}

function focusReplacement() {
  replacementInput.value?.focus({ preventScroll: true });
}
defineExpose({ focusSelect, focusReplacement });
</script>

<style scoped>
.lamanotes-document-find {
  position: fixed;
  z-index: 70;
  top: 3.15rem;
  right: max(0.55rem, env(safe-area-inset-right));
  display: grid;
  width: min(26rem, calc(100vw - 1.1rem));
  align-items: stretch;
  overflow: hidden;
  border: 1px solid rgb(var(--theme-border));
  border-radius: var(--ln-radius-control, 4px);
  color: rgb(var(--theme-text));
  background: rgb(var(--theme-background));
}

.lamanotes-document-find-row {
  display: grid;
  grid-template-columns: 1.65rem minmax(3.2rem, 1fr) 2.7rem repeat(5, 1.9rem);
  min-height: 2rem;
  align-items: stretch;
}
.lamanotes-document-find-replace {
  grid-template-columns: 1.65rem minmax(3.2rem, 1fr) 2.7rem repeat(2, 1.9rem);
  border-top: 1px solid rgb(var(--theme-border));
}

.lamanotes-document-find-icon {
  align-self: center;
  margin-left: 0.58rem;
  color: rgb(var(--theme-text-muted));
}

.lamanotes-document-find input {
  min-width: 0;
  border: 0;
  padding: 0.35rem 0.5rem;
  outline: 0;
  color: rgb(var(--theme-text));
  background: transparent;
  font-size: 0.82rem;
}

.lamanotes-document-find input::-webkit-search-cancel-button {
  display: none;
}

.lamanotes-document-find-count {
  min-width: 2.7rem;
  align-self: center;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.67rem;
  font-variant-numeric: tabular-nums;
  text-align: center;
}

.lamanotes-document-find button {
  display: inline-grid;
  min-width: 0;
  place-items: center;
  border: 0;
  border-left: 1px solid rgb(var(--theme-border) / 0.58);
  color: rgb(var(--theme-text-muted));
  background: transparent;
}

.lamanotes-document-find button:hover,
.lamanotes-document-find button:focus-visible {
  color: rgb(var(--theme-text));
  background: rgb(var(--theme-background-elevated) / 0.74);
  outline: 0;
}

.lamanotes-document-find button:disabled {
  opacity: 0.34;
}
.lamanotes-document-find button[aria-pressed="true"],
.lamanotes-document-find button[aria-expanded="true"] {
  color: rgb(var(--theme-heading));
  background: rgb(var(--theme-brand) / 0.1);
}

@media (max-width: 520px) {
  .lamanotes-document-find {
    top: 3rem;
  }
}
@media (pointer: coarse), (hover: none) {
  .lamanotes-document-find-row {
    min-height: var(--ln-touch-target, 44px);
    grid-template-columns: 1.3rem minmax(2.5rem, 1fr) 2.2rem repeat(5, 2.65rem);
  }
  .lamanotes-document-find-replace {
    grid-template-columns: 1.3rem minmax(2.5rem, 1fr) 2.2rem repeat(2, 2.65rem);
  }
  .lamanotes-document-find input {
    font-size: 1rem;
  }
}
</style>

<style>
::highlight(lamanotes-find-matches) {
  color: inherit;
  background-color: rgb(var(--theme-brand) / 0.3);
}

::highlight(lamanotes-find-active) {
  color: rgb(var(--theme-background));
  background-color: rgb(var(--theme-brand));
}

.lamanotes-document-find-open {
  padding-top: 2.6rem;
}
.lamanotes-document-find-open:has(.lamanotes-document-find-replace) {
  padding-top: 5.4rem;
}
</style>
