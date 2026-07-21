import { reactive } from "vue";

export const desktopShell = reactive({
  enabled: Boolean(window.__NIRVNOTES_DESKTOP_SHELL__),
  cloudOnline: null,
});

export const desktopFallbackConfig = Object.freeze({
  authType: "password",
  googleAuthEnabled: false,
  passwordLoginEnabled: true,
  quickAccessHide: true,
  quickAccessTitle: "PINNED",
  quickAccessTerm: "#pinned",
  quickAccessSort: "lastModified",
  quickAccessLimit: 7,
});

let currentWindowLabel = "";

export function setDesktopWindowTitle(label = "") {
  if (!desktopShell.enabled) {
    return;
  }
  const normalized = String(label || "")
    .replace(/[\r\n\t]+/g, " ")
    .trim();
  document.title = normalized ? `NirvNotes - ${normalized}` : "NirvNotes";
  if (normalized === currentWindowLabel) {
    return;
  }
  currentWindowLabel = normalized;
  const setter = window.pywebview?.api?.set_window_title;
  if (setter) {
    Promise.resolve(setter(normalized)).catch(() => {});
  }
}

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
