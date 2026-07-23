<template>
  <nav class="lamanotes-navbar flex justify-end align-top">
    <div
      class="lamanotes-navbar-actions flex grow flex-wrap items-center justify-end gap-1"
    >
      <div
        v-if="noteToolbarContext"
        class="lamanotes-navbar-context"
        :title="noteToolbarContext.title"
      >
        <span class="lamanotes-navbar-context-text">
          {{ noteToolbarContext.label }}
        </span>
        <button
          v-if="noteToolbarContext.action"
          type="button"
          class="lamanotes-navbar-context-action"
          :title="noteToolbarContext.action.label"
          :aria-label="noteToolbarContext.action.label"
          @click="noteToolbarContext.action.handler"
        >
          <SvgIcon
            type="mdi"
            :path="noteToolbarContext.action.iconPath"
            size="0.88rem"
          />
        </button>
      </div>
      <!-- Home -->
      <RouterLink :to="{ name: 'home' }" class="lamanotes-navbar-action-link">
        <CustomButton
          :iconPath="mdilHome"
          label="Home"
          class="lamanotes-navbar-icon-only lamanotes-icon-only"
        />
      </RouterLink>
      <template v-for="action in leadingNoteActions" :key="action.key">
        <CustomButton
          v-if="action.visible !== false"
          :label="action.label"
          :iconPath="action.iconPath"
          :iconSize="action.iconSize"
          :disabled="action.disabled"
          :style="action.style || 'subtle'"
          class="relative"
          :class="{
            'lamanotes-navbar-icon-only': action.iconOnly,
            'lamanotes-navbar-action-active': action.active,
          }"
          @click="action.handler"
        >
          <div
            v-if="action.unsaved"
            class="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-theme-brand"
          ></div>
          <span v-if="action.badge" class="lamanotes-navbar-action-badge">
            {{ action.badge }}
          </span>
        </CustomButton>
      </template>
      <!-- New Note -->
      <CustomButton
        v-if="showNewButton"
        :iconPath="mdilPlusCircle"
        label="New Note"
        class="lamanotes-navbar-icon-only lamanotes-icon-only"
        @click="createNewNote"
      />
      <!-- Menu -->
      <CustomButton
        :iconPath="mdilMenu"
        label="Menu"
        class="lamanotes-navbar-icon-only lamanotes-icon-only"
        @click="toggleMenu"
      />
      <PrimeMenu ref="menu" :model="menuItems" :popup="true" />
      <template v-for="action in trailingNoteActions" :key="action.key">
        <CustomButton
          v-if="action.visible !== false"
          :label="action.label"
          :iconPath="action.iconPath"
          :iconSize="action.iconSize"
          :disabled="action.disabled"
          :style="action.style || 'subtle'"
          class="relative"
          :class="{
            'lamanotes-navbar-icon-only': action.iconOnly,
            'lamanotes-navbar-action-active': action.active,
          }"
          @click="action.handler"
        >
          <div
            v-if="action.unsaved"
            class="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-theme-brand"
          ></div>
          <span v-if="action.badge" class="lamanotes-navbar-action-badge">
            {{ action.badge }}
          </span>
        </CustomButton>
      </template>
    </div>
  </nav>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import { mdiFormatListNumbered, mdiThemeLightDark, mdiUpdate } from "@mdi/js";
import {
  mdilLogout,
  mdilHome,
  mdilMagnify,
  mdilMenu,
  mdilNoteMultiple,
  mdilPlusBox,
  mdilPlusCircle,
} from "@mdi/light-js";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useToast } from "primevue/usetoast";
import { RouterLink, useRouter } from "vue-router";

import { clearApiCaches, logOutSession } from "../api.js";
import CustomButton from "../components/CustomButton.vue";
import PrimeMenu from "../components/PrimeMenu.vue";
import { authTypes, params, searchSortOptions } from "../constants.js";
import { useGlobalStore } from "../globalStore.js";
import { getToastOptions, toggleTheme } from "../helpers.js";
import { openNewNote } from "../newNoteNavigation.js";
import {
  checkNativeClientUpdate,
  installNativeClientUpdate,
  nativeClientUpdate,
} from "../nativeClientUpdate.js";
import { clearStoredToken } from "../tokenStorage.js";

