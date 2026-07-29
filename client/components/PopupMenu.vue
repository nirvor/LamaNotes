<template>
  <Teleport to="body">
    <div
      v-if="open"
      :id="menuId"
      ref="menu"
      class="lamanotes-popup-menu"
      :style="position"
      role="menu"
      @keydown="handleKeydown"
      @focusout="handleFocusout"
    >
      <template v-for="(item, index) in items" :key="itemKey(item, index)">
        <div
          v-if="item.separator"
          class="lamanotes-menu-separator"
          role="separator"
        ></div>
        <button
          v-else
          type="button"
          class="lamanotes-menu-action"
          :class="{ 'lamanotes-menu-action-active': item.active }"
          :role="item.toggle ? 'menuitemcheckbox' : 'menuitem'"
          :aria-checked="item.toggle ? Boolean(item.active) : undefined"
          :disabled="Boolean(item.disabled)"
          @click="runCommand(item, $event)"
        >
          <IconLabel
            :iconPath="item.icon"
            iconSize="1.05rem"
            :label="item.label"
          />
          <span v-if="item.keyboardShortcut" class="lamanotes-menu-shortcut">
            {{ item.keyboardShortcut }}
          </span>
        </button>
      </template>
    </div>
  </Teleport>
</template>

<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
} from "vue";

import IconLabel from "./IconLabel.vue";

let menuSequence = 0;

const props = defineProps({
  model: {
    type: Array,
    default: () => [],
  },
  popup: Boolean,
});

const menu = ref();
const open = ref(false);
const anchor = ref();
const menuId = `lamanotes-menu-${++menuSequence}`;
const position = reactive({ top: "0px", left: "0px", visibility: "hidden" });
const items = computed(() => (Array.isArray(props.model) ? props.model : []));

function toggle(event) {
  if (open.value) {
    hide({ restoreFocus: true });
    return;
  }
  anchor.value = event?.currentTarget || event?.target || null;
  if (anchor.value) {
    anchor.value.setAttribute("aria-controls", menuId);
    anchor.value.setAttribute("aria-expanded", "true");
    anchor.value.setAttribute("aria-haspopup", "menu");
  }
  open.value = true;
  position.visibility = "hidden";
  nextTick(() => {
    placeMenu();
    // Let the activating click finish before moving keyboard focus. Some
    // WebView/browser combinations otherwise restore focus to the trigger.
    window.requestAnimationFrame(() => focusItem(0));
  });
}

function hide({ restoreFocus = false } = {}) {
  if (!open.value) {
    return;
  }
  open.value = false;
  if (anchor.value) {
    anchor.value.setAttribute("aria-expanded", "false");
    if (restoreFocus) {
      anchor.value.focus({ preventScroll: true });
    }
  }
}

function itemKey(item, index) {
  return item?.key || item?.label || `separator-${index}`;
}

function enabledItems() {
  return Array.from(
    menu.value?.querySelectorAll(
      '[role="menuitem"]:not(:disabled), [role="menuitemcheckbox"]:not(:disabled)',
    ) || [],
  );
}

function focusItem(index) {
  const buttons = enabledItems();
  if (!buttons.length) {
    return;
  }
  const normalized = (index + buttons.length) % buttons.length;
  buttons[normalized].focus({ preventScroll: true });
}

function moveFocus(offset) {
  const buttons = enabledItems();
  const current = buttons.indexOf(document.activeElement);
  focusItem((current < 0 ? 0 : current) + offset);
}

function handleKeydown(event) {
  if (event.key === "Escape") {
    event.preventDefault();
    hide({ restoreFocus: true });
  } else if (event.key === "ArrowDown") {
    event.preventDefault();
    moveFocus(1);
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    moveFocus(-1);
  } else if (event.key === "Home") {
    event.preventDefault();
    focusItem(0);
  } else if (event.key === "End") {
    event.preventDefault();
    focusItem(-1);
  }
}

function handleFocusout() {
  window.setTimeout(() => {
    if (
      open.value &&
      !menu.value?.contains(document.activeElement) &&
      document.activeElement !== anchor.value
    ) {
      hide();
    }
  }, 0);
}

function runCommand(item, originalEvent) {
  if (item.disabled) {
    return;
  }
  hide();
  item.command?.({ originalEvent, item });
}

function placeMenu() {
  if (!menu.value || !anchor.value) {
    return;
  }
  const margin = 8;
  const anchorBox = anchor.value.getBoundingClientRect();
  const menuBox = menu.value.getBoundingClientRect();
  const left = Math.max(
    margin,
    Math.min(
      anchorBox.right - menuBox.width,
      window.innerWidth - menuBox.width - margin,
    ),
  );
  const below = anchorBox.bottom + 4;
  const top =
    below + menuBox.height <= window.innerHeight - margin
      ? below
      : Math.max(margin, anchorBox.top - menuBox.height - 4);
  position.left = `${Math.round(left)}px`;
  position.top = `${Math.round(top)}px`;
  position.visibility = "visible";
}

function handleDocumentPointer(event) {
  if (
    open.value &&
    !menu.value?.contains(event.target) &&
    !anchor.value?.contains(event.target)
  ) {
    hide();
  }
}

function handleViewportChange() {
  if (open.value) {
    hide();
  }
}

onMounted(() => {
  document.addEventListener("pointerdown", handleDocumentPointer, true);
  window.addEventListener("resize", handleViewportChange);
  window.addEventListener("scroll", handleViewportChange, true);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", handleDocumentPointer, true);
  window.removeEventListener("resize", handleViewportChange);
  window.removeEventListener("scroll", handleViewportChange, true);
});

defineExpose({ hide, toggle });
</script>

<style scoped>
.lamanotes-popup-menu {
  position: fixed;
  z-index: 80;
  display: flex;
  width: max-content;
  min-width: 13.75rem;
  max-width: min(22rem, calc(100vw - 1rem));
  flex-direction: column;
  border: 1px solid rgb(var(--theme-border));
  border-radius: var(--ln-radius-control);
  padding: 0.3rem;
  background: rgb(var(--theme-background));
  box-shadow: var(--ln-shadow-card);
}

.lamanotes-menu-action {
  display: flex;
  min-height: 2.15rem;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: var(--ln-space-3);
  border: 0;
  border-radius: var(--ln-radius-control);
  padding: 0.42rem 0.58rem;
  color: rgb(var(--theme-text-muted));
  background: transparent;
  line-height: 1.15;
  text-align: left;
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

.lamanotes-menu-action:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.lamanotes-menu-separator {
  height: 1px;
  margin: 0.38rem 0.28rem;
  background: rgb(var(--theme-border));
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
