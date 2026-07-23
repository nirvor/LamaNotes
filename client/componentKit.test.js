import assert from "node:assert/strict";
import test from "node:test";

import {
  getHtmlSnippet,
  htmlComponentSnippets,
} from "./components/html/componentKit.js";

test("research article scaffold uses section cards and research tags", () => {
  const article = getHtmlSnippet("article");

  assert.match(article, /class="lamanote lamanote-research"/);
  assert.match(article, /class="lamanote-research-section /);
  assert.match(article, /class="lamanote-section-card"/);
  assert.match(article, /#private #research/);
});

test("plot and diagram scaffolds carry the visual quality contract", () => {
  const plot = getHtmlSnippet("plot");
  const diagram = getHtmlSnippet("diagram");

  assert.match(plot, /lamanote-plot lamanote-visual-frame/);
  assert.match(plot, /lamanote-visual-takeaway/);
  assert.match(plot, /quantities and units/);
  assert.match(diagram, /lamanote-diagram lamanote-visual-frame/);
  assert.match(diagram, /flow direction/);
  assert.ok(htmlComponentSnippets.some((snippet) => snippet.id === "section"));
});
