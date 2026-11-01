import assert from "node:assert/strict";
import test from "node:test";
import { saveLocalFileAs } from "./localFileSaveAs.js";

const file = { name: "original.txt", nativeFileId: "local-file", version: "original-version" };

test("native Save as keeps the original identity until a writable result exists", async () => {
  const before = { ...file };
  const selected = await saveLocalFileAs(file, "new text", { nativeApi: {
    async save_native_file_as(...args) {
      assert.deepEqual(args, ["local-file", "new text", "original-version"]);
      return { ok: true, id: "copy-id", path: "C:/copy.txt", name: "copy.txt", content: "new text", writable: true };
    },
  }});
  assert.equal(selected.handle.id, "copy-id");
  assert.equal(selected.nativePayload.path, "C:/copy.txt");
  assert.deepEqual(file, before);
});

test("cancelled or failed Save as does not change the current file", async () => {
  const before = { ...file };
  assert.equal(await saveLocalFileAs(file, "draft", { nativeApi: { save_native_file_as: async () => ({ cancelled: true }) }}), null);
  await assert.rejects(saveLocalFileAs(file, "draft", { nativeApi: { save_native_file_as: async () => ({ conflict: true, external: { content: "outside" } }) }}),
    error => error.code === "external-conflict" && error.external.content === "outside");
  assert.deepEqual(file, before);
});

test("browser Save as adopts the selected writable file and handles cancellation", async () => {
  let content;
  const handle = { createWritable: async () => ({ write: async value => { content = value; }, close: async () => {} }),
    getFile: async () => new File([content], "copy.txt") };
  const selected = await saveLocalFileAs({ name: "original.txt" }, "saved text", { nativeApi: null,
    pickFile: async options => { assert.equal(options.suggestedName, "original.txt"); return handle; } });
  assert.equal(await selected.file.text(), "saved text");
  assert.equal(selected.handle, handle);
  assert.equal(await saveLocalFileAs({ name: "original.txt" }, "draft", { nativeApi: null,
    pickFile: async () => { throw new DOMException("Cancelled", "AbortError"); } }), null);
});
