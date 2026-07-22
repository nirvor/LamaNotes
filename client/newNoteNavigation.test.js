import assert from "node:assert/strict";
import test from "node:test";

import { newNoteLocation } from "./newNoteNavigation.js";

test("web new notes keep using the Library editor", () => {
  assert.deepEqual(newNoteLocation({ desktopEnabled: false }), {
    name: "new",
  });
});

test("desktop new notes start as a stable local draft", () => {
  assert.deepEqual(
    newNoteLocation({ desktopEnabled: true, draftId: "draft-42" }),
    {
      name: "openFile",
      query: { new: "1", draft: "draft-42" },
    },
  );
});
