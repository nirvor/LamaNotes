import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";
import { enhanceReaderLinks, openNativeReaderLink } from "./readerLinks.js";

const page = "https://notes.thuber.org/n/ln-example";
const pdf =
  "https://www.landkreis-cham.de/media/3513/jahresbericht-2017-lkr-cham_web.pdf#page=34";

test("an inline source opens its unique external PDF with the page fragment intact", () => {
  const dom = new JSDOM(
    `<base href="/"><article><a href="#quelle-5">[5]</a><ol><li id="quelle-5"><a href="${pdf}">Report</a></li></ol></article>`,
  );
  const root = dom.window.document.querySelector("article");
  enhanceReaderLinks(root, page);
  const link = root.querySelector("a");
  assert.equal(link.href, pdf);
  assert.equal(link.target, "_blank");
  assert.match(link.rel, /noopener/);
  assert.match(link.rel, /noreferrer/);
  assert.equal(root.querySelector("li a").target, "_blank");
  dom.window.close();
});

test("TOC anchors keep their note and managed assets keep their normal route", () => {
  const dom = new JSDOM(
    '<base href="/"><article><a href="#history">History</a><h2 id="history">History</h2><a href="/api/attachments/map.svg">Map</a><a href="https://example.org/article">Source</a></article>',
  );
  const root = dom.window.document.querySelector("article");
  enhanceReaderLinks(root, page);
  const [toc, asset, external] = root.querySelectorAll("a");
  assert.equal(toc.href, page + "#history");
  assert.equal(toc.hasAttribute("target"), false);
  assert.equal(asset.getAttribute("href"), "/api/attachments/map.svg");
  assert.equal(asset.hasAttribute("target"), false);
  assert.equal(external.target, "_blank");
  dom.window.close();
});

test("ambiguous source entries remain local instead of guessing a destination", () => {
  const dom = new JSDOM(
    '<article><a href="#quelle-1">[1]</a><li id="quelle-1"><a href="https://a.example">A</a><a href="https://b.example">B</a></li></article>',
  );
  const root = dom.window.document.querySelector("article");
  enhanceReaderLinks(root, page);
  assert.equal(root.querySelector("a").href, page + "#quelle-1");
  assert.equal(root.querySelector("a").hasAttribute("target"), false);
  dom.window.close();
});

test("the Windows reader hands an external source to the existing system-browser bridge", async () => {
  const dom = new JSDOM(
    `<article><a href="${pdf}" target="_blank"><span>[5]</span></a></article>`,
  );
  let opened;
  let prevented = false;
  const root = dom.window.document.querySelector("article");
  openNativeReaderLink(
    {
      button: 0,
      target: root.querySelector("span"),
      currentTarget: root,
      preventDefault() {
        prevented = true;
      },
    },
    {
      location: { href: "http://127.0.0.1:19999/n/ln-example" },
      pywebview: {
        api: {
          open_external_url(url) {
            opened = url;
            return { opened: true };
          },
        },
      },
    },
  );
  await Promise.resolve();
  assert.equal(prevented, true);
  assert.equal(opened, pdf);
  dom.window.close();
});
