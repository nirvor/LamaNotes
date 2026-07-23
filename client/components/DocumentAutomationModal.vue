<template>
  <div
    v-if="visible"
    class="lamanotes-automation-backdrop print:hidden"
    role="presentation"
    @click.self="close"
  >
    <section
      ref="dialog"
      class="lamanotes-automation-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="lamanotes-automation-title"
      tabindex="-1"
      @keydown.esc.stop.prevent="close"
      @keydown.tab="trapFocus"
    >
      <header class="lamanotes-automation-header">
        <div class="lamanotes-automation-heading">
          <span class="lamanotes-automation-mark" aria-hidden="true">A</span>
          <strong id="lamanotes-automation-title">Note tools</strong>
        </div>
        <button type="button" title="Close" aria-label="Close" @click="close">
          <SvgIcon type="mdi" :path="mdiClose" size="0.92rem" />
        </button>
      </header>

      <div v-if="!selectedAction" class="lamanotes-automation-list">
        <button
          v-for="action in availableActions"
          :key="action.id"
          type="button"
          class="lamanotes-automation-option"
          @click="previewAction(action)"
        >
          <span>
            <strong>{{ action.label }}</strong>
            <small>{{ action.detail }}</small>
          </span>
          <SvgIcon type="mdi" :path="mdiChevronRight" size="0.9rem" />
        </button>
        <p v-if="!availableActions.length" class="lamanotes-automation-empty">
          No safe automatic tool is available for this file type.
        </p>
      </div>

      <div v-else class="lamanotes-automation-preview">
        <div class="lamanotes-automation-result-line">
          <strong>{{ selectedAction.label }}</strong>
          <span v-if="result?.changed">
            {{ result.changedLines }} changed
            {{ result.changedLines === 1 ? "line" : "lines" }}
          </span>
          <span v-else>No changes needed</span>
        </div>
        <p v-if="problem" class="lamanotes-automation-problem">{{ problem }}</p>
        <pre v-else class="lamanotes-automation-diff"><code
          v-for="(line, index) in result?.preview || []"
          :key="`${index}:${line}`"
          :class="{
            'lamanotes-automation-added': line.startsWith('+ '),
            'lamanotes-automation-removed': line.startsWith('- '),
          }"
        >{{ line }}
</code></pre>
        <footer class="lamanotes-automation-actions">
          <button
            type="button"
            class="lamanotes-automation-back"
            @click="reset"
          >
            <SvgIcon type="mdi" :path="mdiArrowLeft" size="0.86rem" />
            Back
          </button>
          <button
            type="button"
            class="lamanotes-automation-apply"
            :disabled="!result?.changed || Boolean(problem)"
            @click="apply"
          >
            <SvgIcon type="mdi" :path="mdiCheck" size="0.86rem" />
            Apply
          </button>
        </footer>
      </div>
    </section>
  </div>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import { mdiArrowLeft, mdiCheck, mdiChevronRight, mdiClose } from "@mdi/js";
import { nextTick, onBeforeUnmount, ref, watch } from "vue";

import {
  availableDocumentAutomations,
  runDocumentAutomation,
} from "../documentAutomation.js";

const props = defineProps({
  source: { type: String, default: "" },
  language: { type: String, default: "text" },
});
const emit = defineEmits(["apply"]);
const visible = defineModel({ type: Boolean });
const availableActions = ref([]);
const dialog = ref();
const problem = ref("");
const result = ref(null);
const selectedAction = ref(null);
let returnFocusTarget;

watch(
  visible,
  async (isVisible) => {
    if (!isVisible) {
      reset();
      await nextTick();
      returnFocus();
      return;
    }
    returnFocusTarget =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : undefined;
    availableActions.value = availableDocumentAutomations(
      props.language,
      props.source,
    );
    await nextTick();
    const [firstFocusable] = getFocusableElements();
    (firstFocusable || dialog.value)?.focus?.({ preventScroll: true });
  },
  { immediate: true },
);

onBeforeUnmount(returnFocus);

function previewAction(action) {
  selectedAction.value = action;
  problem.value = "";
  try {
    result.value = runDocumentAutomation(action.id, props.source);
  } catch (error) {
    result.value = null;
    problem.value = error?.message || "This note could not be formatted.";
  }
}

function reset() {
  selectedAction.value = null;
  result.value = null;
  problem.value = "";
}

function close() {
  visible.value = false;
}

function getFocusableElements() {
  if (!dialog.value) {
    return [];
  }
  return Array.from(
    dialog.value.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => !element.closest("[inert]"));
}

function trapFocus(event) {
  const focusableElements = getFocusableElements();
  if (!focusableElements.length) {
    event.preventDefault();
    dialog.value?.focus?.();
    return;
  }

  const firstFocusable = focusableElements[0];
  const lastFocusable = focusableElements.at(-1);
  if (event.shiftKey && document.activeElement === firstFocusable) {
    event.preventDefault();
    lastFocusable.focus();
  } else if (!event.shiftKey && document.activeElement === lastFocusable) {
    event.preventDefault();
    firstFocusable.focus();
  }
}

function returnFocus() {
  returnFocusTarget?.focus?.({ preventScroll: true });
  returnFocusTarget = undefined;
}