const globalStore = useGlobalStore();
const menu = ref();
const router = useRouter();
const toast = useToast();
let nativeUpdateCheckTimer = null;

const emit = defineEmits(["toggleSearchModal"]);

const baseMenuItems = computed(() => {
  const items = [
    {
      label: "New Window",
      icon: mdilPlusBox,
      command: openNewWindow,
    },
  ];
  if (nativeClientUpdate.available) {
    items.push({
      label: nativeClientUpdate.installing
        ? "Updating LamaNotes..."
        : "Update LamaNotes",
      icon: mdiUpdate,
      disabled: nativeClientUpdate.installing || !nativeClientUpdate.canInstall,
      command: startNativeClientUpdate,
    });
  }
  items.push(
    { separator: true },
    {
      label: "Search",
      icon: mdilMagnify,
      command: () => emit("toggleSearchModal"),
      keyboardShortcut: "/",
    },
    {
      label: "All Notes",
      icon: mdilNoteMultiple,
      command: () =>
        router.push({
          name: "search",
          query: {
            [params.searchTerm]: "*",
            [params.sortBy]: searchSortOptions.lastModified,
          },
        }),
    },
    {
      label: "View options",
      controls: [
        {
          label: "Toggle theme",
          icon: mdiThemeLightDark,
          command: toggleTheme,
        },
        {
          label: globalStore.showLineNumbers
            ? "Hide line numbers"
            : "Show line numbers",
          icon: mdiFormatListNumbered,
          active: globalStore.showLineNumbers,
          toggle: true,
          command: globalStore.toggleLineNumbers,
        },
      ],
    },
    {
      separator: true,
      visible: showLogOutButton,
    },
    {
      label: "Log Out",
      icon: mdilLogout,
      command: logOut,
      visible: showLogOutButton,
    },
  );
  return items;
});

const menuItems = computed(() => {
  const noteItems = globalStore.noteMenuItems || [];
  if (!noteItems.length) {
    return baseMenuItems.value;
  }

  return [...noteItems, { separator: true }, ...baseMenuItems.value];
});

async function startNativeClientUpdate() {
  toast.add(getToastOptions("Downloading the LamaNotes update..."));
  const result = await installNativeClientUpdate();
  if (result?.started) {
    toast.add(
      getToastOptions(
        "Update verified. LamaNotes will restart now.",
        "Updating",
        "success",
      ),
    );
    return;
  }
  toast.add(
    getToastOptions(
      result?.error || "Could not start the LamaNotes update.",
      "Update Failed",
      "error",
    ),
  );
}

function checkForNativeUpdate() {
  window.clearTimeout(nativeUpdateCheckTimer);
  nativeUpdateCheckTimer = window.setTimeout(() => {
    checkNativeClientUpdate().catch(() => {});
  }, 2500);
}

onMounted(() => {
  checkForNativeUpdate();
  window.addEventListener("lamanotes:native-ready", checkForNativeUpdate);
});

onBeforeUnmount(() => {
  window.clearTimeout(nativeUpdateCheckTimer);
  window.removeEventListener("lamanotes:native-ready", checkForNativeUpdate);
});

const showNewButton = computed(() => {
  return globalStore.config.authType !== authTypes.readOnly;
});

const noteActions = computed(() => globalStore.noteActions || []);
const noteToolbarContext = computed(() => globalStore.noteToolbarContext);

const leadingNoteActions = computed(() =>
  noteActions.value.filter((action) => action.placement !== "end"),
);

const trailingNoteActions = computed(() =>
  noteActions.value.filter((action) => action.placement === "end"),
);

async function logOut() {
  await logOutSession().catch(() => {});
  clearApiCaches();
  clearStoredToken();
  localStorage.clear();
  router.push({ name: "login" });
}

function toggleMenu(event) {
  menu.value.toggle(event);
}

function createNewNote() {
  return openNewNote(router);
}

