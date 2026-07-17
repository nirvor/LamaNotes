import assert from "node:assert/strict";
import test from "node:test";

import {
  isPublicationPending,
  publicationPollDelay,
  publicationProblemMessage,
  publicationToolbarMode,
  validatePublicationSlug,
} from "./publicationState.js";

test("publication toolbar follows the authoritative state", () => {
  assert.equal(
    publicationToolbarMode({ eligible: true, state: "unpublished" }),
    "publish",
  );
  assert.equal(
    publicationToolbarMode({ eligible: true, state: "deploying" }),
    "publishing",
  );
  assert.equal(
    publicationToolbarMode({
      eligible: true,
      state: "current",
      canonicalUrl: "https://pages.example/note/",
    }),
    "show",
  );
  assert.equal(
    publicationToolbarMode({
      eligible: true,
      state: "stale",
      canonicalUrl: "https://pages.example/note/",
    }),
    "update",
  );
  assert.equal(
    publicationToolbarMode({ eligible: false, state: "ineligible" }),
    null,
  );
});

test("slug validation is strict and compact", () => {
  assert.equal(validatePublicationSlug("clean-public-note"), "");
  assert.match(validatePublicationSlug("Clean Note"), /lowercase/);
  assert.match(validatePublicationSlug("api"), /reserved/);
  assert.match(validatePublicationSlug(""), /Enter/);
});

test("polling backs off and errors stay user facing", () => {
  assert.equal(isPublicationPending("verifying"), true);
  assert.equal(publicationPollDelay(0, 1000), 2000);
  assert.equal(publicationPollDelay(6, 12000), 10000);
  assert.match(
    publicationProblemMessage({ code: "asset_missing" }),
    /media file/,
  );
});
