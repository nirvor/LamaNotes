import { renderMarkdownToHtml } from "../work/workNote.js";
import { normalizeTagName } from "../../tagPolicy.js";
import { isSystemTag } from "../../systemTags.js";

const sourceSelector = "template[data-lamanotes-text-markdown]";
const tagLine = /^\s*(?:#[a-zA-Z0-9][a-zA-Z0-9_-]*\s*)+$/;
const unsupportedLegacy =
  "audio,canvas,figure,iframe,img,math,object,pre,script,style,svg,table,template,video";

const parse = (value) =>
  new DOMParser().parseFromString(value || "", "text/html");
const tidy = (value) => String(value || "").replace(/\r\n?/g, "\n");
const tagsIn = (value) =>
  [...String(value).matchAll(/#([a-zA-Z0-9][a-zA-Z0-9_-]*)/g)].map((match) =>
    normalizeTagName(match[1]),
  );

export function escapePlainMarkdown(value = "") {
  return tidy(value).replace(/[!-/:-@[-`{-~]/g, "\\$&");
}

function metadataTags(documentValue) {
  return [
    ...documentValue.querySelectorAll(
      "meta[name='lamanotes-tags'],meta[name='flatnotes-tags']",
    ),
  ]
    .flatMap((meta) => (meta.content || "").split(/[\s,#]+/))
    .map(normalizeTagName)
    .filter(Boolean);
}

function legacyRoot(documentValue) {
  const root = documentValue.querySelector(
    "article.flatnote-migrated,article.lamanote-migrated",
  );
  const kicker = root?.querySelector(".flatnote-kicker,.lamanote-kicker");
  const original = root?.cloneNode(true);
  original
    ?.querySelectorAll("section[data-lamanotes-share-entry]")
    .forEach((entry) => {
      if (
        entry.querySelectorAll(
          ":scope > template[data-lamanotes-share-markdown]",
        ).length === 1
      )
        entry.remove();
    });
  return root &&
    /^Pinned Scratch Note$/i.test(kicker?.textContent.trim() || "") &&
    !original.querySelector(unsupportedLegacy)
    ? root
    : null;
}

export function isTextNoteHtml(value = "") {
  if (!/lamanotes-editor|Pinned\s+Scratch\s+Note/i.test(value)) return false;
  const documentValue = parse(value);
  return Boolean(
    (documentValue.querySelector(
      "meta[name='lamanotes-editor'][content='markdown']",
    ) &&
      documentValue.querySelector(sourceSelector)) ||
      legacyRoot(documentValue),
  );
}

export function hasSharedQuicknotes(value = "") {
  return (
    value.includes("lamanotes-share-quicknote") &&
    Boolean(
      parse(value).head.querySelector("meta[name='lamanotes-share-quicknote']"),
    )
  );
}

export function normalizeTextMarkdown(value = "") {
  const rows = markdownTagRows(value);
  return tidy(value)
    .split("\n")
    .map((line, index) =>
      rows.has(index)
        ? tagsIn(line)
            .filter((tag) => !isSystemTag(tag))
            .map((tag) => `#${tag}`)
            .join(" ")
        : line,
    )
    .join("\n");
}

function markdownTagRows(value) {
  const rows = new Map();
  let fence = null;
  tidy(value)
    .split("\n")
    .forEach((line, index) => {
      const delimiter = line.match(/^\s{0,3}(`{3,}|~{3,})/);
      if (delimiter) {
        if (!fence) fence = delimiter[1];
        else if (
          fence[0] === delimiter[1][0] &&
          delimiter[1].length >= fence.length
        )
          fence = null;
      } else if (!fence && tagLine.test(line)) rows.set(index, tagsIn(line));
    });
  return rows;
}

function inline(node) {
  if (node.nodeType === 3) return node.textContent.replace(/[\t\r\n ]+/g, " ");
  if (node.nodeType !== 1 || node.tagName === "INPUT") return "";
  const text = [...node.childNodes].map(inline).join("");
  if (node.tagName === "BR") return "\n";
  if (["B", "STRONG"].includes(node.tagName)) return `**${text}**`;
  if (["I", "EM"].includes(node.tagName)) return `*${text}*`;
  if (["DEL", "S"].includes(node.tagName)) return `~~${text}~~`;
  if (node.tagName === "CODE") return `\`${text}\``;
  if (node.tagName === "A" && node.getAttribute("href"))
    return `[${text}](${node.getAttribute("href").replace(/\s/g, "%20")})`;
  return text;
}

function blocks(root, title) {
  const result = [];
  for (const node of root.childNodes) {
    if (node.nodeType === 3) {
      if (node.textContent.trim()) result.push(node.textContent.trim());
      continue;
    }
    if (node.nodeType !== 1) continue;
    const tag = node.tagName;
    if (tag === "SECTION" && node.hasAttribute("data-lamanotes-share-entry")) {
      const source = node.querySelector(
        ":scope > template[data-lamanotes-share-markdown]",
      );
      if (source) {
        result.push(source.content.textContent || "");
        continue;
      }
    }
    if (tag === "P" && node.hasAttribute("data-lamanotes-quicknote-entry")) {
      const timestamp = node.querySelector(":scope > small");
      const text = node.querySelector(
        ":scope > span[data-lamanotes-quicknote-text]",
      );
      if (timestamp && text) {
        result.push(
          `<small>${inline(timestamp).trim()}</small>  \n${escapePlainMarkdown(text.textContent).replace(/\n/g, "  \n")}`,
        );
        continue;
      }
    }
    if (/^H[1-6]$/.test(tag)) {
      const text = inline(node).trim();
      if (!(tag === "H1" && text === title))
        result.push(`${"#".repeat(Number(tag[1]))} ${text}`);
    } else if (tag === "UL" || tag === "OL") {
      result.push(
        [...node.children]
          .filter((item) => item.tagName === "LI")
          .map((item, index) => {
            const checkbox = item.querySelector(
              ":scope > input[type='checkbox']",
            );
            const copy = item.cloneNode(true);
            copy
              .querySelectorAll(":scope > ul,:scope > ol")
              .forEach((list) => list.remove());
            const marker = checkbox
              ? `[${checkbox.hasAttribute("checked") || item.dataset.taskChecked === "true" ? "x" : " "}] `
              : "";
            const prefix = tag === "OL" ? `${index + 1}. ` : "- ";
            const nested = [...item.children]
              .filter((child) => child.matches("ul,ol"))
              .map((child) =>
                blocks({ childNodes: [child] }, title).replace(/^/gm, "  "),
              );
            return `${prefix}${marker}${inline(copy).trim()}${nested.length ? "\n" + nested.join("\n") : ""}`;
          })
          .join("\n"),
      );
    } else if (tag === "HR") result.push("---");
    else if (tag === "BLOCKQUOTE")
      result.push(blocks(node, title).replace(/^/gm, "> "));
    else if (["ARTICLE", "SECTION", "MAIN", "DIV"].includes(tag))
      result.push(blocks(node, title));
    else result.push(inline(node).trim());
  }
  return result.filter(Boolean).join("\n\n");
}

export function extractTextMarkdown(value = "", title = "") {
  const documentValue = parse(value);
  const template = documentValue.querySelector(sourceSelector);
  if (template)
    return normalizeTextMarkdown(template.content.textContent || "");
  const root = legacyRoot(documentValue);
  if (!root) {
    if (/<(?:!doctype|html|head|body|article)\b/i.test(value))
      throw new Error("This HTML note needs its original editor.");
    return normalizeTextMarkdown(value);
  }
  let markdown = normalizeTextMarkdown(
    blocks(root, title || documentValue.title),
  );
  const visibleTags = [...markdownTagRows(markdown).values()].flat();
  if (!visibleTags.length) {
    const tags = [
      ...new Set(
        metadataTags(documentValue).filter((tag) => !isSystemTag(tag)),
      ),
    ];
    if (tags.length)
      markdown += `${markdown ? "\n\n" : ""}${tags.map((tag) => `#${tag}`).join(" ")}`;
  }
  return markdown;
}

export function buildTextNoteHtml(title, markdown = "", previousContent = "") {
  const documentValue = parse(previousContent);
  const normalized = normalizeTextMarkdown(markdown);
  const tags = [
    ...new Set([
      ...[...markdownTagRows(normalized).values()].flat(),
      ...metadataTags(documentValue).filter(isSystemTag),
    ]),
  ];
  function setMeta(name, content) {
    const metas = [
      ...documentValue.head.querySelectorAll(`meta[name='${name}']`),
    ];
    const meta = metas.shift() || documentValue.createElement("meta");
    metas.forEach((duplicate) => duplicate.remove());
    meta.name = name;
    meta.content = content;
    if (!meta.parentElement) documentValue.head.append(meta);
  }
  documentValue.title = title;
  setMeta("lamanotes-editor", "markdown");
  setMeta("lamanotes-tags", tags.join(","));
  for (const meta of documentValue.head.querySelectorAll(
    "meta[name='flatnotes-tags']",
  ))
    meta.content = tags.join(",");
  const article = documentValue.createElement("article");
  article.className = "lamanote lamanote-article";
  if (
    documentValue.head.querySelector("meta[name='lamanotes-share-quicknote']")
  )
    article.classList.add("lamanote-quicknotes");
  article.dataset.lamanotesEditor = "markdown";
  const heading = documentValue.createElement("h1");
  heading.textContent = title;
  const body = documentValue.createElement("section");
  body.className = "lamanote-text-body";
  body.innerHTML = renderMarkdownToHtml(normalized);
  const template = documentValue.createElement("template");
  template.dataset.lamanotesTextMarkdown = "";
  template.innerHTML = normalized
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  article.append(heading, body, template);
  documentValue.body.replaceChildren(article);
  return `<!doctype html>\n${documentValue.documentElement.outerHTML}`;
}
