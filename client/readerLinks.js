function externalUrl(value, documentUrl) {
  try {
    const url = new URL(value, documentUrl);
    if (
      !["https:", "http:"].includes(url.protocol) ||
      url.origin === new URL(documentUrl).origin ||
      url.username ||
      url.password
    ) {
      return null;
    }
    return url.href;
  } catch {
    return null;
  }
}

function sourceUrl(root, fragment, documentUrl) {
  let id;
  try {
    id = decodeURIComponent(fragment.slice(1));
  } catch {
    return null;
  }
  const targets = [...root.querySelectorAll("[id]")].filter(
    (element) => element.id === id,
  );
  if (targets.length !== 1) return null;
  const target = targets[0];
  const entry = target.closest("li") || target;
  if (
    !/^(?:quelle|source|ref|reference|cite|fn)[-_]?\d+$/i.test(id) &&
    !entry.closest(
      '.lamanote-sources, .flatnote-sources, [role="doc-bibliography"], [data-lamanotes-component="sources"]',
    )
  ) {
    return null;
  }
  const urls = new Set(
    [...entry.querySelectorAll("a[href]")]
      .map((link) => externalUrl(link.getAttribute("href"), documentUrl))
      .filter(Boolean),
  );
  return urls.size === 1 ? [...urls][0] : null;
}

export function enhanceReaderLinks(root, documentUrl) {
  const page = new URL(documentUrl);
  page.hash = "";
  for (const link of root.querySelectorAll("a[href]")) {
    const raw = link.getAttribute("href").trim();
    const source = raw.startsWith("#") ? sourceUrl(root, raw, page.href) : null;
    const external = source || externalUrl(raw, page.href);
    if (external && !link.hasAttribute("download")) {
      link.setAttribute("href", external);
      link.setAttribute("target", "_blank");
      const rel = new Set(
        (link.getAttribute("rel") || "").split(/\s+/).filter(Boolean),
      );
      rel.add("noopener");
      rel.add("noreferrer");
      link.setAttribute("rel", [...rel].join(" "));
    } else if (raw.startsWith("#")) {
      // The app's <base href="/"> must not detach an anchor from its note.
      link.setAttribute("href", page.href + raw);
    }
  }
}

export function openNativeReaderLink(event, host = globalThis.window) {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.ctrlKey ||
    event.metaKey ||
    event.shiftKey ||
    event.altKey
  )
    return;
  const link = event.target?.closest?.('a[target="_blank"][href]');
  if (
    !link ||
    !event.currentTarget.contains(link) ||
    link.hasAttribute("download")
  )
    return;
  const url = externalUrl(link.getAttribute("href"), host.location.href);
  if (!url?.startsWith("https:") || !host.pywebview?.api?.open_external_url)
    return;
  event.preventDefault();
  Promise.resolve(host.pywebview.api.open_external_url(url))
    .then((result) => {
      if (!result?.opened) host.open(url, "_blank", "noopener,noreferrer");
    })
    .catch(() => host.open(url, "_blank", "noopener,noreferrer"));
}
