const tokenStorageKey = "token";
const persistentSessionKey = "lamanotes:persistent-session";

function isDesktopShell() {
  return Boolean(window.__NIRVNOTES_DESKTOP_SHELL__);
}

function persistNativeToken(token, persist) {
  const api = window.pywebview?.api;
  if (!api) {
    return;
  }
  if (persist && api.store_auth_token) {
    void api.store_auth_token(token).catch(() => {});
  } else if (api.clear_auth_token) {
    void api.clear_auth_token().catch(() => {});
  }
}

export function storeToken(token, persist = false) {
  if (isDesktopShell()) {
    sessionStorage.setItem(tokenStorageKey, token);
    persistNativeToken(token, persist);
  } else {
    sessionStorage.removeItem(tokenStorageKey);
  }

  localStorage.removeItem(tokenStorageKey);
  if (persist) {
    localStorage.setItem(persistentSessionKey, "1");
  } else {
    localStorage.removeItem(persistentSessionKey);
  }
}

export function getStoredToken() {
  return sessionStorage.getItem(tokenStorageKey);
}

export function loadStoredToken() {
  const legacyToken = localStorage.getItem(tokenStorageKey);
  if (legacyToken && isDesktopShell()) {
    sessionStorage.setItem(tokenStorageKey, legacyToken);
    persistNativeToken(legacyToken, true);
    localStorage.setItem(persistentSessionKey, "1");
  }
  localStorage.removeItem(tokenStorageKey);
}

export function clearStoredToken() {
  sessionStorage.removeItem(tokenStorageKey);
  localStorage.removeItem(tokenStorageKey);
  localStorage.removeItem(persistentSessionKey);
  persistNativeToken("", false);
}

export function isCurrentTokenStored() {
  return localStorage.getItem(persistentSessionKey) === "1";
}
