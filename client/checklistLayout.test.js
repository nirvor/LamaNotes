import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { JSDOM } from "jsdom";
import {
  enhanceNoteLead,
  enhanceTaskListCheckboxes,
  resetChecklistGroups,
} from "./components/toastui/renderEnhancements.js";

let dom, root;
beforeEach(() => {
  dom = new JSDOM('<main><div class="toastui-editor-contents"></div></main>', {
    url: "https://example.test",
  });
  globalThis.document = dom.window.document;
  globalThis.requestAnimationFrame = (callback) => queueMicrotask(callback);
  root = document.querySelector("main");
});
afterEach(() => {
  dom.window.close();
  delete globalThis.document;
  delete globalThis.requestAnimationFrame;
});

const task = (name, checked = false) =>
  `<li class="task-list-item"><input type="checkbox" ${checked ? "checked" : ""}><p>${name}</p></li>`;
const render = (html) => {
  root.firstElementChild.innerHTML = html;
};
const options = { onToggle: async () => {}, onAdd: async () => {} };

test("section actions share the label row while note headings and item order survive", () => {
  render(
    `<h5>Produce</h5><ul>${task("Apples")}${task("Pears", true)}</ul><h5>Household</h5><ul>${task("Soap")}</ul>`,
  );
  enhanceTaskListCheckboxes(root, options);
  const groups = root.querySelectorAll(".lamanotes-checklist-group");
  assert.equal(groups.length, 2);
  assert.equal(
    groups[0].querySelector(".lamanotes-checklist-heading h5").textContent,
    "Produce",
  );
  assert.equal(
    groups[0].querySelectorAll(".lamanotes-checklist-heading button").length,
    2,
  );
  assert.equal(
    groups[0].querySelector(":scope > .lamanotes-checklist-entry").hidden,
    true,
  );
  assert.deepEqual(
    [...root.querySelectorAll("li p")].map((p) => p.textContent),
    ["Apples", "Pears", "Soap"],
  );
});

test("a repeated enhancement preserves headings, section order and one control per action", () => {
  render(
    `<h5>Produce</h5><ul>${task("Apples", true)}</ul><h5>Household</h5><ul>${task("Soap")}</ul>`,
  );
  enhanceTaskListCheckboxes(root, options);
  root.querySelector('[aria-label="Hide completed items"]').click();
  enhanceTaskListCheckboxes(root, options);
  assert.deepEqual(
    [...root.querySelectorAll("h5")].map((h) => h.textContent),
    ["Produce", "Household"],
  );
  assert.equal(root.querySelectorAll(".lamanotes-checklist-group").length, 2);
  assert.equal(
    root.querySelectorAll('[aria-label="Add checklist item"]').length,
    2,
  );
  assert.equal(root.querySelectorAll(".lamanotes-checklist-entry").length, 2);
  assert.equal(root.querySelectorAll(".lamanotes-hide-completed").length, 1);
  assert.equal(
    root
      .querySelector('[aria-label="Show completed items"]')
      .getAttribute("aria-pressed"),
    "true",
  );
});

test("before a Markdown update the original source-node hierarchy is restored", () => {
  render(
    `<h5>Produce</h5><ul>${task("Apples")}</ul><h5>Household</h5><ul>${task("Soap")}</ul>`,
  );
  const originalNodes = [...root.firstElementChild.children];
  enhanceTaskListCheckboxes(root, options);
  resetChecklistGroups(root);
  assert.deepEqual([...root.firstElementChild.children], originalNodes);
  assert.equal(root.querySelector(".lamanotes-checklist-tools"), null);
  assert.equal(root.querySelector(".lamanotes-checklist-entry"), null);
});

test("Add opens only its own input and Escape restores the triggering button", () => {
  render(
    `<h5>Produce</h5><ul>${task("Apples")}</ul><h5>Household</h5><ul>${task("Soap")}</ul>`,
  );
  enhanceTaskListCheckboxes(root, options);
  const add = root.querySelectorAll('[aria-label="Add checklist item"]')[1];
  add.click();
  const input = document.activeElement;
  assert.equal(input.getAttribute("aria-label"), "New checklist item");
  assert.equal(
    root.querySelectorAll(".lamanotes-checklist-entry:not([hidden])").length,
    1,
  );
  input.dispatchEvent(
    new dom.window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
  );
  assert.equal(document.activeElement, add);
  assert.equal(
    root.querySelectorAll(".lamanotes-checklist-entry:not([hidden])").length,
    0,
  );
});

