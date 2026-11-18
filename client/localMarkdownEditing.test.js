import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { EditorState } from "@codemirror/state";
import { markdownLanguage } from "@codemirror/lang-markdown";
import { formulaAtCursor } from "./components/editor/formulaPreview.js";
import {
  cellRange,
  startCellEdit,
} from "./components/toastui/editableTableCells.js";

test("formula preview respects the caret, Markdown code, escaped dollars and selections", () => {
  function at(doc, text, selected = false) {
    const anchor = doc.lastIndexOf(text);
    assert.notEqual(anchor, -1);
    const selection = { anchor, head: selected ? anchor + 1 : anchor };
    return formulaAtCursor(
      EditorState.create({ doc, selection, extensions: [markdownLanguage] }),
    )?.source;
  }
  assert.equal(at("Time $a/b$ seconds", "b"), "a/b");
  assert.equal(at("Time $a/b$ seconds", "seconds"), undefined);
  assert.equal(at("Time $a/b$ seconds", "b", true), undefined);
  assert.equal(at("Inline \u0060$a/b$\u0060 test", "b$"), undefined);
  assert.equal(at("Costs \u0060$5\u0060 and $a/b$", "b"), "a/b");
  assert.equal(at("~~~tex\n$a/b$\n~~~", "b"), undefined);
  assert.equal(at("$$a/b$$", "b"), undefined);
  assert.equal(at("Price \\$5 then $x+y$", "y"), "x+y");
});

test("table edits address the rendered cell, preserve its padding, CRLF and escaped pipes", () => {
  const source =
    "Ort: Labor\r\n\r\n| A | B |\r\n|---|---|\r\n| Ref |  15  |\r\n";
  const { from, to } = cellRange(source, "5:8:13");
  assert.equal(source.slice(from, to), "15");
  assert.equal(cellRange(source, "100:1:4"), null);
  assert.equal(cellRange(source, "5:8:45"), null);
  const dom = new JSDOM(
    '<table><tbody><tr><td data-ln-cell="5:8:13">15</td></tr></tbody></table>',
  );
  const doc = dom.window.document;
  const cell = doc.querySelector("td");
  const changes = [];
  const finished = [];
  const savedDocument = globalThis.document;
  globalThis.document = doc;
  try {
    startCellEdit(
      { target: cell, preventDefault() {}, stopPropagation() {} },
      source,
      (c) => changes.push(c),
      (...args) => finished.push(args),
    );
    const input = cell.querySelector("input");
    assert.equal(input.value, "15");
    input.value = "a||b";
    input.dispatchEvent(new dom.window.Event("input"));
    assert.equal(changes[0].after, source.replace("15", "a\\|\\|b"));
    input.dispatchEvent(
      new dom.window.KeyboardEvent("keydown", { key: "Escape" }),
    );
    assert.equal(changes.at(-1).after, source);
    assert.equal(finished.length, 1);
  } finally {
    if (savedDocument === undefined) delete globalThis.document;
    else globalThis.document = savedDocument;
    dom.window.close();
  }
});
