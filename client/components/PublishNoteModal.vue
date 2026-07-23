<template>
  <Modal
    v-model="isVisible"
    aria-label="Publish online"
    class="lamanotes-publish-modal px-5 py-4"
  >
    <div class="mb-3 text-lg font-semibold">Publish online</div>
    <label
      class="mb-1 block text-xs uppercase text-theme-text-muted"
      for="publication-slug"
    >
      Public URL
    </label>
    <div class="lamanotes-publish-url-row">
      <span class="text-theme-text-muted">https://pages.thuber.org/</span>
      <input
        id="publication-slug"
        v-model.trim="slug"
        v-focus
        type="text"
        inputmode="url"
        autocomplete="off"
        spellcheck="false"
        :disabled="busy"
        @keydown.enter.prevent="submit"
      />
      <span class="text-theme-text-muted">/</span>
    </div>
    <div
      v-if="validationMessage || problemMessage"
      class="mt-2 text-sm text-theme-danger"
    >
      {{ validationMessage || problemMessage }}
    </div>
    <div
      v-else-if="qualityWarning"
      class="lamanotes-publish-quality-warning mt-2 text-sm"
      role="status"
    >
      {{ qualityWarning }} Publishing remains available after review.
    </div>
    <div v-else class="mt-2 text-sm text-theme-text-muted">
      This page will be publicly readable.
    </div>
    <div class="mt-5 flex justify-end gap-2">
      <CustomButton label="Cancel" :disabled="busy" @click="close" />
      <CustomButton
        label="Publish"
        style="cta"
        :disabled="busy || Boolean(validationMessage)"
        @click="submit"
      />
    </div>
  </Modal>
</template>

<script setup>
import { computed, ref, watch } from "vue";

import { validatePublicationSlug } from "../publicationState.js";
import CustomButton from "./CustomButton.vue";
import Modal from "./Modal.vue";

const props = defineProps({
  suggestedSlug: { type: String, default: "" },
  busy: Boolean,
  problemMessage: { type: String, default: "" },
  qualityWarning: { type: String, default: "" },
});
const emit = defineEmits(["publish"]);
const isVisible = defineModel({ type: Boolean });
const slug = ref("");
const validationMessage = computed(() => validatePublicationSlug(slug.value));

watch(
  () => [isVisible.value, props.suggestedSlug],
  ([visible]) => {
    if (visible && !props.busy) {
      slug.value = props.suggestedSlug || "";
    }
  },
  { immediate: true },
);

function close() {
  if (!props.busy) {
    isVisible.value = false;
  }
}

function submit() {
  if (!props.busy && !validationMessage.value) {
    emit("publish", slug.value);
  }
}
</script>

<style scoped>
.lamanotes-publish-modal {
  max-width: 29rem;
}

.lamanotes-publish-url-row {
  display: flex;
  min-width: 0;
  align-items: baseline;
  gap: 0.1rem;
  border-bottom: 1px solid rgb(var(--theme-border));
  padding-block: 0.35rem;
  font-size: 0.95rem;
}

.lamanotes-publish-url-row input {
  min-width: 4rem;
  flex: 1;
  background: transparent;
  color: rgb(var(--theme-text));
}

.lamanotes-publish-url-row:focus-within {
  border-bottom-color: rgb(var(--theme-brand));
  box-shadow: 0 2px 0 rgb(var(--theme-brand));
}

.lamanotes-publish-url-row input:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: 2px;
}

.lamanotes-publish-quality-warning {
  color: rgb(var(--theme-warning));
}

@media (max-width: 420px) {
  .lamanotes-publish-url-row {
    font-size: 0.82rem;
  }
}
</style>
