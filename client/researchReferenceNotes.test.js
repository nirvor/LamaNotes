import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const referenceRoot = new URL(
  "../docs/research-reference-notes/",
  import.meta.url,
);

const fixtures = {
  research: {
    id: "lr-11111111111111111111111111111111",
    components: ["lamanote-plot", "lamanote-result"],
  },
  travel: {
    id: "lr-22222222222222222222222222222222",
    components: ["lamanote-map", "lamanote-comparison", "lamanote-result"],
  },
  shopping: {
    id: "lr-33333333333333333333333333333333",
    components: ["lamanote-comparison", "lamanote-steps", "lamanote-result"],
  },
  invest: {
    id: "lr-44444444444444444444444444444444",
    components: ["lamanote-plot", "lamanote-result"],
  },
  practical: {
    id: "lr-55555555555555555555555555555555",
    components: ["lamanote-steps", "lamanote-diagram", "lamanote-result"],
  },
  aluhut: {
    id: "lr-66666666666666666666666666666666",
    components: ["lamanote-diagram", "lamanote-comparison", "lamanote-result"],
  },
};

for (const [type, contract] of Object.entries(fixtures)) {
  test(`${type} reference note keeps its editorial and visual contract`, async () => {
    const html = await readFile(new URL(`${type}.html`, referenceRoot), "utf8");

    assert.match(
      html,
      new RegExp(
        `<meta\\s+name="lamanotes-research-id"\\s+content="${contract.id}"`,
      ),
    );
    assert.match(
      html,
      new RegExp(`<meta name="lamanotes-research-type" content="${type}"`),
    );
    assert.match(
      html,
      /<meta name="lamanotes-research-topic" content="r-fixture"/,
    );
    assert.match(html, /class="lamanote[^"]*lamanote-research"/);
    assert.match(html, /class="lamanote-research-header"/);
    assert.match(html, /class="lamanote-metrics"/);
    assert.equal(
      (html.match(/class="lamanote-section-eyebrow"/g) || []).length,
      3,
    );
    assert.match(html, /data-lamanotes-component="result"/);
    assert.match(
      html,
      /<p class="lamanote-tags">#research #r-fixture #design-reference<\/p>\s*<\/article>/,
    );
    assert.doesNotMatch(html, /\sstyle="/i);
    assert.doesNotMatch(html, /example\.com|attachments\/example/i);
    for (const component of contract.components) {
      assert.match(html, new RegExp(`\\b${component}\\b`));
    }
  });
}
