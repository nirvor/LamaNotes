import { reactive } from "vue";

export const desktopShell = reactive({
  enabled: Boolean(window.__NIRVNOTES_DESKTOP_SHELL__),
  cloudOnline: null,
});

export const desktopFallbackConfig = Object.freeze({
  authType: "password",
  quickAccessHide: true,
  quickAccessTitle: "PINNED",
  quickAccessTerm: "#pinned",
  quickAccessSort: "lastModified",
  quickAccessLimit: 7,
});

export function markCloudOnline() {
  if (desktopShell.enabled) {
    desktopShell.cloudOnline = true;
  }
}

export function markCloudOffline() {
  if (desktopShell.enabled) {
    desktopShell.cloudOnline = false;
  }
}

export function isCloudNetworkError(error) {
  if (!desktopShell.enabled) {
    return false;
  }
  return (
    !error?.response ||
    error.response.headers?.["x-nirvnotes-upstream"] === "offline"
  );
}
