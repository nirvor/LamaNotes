import {
  buildWorkNoteHtml,
  extractWorkMarkdown,
  isWorkNoteHtml,
  normalizeWorkMarkdownTags,
  setWorkMarkdownTag,
} from "./components/work/workNote.js";
import { isSystemTag, normalizeSystemTag } from "./systemTags.js";

const metaTagPattern = /<meta\b[^>]*>/gi;
const tagOnlyElementPattern = /<(p|div|footer)\b([^>]*)>([\s\S]*?)<\/\1>/gi;
const tagOnlyTextPattern = /^#[a-zA-Z0-9_-]+(?:\s+#[a-zA-Z0-9_-]+)*$/;

function normalizeTag(tag = "") {
  return normalizeSystemTag(tag);
}

function getAttributeValue(tagMarkup, attributeName) {
  const match = String(tagMarkup).match(
    new RegExp(
      `\\b${attributeName}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`,
      "i",
    ),
  );
  return match ? (match[1] ?? match[2] ?? match[3] ?? "") : "";
}

function decodeText(value = "") {
  return String(value)
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;|&#160;/gi, " ")
    .replace(/&#35;|&num;/gi, "#")
    .replace(/&amp;/gi, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function splitTags(value = "") {
  return [
    ...new Set(
      String(value)
        .split(/[\s,#]+/)
        .map(normalizeTag)
        .filter(Boolean),
    ),
  ];
}

function findFlatnotesTagsMeta(content = "") {
  return [...String(content).matchAll(metaTagPattern)].find(
    (match) =>
      getAttributeValue(match[0], "name").toLowerCase() === "flatnotes-tags",
  )?.[0];
}

function replaceContentAttribute(metaMarkup, value) {
  const attributePattern = /\bcontent\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/i;
  if (attributePattern.test(metaMarkup)) {
    return metaMarkup.replace(attributePattern, `content="${value}"`);
  }

  const closing = metaMarkup.endsWith("/>") ? "/>" : ">";
  return `${metaMarkup.slice(0, -closing.length).trimEnd()} content="${value}"${closing}`;
}

function setFlatnotesMetaTags(content = "", tags = []) {
  const value = [...new Set(tags.map(normalizeTag).filter(Boolean))].join(",");
  const existingMeta = findFlatnotesTagsMeta(content);
  if (existingMeta) {
    return String(content).replace(
      existingMeta,
      replaceContentAttribute(existingMeta, value),
    );
  }

  const metaMarkup = `<meta name="flatnotes-tags" content="${value}">`;
  if (/<\/head>/i.test(content)) {
    return String(content).replace(/<\/head>/i, `    ${metaMarkup}\n  </head>`);
  }
  return `${metaMarkup}\n${content}`;
}

function getLegacyTagOnlyTags(content = "") {
  const tags = new Set();
  for (const match of String(content).matchAll(tagOnlyElementPattern)) {
    const text = decodeText(match[3]);
    if (!tagOnlyTextPattern.test(text)) {
      continue;
    }
    splitTags(text).forEach((tag) => tags.add(tag));
  }
  return [...tags];
}

function stripLegacyTagFromHtml(content = "", tag = "") {
  const target = normalizeTag(tag);
  return String(content).replace(
    tagOnlyElementPattern,
    (markup, elementName, attributes, innerHtml) => {
      const text = decodeText(innerHtml);
      if (!tagOnlyTextPattern.test(text)) {
        return markup;
      }
      const remaining = splitTags(text).filter((item) => item !== target);
      if (remaining.length === splitTags(text).length) {
        return markup;
      }
      if (!remaining.length) {
        return "";
      }
      return `<${elementName}${attributes}>${remaining
        .map((item) => `#${item}`)
        .join(" ")}</${elementName}>`;
    },
  );
}

export function getFlatnotesMetaTags(content = "") {
  const metaMarkup = findFlatnotesTagsMeta(content);
  return metaMarkup ? splitTags(getAttributeValue(metaMarkup, "content")) : [];
}

export function synchronizeDocumentTags({
  content = "",
  previousContent = "",
  format = "html",
} = {}) {
  if (format !== "html" || isWorkNoteHtml(content)) {
    return content;
  }

  const visibleTags = getLegacyTagOnlyTags(content);
  const previousVisibleTags = getLegacyTagOnlyTags(previousContent);
  if (!visibleTags.length && !previousVisibleTags.length) {
    return content;
  }

  const metadataOnlyTags = getFlatnotesMetaTags(content).filter(isSystemTag);
  return setFlatnotesMetaTags(content, [...visibleTags, ...metadataOnlyTags]);
}

export { isSystemTag };

export function documentHasSystemTag(
  content = "",
  tag = "pinned",
  format = "html",
) {
  const normalizedTag = normalizeTag(tag);
  if (format !== "html") {
    return normalizeWorkMarkdownTags(content).tags.includes(normalizedTag);
  }

  return (
    getFlatnotesMetaTags(content).includes(normalizedTag) ||
    getLegacyTagOnlyTags(content).includes(normalizedTag)
  );
}

export function setDocumentSystemTag({
  content = "",
  title = "Untitled",
  format = "html",
  tag = "pinned",
  enabled = true,
} = {}) {
  const normalizedTag = normalizeTag(tag);
  if (!normalizedTag) {
    return content;
  }

  if (format !== "html") {
    return setWorkMarkdownTag(content, normalizedTag, enabled);
  }

  const existingMetaTags = getFlatnotesMetaTags(content);
  if (isWorkNoteHtml(content)) {
    const markdown = setWorkMarkdownTag(
      extractWorkMarkdown(content),
      normalizedTag,
      false,
    );
    const contentTags = new Set(normalizeWorkMarkdownTags(markdown).tags);
    const metadataOnlyTags = existingMetaTags.filter(
      (item) => item !== normalizedTag && !contentTags.has(item),
    );
    if (enabled) {
      metadataOnlyTags.push(normalizedTag);
    }
    return buildWorkNoteHtml(title, markdown, {
      systemTags: metadataOnlyTags,
    });
  }

  const strippedContent = stripLegacyTagFromHtml(content, normalizedTag);
  const nextTags = existingMetaTags.filter((item) => item !== normalizedTag);
  if (enabled) {
    nextTags.push(normalizedTag);
  }
  return setFlatnotesMetaTags(strippedContent, nextTags);
}
