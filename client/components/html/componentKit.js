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
<article class="lamanote lamanote-research" data-lamanotes-component="article">
  <p class="lamanote-kicker">Research Note</p>
  <p class="lamanote-deck">${selectedOrFallback(
    selection,
    "One compact orientation sentence for the note.",
  )}</p>

  <section class="lamanote-summary" data-lamanotes-component="summary">
    <ul>
      <li>Main result or practical answer.</li>
      <li>Most important constraint or caveat.</li>
      <li>Concrete next action.</li>
    </ul>
  </section>

  <section class="lamanote-research-section lamanote-research-section--evidence" data-lamanotes-component="section">
    <h2>Evidence and interpretation</h2>
    <div class="lamanote-section-card">
      <p>Write the useful substance here. Keep established evidence, interpretation, and uncertainty visibly separate.</p>
    </div>
  </section>

  <section class="lamanote-source-list" data-lamanotes-component="sources">
    <h2>Sources</h2>
    <ul>
      <li><a href="https://example.com">Source title</a></li>
    </ul>
  </section>

  <p>#private #research</p>
</article>
`,
  },
  {
    id: "section",
    label: "Research section",
    body: (selection) => `
<section class="lamanote-research-section lamanote-research-section--evidence" data-lamanotes-component="section">
  <h2>Descriptive section title</h2>
  <div class="lamanote-section-card">
    <p>${selectedOrFallback(
      selection,
      "Evidence-backed section content. Group related subtopics in this one major section card.",
    )}</p>
  </div>
</section>
`,
  },
  {
    id: "summary",
    label: "Summary",
    body: (selection) => `
<section class="lamanote-summary" data-lamanotes-component="summary">
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
<figure class="lamanote-hero lamanote-hero-contained" data-lamanotes-component="hero">
  <img src="attachments/example-image.png" alt="Short descriptive alt text" loading="eager" decoding="async">
  <figcaption>Short caption.</figcaption>
</figure>
`,
  },
  {
    id: "metrics",
    label: "Metrics",
    body: () => `
<section class="lamanote-metrics" data-lamanotes-component="metrics">
  <div class="lamanote-metric">
    <div class="lamanote-metric-label">Metric</div>
    <div class="lamanote-metric-value">Value</div>
    <div class="lamanote-metric-note">Short context.</div>
  </div>
  <div class="lamanote-metric">
    <div class="lamanote-metric-label">Metric</div>
    <div class="lamanote-metric-value">Value</div>
    <div class="lamanote-metric-note">Short context.</div>
  </div>
</section>
`,
  },
  {
    id: "callout",
    label: "Callout",
    body: (selection) => `
<aside class="lamanote-callout" data-lamanotes-component="callout">
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
<section class="lamanote-media-row" data-lamanotes-component="media-row">
  <figure class="lamanotes-media-figure">
    <img src="attachments/example-a.png" alt="Image A" loading="lazy" decoding="async">
    <figcaption>Image A.</figcaption>
  </figure>
  <figure class="lamanotes-media-figure">
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
<figure class="lamanote-plot lamanote-visual-frame" data-lamanotes-component="plot">
  <img src="attachments/example-plot.png" alt="Describe the variables, comparison, direction, and important exception" loading="lazy" decoding="async">
  <p class="lamanote-visual-takeaway">Takeaway: state the one relationship the reader should retain.</p>
  <figcaption><strong>Figure 1.</strong> Define quantities and units, date the evidence, state important assumptions or uncertainty, and link the direct source.</figcaption>
</figure>
`,
  },
  {
    id: "diagram",
    label: "Diagram",
    body: () => `
<figure class="lamanote-diagram lamanote-visual-frame lamanote-visual-wide" data-lamanotes-component="diagram">
  <img src="attachments/example-diagram.png" alt="Describe the actors, flow direction, decision points, and final outcomes" loading="lazy" decoding="async">
  <p class="lamanote-visual-takeaway">Takeaway: explain what the architecture or mechanism changes.</p>
  <figcaption><strong>Figure 2.</strong> Name the flow direction, define color meaning, and distinguish measured structure from illustration.</figcaption>
</figure>
`,
  },
  {
    id: "timeline",
    label: "Timeline",
    body: () => `
<ol class="lamanote-timeline" data-lamanotes-component="timeline">
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
<section class="lamanote-source-list" data-lamanotes-component="sources">
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
  const safeAlt = escapeAttribute(
    altText || metadata.originalFilename || "Image",
  );
  const safeCaption = escapeHtml(altText || metadata.originalFilename || "");
  const width = metadata.width ? ` width="${Number(metadata.width)}"` : "";
  const height = metadata.height ? ` height="${Number(metadata.height)}"` : "";
  const assetFilename = metadata.filename
    ? ` data-lamanotes-asset-filename="${escapeHtml(metadata.filename)}"`
    : "";
  const assetHash = metadata.sha256
    ? ` data-lamanotes-asset-sha256="${escapeHtml(metadata.sha256)}"`
    : "";

  return `
<figure class="lamanotes-media-figure lamanote-media" data-lamanotes-component="media"${assetFilename}${assetHash}>
  <img src="${safeUrl}" alt="${safeAlt}" loading="lazy" decoding="async"${width}${height}>
  <figcaption>${safeCaption}</figcaption>
</figure>
`;
}

export function createLinkCardSnippet(url, label = "Link") {
  const safeUrl = escapeAttribute(url);
  const safeLabel = escapeHtml(label || "Link");

  return `
<aside class="lamanote-link-card" data-lamanotes-component="link">
  <a href="${safeUrl}" rel="noopener noreferrer">${safeLabel}</a>
  <span>${safeUrl}</span>
</aside>
`;
}

export function createCodeBlockSnippet(text, language = "text") {
  const safeLanguage = escapeAttribute(language || "text");
  const safeCode = escapeHtml(
    String(text || "")
      .replace(/\r\n?/g, "\n")
      .trimEnd(),
  );

  return `
<pre data-lamanotes-component="code"><code class="language-${safeLanguage}">${safeCode}</code></pre>
`;
}
