import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { JSDOM } from "jsdom";
import {
  appendChecklistSectionItem,
  readChecklistSection,
  replaceChecklistSection,
} from "./checklistSections.js";
import {
  buildWorkNoteHtml,
  extractWorkMarkdown,
} from "./components/work/workNote.js";

let dom;
beforeEach(() => {
  dom = new JSDOM("");
  globalThis.document = dom.window.document;
  globalThis.DOMParser = dom.window.DOMParser;
});
afterEach(() => {
  dom.window.close();
  delete globalThis.document;
  delete globalThis.DOMParser;
});

const produce = { headingIndex: 0, heading: "Produce" };
const household = { headingIndex: 1, heading: "Household" };
const htmlOptions = { format: "html" };
const task = (text, checked = false) =>
  `<li class="task-list-item${checked ? " checked" : ""}"><input type="checkbox"${checked ? " checked" : ""}>${text}</li>`;

test("HTML section editing preserves the complete envelope and every other section byte for byte", () => {
  const prefix =
    '<!DOCTYPE html>\n<html lang="de"><head><meta name="lamanotes-id" content="fixed"><meta name="lamanotes-tags" content="private,pinned"><title>Shopping</title></head><body><article id="same"><!-- keep -->\n<h5>Produce</h5>';
  const suffix =
    '\n<h5>Household</h5><ul data-custom="kept">' +
    task("Soap", true) +
    "</ul><p>#private</p><!-- tail --></article></body></html>";
  const source =
    prefix + "\n<ul>" + task("Apples", true) + task("Pears") + "</ul>" + suffix;
  assert.equal(
    readChecklistSection(source, produce, htmlOptions).markdown,
    "- [x] Apples\n- [ ] Pears",
  );
  const updated = replaceChecklistSection(
    source,
    produce,
    "- [x] Apples\n- [ ] Bananas",
    htmlOptions,
  );
  assert.ok(updated.startsWith(prefix));
  assert.ok(updated.endsWith(suffix));
  assert.equal(
    readChecklistSection(updated, produce, htmlOptions).markdown,
    "- [x] Apples\n- [ ] Bananas",
  );
});

test("an unchanged section is an exact no-op, including nested lists and attributes", () => {
  const source = `<h5>Produce</h5><ul class='custom'>${task("Apples", true)}<li>Next aisle<ul>${task("Pears")}</ul></li></ul><h5>Household</h5>`;
  const current = readChecklistSection(source, produce, htmlOptions).markdown;
  assert.equal(current, "- [x] Apples\n- Next aisle\n  - [ ] Pears");
  assert.equal(
    replaceChecklistSection(source, produce, current, htmlOptions),
    source,
  );
  const updated = replaceChecklistSection(
    source,
    produce,
    current.replace("Pears", "Plums"),
    htmlOptions,
  );
  assert.equal(
    readChecklistSection(updated, produce, htmlOptions).markdown,
    current.replace("Pears", "Plums"),
  );
});

test("empty HTML sections accept their first item without a checkbox anchor", () => {
  const source = `<h5>Produce</h5><ul>${task("Apples", true)}</ul><h5>Household</h5>\n<p><br></p><p>#private #pinned</p>`;
  const updated = appendChecklistSectionItem(
    source,
    household,
    "Soap & towels",
    htmlOptions,
  );
  assert.ok(
    updated.startsWith(source.slice(0, source.indexOf("<h5>Household"))),
  );
  assert.ok(updated.endsWith("<p>#private #pinned</p>"));
  assert.equal(
    readChecklistSection(updated, household, htmlOptions).markdown,
    "- [ ] Soap & towels",
  );
});

test("HTML append preserves existing checked items and uses the outer list", () => {
  const source = `<h5>Produce</h5><ul>${task("Apples", true)}<li>Nested<ul>${task("Pears", true)}</ul></li></ul><h5>Household</h5>`;
  const updated = appendChecklistSectionItem(
    source,
    produce,
    "<script>alert(1)</script>",
    htmlOptions,
  );
  assert.ok(updated.startsWith(source.slice(0, source.indexOf("</ul><h5>"))));
  const doc = new DOMParser().parseFromString(updated, "text/html");
  assert.equal(doc.querySelectorAll("input[checked]").length, 2);
  assert.equal(doc.querySelectorAll("script").length, 0);
  assert.equal(
    doc.querySelector("body > ul > li:last-child").textContent,
    "<script>alert(1)</script>",
  );
});

test("HTML bold section labels and duplicate headings are selected by index", () => {
  const source = `<p><strong>Extra</strong></p><ul>${task("One")}</ul><p><strong>Extra</strong></p><ul>${task("Two", true)}</ul>`;
  const updated = replaceChecklistSection(
    source,
    { headingIndex: 1, heading: "Extra" },
    "- [x] Three",
    htmlOptions,
  );
  assert.ok(updated.startsWith(source.slice(0, source.lastIndexOf("<ul>"))));
  assert.equal(
    readChecklistSection(
      updated,
      { headingIndex: 0, heading: "Extra" },
      htmlOptions,
    ).markdown,
    "- [ ] One",
  );
  assert.equal(
    readChecklistSection(
      updated,
      { headingIndex: 1, heading: "Extra" },
      htmlOptions,
    ).markdown,
    "- [x] Three",
  );
});

