const shellCachePrefix = "lamanotes-shell-";
const shellVersion = "__LAMANOTES_SHELL_VERSION__";

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const response = await fetch("/offline-shell.json", {
        cache: "no-store",
      });
      if (!response.ok) throw new Error("Offline shell unavailable");
      const manifest = await response.json();
      if (
        manifest.version !== shellVersion ||
        !Array.isArray(manifest.resources)
      )
        throw new Error("Invalid offline shell");
      const cache = await caches.open(shellCachePrefix + manifest.version);
      await cache.addAll(manifest.resources);
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const current = shellCachePrefix + shellVersion;
      for (const name of await caches.keys()) {
        if (name.startsWith(shellCachePrefix) && name !== current)
          await caches.delete(name);
      }
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const target = new URL(event.request.url);
  if (
    event.request.method === "GET" &&
    target.origin === self.location.origin
  ) {
    if (
      event.request.mode === "navigate" &&
      !target.pathname.startsWith("/api/")
    ) {
      event.respondWith(navigateWithOfflineHome(event.request));
      return;
    }
    if (
      target.pathname.startsWith("/assets/") ||
      /\.(?:woff2?|ttf)$/.test(target.pathname)
    ) {
      event.respondWith(
        caches
          .match(event.request)
          .then((cached) => cached || fetch(event.request)),
      );
      return;
    }
  }
  if (
    event.request.method !== "POST" ||
    target.origin !== self.location.origin ||
    target.pathname !== "/capture/share"
  )
    return;
  event.respondWith(holdSharedSelection(event.request));
});

async function navigateWithOfflineHome(request) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3500);
  try {
    const response = await fetch(request, { signal: controller.signal });
    if (response.ok || response.status < 500) return response;
  } catch {
    // The cached home keeps quick capture available without a connection.
  } finally {
    clearTimeout(timeout);
  }
  const shell = await caches.match("/index.html");
  if (!shell) return Response.error();
  if (new URL(request.url).pathname !== "/")
    return Response.redirect(new URL("/", self.location.origin).href, 303);
  return shell;
}

async function holdSharedSelection(request) {
  try {
    const form = await request.formData();
    const files = form
      .getAll("files")
      .filter((value) => value instanceof File && value.size);
    if (
      files.length > 10 ||
      files.reduce((sum, file) => sum + file.size, 0) > 20 * 1024 * 1024
    )
      return new Response("Share up to 20 MB at once.", { status: 413 });
    const text = String(form.get("text") || "");
    const url = String(form.get("url") || "");
    const title = String(form.get("title") || "");
    if (text.length > 100000 || url.length > 4000 || title.length > 180)
      return new Response("The shared selection is too large.", {
        status: 413,
      });
    const id = crypto.randomUUID();
    const db = await new Promise((resolve, reject) => {
      const opening = indexedDB.open("lamanotes-private-intake-v1", 1);
      opening.onupgradeneeded = () =>
        opening.result.createObjectStore("incoming", { keyPath: "id" });
      opening.onsuccess = () => resolve(opening.result);
      opening.onerror = () => reject(opening.error);
    });
    await new Promise((resolve, reject) => {
      const tx = db.transaction("incoming", "readwrite");
      tx.objectStore("incoming").put({
        id,
        text,
        url,
        title,
        files,
        receivedAt: Date.now(),
      });
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    db.close();
    return Response.redirect(
      new URL(`/capture?incoming=${id}`, self.location.origin).href,
      303,
    );
  } catch {
    return new Response(
      "Could not hold the selection on this device. Open LamaNotes and select it again.",
      { status: 400 },
    );
  }
}
