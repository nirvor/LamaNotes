<template>
  <nav class="flatnotes-navbar mb-2 flex justify-end align-top md:mb-3">
    <div
      class="flatnotes-navbar-actions flex grow flex-wrap items-center justify-end gap-1"
    >
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
            'flatnotes-navbar-icon-only': action.iconOnly,
            'flatnotes-navbar-action-active': action.active,
          }"
          @click="action.handler"
        >
          <div
            v-if="action.unsaved"
            class="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-theme-brand"
          ></div>
        </CustomButton>
      </template>
      <!-- Home -->
      <RouterLink :to="{ name: 'home' }">
        <CustomButton
          :iconPath="mdilHome"
          label="Home"
          class="flatnotes-navbar-icon-only"
        />
      </RouterLink>
      <!-- New Note -->
      <RouterLink v-if="showNewButton" :to="{ name: 'new' }">
        <CustomButton :iconPath="mdilPlusCircle" label="New Note" />
      </RouterLink>
      <!-- Note Switcher -->
      <CustomButton
        v-if="showNoteSwitcherButton"
        :iconPath="mdiBookMultipleOutline"
        label="Notes"
        class="flatnotes-navbar-icon-only"
        @click="toggleNoteDrawer"
      />
      <!-- Menu -->
      <CustomButton :iconPath="mdilMenu" label="Menu" @click="toggleMenu" />
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
            'flatnotes-navbar-icon-only': action.iconOnly,
            'flatnotes-navbar-action-active': action.active,
          }"
          @click="action.handler"
        >
          <div
            v-if="action.unsaved"
            class="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-theme-brand"
          ></div>
        </CustomButton>
      </template>
    </div>
  </nav>
</template>

<script setup>
import { mdiBookMultipleOutline, mdiUpdate } from "@mdi/js";
import {
  mdilLogout,
  mdilHome,
  mdilMagnify,
  mdilMenu,
  mdilMonitor,
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
        ? "Updating NirvNotes..."
        : "Update NirvNotes",
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
      label: "Toggle Theme",
      icon: mdilMonitor,
      command: toggleTheme,
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
  toast.add(getToastOptions("Downloading the NirvNotes update..."));
  const result = await installNativeClientUpdate();
  if (result?.started) {
    toast.add(
      getToastOptions(
        "Update verified. NirvNotes will restart now.",
        "Updating",
        "success",
      ),
    );
    return;
  }
  toast.add(
    getToastOptions(
      result?.error || "Could not start the NirvNotes update.",
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
  window.addEventListener("nirvnotes:native-ready", checkForNativeUpdate);
});

onBeforeUnmount(() => {
  window.clearTimeout(nativeUpdateCheckTimer);
  window.removeEventListener("nirvnotes:native-ready", checkForNativeUpdate);
});

const showNewButton = computed(() => {
  return globalStore.config.authType !== authTypes.readOnly;
});

const noteActions = computed(() => globalStore.noteActions || []);

const leadingNoteActions = computed(() =>
  noteActions.value.filter((action) => action.placement !== "end"),
);

const trailingNoteActions = computed(() =>
  noteActions.value.filter((action) => action.placement === "end"),
);

const showNoteSwitcherButton = computed(() => {
  return globalStore.config.authType != null;
});

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

function toggleNoteDrawer() {
  window.dispatchEvent(new CustomEvent("flatnotes:toggle-note-drawer"));
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
          result?.error || "Could not open a new NirvNotes window.",
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
.flatnotes-navbar {
  position: sticky;
  top: 0;
  z-index: 35;
  margin-inline: -0.45rem;
  padding-inline: 0.45rem;
  background-color: rgb(var(--theme-background));
  isolation: isolate;
}

@media print {
  .flatnotes-navbar {
    position: static;
  }
}

@media (max-width: 560px) {
  .flatnotes-navbar-actions {
    gap: 0.12rem;
  }

  .flatnotes-navbar-actions :deep(.flatnotes-custom-button) {
    min-width: 1.75rem;
    padding-inline: 0.42rem;
  }

  .flatnotes-navbar-actions :deep(.flatnotes-icon-label-text) {
    display: none;
  }

  .flatnotes-navbar-actions :deep(.flatnotes-icon-label-icon) {
    margin-right: 0 !important;
  }
}

.flatnotes-navbar-actions :deep(.flatnotes-navbar-icon-only) {
  display: inline-flex;
  min-width: 1.78rem;
  align-items: center;
  justify-content: center;
  padding-inline: 0.42rem;
}

.flatnotes-navbar-actions :deep(.flatnotes-navbar-action-active) {
  color: rgb(var(--theme-brand));
}

.flatnotes-navbar-actions
  :deep(.flatnotes-navbar-icon-only .flatnotes-icon-label-text) {
  display: none;
}

.flatnotes-navbar-actions
  :deep(.flatnotes-navbar-icon-only .flatnotes-icon-label-icon) {
  margin-right: 0 !important;
}
</style>
