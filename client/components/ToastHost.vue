<template>
  <Teleport to="body">
    <div
      class="lamanotes-toast-host"
      aria-live="polite"
      aria-relevant="additions"
    >
      <TransitionGroup name="lamanotes-toast">
        <div
          v-for="message in toast.messages"
          :key="message.id"
          class="lamanotes-toast"
          :class="`lamanotes-toast-${message.severity}`"
          :role="message.severity === 'error' ? 'alert' : 'status'"
        >
          <div class="lamanotes-toast-copy">
            <strong v-if="message.summary">{{ message.summary }}</strong>
            <span v-if="message.detail">{{ message.detail }}</span>
          </div>
          <button
            v-if="message.closable"
            type="button"
            class="lamanotes-toast-close"
            aria-label="Dismiss message"
            @click="toast.remove(message.id)"
          >
            &times;
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { useToast } from "../toastStore.js";

const toast = useToast();
</script>

<style scoped>
.lamanotes-toast-host {
  position: fixed;
  z-index: 90;
  right: max(0.75rem, env(safe-area-inset-right));
  bottom: max(0.75rem, env(safe-area-inset-bottom));
  display: flex;
  width: min(24rem, calc(100vw - 1.5rem));
  flex-direction: column;
  align-items: stretch;
  gap: 0.4rem;
  pointer-events: none;
}

.lamanotes-toast {
  display: flex;
  min-height: 2.4rem;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ln-space-3);
  border: 1px solid rgb(var(--theme-border));
  border-radius: var(--ln-radius-control);
  padding: 0.55rem 0.68rem;
  color: rgb(var(--theme-text));
  background: rgb(var(--theme-background-elevated));
  box-shadow: var(--ln-shadow-card);
  pointer-events: auto;
}

.lamanotes-toast-success {
  border-color: rgb(var(--theme-success) / 0.58);
}

.lamanotes-toast-error {
  border-color: rgb(var(--theme-danger) / 0.68);
}

.lamanotes-toast-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 0.08rem;
  font-size: 0.82rem;
  line-height: 1.3;
}

.lamanotes-toast-copy strong {
  font-size: 0.84rem;
}

.lamanotes-toast-close {
  display: grid;
  width: var(--ln-control-size);
  height: var(--ln-control-size);
  flex: 0 0 auto;
  place-items: center;
  border: 0;
  color: rgb(var(--theme-text-muted));
  background: transparent;
}

.lamanotes-toast-close:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: 2px;
}

.lamanotes-toast-enter-active,
.lamanotes-toast-leave-active {
  transition:
    opacity 120ms ease,
    transform 120ms ease;
}

.lamanotes-toast-enter-from,
.lamanotes-toast-leave-to {
  opacity: 0;
  transform: translateY(0.3rem);
}
</style>
