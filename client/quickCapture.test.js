import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { after, afterEach, test } from "node:test";
import { compileScript, parse } from "@vue/compiler-sfc";
import * as icons from "@mdi/js";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><body></body>");
for (const key of [
  "window",
  "document",
  "HTMLElement",
  "SVGElement",
  "Element",
  "Node",
])
  globalThis[key] = dom.window[key];
const Vue = await import("vue");
const source = readFileSync(
  new URL("./components/quicknotes/QuickCapture.vue", import.meta.url),
  "utf8",
);
const { descriptor } = parse(source);
const compiled = compileScript(descriptor, {
  id: "quick-capture-test",
  inlineTemplate: true,
})
  .content.replace(
    /import\s*\{([^}]+)\}\s*from\s*["'](vue|@mdi\/js)["'];?/g,
    (_, names, module) =>
      `const { ${names.replace(/\bas\b/g, ":")} } = ${module === "vue" ? "Vue" : "icons"};`,
  )
  .replace("export default", "return");
const QuickCapture = new Function("Vue", "icons", compiled)(Vue, icons);
let app;

function mount(initial = {}) {
  const props = Vue.reactive({
    modelValue: "",
    busy: false,
    pendingCount: 0,
    status: "",
    message: "",
    ...initial,
  });
  const updates = [],
    submissions = [];
  const host = document.createElement("main");
  document.body.append(host);
  app = Vue.createApp({
    render: () =>
      Vue.h(QuickCapture, {
        ...props,
        "onUpdate:modelValue": (value) => {
          updates.push(value);
          props.modelValue = value;
        },
        onSubmit: (value) => submissions.push(value),
      }),
  });
  app.mount(host);
  return {
    props,
    updates,
    submissions,
    host,
    input: host.querySelector("textarea"),
    button: host.querySelector("button"),
    form: host.querySelector("form"),
  };
}
afterEach(() => {
  app?.unmount();
  document.body.replaceChildren();
});
after(() => {
  dom.window.close();
  for (const key of [
    "window",
    "document",
    "HTMLElement",
    "SVGElement",
    "Element",
    "Node",
  ])
    delete globalThis[key];
});

test("capture stays one line and leaves the keyboard alone until focus or restored text", async () => {
  const { input, button, host } = mount();
  assert.equal(input.rows, 1);
  assert.notEqual(document.activeElement, input);
  assert.equal(input.hasAttribute("autofocus"), false);
  assert.equal(button.disabled, true);
  assert.equal(host.querySelector('[role="status"]'), null);
  input.focus();
  await Vue.nextTick();
  assert.equal(input.rows, 3);
  input.blur();
  await Vue.nextTick();
  assert.equal(input.rows, 1);
});

test("multiline input is emitted intact and only modified Enter submits", async () => {
  const { input, submissions, updates, button } = mount();
  input.value = "An idea\nAnother line  ";
  input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  await Vue.nextTick();
  assert.deepEqual(updates, ["An idea\nAnother line  "]);
  assert.equal(input.rows, 3);
  assert.equal(button.disabled, false);
  const enter = new dom.window.KeyboardEvent("keydown", {
    key: "Enter",
    bubbles: true,
    cancelable: true,
  });
  input.dispatchEvent(enter);
  assert.equal(enter.defaultPrevented, false);
  assert.deepEqual(submissions, []);
  const shortcut = new dom.window.KeyboardEvent("keydown", {
    key: "Enter",
    ctrlKey: true,
    bubbles: true,
    cancelable: true,
  });
  input.dispatchEvent(shortcut);
  assert.equal(shortcut.defaultPrevented, true);
  assert.deepEqual(submissions, ["An idea\nAnother line  "]);
  assert.equal(input.value, "An idea\nAnother line  ");
});

test("busy, blank input, IME composition and held shortcuts cannot submit duplicates", async () => {
  const { input, props, submissions, button, form } = mount({
    modelValue: "A thought",
  });
  input.dispatchEvent(new dom.window.CompositionEvent("compositionstart"));
  input.dispatchEvent(
    new dom.window.KeyboardEvent("keydown", {
      key: "Enter",
      metaKey: true,
      bubbles: true,
      cancelable: true,
    }),
  );
  assert.deepEqual(submissions, []);
  input.dispatchEvent(new dom.window.CompositionEvent("compositionend"));
  input.dispatchEvent(
    new dom.window.KeyboardEvent("keydown", {
      key: "Enter",
      metaKey: true,
      repeat: true,
      bubbles: true,
      cancelable: true,
    }),
  );
  assert.deepEqual(submissions, []);
  props.busy = true;
  await Vue.nextTick();
  assert.equal(input.readOnly, true);
  assert.equal(button.disabled, true);
  form.dispatchEvent(
    new dom.window.Event("submit", { bubbles: true, cancelable: true }),
  );
  assert.deepEqual(submissions, []);
  props.busy = false;
  props.modelValue = " \n ";
  await Vue.nextTick();
  form.dispatchEvent(new dom.window.Event("submit", { cancelable: true }));
  assert.deepEqual(submissions, []);
});

test("failure keeps the draft and contextual messages remain accessible without added controls", async () => {
  const { input, form, host, props, submissions } = mount({
    modelValue: "Remember this",
  });
  form.dispatchEvent(
    new dom.window.Event("submit", { bubbles: true, cancelable: true }),
  );
  assert.deepEqual(submissions, ["Remember this"]);
  props.status = "error";
  props.message = "Device storage is full. Your text is kept.";
  await Vue.nextTick();
  assert.equal(input.value, "Remember this");
  const status = host.querySelector('[role="alert"]');
  assert.equal(status.textContent.trim(), props.message);
  assert.equal(input.getAttribute("aria-describedby"), status.id);
  assert.equal(host.querySelectorAll("button").length, 1);
  props.status = "pending";
  props.pendingCount = 2;
  props.message = "Saved on this device · Waiting for connection";
  await Vue.nextTick();
  assert.equal(
    host.querySelector('[role="status"]').textContent.trim(),
    props.message,
  );
  props.status = "saved";
  props.message = "";
  props.modelValue = "";
  await Vue.nextTick();
  assert.equal(
    host.querySelector('[role="status"]').textContent.trim(),
    "Saved to Quicknotes",
  );
  assert.equal(input.value, "");
  assert.equal(input.rows, 1);
});

test("restored text and pending captures do not require automatic focus or a connection", async () => {
  const { input, props, button, host, form, submissions } = mount({
    modelValue: "Restored local draft",
    pendingCount: 2,
  });
  assert.equal(input.rows, 3);
  assert.notEqual(document.activeElement, input);
  assert.equal(
    host.querySelector('[role="status"]').textContent.trim(),
    "2 thoughts waiting to send",
  );
  props.status = "blocked";
  await Vue.nextTick();
  assert.equal(
    host.querySelector('[role="status"]').textContent.trim(),
    "Sign in to send",
  );
  assert.equal(button.disabled, false);
  form.dispatchEvent(new dom.window.Event("submit", { cancelable: true }));
  assert.deepEqual(submissions, ["Restored local draft"]);
});
