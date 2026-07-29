import assert from "node:assert/strict";
import test from "node:test";

globalThis.window = {
  clearTimeout,
  setTimeout,
};

const { useToast } = await import("./toastStore.js");

test("lightweight toast store adds and removes messages without a UI plugin", () => {
  const toast = useToast();
  toast.clear();
  const id = toast.add({
    summary: "Saved",
    detail: "The note was saved.",
    severity: "success",
    life: 0,
  });

  assert.equal(toast.messages.length, 1);
  assert.equal(toast.messages[0].severity, "success");
  toast.remove(id);
  assert.equal(toast.messages.length, 0);
});
