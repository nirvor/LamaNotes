<template>
  <Menu ref="menu" :pt="style">
    <template #item="{ item, props }">
      <a
        v-bind="props.action"
        class="lamanotes-menu-action flex items-center justify-between"
        :class="{ 'lamanotes-menu-action-active': item.active }"
      >
        <IconLabel
          :iconPath="item.icon"
          iconSize="1.05rem"
          :label="item.label"
        />
        <span v-if="item.keyboardShortcut" class="lamanotes-menu-shortcut">{{
          item.keyboardShortcut
        }}</span>
      </a>
    </template>
  </Menu>
</template>
<script setup>
import Menu from "primevue/menu";
import { ref } from "vue";

import IconLabel from "./IconLabel.vue";

const menu = ref();

const style = {
  root: "min-w-[13.75rem] border p-1.5 rounded border-theme-border bg-theme-background shadow-sm",
  menuitem: ({ context }) => ({
    class: [
      "text-theme-text-muted rounded p-0.5",
      {
        "bg-theme-background-elevated": context.focused,
      },
    ],
    role: context.item.toggle ? "menuitemcheckbox" : "menuitem",
    "aria-checked": context.item.toggle
      ? Boolean(context.item.active)
      : undefined,
  }),
  separator: "border-t border-theme-border my-2",
};

function toggle(event) {
  menu.value.toggle(event);
}

defineExpose({ toggle });
</script>

<style scoped>
.lamanotes-menu-action {
  min-height: 2.15rem;
  width: 100%;
  align-items: center;
  gap: var(--ln-space-3);
  border-radius: var(--ln-radius-control);
  padding: 0.42rem 0.58rem;
  color: rgb(var(--theme-text-muted));
  line-height: 1.15;
  transition:
    color 140ms ease,
    background-color 140ms ease;
}

.lamanotes-menu-action:hover,
.lamanotes-menu-action:focus-visible {
  color: rgb(var(--theme-text));
  background: rgb(var(--theme-background-elevated));
}

.lamanotes-menu-action:focus-visible {
  outline: 2px solid rgb(var(--theme-brand));
  outline-offset: 2px;
}

.lamanotes-menu-action-active {
  color: rgb(var(--theme-brand));
  background: rgb(var(--theme-background-elevated) / 0.58);
}

.lamanotes-menu-action[aria-disabled="true"] {
  cursor: not-allowed;
  opacity: 0.48;
}

.lamanotes-menu-shortcut {
  margin-left: var(--ln-space-4);
  border: 1px solid rgb(var(--theme-border) / 0.72);
  border-radius: var(--ln-radius-control);
  padding: 0.18rem 0.42rem;
  color: rgb(var(--theme-text-very-muted));
  background: rgb(var(--theme-background-elevated) / 0.72);
  font-size: 0.7rem;
  line-height: 1;
}

@media (pointer: coarse), (hover: none) {
  .lamanotes-menu-action {
    min-height: var(--ln-touch-target);
  }
}
</style>
