<template>
  <div
    v-if="visible"
    class="flatnotes-automation-backdrop print:hidden"
    role="presentation"
    @click.self="close"
  >
    <section
      ref="dialog"
      class="flatnotes-automation-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="flatnotes-automation-title"
      tabindex="-1"
      @keydown.esc.stop.prevent="close"
    >
      <header class="flatnotes-automation-header">
        <div class="flatnotes-automation-heading">
          <span class="flatnotes-automation-mark" aria-hidden="true">A</span>
          <strong id="flatnotes-automation-title">Note tools</strong>
        </div>
        <button type="button" title="Close" aria-label="Close" @click="close">
          <SvgIcon type="mdi" :path="mdiClose" size="0.92rem" />
        </button>
      </header>

      <div v-if="!selectedAction" class="flatnotes-automation-list">
        <button
          v-for="action in availableActions"
          :key="action.id"
          type="button"
          class="flatnotes-automation-option"
          @click="previewAction(action)"
        >
          <span>
            <strong>{{ action.label }}</strong>
            <small>{{ action.detail }}</small>
          </span>
          <SvgIcon type="mdi" :path="mdiChevronRight" size="0.9rem" />
        </button>
        <p v-if="!availableActions.length" class="flatnotes-automation-empty">
          No safe automatic tool is available for this file type.
        </p>
      </div>

      <div v-else class="flatnotes-automation-preview">
        <div class="flatnotes-automation-result-line">
          <strong>{{ selectedAction.label }}</strong>
          <span v-if="result?.changed">
            {{ result.changedLines }} changed
            {{ result.changedLines === 1 ? "line" : "lines" }}
          </span>
          <span v-else>No changes needed</span>
        </div>
        <p v-if="problem" class="flatnotes-automation-problem">{{ problem }}</p>
        <pre v-else class="flatnotes-automation-diff"><code
          v-for="(line, index) in result?.preview || []"
          :key="`${index}:${line}`"
          :class="{
            'flatnotes-automation-added': line.startsWith('+ '),
            'flatnotes-automation-removed': line.startsWith('- '),
          }"
        >{{ line }}
</code></pre>
        <footer class="flatnotes-automation-actions">
          <button
            type="button"
            class="flatnotes-automation-back"
            @click="reset"
          >
            <SvgIcon type="mdi" :path="mdiArrowLeft" size="0.86rem" />
            Back
          </button>
          <button
            type="button"
            class="flatnotes-automation-apply"
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
import { nextTick, ref, watch } from "vue";

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

watch(
  visible,
  (isVisible) => {
    if (!isVisible) {
      reset();
      return;
    }
    availableActions.value = availableDocumentAutomations(
      props.language,
      props.source,
    );
    nextTick(() => dialog.value?.focus?.({ preventScroll: true }));
  },
  { immediate: true },
);

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

function apply() {
  if (!result.value?.changed || problem.value) {
    return;
  }
  emit("apply", result.value.output);
  close();
}
</script>

<style scoped>
.flatnotes-automation-backdrop {
  position: fixed;
  inset: 0;
  z-index: 55;
  display: grid;
  place-items: start center;
  padding: min(12vh, 6rem) 0.65rem 1rem;
  background: rgb(2 6 12 / 0.48);
  backdrop-filter: blur(3px);
}

.flatnotes-automation-dialog {
  width: min(100%, 42rem);
  max-height: min(76vh, 42rem);
  overflow: auto;
  border: 1px solid rgb(var(--theme-border));
  border-radius: 6px;
  color: rgb(var(--theme-text));
  background: rgb(var(--theme-background));
  box-shadow: 0 18px 45px rgb(0 0 0 / 0.28);
  outline: none;
}

.flatnotes-automation-header,
.flatnotes-automation-result-line,
.flatnotes-automation-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
}

.flatnotes-automation-header {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 0.58rem 0.7rem;
  border-bottom: 1px solid rgb(var(--theme-border));
  background: rgb(var(--theme-background));
}

.flatnotes-automation-header button,
.flatnotes-automation-back,
.flatnotes-automation-apply {
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

.flatnotes-automation-header button:hover,
.flatnotes-automation-back:hover {
  border-color: rgb(var(--theme-border));
  color: rgb(var(--theme-text));
}

.flatnotes-automation-heading {
  display: flex;
  align-items: center;
  gap: 0.48rem;
}

.flatnotes-automation-mark {
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

.flatnotes-automation-list {
  padding: 0.4rem 0.5rem 0.55rem;
}

.flatnotes-automation-option {
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

.flatnotes-automation-option:hover,
.flatnotes-automation-option:focus-visible {
  color: rgb(var(--theme-heading));
  background: rgb(var(--theme-background-elevated) / 0.52);
  outline: none;
}

.flatnotes-automation-option span {
  display: grid;
  gap: 0.08rem;
}

.flatnotes-automation-option small,
.flatnotes-automation-result-line span,
.flatnotes-automation-empty {
  color: rgb(var(--theme-text-muted));
  font-size: 0.74rem;
}

.flatnotes-automation-preview {
  padding: 0.68rem;
}

.flatnotes-automation-result-line {
  margin-bottom: 0.55rem;
}

.flatnotes-automation-diff {
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

.flatnotes-automation-diff code {
  display: block;
}

.flatnotes-automation-added {
  color: rgb(var(--theme-heading));
  background: rgb(var(--theme-link) / 0.09);
}

.flatnotes-automation-removed {
  color: rgb(var(--theme-text-muted));
  text-decoration: line-through;
  text-decoration-color: rgb(var(--theme-danger) / 0.58);
}

.flatnotes-automation-problem {
  margin: 0.45rem 0 0.7rem;
  color: rgb(var(--theme-danger));
  font-size: 0.82rem;
}

.flatnotes-automation-actions {
  margin-top: 0.62rem;
}

.flatnotes-automation-back,
.flatnotes-automation-apply {
  padding-inline: 0.52rem;
  font-size: 0.78rem;
}

.flatnotes-automation-apply {
  border-color: rgb(var(--theme-heading) / 0.72);
  color: rgb(var(--theme-heading));
}

.flatnotes-automation-apply:disabled {
  cursor: default;
  opacity: 0.42;
}
</style>
