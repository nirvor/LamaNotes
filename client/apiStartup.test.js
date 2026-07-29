import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const apiSource = await readFile(new URL("./api.js", import.meta.url), "utf8");

test("authenticated startup coalesces safe config and body-free index", () => {
  assert.match(apiSource, /\.get\("api\/bootstrap"\)/);
  assert.match(apiSource, /applyBootstrap\(response\.data\)/);
  assert.match(
    apiSource,
    /if \(bootstrapRequest\)[\s\S]*?return bootstrapRequest/,
  );
  assert.match(apiSource, /setWarmConfig\(payload\.config\)/);
  assert.match(apiSource, /setWarmIndex\(index\)/);
  assert.match(apiSource, /error\?\.response\?\.status === 404/);
  assert.match(apiSource, /\.get\("api\/auth-check"\)/);
  assert.match(apiSource, /requestGeneration === cacheGeneration/);
  assert.match(apiSource, /if \(bootstrapRequest === request\)/);
  const bootstrapBlock = apiSource.slice(
    apiSource.indexOf("function applyBootstrap"),
    apiSource.indexOf("function cloneIndex"),
  );
  assert.doesNotMatch(bootstrapBlock, /content|noteCache/);
});
