<template>
  <LoadingIndicator
    ref="loadingIndicator"
    class="flatnotes-app-shell container mx-auto flex min-h-screen w-full min-w-0 max-w-full flex-col px-1.5 py-3 print:max-w-full"
    :class="{
      'flatnotes-app-shell-note': route.name === 'note' || route.name === 'new',
      'flatnotes-app-shell-dashboard': isDashboardRoute,
      'flatnotes-app-shell-note-work':
        isNoteRoute && globalStore.noteLayoutKind === 'work',
      'flatnotes-app-shell-note-research':
        isNoteRoute && globalStore.noteLayoutKind === 'research',
      'flatnotes-app-shell-note-markdown':
        isNoteRoute && globalStore.noteLayoutKind === 'markdown',
    }"
  >
    <PrimeToast />
    <SearchModal v-if="isSearchModalVisible" v-model="isSearchModalVisible" />
    <NavBar
      v-if="showNavBar"
      ref="navBar"
      :class="{
        'print:hidden': route.name == 'note',
      }"
      @toggleSearchModal="toggleSearchModal"
    />
    <div
      v-if="desktopShell.enabled && desktopShell.cloudOnline === false"
      class="flatnotes-cloud-offline-strip print:hidden"
      role="status"
    >
      Cloud unavailable. Local files remain editable.
    </div>
    <RouterView />
  </LoadingIndicator>
</template>

