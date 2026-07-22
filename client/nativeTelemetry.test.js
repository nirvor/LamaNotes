import assert from "node:assert/strict";
import test from "node:test";

import { reportNativeReady } from "./nativeTelemetry.js";

test("native readiness waits for the pywebview bridge", () => {
  const host = new EventTarget();
  const reports = [];

  reportNativeReady({ phase: "editor" }, host);
  assert.deepEqual(reports, []);

  host.pywebview = {
    api: {
      report_client_ready(metrics) {
        reports.push(metrics);
      },
    },
  };
  host.dispatchEvent(new Event("pywebviewready"));

  assert.deepEqual(reports, [{ phase: "editor" }]);
});

test("native readiness reports immediately when the bridge exists", () => {
  const reports = [];
  const host = new EventTarget();
  host.pywebview = {
    api: {
      report_client_ready(metrics) {
        reports.push(metrics);
      },
    },
  };

  reportNativeReady({ phase: "shell" }, host);

  assert.deepEqual(reports, [{ phase: "shell" }]);
});
