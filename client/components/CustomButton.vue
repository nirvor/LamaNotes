<template>
  <button
    class="lamanotes-custom-button text-nowrap rounded px-1.5 py-0.5 text-[0.94rem]"
    :disabled="disabled"
    :class="{
      'bg-theme-background text-theme-text-muted hover:bg-theme-background-elevated':
        style === 'subtle',
      'border bg-theme-background hover:bg-theme-background-elevated':
        style === 'cta',
      'border border-theme-danger text-theme-danger hover:bg-theme-danger/10':
        style === 'danger',
      'border border-theme-success text-theme-success hover:bg-theme-success/10':
        style === 'success',
      'cursor-default opacity-45 hover:bg-theme-background': disabled,
    }"
    :title="label"
    :aria-label="label"
  >
    <slot></slot>
    <IconLabel :iconPath="iconPath" :iconSize="iconSize" :label="label" />
  </button>
</template>

<script setup>
import IconLabel from "./IconLabel.vue";

defineProps({
  iconPath: String,
  iconSize: String,
  label: String,
  disabled: Boolean,
  style: {
    type: String,
    default: "subtle",
    validator: (value) => {
      return ["subtle", "cta", "danger", "success"].includes(value);
    },
  },
});
</script>

<style scoped>
.lamanotes-custom-button {
  min-width: 0;
  min-height: var(--ln-control-size);
  border-radius: var(--ln-radius-control);
  touch-action: manipulation;
}

.lamanotes-custom-button:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: 2px;
}

@media (max-width: 560px) {
  .lamanotes-custom-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
}

@media (pointer: coarse), (hover: none) {
  .lamanotes-custom-button {
    min-width: var(--ln-touch-target);
    min-height: var(--ln-touch-target);
  }
}
</style>
