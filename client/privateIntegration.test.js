import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import { captureKind, captureNoteHtml, sharedSelection, validateSelection } from "./captureIntake.js";

test('Android links become sources and media remains playable with safe names', () => {
  assert.deepEqual(sharedSelection({text:'https://example.org/read'}), {title:'example.org',text:'',url:'https://example.org/read'});
  assert.equal(sharedSelection({title:'A/B: C?',text:'A thought'}).title, 'A B  C');
  assert.throws(() => validateSelection('', '', [{size:21*1024*1024}]), /20 MB/);
  assert.throws(() => validateSelection('', 'https://user:pass@example.org', []), /login details/);
  const html = captureNoteHtml('Voice note', '', [{assetId:'la-'+'a'.repeat(32),mediaType:'audio/mp4',name:'My <audio>.m4a'}]);
  assert.ok(html.includes('<audio controls'));
  assert.ok(html.includes('My &lt;audio&gt;.m4a'));
});

test("capture HTML escapes untrusted text and does not invent a research theme", () => {
  const html = captureNoteHtml(
    '<script>alert("x")</script>\nSecond line',
    "javascript:alert(1)",
  );
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(html.includes("<br>Second line"));
  assert.ok(!html.includes("<script>"));
  assert.ok(!html.includes("href="));
  assert.ok(!html.includes("research"));
});

test("capture kinds retain file/voice provenance", () => {
  assert.equal(captureKind(null, "https://example.org"), "link");
  assert.equal(captureKind({ type: "audio/wav" }, ""), "audio");
  assert.equal(captureKind({ type: "image/png" }, ""), "image");
  assert.equal(captureKind({ type: "application/pdf" }, ""), "file");
});

test("owned media uses only the authenticated asset route", () => {
  const assetId = "la-" + "a".repeat(32);
  const html = captureNoteHtml("Note", "https://example.org/?a=1&b=2", [
    { assetId, mediaType: "image/png" },
  ]);
  assert.ok(html.includes(`/api/private/v1/assets/${assetId}/content`));
  assert.ok(html.includes("a=1&amp;b=2"));
  assert.ok(!html.includes("style="));
});

test("share target requires local service-worker preview before explicit API import", () => {
  const manifest = JSON.parse(
    readFileSync(new URL("./public/site.webmanifest", import.meta.url)),
  );
  assert.equal(manifest.share_target.action, "/capture/share");
  assert.equal(manifest.share_target.method, "POST");
  const source = readFileSync(
    new URL("./public/sw.js", import.meta.url),
    "utf8",
  );
  const handlers = new Map();
  vm.runInNewContext(source, {
    self: {
      addEventListener: (event, handler) => handlers.set(event, handler),
      location: { origin: "https://notes.example" },
    },
    URL,
  });
  let intercepted = false;
  handlers.get("fetch")({
    request: { method: "GET", url: "https://notes.example/api/index" },
    respondWith: () => {
      intercepted = true;
    },
  });
  assert.equal(intercepted, false);
  assert.ok(source.includes("indexedDB.open"));
  assert.ok(!source.includes("fetch("));
  assert.ok(!source.includes("cache.put"));
});

test("capture UI never imports on file selection or mount", () => {
  const source = readFileSync(
    new URL("./views/Capture.vue", import.meta.url),
    "utf8",
  );
  assert.ok(source.includes('@submit.prevent="importCapture"'));
  assert.ok(source.includes("personal.value &&"));
  assert.ok(source.includes("await discardIncoming(incomingId)"));
  assert.ok(!source.includes("localStorage"));
});

test("narrow reader shares production components without the owner bootstrap", () => {
  const entry = readFileSync(
    new URL("./privateReader.js", import.meta.url),
    "utf8",
  );
  assert.ok(!entry.includes('from "./index.js"'));
  assert.ok(!entry.includes('from "./App.vue"'));
  const reader = readFileSync(
    new URL("./views/PrivateReader.vue", import.meta.url),
    "utf8",
  );
  for (const shared of [
    "HtmlViewer.vue",
    "WorkNoteViewer.vue",
    "appShell.css",
    "noteShell.css",
  ])
    assert.ok(reader.includes(shared));
  for (const marker of [
    "data-private-reader-ready",
    "data-note-id",
    "data-note-version",
    "document.fonts.ready",
    "image.decode()",
    "@rendered=",
  ])
    assert.ok(reader.includes(marker));
  assert.ok(!reader.includes("getSemanticIndex"));
  assert.ok(!reader.includes("getStoredToken"));
});

test("wide visual panning applies to generic notes as well as research", () => {
  const css = readFileSync(
    new URL(
      "./components/toastui/toastui-editor-overrides.scss",
      import.meta.url,
    ),
    "utf8",
  );
  assert.ok(
    css.includes(".toastui-editor-contents figure.lamanote-visual-wide {"),
  );
  assert.ok(!css.includes(".lamanote-research figure.lamanote-visual-wide {"));
});
