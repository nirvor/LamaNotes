import assert from "node:assert/strict";
import test from "node:test";

import {
  findHtmlPlaceholderWarnings,
  getHtmlSnippet,
  htmlComponentSnippets,
} from "./components/html/componentKit.js";

test("generic article scaffold is tag-independent", () => {
  const article = getHtmlSnippet("article", "Selected orientation");

  assert.match(article, /class="lamanote lamanote-article"/);
  assert.match(article, /class="lamanote-section"/);
  assert.match(article, /class="lamanote-section-card"/);
  assert.doesNotMatch(article, /lamanote-research/);
  assert.doesNotMatch(article, /#(?:private|research|r-)/);
  assert.match(article, /Selected orientation/);
});

test("research article keeps research metadata explicit", () => {
  const article = getHtmlSnippet("research-article");

  assert.match(article, /class="lamanote lamanote-article lamanote-research"/);
  assert.match(article, /#research #r-topic/);
  assert.doesNotMatch(article, /#private/);
});

test("all picker snippets use the shared component contract", () => {
  htmlComponentSnippets.forEach((snippet) => {
    const html = getHtmlSnippet(snippet.id);
    assert.match(html, /data-lamanotes-component=/, snippet.id);
    assert.ok(
      findHtmlPlaceholderWarnings(html).length,
      `${snippet.id} should keep its replaceable scaffold visible to the quality check`,
    );
  });
});

test("plot and diagram scaffolds carry the visual quality contract", () => {
  const plot = getHtmlSnippet("plot");
  const diagram = getHtmlSnippet("diagram");
  const wideDiagram = getHtmlSnippet("wide-diagram");

  assert.match(plot, /lamanote-plot lamanote-visual-frame/);
  assert.match(plot, /lamanote-visual-question/);
  assert.match(plot, /lamanote-visual-takeaway/);
  assert.match(plot, /quantities and units/);
  assert.match(diagram, /lamanote-diagram lamanote-visual-frame/);
  assert.match(diagram, /flow direction/);
  assert.doesNotMatch(diagram, /lamanote-visual-wide/);
  assert.match(wideDiagram, /lamanote-visual-wide/);
});

test("placeholder checks are narrow and non-blocking", () => {
  const warnings = findHtmlPlaceholderWarnings(
    `${getHtmlSnippet("research-article")}${getHtmlSnippet("plot")}`,
  );

  assert.deepEqual(
    warnings.map(({ id }) => id),
    ["example-media", "research-topic", "scaffold-copy"],
  );
  assert.deepEqual(
    findHtmlPlaceholderWarnings(`
      <article class="lamanote lamanote-article">
        <h1>Measured result</h1>
        <p>Real content with #research and #r-agent-tools.</p>
        <img src="attachments/figure-2.png" alt="Measured comparison">
      </article>
    `),
    [],
  );
});
