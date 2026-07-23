<template>
  <Menu ref="menu" :pt="style">
    <template #item="{ item, props }">
      <div
        v-if="item.controls"
        class="lamanotes-menu-control-row"
        role="group"
        :aria-label="item.label"
      >
        <button
          v-for="control in item.controls"
          :key="control.label"
          type="button"
          class="lamanotes-menu-control"
          :class="{ 'lamanotes-menu-control-active': control.active }"
          :title="control.label"
          :aria-label="control.label"
          :aria-pressed="control.toggle ? Boolean(control.active) : undefined"
          @click.stop="control.command"
        >
          <SvgIcon type="mdi" :path="control.icon" size="1rem" />
        </button>
      </div>
      <a v-else class="flex items-center justify-between" v-bind="props.action">
        <IconLabel :iconPath="item.icon" :label="item.label" />
        <span
          v-if="item.keyboardShortcut"
          class="ml-4 rounded bg-theme-background-elevated px-3 py-1 text-xs"
          >{{ item.keyboardShortcut }}</span
        >
      </a>
    </template>
  </Menu>
</template>
<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import Menu from "primevue/menu";
import { ref } from "vue";

import IconLabel from "./IconLabel.vue";

const menu = ref();

const style = {
  root: "border p-1 rounded border-theme-border bg-theme-background",
  menuitem: ({ context }) => ({
    class: [
      "text-theme-text-muted rounded px-2 py-1",
      "hover:bg-theme-background-elevated hover:cursor-pointer",
      {
        "bg-theme-background-elevated": context.focused,
      },
    ],
  }),
  separator: "border-t border-theme-border my-2",
};

function toggle(event) {
  menu.value.toggle(event);
}

defineExpose({ toggle });
</script>

<style scoped>
.lamanotes-menu-control-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.08rem;
}

.lamanotes-menu-control {
  display: inline-grid;
  width: var(--ln-control-size);
  height: var(--ln-control-size);
  place-items: center;
  border: 1px solid transparent;
  border-radius: var(--ln-radius-control);
  color: rgb(var(--theme-text-muted));
  background: transparent;
}

.lamanotes-menu-control:hover,
.lamanotes-menu-control:focus-visible {
  border-color: rgb(var(--theme-border));
  color: rgb(var(--theme-text));
  background: rgb(var(--theme-background-elevated));
}

.lamanotes-menu-control:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: 2px;
}

.lamanotes-menu-control-active {
  color: rgb(var(--theme-brand));
  background: rgb(var(--theme-background-elevated) / 0.58);
}

@media (pointer: coarse), (hover: none) {
  .lamanotes-menu-control {
    width: var(--ln-touch-target);
    height: var(--ln-touch-target);
  }
}
</style>
