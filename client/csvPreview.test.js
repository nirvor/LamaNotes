import assert from "node:assert/strict";
import test from "node:test";

import {
  buildCsvPreview,
  detectCsvDelimiter,
  parseDelimitedRows,
} from "./csvPreview.js";

test("parses quoted CSV cells without changing raw values", () => {
  const source =
    'name,note,value\nAlpha,"one, two",3.5\nBeta,"line 1\nline 2",4\n';
  const preview = buildCsvPreview(source);

  assert.deepEqual(preview.header, ["name", "note", "value"]);
  assert.deepEqual(preview.rows[0], ["Alpha", "one, two", "3.5"]);
  assert.deepEqual(preview.rows[1], ["Beta", "line 1\nline 2", "4"]);
  assert.equal(preview.columnCount, 3);
});

test("detects common German semicolon-separated CSV files", () => {
  const source = "name;temperatur;status\nProbe A;-8,0;ok\nProbe B;42,0;ok\n";

  assert.equal(detectCsvDelimiter(source), ";");
  assert.deepEqual(parseDelimitedRows(source, ";").rows[1], [
    "Probe A",
    "-8,0",
    "ok",
  ]);
});

test("bounds the rendered table while reporting truncation", () => {
  const source = [
    "id,value",
    ...Array.from({ length: 8 }, (_, i) => `${i},x`),
  ].join("\n");
  const preview = buildCsvPreview(source, 4);

  assert.equal(preview.rows.length, 3);
  assert.equal(preview.truncated, true);
});
