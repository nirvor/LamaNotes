<template>
  <div
    v-if="isVisible"
    class="lamanotes-modal-backdrop fixed inset-0 z-50 flex h-dvh w-dvw items-start justify-center"
    @click.self="closeHandler"
  >
    <div
      ref="dialog"
      class="lamanotes-modal-panel relative grow border border-theme-border bg-theme-background"
      :class="$attrs.class"
      role="dialog"
      aria-modal="true"
      :aria-label="ariaLabel"
      tabindex="-1"
      @keydown.esc.stop.prevent="closeHandler"
      @keydown.tab="trapFocus"
    >
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from "vue";

defineOptions({
  inheritAttrs: false,
});
const props = defineProps({
  closeHandlerOverride: Function,
  ariaLabel: { type: String, default: "Dialog" },
});
const isVisible = defineModel({ type: Boolean });
const dialog = ref();
let returnFocusTarget;

watch(
  isVisible,
  async (visible) => {
    if (visible) {
      returnFocusTarget =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : undefined;
      await nextTick();
      const [firstFocusable] = getFocusableElements();
      (firstFocusable || dialog.value)?.focus?.({ preventScroll: true });
      return;
    }

    await nextTick();
    returnFocus();
  },
  { immediate: true },
);

onBeforeUnmount(returnFocus);

function closeHandler() {
  if (props.closeHandlerOverride) {
    props.closeHandlerOverride();
  } else {
    isVisible.value = false;
  }
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
</script>

<style scoped>
.lamanotes-modal-backdrop {
  padding: clamp(1rem, 10vh, 5rem) max(0.5rem, env(safe-area-inset-right))
    max(1rem, env(safe-area-inset-bottom))
    max(0.5rem, env(safe-area-inset-left));
  background: rgb(2 6 12 / 0.7);
}

.lamanotes-modal-panel {
  width: min(100%, 31.25rem);
  max-height: calc(
    100dvh - clamp(2rem, 20vh, 10rem) - env(safe-area-inset-bottom)
  );
  overflow: auto;
  border-radius: var(--ln-radius-card);
  box-shadow: var(--ln-shadow-card);
}

.lamanotes-modal-panel:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: 2px;
}
</style>
