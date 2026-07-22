import assert from "node:assert/strict";
import test from "node:test";

import {
  alignMarkdownTables,
  availableDocumentAutomations,
  cleanMarkdown,
  repairMarkdown,
  runDocumentAutomation,
} from "./documentAutomation.js";

test("markdown tools are context-aware and table alignment is conditional", () => {
  assert.deepEqual(
    availableDocumentAutomations("markdown", "# Note\n").map(({ id }) => id),
    ["clean-markdown", "repair-markdown"],
  );
  assert.deepEqual(
    availableDocumentAutomations(
      "md",
      "| A | B |\n| --- | --- |\n| x | yy |\n",
    ).map(({ id }) => id),
    ["clean-markdown", "align-tables", "repair-markdown"],
  );
});

test("clean markdown fixes headings, blank space and duplicate rules", () => {
  const output = cleanMarkdown("##Heading  \n\n\n---\n\n---\nText   \n");
  assert.equal(output, "## Heading  \n\n---\nText  \n");
});

test("markdown table alignment keeps values and alignment markers", () => {
  const output = alignMarkdownTables(
    "| Part | Value |\n| :--- | ---: |\n| A | 12 |\n| Longer | 3 |\n",
  );
  assert.equal(
    output,
    "| Part   | Value |\n| :----- | ----: |\n| A      | 12    |\n| Longer | 3     |\n",
  );
});

test("repair markdown closes one unfinished code fence", () => {
  assert.equal(
    repairMarkdown("#Title\n\n```js\nconst x = 1;"),
    "# Title\n\n```js\nconst x = 1;\n\n```\n",
  );
});

test("JSON formatting validates before changing source", () => {
  const result = runDocumentAutomation("format-json", '{"b":2,"a":1}');
  assert.equal(result.output, '{\n  "b": 2,\n  "a": 1\n}\n');
  assert.throws(
    () => runDocumentAutomation("format-json", "{broken}"),
    /Invalid JSON/,
  );
});

test("empty documents remain empty", () => {
  assert.equal(cleanMarkdown(""), "");
  assert.equal(repairMarkdown(""), "");
  assert.equal(runDocumentAutomation("tidy-text", "").output, "");
});