function apply() {
  if (!result.value?.changed || problem.value) {
    return;
  }
  emit("apply", result.value.output);
  close();
}
</script>

<style scoped>
.lamanotes-automation-backdrop {
  position: fixed;
  inset: 0;
  z-index: 55;
  display: grid;
  place-items: start center;
  padding: min(12vh, 6rem) 0.65rem 1rem;
  background: rgb(2 6 12 / 0.7);
}

.lamanotes-automation-dialog {
  width: min(100%, 42rem);
  max-height: min(76vh, 42rem);
  overflow: auto;
  border: 1px solid rgb(var(--theme-border));
  border-radius: var(--ln-radius-card);
  color: rgb(var(--theme-text));
  background: rgb(var(--theme-background));
  box-shadow: var(--ln-shadow-card);
  outline: none;
}

.lamanotes-automation-dialog:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: 2px;
}

.lamanotes-automation-header,
.lamanotes-automation-result-line,
.lamanotes-automation-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
}

.lamanotes-automation-header {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 0.58rem 0.7rem;
  border-bottom: 1px solid rgb(var(--theme-border));
  background: rgb(var(--theme-background));
}

.lamanotes-automation-header button,
.lamanotes-automation-back,
.lamanotes-automation-apply {
  display: inline-flex;
  min-width: 1.8rem;
  min-height: 1.8rem;
  align-items: center;
  justify-content: center;
  gap: 0.32rem;
  border: 1px solid transparent;
  border-radius: 4px;
  color: rgb(var(--theme-text-muted));
}

.lamanotes-automation-header button:hover,
.lamanotes-automation-back:hover {
  border-color: rgb(var(--theme-border));
  color: rgb(var(--theme-text));
}

.lamanotes-automation-heading {
  display: flex;
  align-items: center;
  gap: 0.48rem;
}

.lamanotes-automation-mark {
  display: grid;
  width: 1.45rem;
  height: 1.45rem;
  place-items: center;
  border: 1px solid rgb(var(--theme-heading) / 0.7);
  border-radius: 4px;
  color: rgb(var(--theme-heading));
  font-size: 0.72rem;
  font-weight: 700;
}

.lamanotes-automation-list {
  padding: 0.4rem 0.5rem 0.55rem;
}

.lamanotes-automation-option {
  display: flex;
  width: 100%;
  min-height: 2.65rem;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.42rem 0.52rem;
  border-bottom: 1px solid rgb(var(--theme-border) / 0.58);
  text-align: left;
}

.lamanotes-automation-option:hover,
.lamanotes-automation-option:focus-visible {
  color: rgb(var(--theme-heading));
  background: rgb(var(--theme-background-elevated) / 0.52);
}

.lamanotes-automation-header button:focus-visible,
.lamanotes-automation-option:focus-visible,
.lamanotes-automation-back:focus-visible,
.lamanotes-automation-apply:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: 2px;
}

.lamanotes-automation-option span {
  display: grid;
  gap: 0.08rem;
}

.lamanotes-automation-option small,
.lamanotes-automation-result-line span,
.lamanotes-automation-empty {
  color: rgb(var(--theme-text-muted));
  font-size: 0.74rem;
}

.lamanotes-automation-preview {
  padding: 0.68rem;
}

.lamanotes-automation-result-line {
  margin-bottom: 0.55rem;
}

.lamanotes-automation-diff {
  max-height: min(52vh, 30rem);
  overflow: auto;
  padding: 0.58rem 0.65rem;
  border: 1px solid rgb(var(--theme-border));
  border-radius: 4px;
  color: rgb(var(--theme-text-muted));
  background: rgb(var(--theme-background-elevated) / 0.48);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.72rem;
  line-height: 1.48;
  white-space: pre-wrap;
  word-break: break-word;
}

.lamanotes-automation-diff code {
  display: block;
}

.lamanotes-automation-added {
  color: rgb(var(--theme-heading));
  background: rgb(var(--theme-link) / 0.09);
}

.lamanotes-automation-removed {
  color: rgb(var(--theme-text-muted));
  text-decoration: line-through;
  text-decoration-color: rgb(var(--theme-danger) / 0.58);
}

.lamanotes-automation-problem {
  margin: 0.45rem 0 0.7rem;
  color: rgb(var(--theme-danger));
  font-size: 0.82rem;
}

.lamanotes-automation-actions {
  margin-top: 0.62rem;
}

.lamanotes-automation-back,
.lamanotes-automation-apply {
  padding-inline: 0.52rem;
  font-size: 0.78rem;
}

.lamanotes-automation-apply {
  border-color: rgb(var(--theme-heading) / 0.72);
  color: rgb(var(--theme-heading));
}

@media (pointer: coarse), (hover: none) {
  .lamanotes-automation-header button,
  .lamanotes-automation-back,
  .lamanotes-automation-apply,
  .lamanotes-automation-option {
    min-height: var(--ln-touch-target);
  }

  .lamanotes-automation-header button {
    min-width: var(--ln-touch-target);
  }
}

.lamanotes-automation-apply:disabled {
  cursor: default;
  opacity: 0.42;
}
</style>
