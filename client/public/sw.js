self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  const target = new URL(event.request.url);
  if (
    event.request.method !== "POST" ||
    target.origin !== self.location.origin ||
    target.pathname !== "/capture/share"
  )
    return;
  event.respondWith(holdSharedSelection(event.request));
});

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
