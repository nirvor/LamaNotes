const DESKTOP_FILE_SESSION_KEY = "lamanotes:desktop-files:v1";
const DESKTOP_ROUTE_SESSION_KEY = "lamanotes:desktop-route:v1";
const DESKTOP_SCROLL_PREFIX = "lamanotes:route-scroll:";

export function loadDesktopFileSession() {
  try {
    const session = JSON.parse(
      localStorage.getItem(DESKTOP_FILE_SESSION_KEY) || "null",
    );
    if (!session || !Array.isArray(session.paths)) {
      return null;
    }
    const paths = session.paths.filter(
      (path) => typeof path === "string" && path.trim(),
    );
    return paths.length ? { ...session, paths } : null;
  } catch {
    localStorage.removeItem(DESKTOP_FILE_SESSION_KEY);
    return null;
  }
}

export function saveDesktopFileSession({ files, activePath, editMode }) {
  const paths = [...new Set(files.map((file) => file.path).filter(Boolean))];
  if (!paths.length) {
    return;
  }
  localStorage.setItem(
    DESKTOP_FILE_SESSION_KEY,
    JSON.stringify({
      paths,
      activePath: activePath || paths[0],
      editMode: Boolean(editMode),
      savedAt: Date.now(),
    }),
  );
}

export function clearDesktopFileSession() {
  localStorage.removeItem(DESKTOP_FILE_SESSION_KEY);
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
