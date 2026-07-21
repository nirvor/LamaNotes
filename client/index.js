import App from "/App.vue";
import PrimeVue from "primevue/config";
import ToastService from "primevue/toastservice";
import { createApp } from "vue";
import { createPinia } from "pinia";
import {
  filesFromLaunchParams,
  filesFromNativePayloads,
  publishExternalFileLaunch,
  publishExternalFileLaunchError,
  supportsFileHandlingLaunchQueue,
  supportsNativeFileBridge,
} from "./externalFiles.js";
import {
  loadDesktopFileSession,
  loadDesktopRouteSession,
  saveDesktopRouteSession,
} from "./desktopSession.js";
import { loadStoredToken } from "./tokenStorage.js";
import {
  isFileTransfer,
  isPlainTextTransfer,
  readPlainTextTransfer,
} from "./textDrop.js";
import router from "/router.js";

const app = createApp(App);
const pinia = createPinia();

loadStoredToken();

app.use(router);
app.use(pinia);
app.use(PrimeVue, { unstyled: true });
app.use(ToastService);

// Custom v-focus directive to focus on an element when mounted
app.directive("focus", {
  mounted(el) {
    el.focus();
  },
});

app.mount("#app");

let nativeHostInitialized = false;
let nativeLaunchConsumptionInFlight = null;

async function publishNativeFiles(payloads, message, options = {}) {
  const files = filesFromNativePayloads(payloads || []);
  if (!files.length) {
    return false;
  }

  publishExternalFileLaunch(
    files,
    message || "Opened from NirvNotes client.",
    options,
  );
  await router.push({ name: "openFile" }).catch(() => {});
  return true;
}

async function restoreNativeFileSession() {
  const currentRouteName = router.currentRoute.value.name;
  if (
    !supportsNativeFileBridge() ||
    !["home", "openFile"].includes(currentRouteName) ||
    routeWantsNativeLaunch()
  ) {
    return false;
  }
  const session = loadDesktopFileSession();
  if (!session?.paths?.length) {
    return false;
  }
  try {
    const payloads = await window.pywebview.api.restore_native_files(
      session.paths,
    );
    const activeIndex = payloads.findIndex(
      (payload) => payload.path === session.activePath,
    );
    if (activeIndex > 0) {
      payloads.unshift(payloads.splice(activeIndex, 1)[0]);
    }
    return publishNativeFiles(payloads, "Previous local session restored.", {
      restoreSession: session,
    });
  } catch (error) {
    console.error(error);
    return false;
  }
}

async function restoreNativeHostSession() {
  const routeSession = loadDesktopRouteSession();
  const restoredFiles = await restoreNativeFileSession();
  if (restoredFiles) {
    return true;
  }
  if (
    routeSession?.path &&
    routeSession.path !== "/" &&
    router.currentRoute.value.name === "home"
  ) {
    await router.replace(routeSession.path).catch(() => {});
    return true;
  }
  return false;
}

async function consumeNativeLaunchFiles() {
  if (!supportsNativeFileBridge()) {
    return false;
  }

  document.body.classList.add("nirvnotes-native-host");
  try {
    const payloads = await window.pywebview.api.consume_launch_files();
    return await publishNativeFiles(payloads, "Opened from Windows client.");
  } catch (error) {
    publishExternalFileLaunchError("Could not read the local file.");
    await router.push({ name: "openFile" }).catch(() => {});
    console.error(error);
    return false;
  }
}

function routeWantsNativeLaunch() {
  const route = router.currentRoute.value;
  return route.name === "openFile" && route.query.nativeLaunch === "1";
}

function scheduleNativeLaunchFileConsumption() {
  if (!supportsNativeFileBridge() || !routeWantsNativeLaunch()) {
    return;
  }

  if (nativeLaunchConsumptionInFlight) {
    return;
  }

  nativeLaunchConsumptionInFlight = consumeNativeLaunchFiles().finally(() => {
    nativeLaunchConsumptionInFlight = null;
  });
}

async function consumeNativeLaunchFilesNow() {
  if (nativeLaunchConsumptionInFlight) {
    return nativeLaunchConsumptionInFlight;
  }

  nativeLaunchConsumptionInFlight = consumeNativeLaunchFiles().finally(() => {
    nativeLaunchConsumptionInFlight = null;
  });
  return nativeLaunchConsumptionInFlight;
}

async function openNativeFilesFromDialog() {
  if (!supportsNativeFileBridge()) {
    return;
  }

  try {
    const payloads = await window.pywebview.api.open_local_files();
    await publishNativeFiles(payloads, "Loaded from Windows client.");
  } catch (error) {
    publishExternalFileLaunchError("Could not open the local file.");
    await router.push({ name: "openFile" }).catch(() => {});
    console.error(error);
  }
}

function syncWindowControlsOverlayClass() {
  const overlay = navigator.windowControlsOverlay;
  document.body.classList.toggle(
    "flatnotes-window-controls-overlay",
    Boolean(overlay?.visible),
  );
}

if ("windowControlsOverlay" in navigator) {
  syncWindowControlsOverlayClass();
  navigator.windowControlsOverlay.addEventListener(
    "geometrychange",
    syncWindowControlsOverlayClass,
  );
}

window.addEventListener(
  "nirvnotes:open-native-file-dialog",
  openNativeFilesFromDialog,
);

