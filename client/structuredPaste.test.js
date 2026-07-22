import assert from "node:assert/strict";
import test from "node:test";

import {
  fitStructuredPasteToContext,
  markdownTableFromDelimitedText,
  structuredPasteOptions,
} from "./structuredPaste.js";

test("CSV paste offers a Markdown table while keeping raw as the default", () => {
  const options = structuredPasteOptions("name,value\nalpha,3\n");
  assert.deepEqual(
    options.map(({ id }) => id),
    ["table"],
  );
  assert.equal(
    options[0].content,
    "| name | value |\n| --- | --- |\n| alpha | 3 |",
  );
});

test("tabular conversion handles quoted delimiters", () => {
  assert.equal(
    markdownTableFromDelimitedText('name,value\n"alpha,beta",3'),
    "| name | value |\n| --- | --- |\n| alpha,beta | 3 |",
  );
});

test("multiline prose offers a quote and code offers a fenced block", () => {
  assert.deepEqual(
    structuredPasteOptions("First line\nSecond line").map(({ id }) => id),
    ["quote"],
  );
  assert.ok(
    structuredPasteOptions("const answer = 42;\nconsole.log(answer);").some(
      ({ id, content }) => id === "code" && content.includes("```"),
    ),
  );
});

test("block conversions stay valid when pasted at a line edge", () => {
  assert.equal(
    fitStructuredPasteToContext("Before", 6, 6, "| A | B |"),
    "\n\n| A | B |",
  );
  assert.deepEqual(
    fitStructuredPasteToContext("Before\nraw\nAfter", 7, 10, "> raw"),
    "\n> raw\n",
  );
  assert.deepEqual(
    fitStructuredPasteToContext("\n\nraw\n\n", 2, 5, "```\nraw\n```"),
    "```\nraw\n```",
  );
});
