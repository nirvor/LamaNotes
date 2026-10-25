import assert from "node:assert/strict";
import test from "node:test";
import { createFocusQuicknotesRefresher } from "./focusIntegration.js";

test("Focus lease refresh is coalesced and throttled during normal owner use", async () => {
  let calls = 0;
  let now = 1000;
  const refresh = createFocusQuicknotesRefresher(async () => { calls++; return { connected: true }; }, () => now);
  const first = refresh();
  assert.equal(refresh(), first);
  assert.deepEqual(await first, { connected: true });
  assert.equal(await refresh(), null);
  assert.equal(calls, 1);
  now += 5 * 60 * 1000;
  assert.deepEqual(await refresh(), { connected: true });
  assert.equal(calls, 2);
});

test("Offline and unavailable connections stay quiet and can retry later", async () => {
  let calls = 0;
  let now = 1000;
  const refresh = createFocusQuicknotesRefresher(async () => { calls++; throw new Error("unavailable"); }, () => now);
  assert.equal(await refresh(), null);
  assert.equal(await refresh(), null);
  assert.equal(calls, 1);
  now += 5 * 60 * 1000;
  assert.equal(await refresh(), null);
  assert.equal(calls, 2);
});
