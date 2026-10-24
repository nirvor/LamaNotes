export const shareDatabase = "lamanotes-private-intake-v1";

export async function openIntake() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(shareDatabase, 1);
    request.onupgradeneeded = () =>
      request.result.createObjectStore("incoming", { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function readIncoming(id) {
  if (!/^[a-f0-9-]{36}$/.test(id || "")) return null;
  const db = await openIntake();
  return new Promise((resolve, reject) => {
    const request = db.transaction("incoming").objectStore("incoming").get(id);
    request.onsuccess = () => {
      db.close();
      resolve(request.result || null);
    };
    request.onerror = () => {
      db.close();
      reject(request.error);
    };
  });
}

export async function discardIncoming(id) {
  if (!id) return;
  const db = await openIntake();
  await new Promise((resolve, reject) => {
    const tx = db.transaction("incoming", "readwrite");
    tx.objectStore("incoming").delete(id);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export function captureKind(file, url) {
  if (file?.type?.startsWith("image/")) return "image";
  if (file?.type?.startsWith("audio/")) return "audio";
  if (file) return "file";
  return url ? "link" : "text";
}

export function sharedSelection(incoming) {
  let text = String(incoming.text || '').trim(), url = String(incoming.url || '').trim();
  if (!url && /^https?:\/\/\S+$/i.test(text)) { url = text; text = ''; }
  const suggested = incoming.title || text.split('\n')[0] || incoming.files?.[0]?.name || (url ? new URL(url).hostname : 'Shared note');
  const title = String(suggested).replace(/[<>:"/\\|?*\u0000-\u001f]/g, ' ').trim().replace(/\.+$/, '').slice(0, 180) || 'Shared note';
  return { title, text, url };
}

export function validateSelection(text, url, files) {
  if (text.length > 100000 || url.length > 4000) throw new Error('The shared text or link is too large.');
  if (files.length > 10 || files.reduce((total, file) => total + file.size, 0) > 20 * 1024 * 1024) throw new Error('Share up to 10 files, 20 MB in total.');
  if (url) {
    const parsed = new URL(url);
    if (!['https:', 'http:'].includes(parsed.protocol) || parsed.username || parsed.password) throw new Error('Use an HTTP or HTTPS source link without login details.');
  }
}

export function captureNoteHtml(text, url, assets = []) {
  const escape = (value) =>
    String(value).replace(
      /[&<>"']/g,
      (char) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[char],
    );
  const source =
    url && /^https?:\/\//i.test(url)
      ? `<p><a href="${escape(url)}">Source</a></p>`
      : "";
  const figures = assets
    .filter((asset) => asset.mediaType.startsWith("image/"))
    .map(
      (asset) =>
        `<figure class="lamanote-media"><img src="/api/private/v1/assets/${asset.assetId}/content" alt="${escape(asset.name || 'Image')}"></figure>`,
    )
    .join("\n");
  const audio = assets.filter(asset => asset.mediaType.startsWith('audio/')).map(asset => `<figure class="lamanote-media"><audio controls preload="metadata" src="/api/private/v1/assets/${asset.assetId}/content"></audio><figcaption>${escape(asset.name || 'Audio')}</figcaption></figure>`).join('\n');
  const files = assets
    .filter((asset) => !asset.mediaType.startsWith("image/") && !asset.mediaType.startsWith('audio/'))
    .map(
      (asset) =>
        `<p><a href="/api/private/v1/assets/${asset.assetId}/content" download>${escape(asset.name || asset.mediaType)}</a></p>`,
    )
    .join("\n");
  return `<article class="lamanote lamanote-article" data-lamanotes-component="article">${text
    .split(/\n\s*\n/)
    .filter(Boolean)
    .map((paragraph) => `<p>${escape(paragraph).replace(/\n/g, "<br>")}</p>`)
    .join("\n")}${source}${figures}${audio}${files}</article>`;
}
