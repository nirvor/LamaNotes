<template>
  <form
    class="lamanotes-quick-capture"
    aria-label="Capture a thought"
    :aria-busy="busy"
    @submit.prevent="submit"
  >
    <div class="lamanotes-quick-capture-field">
      <svg
        class="lamanotes-quick-capture-note"
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <path :d="mdiNoteTextOutline" />
      </svg>
      <textarea
        :value="modelValue"
        :rows="expanded ? 3 : 1"
        :readonly="busy"
        :aria-describedby="statusText ? statusId : undefined"
        aria-label="Thought for Quicknotes"
        aria-keyshortcuts="Control+Enter Meta+Enter"
        placeholder="Capture a thought..."
        spellcheck="true"
        maxlength="10000"
        @input="$emit('update:modelValue', $event.target.value)"
        @focus="focused = true"
        @blur="focused = false"
        @keydown="keydown"
        @compositionstart="composing = true"
        @compositionend="composing = false"
      ></textarea>
      <button
        type="submit"
        :disabled="!canSubmit"
        :aria-label="busy ? 'Saving thought' : 'Save to Quicknotes'"
        :title="busy ? 'Saving thought' : 'Save to Quicknotes'"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path :d="mdiSendOutline" />
        </svg>
      </button>
    </div>
    <p
      v-if="statusText"
      :id="statusId"
      class="lamanotes-quick-capture-status"
      :class="{ 'lamanotes-quick-capture-error': status === 'error' }"
      :role="status === 'error' ? 'alert' : 'status'"
      :aria-live="status === 'error' ? 'assertive' : 'polite'"
      aria-atomic="true"
    >
      {{ statusText }}
    </p>
  </form>
</template>

<script setup>
import { mdiNoteTextOutline, mdiSendOutline } from "@mdi/js";
import { computed, ref, useId } from "vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  busy: { type: Boolean, default: false },
  pendingCount: { type: Number, default: 0 },
  status: { type: String, default: "" },
  message: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue", "submit"]);
const focused = ref(false);
const composing = ref(false);
const statusId = `quick-capture-status-${useId()}`;
const expanded = computed(() => focused.value || props.modelValue.length > 0);
const canSubmit = computed(() => !props.busy && !!props.modelValue.trim());
const statusText = computed(() => {
  if (props.message) return props.message;
  if (props.status === "saved") return "Saved to Quicknotes";
  if (props.status === "pending")
    return "Saved on this device · Waiting for connection";
  if (props.status === "blocked") return "Sign in to send";
  if (props.status === "error") return "Could not save. Your text is kept.";
  const count = Math.max(0, Math.floor(props.pendingCount));
  return count
    ? `${count} ${count === 1 ? "thought" : "thoughts"} waiting to send`
    : "";
});

function submit() {
  if (canSubmit.value && !composing.value) emit("submit", props.modelValue);
}

function keydown(event) {
  if (event.key !== "Enter" || !(event.ctrlKey || event.metaKey)) return;
  if (event.isComposing || composing.value) return;
  event.preventDefault();
  if (!event.repeat) submit();
}
</script>

<style scoped>
.lamanotes-quick-capture {
  min-width: 0;
  margin: 0;
}
.lamanotes-quick-capture-field {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) 44px;
  align-items: start;
  gap: 8px;
  padding: 2px 2px 2px 10px;
  border: 1px solid rgb(var(--theme-border));
  border-radius: var(--ln-radius-control);
  background: rgb(var(--theme-background-elevated));
}
.lamanotes-quick-capture-field:focus-within {
  border-color: rgb(var(--theme-brand));
  outline: 1px solid rgb(var(--theme-brand));
  outline-offset: 0;
}
.lamanotes-quick-capture svg {
  display: block;
  fill: currentColor;
}
.lamanotes-quick-capture-note {
  width: 16px;
  height: 16px;
  margin-top: 14px;
  color: rgb(var(--theme-text-muted));
}
.lamanotes-quick-capture textarea {
  box-sizing: border-box;
  display: block;
  min-width: 0;
  width: 100%;
  padding: 10px 0;
  border: 0;
  border-radius: 0;
  outline: none;
  resize: none;
  color: rgb(var(--theme-text));
  background: transparent;
  font: inherit;
  font-size: 16px;
  line-height: 24px;
  overflow-y: auto;
}
.lamanotes-quick-capture textarea::placeholder {
  color: rgb(var(--theme-text-muted));
  opacity: 1;
}
.lamanotes-quick-capture button {
  box-sizing: border-box;
  display: flex;
  align-self: end;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  min-width: 44px;
  min-height: 44px;
  padding: 0;
  border: 0;
  border-radius: var(--ln-radius-control);
  color: rgb(var(--theme-brand));
  background: transparent;
  touch-action: manipulation;
}
.lamanotes-quick-capture button svg {
  width: 20px;
  height: 20px;
}
.lamanotes-quick-capture button:hover:not(:disabled) {
  background: rgb(var(--theme-background));
}
.lamanotes-quick-capture button:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: -3px;
}
.lamanotes-quick-capture button:disabled {
  color: rgb(var(--theme-text-muted));
  opacity: 0.55;
}
.lamanotes-quick-capture-status {
  margin: 4px 0 0;
  padding-inline: 34px 4px;
  color: rgb(var(--theme-text-muted));
  font-size: var(--ln-font-small, 0.86em);
  line-height: var(--ln-line-small, 1.38);
  overflow-wrap: anywhere;
}
.lamanotes-quick-capture-error {
  color: rgb(var(--theme-danger));
}
</style>