test("adding uses the original global item index and blocks duplicate pending saves", async () => {
  render(
    `<h5>Produce</h5><ul>${task("Apples")}${task("Pears")}</ul><h5>Household</h5><ul>${task("Soap")}</ul>`,
  );
  let finish,
    calls = [];
  enhanceTaskListCheckboxes(root, {
    ...options,
    onAdd: (value) => {
      calls.push(value);
      return new Promise((resolve) => {
        finish = resolve;
      });
    },
  });
  root.querySelectorAll('[aria-label="Add checklist item"]')[1].click();
  const input = document.activeElement;
  input.value = "Paper";
  const form = input.closest("form");
  const submit = () =>
    form.dispatchEvent(
      new dom.window.Event("submit", { bubbles: true, cancelable: true }),
    );
  submit();
  submit();
  assert.deepEqual(calls, [{ afterIndex: 2, text: "Paper" }]);
  assert.equal(input.disabled, true);
  assert.equal(form.querySelector("button").disabled, true);
  finish();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(form.hidden, true);
  assert.equal(input.disabled, false);
  assert.equal(
    document.activeElement.getAttribute("aria-label"),
    "Add checklist item",
  );
});

test("failed saves retain the local entry and return focus for correction", async () => {
  render(`<h5>Produce</h5><ul>${task("Apples")}</ul>`);
  enhanceTaskListCheckboxes(root, {
    ...options,
    onAdd: async () => {
      throw new Error("Conflict");
    },
  });
  root.querySelector('[aria-label="Add checklist item"]').click();
  const input = document.activeElement;
  input.value = "Pears";
  input
    .closest("form")
    .dispatchEvent(new dom.window.Event("submit", { cancelable: true }));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(input.value, "Pears");
  assert.equal(input.closest("form").hidden, false);
  assert.equal(document.activeElement, input);
});

test("unlabelled lists do not consume a preceding content paragraph", () => {
  render(`<p>Read this before shopping.</p><ul>${task("Apples")}</ul>`);
  enhanceTaskListCheckboxes(root, options);
  assert.equal(
    root.querySelector(".toastui-editor-contents > p").textContent,
    "Read this before shopping.",
  );
  assert.equal(root.querySelector(".lamanotes-checklist-heading"), null);
});

test("mixed prose containing bold text remains prose beside a checklist", () => {
  render(
    `<p>Remember <strong>fresh fruit</strong> this week.</p><ul>${task("Apples")}</ul>`,
  );
  enhanceTaskListCheckboxes(root, options);
  assert.equal(
    root.querySelector(".toastui-editor-contents > p").textContent,
    "Remember fresh fruit this week.",
  );
  assert.equal(root.querySelector(".lamanotes-checklist-heading"), null);
});

test("a short standalone bold label can share the section actions", () => {
  render(`<p><strong>Produce</strong></p><ul>${task("Apples")}</ul>`);
  enhanceTaskListCheckboxes(root, options);
  assert.equal(
    root.querySelector(".lamanotes-checklist-heading > p").textContent,
    "Produce",
  );
});

test("nested lists and labels survive repeated grouping without moving to another section", () => {
  render(
    `<h5>Produce</h5><ul>${task("Apples")}<li>Next aisle<ul>${task("Pears", true)}</ul></li></ul><h5>Household</h5><ul>${task("Soap")}</ul>`,
  );
  enhanceTaskListCheckboxes(root, options);
  enhanceTaskListCheckboxes(root, options);
  assert.equal(root.querySelectorAll("h5").length, 2);
  assert.equal(
    root.querySelector(
      ".lamanotes-checklist-group > ul > li:last-child ul li p",
    ).textContent,
    "Pears",
  );
  assert.equal(root.querySelectorAll("input[type=checkbox]").length, 3);
});

test("read-only rendering keeps viewing actions without enabling note mutations", () => {
  render(`<h5>Produce</h5><ul>${task("Apples", true)}</ul>`);
  enhanceTaskListCheckboxes(root, { disabled: true });
  assert.equal(root.querySelector("input[type=checkbox]").disabled, true);
  assert.equal(root.querySelector('[aria-label="Add checklist item"]'), null);
  assert.equal(
    root.querySelector('[aria-label="Hide completed items"]').disabled,
    false,
  );
});

test("a short checklist is not cloned into an automatic summary with duplicate controls", () => {
  render(
    `<h5>Produce</h5><ul>${task("Apples")}${task("Pears", true)}</ul><h5>Household</h5><ul>${task("Soap")}</ul>`,
  );
  enhanceNoteLead(root);
  enhanceTaskListCheckboxes(root, options);
  assert.equal(root.querySelector(".lamanotes-note-lead"), null);
  assert.equal(root.querySelectorAll("input[type=checkbox]").length, 3);
  assert.deepEqual(
    [...root.querySelectorAll("input[type=checkbox]")].map(
      (input) => input.dataset.lamanotesTaskIndex,
    ),
    ["0", "1", "2"],
  );
});
