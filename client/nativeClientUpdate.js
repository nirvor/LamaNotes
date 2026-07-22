import { reactive } from "vue";

export const nativeClientUpdate = reactive({
  checked: false,
  available: false,
  canInstall: false,
  installing: false,
  currentVersion: "",
  version: "",
  error: "",
});

let checkInFlight = null;

export function supportsNativeClientUpdate() {
  return Boolean(window.pywebview?.api?.get_client_update_status);
}

export async function checkNativeClientUpdate(force = false) {
  if (!supportsNativeClientUpdate()) {
    return nativeClientUpdate;
  }
  if (checkInFlight && !force) {
    return checkInFlight;
  }

  checkInFlight = window.pywebview.api
    .get_client_update_status(force)
    .then((status) => {
      Object.assign(nativeClientUpdate, {
        checked: true,
        available: Boolean(status?.available),
        canInstall: Boolean(status?.canInstall),
        currentVersion: status?.currentVersion || "",
        version: status?.version || "",
        error: status?.error || "",
      });
      return nativeClientUpdate;
    })
    .catch((error) => {
      nativeClientUpdate.checked = true;
      nativeClientUpdate.error = "Could not check for LamaNotes updates.";
      console.error(error);
      return nativeClientUpdate;
    })
    .finally(() => {
      checkInFlight = null;
    });
  return checkInFlight;
}

export async function installNativeClientUpdate() {
  if (!window.pywebview?.api?.install_client_update) {
    return { started: false, error: "Native update support is unavailable." };
  }

  nativeClientUpdate.installing = true;
  try {
    const result = await window.pywebview.api.install_client_update();
    if (!result?.started) {
      nativeClientUpdate.error = result?.error || "Could not start the update.";
    }
    return result;
  } finally {
    nativeClientUpdate.installing = false;
  }
}
