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
  window.setTimeout(initializeNativeHost, 250);
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
