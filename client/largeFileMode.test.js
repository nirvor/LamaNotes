import assert from "node:assert/strict";
import test from "node:test";

import {
  LARGE_FILE_BYTE_THRESHOLD,
  LARGE_FILE_LINE_THRESHOLD,
  buildLargeFilePreview,
  shouldUseLargeFileMode,
} from "./largeFileMode.js";

test("large-file mode stays invisible for normal notes", () => {
  assert.equal(shouldUseLargeFileMode("# Short\n\nNormal note.", 24), false);
});

test("large-file mode activates by byte size or line count", () => {
  assert.equal(
    shouldUseLargeFileMode("small", LARGE_FILE_BYTE_THRESHOLD),
    true,
  );
  assert.equal(
    shouldUseLargeFileMode("x\n".repeat(LARGE_FILE_LINE_THRESHOLD + 1), 0),
    true,
  );
});

test("large-file preview is bounded without changing source", () => {
  const source = "line\n".repeat(5000);
  const preview = buildLargeFilePreview(source);

  assert.equal(preview.truncated, true);
  assert.ok(preview.content.length < source.length);
  assert.equal(source, "line\n".repeat(5000));
});