async function openNewWindow() {
  const targetRoute =
    router.currentRoute.value.name === "openFile"
      ? router.resolve({ name: "home" })
      : router.resolve(router.currentRoute.value.fullPath || { name: "home" });

  if (window.pywebview?.api?.open_new_window) {
    let result;
    try {
      result = await window.pywebview.api.open_new_window(targetRoute.href);
    } catch (error) {
      console.error(error);
      result = { started: false };
    }
    if (!result?.started) {
      toast.add(
        getToastOptions(
          result?.error || "Could not open a new LamaNotes window.",
          "New Window Failed",
          "error",
        ),
      );
    }
    return;
  }

  window.open(targetRoute.href, "_blank", "noopener");
}

function showLogOutButton() {
  return ![authTypes.none, authTypes.readOnly].includes(
    globalStore.config.authType,
  );
}
</script>

<style scoped>
.lamanotes-navbar {
  position: sticky;
  top: 0;
  z-index: 35;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  margin-inline: -0.45rem;
  padding-inline: 0.45rem;
  margin-bottom: 0.35rem;
  background-color: rgb(var(--theme-background));
  isolation: isolate;
}

.lamanotes-navbar-action-link {
  display: inline-flex;
  align-items: center;
  align-self: center;
  line-height: 1;
}

.lamanotes-navbar-actions {
  position: relative;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  flex: 1 1 100%;
}

.lamanotes-navbar-context {
  position: absolute;
  top: 50%;
  left: 0;
  display: flex;
  min-width: 0;
  max-width: calc(100% - 16.8rem);
  transform: translateY(-50%);
  align-items: center;
  justify-content: flex-start;
  gap: 0.12rem;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.66rem;
  line-height: 1;
}

.lamanotes-navbar-context-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lamanotes-navbar-context-action {
  display: inline-grid;
  width: var(--ln-control-size);
  height: var(--ln-control-size);
  flex: 0 0 auto;
  place-items: center;
  border: 0;
  border-radius: 3px;
  color: rgb(var(--theme-text-muted));
  background: transparent;
}

.lamanotes-navbar-context-action:hover,
.lamanotes-navbar-context-action:focus-visible {
  color: rgb(var(--theme-heading));
  background: rgb(var(--theme-background-elevated) / 0.72);
}

.lamanotes-navbar-action-badge {
  position: absolute;
  top: -0.12rem;
  right: -0.08rem;
  display: grid;
  width: 0.76rem;
  height: 0.76rem;
  place-items: center;
  border: 1px solid rgb(var(--theme-background));
  border-radius: 3px;
  color: rgb(var(--theme-background));
  background: rgb(var(--theme-heading));
  font-size: 0.48rem;
  font-weight: 700;
  line-height: 1;
}

@media print {
  .lamanotes-navbar {
    position: static;
  }
}

@media (max-width: 560px) {
  .lamanotes-navbar-context {
    max-width: calc(100% - 15.8rem);
    font-size: 0.6rem;
  }

  .lamanotes-navbar-actions {
    gap: 0.12rem;
  }

  .lamanotes-navbar-actions :deep(.lamanotes-custom-button) {
    min-width: var(--ln-control-size);
    padding-inline: 0.42rem;
  }

  .lamanotes-navbar-actions :deep(.lamanotes-icon-label-text) {
    display: none;
  }

  .lamanotes-navbar-actions :deep(.lamanotes-icon-label-icon) {
    margin-right: 0 !important;
  }
}

.lamanotes-navbar-actions :deep(.lamanotes-navbar-icon-only) {
  display: inline-flex;
  min-width: var(--ln-control-size);
  align-items: center;
  justify-content: center;
  padding-inline: 0.42rem;
}

.lamanotes-navbar-actions :deep(.lamanotes-navbar-action-active) {
  color: rgb(var(--theme-brand));
}

.lamanotes-navbar-actions
  :deep(.lamanotes-navbar-icon-only .lamanotes-icon-label-text) {
  display: none;
}

.lamanotes-navbar-actions
  :deep(.lamanotes-navbar-icon-only .lamanotes-icon-label-icon) {
  margin-right: 0 !important;
}

@media (pointer: coarse), (hover: none) {
  .lamanotes-navbar-context-action {
    width: var(--ln-touch-target);
    height: var(--ln-touch-target);
  }

  .lamanotes-navbar-actions :deep(.lamanotes-custom-button),
  .lamanotes-navbar-actions :deep(.lamanotes-navbar-icon-only) {
    min-width: var(--ln-touch-target);
    min-height: var(--ln-touch-target);
  }
}
</style>
