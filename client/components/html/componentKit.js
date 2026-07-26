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
    label: "Generic article",
    body: (selection) => `
<article class="lamanote lamanote-article" data-lamanotes-component="article">
  <p class="lamanote-kicker">Note</p>
  <h1>Descriptive note title</h1>
  <p class="lamanote-deck">${selectedOrFallback(
    selection,
    "Write one compact orientation sentence, or remove this deck.",
  )}</p>

  <section class="lamanote-section" data-lamanotes-component="section">
    <h2>Descriptive section title</h2>
    <div class="lamanote-section-card">
      <p>Replace this scaffold with the useful substance, or remove the card when plain prose is enough.</p>
    </div>
  </section>
</article>
`,
  },
  {
    id: "research-article",
    label: "Research article",
    body: (selection) => `
<article class="lamanote lamanote-article lamanote-research" data-lamanotes-component="article">
  <header class="lamanote-research-header" data-lamanotes-component="research-header">
    <p class="lamanote-kicker">Research Note</p>
    <h1>Descriptive research title</h1>
    <p class="lamanote-deck">${selectedOrFallback(
      selection,
      "State the question, scope, and central answer in one compact orientation paragraph.",
    )}</p>
  </header>

  <section class="lamanote-section lamanote-section--evidence" data-lamanotes-component="section">
    <p class="lamanote-section-eyebrow">Evidence</p>
    <h2>Evidence and interpretation</h2>
    <div class="lamanote-section-card">
      <p>Replace this scaffold with sourced evidence. Keep measurement, interpretation, and uncertainty visibly separate.</p>
    </div>
  </section>

  <section class="lamanote-result" data-lamanotes-component="result" data-result-kind="assessment">
    <p class="lamanote-result-label">Assessment</p>
    <p class="lamanote-result-main">State the type-appropriate result in one direct sentence.</p>
    <p class="lamanote-result-note">Name the condition, reservation, or next action which changes this result.</p>
  </section>

  <p class="lamanote-tags">#research #r-topic</p>
</article>
`,
  },
  {
    id: "section",
    label: "Section",
    body: (selection) => `
<section class="lamanote-section" data-lamanotes-component="section">
  <h2>Descriptive section title</h2>
  <div class="lamanote-section-card">
    <p>${selectedOrFallback(
      selection,
      "Group one major topic and its related subtopics in this section card.",
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
    id: "result",
    label: "Result / recommendation",
    body: (selection) => `
<section class="lamanote-result" data-lamanotes-component="result" data-result-kind="assessment">
  <p class="lamanote-result-label">Assessment</p>
  <p class="lamanote-result-main">${selectedOrFallback(
    selection,
    "State the type-appropriate result in one direct sentence.",
  )}</p>
  <p class="lamanote-result-note">Name the condition, reservation, or next action which changes this result.</p>
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
    id: "comparison-table",
    label: "Comparison table",
    body: () => `
<table class="lamanote-comparison" data-lamanotes-component="comparison">
  <caption>State what is compared, the date, and the decision context.</caption>
  <thead>
    <tr>
      <th scope="col">Option</th>
      <th scope="col">Comparable measure</th>
      <th scope="col">Important reservation</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th scope="row">Option A</th>
      <td>Value with unit and basis</td>
      <td>Condition which limits the comparison</td>
    </tr>
    <tr data-preferred="true">
      <th scope="row">Option B</th>
      <td>Value with the same unit and basis</td>
      <td>Why this is preferred, and for whom</td>
    </tr>
  </tbody>
</table>
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
    id: "panel",
    label: "Panel",
    body: (selection) => `
<aside class="lamanote-panel" data-lamanotes-component="panel">
  <h3>Panel title</h3>
  <p>${selectedOrFallback(
    selection,
    "Use a panel for a real decision, working instruction, or grouped reference.",
  )}</p>
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
  <p class="lamanote-visual-question"><strong>Question:</strong> State the quantitative comparison this plot answers.</p>
  <div class="lamanote-plot-pair" data-lamanotes-plot-engine="plotly">
    <img class="lamanote-plot-image lamanote-plot-image--light" src="attachments/example-plot-light.svg" alt="Describe the variables, comparison, direction, scale, and important exception" loading="lazy" decoding="async">
    <img class="lamanote-plot-image lamanote-plot-image--dark" src="attachments/example-plot-dark.svg" alt="Describe the variables, comparison, direction, scale, and important exception" loading="lazy" decoding="async">
  </div>
  <p class="lamanote-visual-takeaway">Takeaway: state the one relationship the reader should retain.</p>
  <figcaption><strong>Figure 1.</strong> Export the inspected Plotly figure through the shared Research toolkit. Keep the legend, axis titles, ticks, scale rationale, quantities and units, evidence date, assumptions or uncertainty, and a direct source.</figcaption>
</figure>
`,
  },
  {
    id: "diagram",
    label: "Diagram",
    body: () => `
<figure class="lamanote-diagram lamanote-flow lamanote-visual-frame" data-lamanotes-component="diagram">
  <pre><code class="language-mermaid">flowchart LR
    A["Input"] --> B["Process"]
    B --> C["Verification"]
    C --> D["Decision"]
    D --> E["Outcome"]</code></pre>
  <p class="lamanote-visual-takeaway">Takeaway: explain what the architecture or mechanism changes.</p>
  <figcaption><strong>Figure 2.</strong> Use the shared Mermaid renderer, short labels, rectangular unfilled nodes, clean connectors, one flow direction, and color only when it encodes meaning. Distinguish evidence-derived structure from illustration.</figcaption>
</figure>
`,
  },
  {
    id: "wide-diagram",
    label: "Wide diagram",
    body: () => `
<figure class="lamanote-diagram lamanote-flow lamanote-visual-frame lamanote-visual-wide" data-lamanotes-component="diagram">
  <pre><code class="language-mermaid">flowchart LR
    A["Input"] --> B["Process"] --> C["Verification"] --> D["Decision"] --> E["Outcome"]</code></pre>
  <p class="lamanote-visual-takeaway">Takeaway: explain what the architecture or mechanism changes.</p>
  <figcaption><strong>Figure 2.</strong> Keep the same rectangular Mermaid grammar. Use this wide variant only when readable labels require local horizontal panning.</figcaption>
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
    id: "steps",
    label: "Practical steps",
    body: () => `
<ol class="lamanote-steps" data-lamanotes-component="steps">
  <li>
    <div>
      <strong>Check the starting state.</strong>
      <p>Name the observable condition and the stop criterion before changing anything.</p>
    </div>
  </li>
  <li>
    <div>
      <strong>Perform one bounded action.</strong>
      <p>Give the command or manual step, the expected result, and the failure branch.</p>
    </div>
  </li>
  <li>
    <div>
      <strong>Verify the result.</strong>
      <p>Use an independent check and state what must remain unchanged.</p>
    </div>
  </li>
</ol>
`,
  },
  {
    id: "link-list",
    label: "Link list",
    body: () => `
<ul class="lamanote-link-list" data-lamanotes-component="link-list">
  <li><a href="https://example.com">Useful reference</a></li>
</ul>
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

const htmlPlaceholderChecks = [
  {
    id: "example-link",
    label: "example.com link",
    pattern: /https?:\/\/(?:www\.)?example\.com(?:[/"'<\s]|$)/i,
  },
  {
    id: "example-media",
    label: "example media path",
    pattern:
      /attachments\/example(?:[-_][a-z0-9_-]+)?\.(?:avif|gif|jpe?g|png|svg|webp)\b/i,
  },
  {
    id: "research-topic",
    label: "#r-topic facet",
    pattern: /(^|[\s>])#r-topic(?:[\s<]|$)/i,
  },
  {
    id: "scaffold-copy",
    label: "component scaffold text",
    pattern:
      /(Descriptive (?:note|research|section) title|Replace this scaffold|Main result or practical answer|Important caveat or uncertainty|Concrete next action|Short descriptive alt text|Important practical caveat or interpretation|Use a panel for a real decision|State the type-appropriate result|Comparable measure|Check the starting state|<div class="lamanote-metric-(?:label|value)">(?:Metric|Value)<\/div>|Takeaway: (?:state|explain)|First useful event or action|Second useful event or action)/i,
  },
];

export function getHtmlSnippet(id, selection = "") {
  const snippet = htmlComponentSnippets.find((item) => item.id === id);
  if (!snippet) {
    return "";
  }

  return snippet.body(selection);
}

export function findHtmlPlaceholderWarnings(html = "") {
  const value = String(html || "");
  return htmlPlaceholderChecks
    .filter(({ pattern }) => pattern.test(value))
    .map(({ id, label }) => ({ id, label }));
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
