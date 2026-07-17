function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/"/g, "&quot;");
}

function selectedOrFallback(selection, fallback) {
  const trimmed = String(selection || "").trim();
  return trimmed ? escapeHtml(trimmed) : fallback;
}

export const htmlComponentSnippets = [
  {
    id: "article",
    label: "Article",
    body: (selection) => `
<article class="flatnote" data-flatnotes-component="article">
  <p class="flatnote-kicker">Research Note</p>
  <p class="flatnote-deck">${selectedOrFallback(
    selection,
    "One compact orientation sentence for the note.",
  )}</p>

  <section class="flatnote-summary" data-flatnotes-component="summary">
    <ul>
      <li>Main result or practical answer.</li>
      <li>Most important constraint or caveat.</li>
      <li>Concrete next action.</li>
    </ul>
  </section>

  <h2>Notes</h2>
  <p>Write the useful substance here.</p>

  <section class="flatnote-source-list" data-flatnotes-component="sources">
    <h2>Sources</h2>
    <ul>
      <li><a href="https://example.com">Source title</a></li>
    </ul>
  </section>

  <p>#private</p>
</article>
`,
  },
  {
    id: "summary",
    label: "Summary",
    body: (selection) => `
<section class="flatnote-summary" data-flatnotes-component="summary">
  <ul>
    <li>${selectedOrFallback(selection, "Main result or answer.")}</li>
    <li>Important caveat or uncertainty.</li>
    <li>Concrete next action.</li>
  </ul>
</section>
`,
  },
  {
    id: "hero",
    label: "Hero",
    body: () => `
<figure class="flatnote-hero flatnote-hero-contained" data-flatnotes-component="hero">
  <img src="attachments/example-image.png" alt="Short descriptive alt text" loading="eager" decoding="async">
  <figcaption>Short caption.</figcaption>
</figure>
`,
  },
  {
    id: "metrics",
    label: "Metrics",
    body: () => `
<section class="flatnote-metrics" data-flatnotes-component="metrics">
  <div class="flatnote-metric">
    <div class="flatnote-metric-label">Metric</div>
    <div class="flatnote-metric-value">Value</div>
    <div class="flatnote-metric-note">Short context.</div>
  </div>
  <div class="flatnote-metric">
    <div class="flatnote-metric-label">Metric</div>
    <div class="flatnote-metric-value">Value</div>
    <div class="flatnote-metric-note">Short context.</div>
  </div>
</section>
`,
  },
  {
    id: "callout",
    label: "Callout",
    body: (selection) => `
<aside class="flatnote-callout" data-flatnotes-component="callout">
  <strong>Note.</strong> ${selectedOrFallback(
    selection,
    "Important practical caveat or interpretation.",
  )}
</aside>
`,
  },
  {
    id: "media-row",
    label: "Media row",
    body: () => `
<section class="flatnote-media-row" data-flatnotes-component="media-row">
  <figure class="flatnotes-media-figure">
    <img src="attachments/example-a.png" alt="Image A" loading="lazy" decoding="async">
    <figcaption>Image A.</figcaption>
  </figure>
  <figure class="flatnotes-media-figure">
    <img src="attachments/example-b.png" alt="Image B" loading="lazy" decoding="async">
    <figcaption>Image B.</figcaption>
  </figure>
</section>
`,
  },
  {
    id: "plot",
    label: "Plot",
    body: () => `
<figure class="flatnote-plot" data-flatnotes-component="plot">
  <img src="attachments/example-plot.png" alt="Plot description" loading="lazy" decoding="async">
  <figcaption>Plot caption with the takeaway, not just the filename.</figcaption>
</figure>
`,
  },
  {
    id: "timeline",
    label: "Timeline",
    body: () => `
<ol class="flatnote-timeline" data-flatnotes-component="timeline">
  <li>
    <time>Step 1</time>
    <span>First useful event or action.</span>
  </li>
  <li>
    <time>Step 2</time>
    <span>Second useful event or action.</span>
  </li>
</ol>
`,
  },
  {
    id: "sources",
    label: "Sources",
    body: () => `
<section class="flatnote-source-list" data-flatnotes-component="sources">
  <h2>Sources</h2>
  <ul>
    <li><a href="https://example.com">Source title</a></li>
  </ul>
</section>
`,
  },
];

export function getHtmlSnippet(id, selection = "") {
  const snippet = htmlComponentSnippets.find((item) => item.id === id);
  if (!snippet) {
    return "";
  }

  return snippet.body(selection);
}

export function createMediaFigureSnippet(url, altText, metadata = {}) {
  const safeUrl = escapeAttribute(url);
  const safeAlt = escapeAttribute(altText || metadata.originalFilename || "Image");
  const safeCaption = escapeHtml(altText || metadata.originalFilename || "");
  const width = metadata.width ? ` width="${Number(metadata.width)}"` : "";
  const height = metadata.height ? ` height="${Number(metadata.height)}"` : "";
  const assetFilename = metadata.filename
    ? ` data-flatnotes-asset-filename="${escapeHtml(metadata.filename)}"`
    : "";
  const assetHash = metadata.sha256
    ? ` data-flatnotes-asset-sha256="${escapeHtml(metadata.sha256)}"`
    : "";

  return `
<figure class="flatnotes-media-figure flatnote-media" data-flatnotes-component="media"${assetFilename}${assetHash}>
  <img src="${safeUrl}" alt="${safeAlt}" loading="lazy" decoding="async"${width}${height}>
  <figcaption>${safeCaption}</figcaption>
</figure>
`;
}

export function createLinkCardSnippet(url, label = "Link") {
  const safeUrl = escapeAttribute(url);
  const safeLabel = escapeHtml(label || "Link");

  return `
<aside class="flatnote-link-card" data-flatnotes-component="link">
  <a href="${safeUrl}" rel="noopener noreferrer">${safeLabel}</a>
  <span>${safeUrl}</span>
</aside>
`;
}

export function createCodeBlockSnippet(text, language = "text") {
  const safeLanguage = escapeAttribute(language || "text");
  const safeCode = escapeHtml(String(text || "").replace(/\r\n?/g, "\n").trimEnd());

  return `
<pre data-flatnotes-component="code"><code class="language-${safeLanguage}">${safeCode}</code></pre>
`;
}