test("Markdown replacements respect fences, section boundaries, tags and CRLF", () => {
  const prefix =
    "# Shopping\r\n\r\n```md\r\n## Example\r\n- [x] Not real\r\n```\r\n\r\n## Produce\r\n";
  const suffix = "## Household\r\n\r\n- [x] Soap\r\n\r\n#private #pinned\r\n";
  const source = prefix + "\r\n- [x] Apples\r\n- [ ] Pears\r\n\r\n" + suffix;
  const updated = replaceChecklistSection(
    source,
    produce,
    "- [x] Apples\n- [ ] Plums",
  );
  assert.ok(updated.startsWith(prefix));
  assert.ok(updated.endsWith(suffix));
  assert.equal(readChecklistSection(updated, household).markdown, "- [x] Soap");
  assert.ok(updated.includes("- [x] Apples\r\n- [ ] Plums"));
});

test("empty Markdown sections remain editable when no list exists", () => {
  const source = "## Produce\n- [x] Apples\n\n## Household\n\n#private\n";
  const updated = appendChecklistSectionItem(source, household, "Towels");
  assert.equal(
    readChecklistSection(updated, household).markdown,
    "- [ ] Towels",
  );
  assert.ok(updated.startsWith("## Produce\n- [x] Apples\n\n## Household\n"));
  assert.ok(updated.endsWith("#private\n"));
});

test("an unlabelled list is patched without touching surrounding prose", () => {
  const source =
    "Before the list.\n\n- [x] Apples\n- [ ] Pears\n\nAfter the list.\n";
  const updated = replaceChecklistSection(
    source,
    { taskIndex: 0 },
    "- [x] Apples\n- [ ] Plums",
  );
  assert.ok(updated.startsWith("Before the list.\n\n"));
  assert.ok(updated.endsWith("After the list.\n"));
});

test("Work note updates keep metadata, IDs, other rendered sections and other template text", () => {
  let source = buildWorkNoteHtml(
    "Shopping",
    "## Produce\n\n- [x] Apples\n- [ ] Pears\n\n## Household\n\n- [x] Soap\n\n#private\n",
    { systemTags: ["pinned"] },
  );
  source = source
    .replace("<article class=", '<article data-note-id="fixed" class=')
    .replace(
      "<title>Shopping</title>",
      "<title>Shopping</title><!-- preserve -->",
    );
  const originalDoc = new DOMParser().parseFromString(source, "text/html");
  const otherSection = source.slice(
    source.indexOf("<h2>Household</h2>"),
    source.indexOf("</section>"),
  );
  const updated = replaceChecklistSection(
    source,
    produce,
    "- [x] Apples\n- [ ] Plums",
    htmlOptions,
  );
  assert.ok(updated);
  const updatedDoc = new DOMParser().parseFromString(updated, "text/html");
  assert.equal(updatedDoc.head.innerHTML, originalDoc.head.innerHTML);
  assert.equal(updatedDoc.querySelector("article").dataset.noteId, "fixed");
  assert.ok(updated.includes(otherSection));
  assert.equal(
    extractWorkMarkdown(updated),
    "## Produce\n\n- [x] Apples\n- [ ] Plums\n\n## Household\n\n- [x] Soap\n\n#private\n",
  );
});

test("section selection fails safely if the heading changed or HTML is malformed", () => {
  assert.equal(readChecklistSection("## Other\n- [ ] Apples", produce), null);
  assert.equal(
    replaceChecklistSection("## Other\n- [ ] Apples", produce, "changed"),
    null,
  );
  assert.equal(
    replaceChecklistSection(
      "<h5>Produce</h5><ul><li>Broken",
      produce,
      "changed",
      htmlOptions,
    ),
    null,
  );
  assert.equal(appendChecklistSectionItem("## Produce\n", produce, "  "), null);
});

test("a complex HTML section is not converted into a lossy plain text editor", () => {
  assert.equal(
    readChecklistSection(
      "<h5>Produce</h5><table><tr><td>Keep table</td></tr></table>",
      produce,
      htmlOptions,
    ),
    null,
  );
});

test("editing another line does not add visible escape characters to literal item symbols", () => {
  const source = `<h5>Produce</h5><ul>${task("[small] *fresh* C:\\Fruit", true)}${task("Pears")}</ul>`;
  const current = readChecklistSection(source, produce, htmlOptions).markdown;
  const updated = replaceChecklistSection(
    source,
    produce,
    current.replace("Pears", "Plums"),
    htmlOptions,
  );
  const doc = new DOMParser().parseFromString(updated, "text/html");
  assert.equal(
    doc.querySelector("li").textContent,
    "[small] *fresh* C:\\Fruit",
  );
  assert.equal(doc.querySelector("li em"), null);
});
