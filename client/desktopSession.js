const DESKTOP_FILE_SESSION_KEY = "lamanotes:desktop-files:v1";
const DESKTOP_ROUTE_SESSION_KEY = "lamanotes:desktop-route:v1";
const DESKTOP_SCROLL_PREFIX = "lamanotes:route-scroll:";
let nativeDesktopSessionWrite = Promise.resolve();

export function loadDesktopFileSession() {
  try {
    return normalizeDesktopFileSession(
      JSON.parse(localStorage.getItem(DESKTOP_FILE_SESSION_KEY) || "null"),
    );
  } catch {
    localStorage.removeItem(DESKTOP_FILE_SESSION_KEY);
    return null;
  }
}

export async function loadHostDesktopFileSession() {
  const api = globalThis.window?.pywebview?.api;
  if (typeof api?.load_desktop_file_session !== "function") {
    return loadDesktopFileSession();
  }

  try {
    const session = normalizeDesktopFileSession(
      await api.load_desktop_file_session(),
    );
    if (!session) {
      localStorage.removeItem(DESKTOP_FILE_SESSION_KEY);
      return null;
    }
    storeLocalDesktopFileSession(session);
    return session;
  } catch (error) {
    console.error("Could not read the shared desktop file session.", error);
    return null;
  }
}

export function saveDesktopFileSession({ files, activePath, editMode }) {
  const session = normalizeDesktopFileSession({
    paths: files.map((file) => file.path),
    activePath,
    editMode,
    savedAt: Date.now(),
  });
  if (!session) {
    return Promise.resolve(false);
  }
  storeLocalDesktopFileSession(session);
  return queueNativeDesktopSessionOperation(
    "save_desktop_file_session",
    session,
  );
}

export function clearDesktopFileSession() {
  localStorage.removeItem(DESKTOP_FILE_SESSION_KEY);
  return queueNativeDesktopSessionOperation("clear_desktop_file_session");
}

export function loadDesktopRouteSession() {
  try {
    const session = JSON.parse(
      localStorage.getItem(DESKTOP_ROUTE_SESSION_KEY) || "null",
    );
    return typeof session?.path === "string" ? session : null;
  } catch {
    localStorage.removeItem(DESKTOP_ROUTE_SESSION_KEY);
    return null;
  }
}

export function saveDesktopRouteSession(path) {
  const normalizedPath = normalizeSessionRoute(path);
  if (!normalizedPath || normalizedPath.startsWith("/login")) {
    return;
  }
  localStorage.setItem(
    DESKTOP_ROUTE_SESSION_KEY,
    JSON.stringify({ path: normalizedPath, savedAt: Date.now() }),
  );
}

export function saveDesktopRouteScroll(path, position) {
  const key = routeScrollKey(path);
  if (key) {
    localStorage.setItem(key, String(Math.max(0, Number(position) || 0)));
  }
}

export function loadDesktopRouteScroll(path) {
  const key = routeScrollKey(path);
  return key ? Number(localStorage.getItem(key)) || 0 : 0;
}

function routeScrollKey(path) {
  const normalizedPath = normalizeSessionRoute(path);
  if (!normalizedPath || normalizedPath.startsWith("/open-file")) {
    return "";
  }
  return `${DESKTOP_SCROLL_PREFIX}${normalizedPath}`;
}

function normalizeSessionRoute(path) {
  try {
    const url = new URL(String(path || "/"), window.location.origin);
    url.searchParams.delete("nativeLaunch");
    url.searchParams.delete("handoff");
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return "/";
  }
}

function normalizeDesktopFileSession(session) {
  if (!session || !Array.isArray(session.paths)) {
    return null;
  }
  const paths = [
    ...new Set(
      session.paths
        .filter((path) => typeof path === "string")
        .map((path) => path.trim())
        .filter(Boolean),
    ),
  ];
  if (!paths.length) {
    return null;
  }
  return {
    paths,
    activePath: paths.includes(session.activePath)
      ? session.activePath
      : paths[0],
    editMode: Boolean(session.editMode),
    savedAt: Number.isFinite(Number(session.savedAt))
      ? Math.max(0, Number(session.savedAt))
      : Date.now(),
  };
}

function storeLocalDesktopFileSession(session) {
  localStorage.setItem(DESKTOP_FILE_SESSION_KEY, JSON.stringify(session));
}

function queueNativeDesktopSessionOperation(method, payload) {
  const api = globalThis.window?.pywebview?.api;
  if (typeof api?.[method] !== "function") {
    return Promise.resolve(false);
  }
  nativeDesktopSessionWrite = nativeDesktopSessionWrite
    .catch(() => false)
    .then(async () => {
      if (payload === undefined) {
        await api[method]();
      } else {
        await api[method](payload);
      }
      return true;
    })
    .catch((error) => {
      console.error("Could not update the shared desktop file session.", error);
      return false;
    });
  return nativeDesktopSessionWrite;
}
