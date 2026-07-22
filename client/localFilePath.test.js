import assert from "node:assert/strict";
import test from "node:test";

import {
  abbreviatedLocalDirectory,
  localFileDirectory,
  localFilePathContext,
} from "./localFilePath.js";

test("desktop work paths omit the profile and filename", () => {
  const path = "C:\\Users\\thoma\\Desktop\\work\\Project Alpha\\prompt.md";

  assert.equal(
    abbreviatedLocalDirectory(path),
    ".../Desktop/work/Project Alpha/",
  );
  assert.equal(
    localFileDirectory(path),
    "C:/Users/thoma/Desktop/work/Project Alpha",
  );
});

test("deep desktop paths keep project and leaf context", () => {
  const path =
    "C:\\Users\\thoma\\Desktop\\work\\Project Alpha\\runs\\latest\\prompt.md";

  assert.equal(
    abbreviatedLocalDirectory(path),
    ".../Desktop/work/Project Alpha/.../latest/",
  );
});

test("generic paths use only the final folder segments", () => {
  assert.equal(
    abbreviatedLocalDirectory("D:\\archive\\2026\\results\\table.csv"),
    ".../archive/2026/results/",
  );
  assert.equal(abbreviatedLocalDirectory("New Note.md"), "");
});

test("the copy value preserves the exact native Windows path", () => {
  const path = "C:\\Users\\thoma\\Desktop\\work\\Project Alpha\\prompt.md";

  assert.deepEqual(localFilePathContext(path), {
    label: ".../Desktop/work/Project Alpha/",
    fullPath: path,
  });
  assert.equal(localFilePathContext("New Note.md"), null);
});