<script setup>
import Mousetrap from "mousetrap";
import "mousetrap/plugins/global-bind/mousetrap-global-bind";
import { useToast } from "primevue/usetoast";
import {
  computed,
  defineAsyncComponent,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { RouterView, useRoute } from "vue-router";

import {
  apiErrorHandler,
  getCachedConfig,
  getConfig,
  getSemanticIndex,
} from "./api.js";
import PrimeToast from "./components/PrimeToast.vue";
import { useGlobalStore } from "./globalStore.js";
import { loadTheme } from "./helpers.js";
import {
  desktopFallbackConfig,
  desktopShell,
  isCloudNetworkError,
} from "./desktopShell.js";
import {
  loadDesktopRouteScroll,
  saveDesktopRouteScroll,
} from "./desktopSession.js";
import NavBar from "./partials/NavBar.vue";
import LoadingIndicator from "./components/LoadingIndicator.vue";
import { openNewNote } from "./newNoteNavigation.js";
import router from "./router.js";

const SearchModal = defineAsyncComponent(
  () => import("./partials/SearchModal.vue"),
);

const globalStore = useGlobalStore();
const isSearchModalVisible = ref(false);
const loadingIndicator = ref();
const navBar = ref();
const route = useRoute();
const toast = useToast();

// '/' to search
Mousetrap.bind("/", () => {
  if (route.name !== "login") {
    toggleSearchModal();
    return false;
  }
});

// 'CTRL + ALT/OPT + N' to create new note
Mousetrap.bindGlobal("ctrl+alt+n", () => {
  if (route.name !== "login") {
    openNewNote(router);
    return false;
  }
});

// 'CTRL + ALT/OPT + H' to go to home
Mousetrap.bindGlobal("ctrl+alt+h", () => {
  if (route.name !== "login") {
    router.push({ name: "home" });
    return false;
  }
});

let routeScrollTimer = null;

onMounted(() => {
  loadInitialConfig();
  if (desktopShell.enabled) {
    window.addEventListener("scroll", scheduleRouteScrollSave, {
      passive: true,
    });
    restoreRouteScroll(route.fullPath);
  }
});

onBeforeUnmount(() => {
  window.clearTimeout(routeScrollTimer);
  saveCurrentRouteScroll();
  window.removeEventListener("scroll", scheduleRouteScrollSave);
});

watch(
  () => route.fullPath,
  (path, previousPath) => {
    if (!desktopShell.enabled) {
      return;
    }
    if (previousPath) {
      saveDesktopRouteScroll(previousPath, window.scrollY);
    }
    restoreRouteScroll(path);
  },
);

function loadInitialConfig() {
  const warmConfig = desktopShell.enabled ? getCachedConfig() : null;
  if (warmConfig) {
    globalStore.config = warmConfig;
    markAppLoaded();
    warmCommonNoteViews();
    void getSemanticIndex().catch(() => {});
  }

  getConfig({ force: Boolean(warmConfig) })
    .then((data) => {
      globalStore.config = data;
      if (!warmConfig) {
        markAppLoaded();
        warmCommonNoteViews();
      }
      void getSemanticIndex().catch(() => {});
    })
    .catch((error) => {
      if (
        isCloudNetworkError(error) ||
        (desktopShell.enabled &&
          route.name === "openFile" &&
          error.response?.status === 401)
      ) {
        globalStore.config = desktopFallbackConfig;
        markAppLoaded();
        return;
      }
      apiErrorHandler(error, toast);
      loadingIndicator.value?.setFailed();
    });
}

let appReadyReported = false;
let appMarkedLoaded = false;

function markAppLoaded() {
  if (appMarkedLoaded) {
    return;
  }
  appMarkedLoaded = true;
  loadingIndicator.value?.setLoaded();
  performance.mark("nirvnotes-app-ready");
  if (appReadyReported || !window.pywebview?.api?.report_client_ready) {
    return;
  }
  appReadyReported = true;
  nextTick(() => {
    window.requestAnimationFrame(() => {
      window.pywebview.api
        .report_client_ready({
          phase: "shell",
          route: route.fullPath,
          browserMs: Math.round(performance.now()),
        })
        .catch(() => {});
    });
  });
}

const showNavBar = computed(() => {
  return route.name !== "login";
});

const isNoteRoute = computed(
  () => route.name === "note" || route.name === "new",
);

const isDashboardRoute = computed(() => {
  if (route.name !== "note") {
    return false;
  }
  const title = normalizeNoteTitle(route.params.title);
  return (
    title === "nirv-bot" ||
    title === "nirv bot status" ||
    title.startsWith("nirv bot ") ||
    title.startsWith("nirv-bot ")
  );
});

function normalizeNoteTitle(value) {
  const raw = Array.isArray(value) ? value[0] : value;
  const text = String(raw || "");
  try {
    return decodeURIComponent(text).trim().toLowerCase().replace(/\s+/g, " ");
  } catch {
    return text.trim().toLowerCase().replace(/\s+/g, " ");
  }
}

function toggleSearchModal() {
  isSearchModalVisible.value = !isSearchModalVisible.value;
}

function scheduleRouteScrollSave() {
  window.clearTimeout(routeScrollTimer);
  routeScrollTimer = window.setTimeout(saveCurrentRouteScroll, 120);
}

function saveCurrentRouteScroll() {
  saveDesktopRouteScroll(route.fullPath, window.scrollY);
}

function restoreRouteScroll(path) {
  const position = loadDesktopRouteScroll(path);
  nextTick(() => window.scrollTo({ top: position, behavior: "instant" }));
}

function warmCommonNoteViews() {
  const warmLightViews = () => {
    void Promise.all([
      import("./components/html/HtmlViewer.vue"),
      import("./components/work/WorkNoteViewer.vue"),
    ]).catch(() => {});
  };
  const warmMarkdownView = () => {
    void import("./components/toastui/ToastViewer.vue").catch(() => {});
  };

  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(warmLightViews, { timeout: 1200 });
    window.setTimeout(
      () => window.requestIdleCallback(warmMarkdownView, { timeout: 3500 }),
      desktopShell.enabled ? 1800 : 700,
    );
  } else {
    window.setTimeout(warmLightViews, 500);
    window.setTimeout(warmMarkdownView, desktopShell.enabled ? 2600 : 1200);
  }
}

loadTheme();
</script>

<style scoped>
.flatnotes-app-shell {
  overflow: visible;
}

.flatnotes-app-shell-note {
  max-width: min(100%, 68rem);
}

.flatnotes-app-shell-note-work {
  max-width: min(100%, 54rem);
}

.flatnotes-app-shell-note-markdown {
  max-width: min(100%, 58rem);
}

.flatnotes-app-shell-note-research {
  max-width: min(100%, 76rem);
}

.flatnotes-app-shell-dashboard,
.flatnotes-app-shell-note.flatnotes-app-shell-dashboard {
  width: min(100%, calc(100vw - 1.5rem));
  max-width: none;
}

.flatnotes-cloud-offline-strip {
  align-self: flex-end;
  margin: -0.3rem 0 0.45rem;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.68rem;
  line-height: 1;
}
</style>