window.addEventListener("nirvnotes:native-file-drag-state", (event) => {
  document.body.classList.toggle(
    "nirvnotes-native-file-drag-active",
    Boolean(event.detail?.active),
  );
});

let nativeFileDragDepth = 0;
let nativeTextDragDepth = 0;
let internalDragActive = false;

function isNativeFileDrag(event) {
  return supportsNativeFileBridge() && isFileTransfer(event.dataTransfer);
}

function isExternalTextDrag(event) {
  return (
    !internalDragActive &&
    document.body.classList.contains("nirvnotes-text-drop-enabled") &&
    isPlainTextTransfer(event.dataTransfer)
  );
}

function showNativeFileDropTarget(active) {
  document.body.classList.toggle("nirvnotes-native-file-drag-active", active);
}

function showNativeTextDropTarget(active) {
  document.body.classList.toggle("nirvnotes-native-text-drag-active", active);
}

function clearDropTargets() {
  nativeFileDragDepth = 0;
  nativeTextDragDepth = 0;
  showNativeFileDropTarget(false);
  showNativeTextDropTarget(false);
}

window.addEventListener(
  "dragstart",
  () => {
    internalDragActive = true;
  },
  true,
);

window.addEventListener(
  "dragend",
  () => {
    internalDragActive = false;
    clearDropTargets();
  },
  true,
);

window.addEventListener("dragenter", (event) => {
  if (isNativeFileDrag(event)) {
    event.preventDefault();
    nativeFileDragDepth += 1;
    showNativeFileDropTarget(true);
  } else if (isExternalTextDrag(event)) {
    event.preventDefault();
    nativeTextDragDepth += 1;
    showNativeTextDropTarget(true);
  }
});

window.addEventListener("dragover", (event) => {
  if (!isNativeFileDrag(event) && !isExternalTextDrag(event)) {
    return;
  }
  event.preventDefault();
  event.dataTransfer.dropEffect = "copy";
});

window.addEventListener("dragleave", (event) => {
  if (document.body.classList.contains("nirvnotes-native-file-drag-active")) {
    nativeFileDragDepth = Math.max(0, nativeFileDragDepth - 1);
    if (nativeFileDragDepth === 0 || event.relatedTarget === null) {
      showNativeFileDropTarget(false);
    }
  }
  if (document.body.classList.contains("nirvnotes-native-text-drag-active")) {
    nativeTextDragDepth = Math.max(0, nativeTextDragDepth - 1);
    if (nativeTextDragDepth === 0 || event.relatedTarget === null) {
      showNativeTextDropTarget(false);
    }
  }
});

window.addEventListener("drop", (event) => {
  if (isNativeFileDrag(event)) {
    event.preventDefault();
    clearDropTargets();
    return;
  }
  if (!isExternalTextDrag(event)) {
    clearDropTargets();
    return;
  }

  const text = readPlainTextTransfer(event.dataTransfer);
  clearDropTargets();
  if (!text) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  window.dispatchEvent(
    new CustomEvent("nirvnotes:text-drop", {
      detail: {
        text,
        clientX: event.clientX,
        clientY: event.clientY,
      },
    }),
  );
});

window.addEventListener("blur", () => {
  internalDragActive = false;
  clearDropTargets();
});

window.addEventListener("nirvnotes:consume-native-launch-files", () => {
  consumeNativeLaunchFilesNow();
});

window.__nirvnotesConsumeNativeLaunchFiles = consumeNativeLaunchFilesNow;

async function initializeNativeHost() {
  if (nativeHostInitialized || !supportsNativeFileBridge()) {
    return;
  }

  nativeHostInitialized = true;
  await router.isReady();
  document.body.classList.add("nirvnotes-native-host");
  window.dispatchEvent(new CustomEvent("nirvnotes:native-ready"));
  if (routeWantsNativeLaunch()) {
    await consumeNativeLaunchFilesNow();
  } else {
    await restoreNativeHostSession();
  }
}

function scheduleNativeHostInitialization() {
  window.queueMicrotask(initializeNativeHost);
}

window.addEventListener("pywebviewready", scheduleNativeHostInitialization, {
  once: true,
});

router.afterEach((to) => {
  if (nativeHostInitialized) {
    saveDesktopRouteSession(to.fullPath);
  }
  window.setTimeout(scheduleNativeLaunchFileConsumption, 0);
});

if (supportsNativeFileBridge()) {
  document.body.classList.add("nirvnotes-native-host");
  window.addEventListener("load", scheduleNativeHostInitialization, {
    once: true,
  });
}

if (supportsFileHandlingLaunchQueue()) {
  window.launchQueue.setConsumer(async (launchParams) => {
    try {
      const files = await filesFromLaunchParams(launchParams);
      if (!files.length) {
        return;
      }

      publishExternalFileLaunch(files, "Opened from Windows.");
      await router.push({ name: "openFile" }).catch(() => {});
    } catch (error) {
      publishExternalFileLaunchError("Could not read the file from Windows.");
      await router.push({ name: "openFile" }).catch(() => {});
      console.error(error);
    }
  });
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    if (
      supportsNativeFileBridge() ||
      window.pywebview ||
      document.body.classList.contains("nirvnotes-native-host")
    ) {
      return;
    }

    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
