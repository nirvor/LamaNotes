import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const referenceRoot = new URL(
  "../docs/research-reference-notes/",
  import.meta.url,
);

const surfacedComponents = new Set([
  "lamanote-callout",
  "lamanote-comparison",
  "lamanote-link-card",
  "lamanote-panel",
  "lamanote-result",
  "lamanote-summary",
  "lamanote-visual-frame",
]);

function assertNoNestedSurfaces(html, type) {
  const stack = [];
  const voidElements = new Set([
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
  ]);
  const tagPattern = /<\/?([a-z][a-z0-9-]*)\b[^>]*>/gi;

  for (const match of html.matchAll(tagPattern)) {
    const source = match[0];
    const tag = match[1].toLowerCase();
    if (source.startsWith("</")) {
      const index = stack.findLastIndex((entry) => entry.tag === tag);
      if (index >= 0) {
        stack.length = index;
      }
      continue;
    }

    const classes =
      source
        .match(/\bclass="([^"]*)"/)?.[1]
        .split(/\s+/)
        .filter(Boolean) || [];
    if (
      classes.some((className) => surfacedComponents.has(className)) &&
      stack.some((entry) => entry.isSectionCard)
    ) {
      assert.fail(`${type} nests a surfaced component inside a section card`);
    }

    if (!source.endsWith("/>") && !voidElements.has(tag)) {
      stack.push({
        tag,
        isSectionCard: classes.includes("lamanote-section-card"),
      });
    }
  }
}

const fixtures = {
  research: {
    id: "lr-11111111111111111111111111111111",
    components: ["lamanote-plot", "lamanote-result"],
  },
  travel: {
    id: "lr-22222222222222222222222222222222",
    components: ["lamanote-map", "lamanote-comparison", "lamanote-result"],
  },
  shopping: {
    id: "lr-33333333333333333333333333333333",
    components: ["lamanote-comparison", "lamanote-steps", "lamanote-result"],
  },
  invest: {
    id: "lr-44444444444444444444444444444444",
    components: ["lamanote-plot", "lamanote-result"],
  },
  practical: {
    id: "lr-55555555555555555555555555555555",
    components: ["lamanote-steps", "lamanote-diagram", "lamanote-result"],
  },
  aluhut: {
    id: "lr-66666666666666666666666666666666",
    components: ["lamanote-diagram", "lamanote-comparison", "lamanote-result"],
  },
};

for (const [type, contract] of Object.entries(fixtures)) {
  test(`${type} reference note keeps its editorial and visual contract`, async () => {
    const html = await readFile(new URL(`${type}.html`, referenceRoot), "utf8");

    assert.match(
      html,
      new RegExp(
        `<meta\\s+name="lamanotes-research-id"\\s+content="${contract.id}"`,
      ),
    );
    assert.match(
      html,
      new RegExp(`<meta name="lamanotes-research-type" content="${type}"`),
    );
    assert.match(
      html,
      /<meta name="lamanotes-research-topic" content="r-fixture"/,
    );
    assert.match(html, /class="lamanote[^"]*lamanote-research"/);
    assert.match(html, /class="lamanote-research-header"/);
    assert.match(html, /class="lamanote-metrics"/);
    assert.equal(
      (html.match(/class="lamanote-section-eyebrow"/g) || []).length,
      3,
    );
    assert.match(html, /data-lamanotes-component="result"/);
    assert.match(
      html,
      /<p class="lamanote-tags">#research #r-fixture #design-reference<\/p>\s*<\/article>/,
    );
    assert.doesNotMatch(html, /\sstyle="/i);
    assert.doesNotMatch(html, /example\.com|attachments\/example/i);
    assertNoNestedSurfaces(html, type);
    for (const component of contract.components) {
      assert.match(html, new RegExp(`\\b${component}\\b`));
    }
    if (type === "practical" || type === "aluhut") {
      assert.match(html, /\blamanote-flow\b/);
      assert.match(html, /class="language-mermaid"/);
      assert.doesNotMatch(html, /<figure[^>]+lamanote-flow[\s\S]*?<svg/);
      assert.doesNotMatch(
        html,
        /<svg[\s\S]*?<rect[^>]+width="(?:820|900)"[^>]+height="(?:320|430|470)"/,
      );
    }
    if (contract.components.includes("lamanote-plot")) {
      assert.match(html, /data-lamanotes-plot-engine="plotly"/);
      assert.match(html, /lamanote-plot-image--light/);
      assert.match(html, /lamanote-plot-image--dark/);
      assert.doesNotMatch(html, /<figure[^>]+lamanote-plot[\s\S]*?<svg/);
    }
    assert.doesNotMatch(html, /\brx="[1-9]/);
  });
}
