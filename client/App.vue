<template>
  <LoadingIndicator
    ref="loadingIndicator"
    class="lamanotes-app-shell container mx-auto flex min-h-screen w-full min-w-0 max-w-full flex-col px-1.5 py-3 print:max-w-full"
    :class="{
      'lamanotes-app-shell-note': route.name === 'note' || route.name === 'new',
      'lamanotes-app-shell-dashboard': isDashboardRoute,
      'lamanotes-app-shell-note-work':
        isNoteRoute && globalStore.noteLayoutKind === 'work',
      'lamanotes-app-shell-note-article':
        isNoteRoute && globalStore.noteLayoutKind === 'article',
      'lamanotes-app-shell-note-markdown':
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
      class="lamanotes-cloud-offline-strip print:hidden"
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
import { reportNativeReady } from "./nativeTelemetry.js";
import { scheduleIdleWork } from "./performanceScheduling.js";
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
let cancelDeferredConfig = null;
let cancelIndexWarmup = null;

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
  cancelDeferredConfig?.();
  cancelIndexWarmup?.();
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
  // The first router navigation can still be resolving when App mounts.
  const localFirst =
    desktopShell.enabled &&
    (route.name === "openFile" || window.location.pathname === "/open-file");
  const warmConfig = desktopShell.enabled ? getCachedConfig() : null;
  if (warmConfig || localFirst) {
    globalStore.config = warmConfig || desktopFallbackConfig;
    markAppLoaded();
    if (!localFirst) {
      warmCommonNoteViews();
      scheduleIndexWarmup();
    }
  }

  const refreshConfig = () =>
    getConfig({ force: Boolean(warmConfig) })
      .then((data) => {
        globalStore.config = data;
        if (!warmConfig && !localFirst) {
          markAppLoaded();
          warmCommonNoteViews();
          scheduleIndexWarmup();
        }
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

  if (localFirst) {
    cancelDeferredConfig = scheduleIdleWork(refreshConfig, {
      delay: 900,
      timeout: 2200,
    });
  } else {
    void refreshConfig();
  }
}

let appReadyReported = false;
let appMarkedLoaded = false;

function markAppLoaded() {
  if (appMarkedLoaded) {
    return;
  }
  appMarkedLoaded = true;
  loadingIndicator.value?.setLoaded();
  performance.mark("lamanotes-app-ready");
  if (appReadyReported) {
    return;
  }
  appReadyReported = true;
  nextTick(() => {
    window.requestAnimationFrame(() => {
      reportNativeReady({
        phase: "shell",
        route: route.fullPath,
        browserMs: Math.round(performance.now()),
      });
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

function scheduleIndexWarmup() {
  cancelIndexWarmup?.();
  cancelIndexWarmup = scheduleIdleWork(
    () => void getSemanticIndex().catch(() => {}),
    { delay: desktopShell.enabled ? 700 : 250, timeout: 2200 },
  );
}

loadTheme();
</script>

<style scoped>
.lamanotes-app-shell {
  overflow: visible;
  padding-right: max(0.375rem, env(safe-area-inset-right));
  padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
  padding-left: max(0.375rem, env(safe-area-inset-left));
}

.lamanotes-app-shell-note {
  max-width: min(100%, var(--ln-content-max));
}

.lamanotes-app-shell-note-work {
  max-width: min(100%, 54rem);
}

.lamanotes-app-shell-note-markdown {
  max-width: min(100%, 58rem);
}

.lamanotes-app-shell-note-article {
  max-width: min(100%, var(--ln-content-max));
}

.lamanotes-app-shell-dashboard,
.lamanotes-app-shell-note.lamanotes-app-shell-dashboard {
  width: min(100%, calc(100vw - 1.5rem));
  max-width: none;
}

.lamanotes-cloud-offline-strip {
  align-self: flex-end;
  margin: -0.3rem 0 0.45rem;
  color: rgb(var(--theme-text-very-muted));
  font-size: 0.68rem;
  line-height: 1;
}
</style>
