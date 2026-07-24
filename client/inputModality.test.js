import assert from "node:assert/strict";
import test from "node:test";

import { shouldAutoFocusSearch } from "./inputModality.js";

test("home search keeps desktop keyboard-first focus", () => {
  const host = {
    matchMedia: () => ({ matches: false }),
  };

  assert.equal(shouldAutoFocusSearch(host), true);
});

test("home search does not reopen the keyboard after touch navigation", () => {
  const host = {
    matchMedia: (query) => ({
      matches: query === "(pointer: coarse), (hover: none)",
    }),
  };

  assert.equal(shouldAutoFocusSearch(host), false);
});
