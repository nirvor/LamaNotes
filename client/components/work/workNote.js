const workNoteSelector = "[data-lamanotes-note-kind='work']";
const markdownTemplateSelector = "template[data-lamanotes-work-markdown]";

function escapeHtml(value = "") {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttribute(value = "") {
  return escapeHtml(value).replace(/'/g, "&#39;");
}

function isFullHtmlDocument(value = "") {
  return /<(?:!doctype|html|head|body)\b/i.test(value);
}

function parseHtml(value = "") {
  return new DOMParser().parseFromString(value || "", "text/html");
}

function getBodyHtml(value = "") {
  if (!isFullHtmlDocument(value)) {
    return value || "";
  }

  return parseHtml(value).body?.innerHTML || value || "";
}

function normalizeMarkdown(value = "") {
  return String(value || "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n");
}

function normalizeTagName(tag = "") {
  return tag.replace(/^#/, "").trim().toLowerCase();
}

function sortWorkTags(tags = []) {
  const primaryOrder = new Map([
    ["private", 0],
    ["work", 0],
    ["infra", 0],
  ]);

  return [...tags].sort((left, right) => {
    const leftPrimary = primaryOrder.has(left) ? primaryOrder.get(left) : 1;
    const rightPrimary = primaryOrder.has(right) ? primaryOrder.get(right) : 1;
    if (leftPrimary !== rightPrimary) {
      return leftPrimary - rightPrimary;
    }

    const leftProject = left.startsWith("project-") ? 0 : 1;
    const rightProject = right.startsWith("project-") ? 0 : 1;
    if (leftProject !== rightProject) {
      return leftProject - rightProject;
    }

    const leftTask = left.startsWith("task-") ? 0 : 1;
    const rightTask = right.startsWith("task-") ? 0 : 1;
    if (leftTask !== rightTask) {
      return leftTask - rightTask;
    }

    return left.localeCompare(right);
  });
}

const workTagTokenPattern = /(^|[ \t])#([a-zA-Z0-9][a-zA-Z0-9_-]*)([ \t]?)/g;
const workTagOnlyLinePattern = /^\s*(?:#[a-zA-Z0-9][a-zA-Z0-9_-]*\s*)+$/;

function collectTagsFromLine(line, addTag) {
  [...line.matchAll(/#[a-zA-Z0-9][a-zA-Z0-9_-]*/g)].forEach((match) =>
    addTag(match[0]),
  );
}

function removeInlineTagsFromLine(line, addTag) {
  let removed = false;
  const cleanedLine = line.replace(
    workTagTokenPattern,
    (match, prefix, tag) => {
      addTag(tag);
      removed = true;
      return prefix;
    },
  );

  return { line: cleanedLine, removed };
}

function getBottomTagLineIndexes(lines) {
  const indexes = new Set();
  let index = lines.length - 1;

  while (index >= 0 && !lines[index].trim()) {
    index -= 1;
  }

  while (index >= 0 && workTagOnlyLinePattern.test(lines[index])) {
    indexes.add(index);
    index -= 1;
    while (index >= 0 && !lines[index].trim()) {
      index -= 1;
    }
  }

  return indexes;
}

function hasMovableWorkMarkdownTags(markdown = "") {
  const lines = normalizeMarkdown(markdown).split("\n");
  const bottomTagLineIndexes = getBottomTagLineIndexes(lines);
  let inCodeFence = false;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.trim();
    const fenceLine = trimmed.startsWith("```");
    if (fenceLine) {
      inCodeFence = !inCodeFence;
      continue;
    }

    if (inCodeFence || bottomTagLineIndexes.has(index)) {
      continue;
    }

    if (workTagOnlyLinePattern.test(line) || workTagTokenPattern.test(line)) {
      workTagTokenPattern.lastIndex = 0;
      return true;
    }

    workTagTokenPattern.lastIndex = 0;
  }

  return false;
}

function normalizeWorkMarkdownTags(markdown = "") {
  const lines = normalizeMarkdown(markdown).split("\n");
  const bodyLines = [];
  const tags = new Set();
  let inCodeFence = false;
  let removedTag = false;

  const addTag = (tag) => {
    const normalizedTag = normalizeTagName(tag);
    if (normalizedTag) {
      tags.add(normalizedTag);
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    const fenceLine = trimmed.startsWith("```");
    if (fenceLine) {
      bodyLines.push(line);
      inCodeFence = !inCodeFence;
      continue;
    }

    if (inCodeFence) {
      bodyLines.push(line);
      continue;
    }

    if (workTagOnlyLinePattern.test(line)) {
      collectTagsFromLine(line, addTag);
      removedTag = true;
      continue;
    }

    const cleaned = removeInlineTagsFromLine(line, addTag);
    if (cleaned.removed) {
      removedTag = true;
    }
    bodyLines.push(cleaned.line);
  }

  while (bodyLines.length && !bodyLines[bodyLines.length - 1].trim()) {
    bodyLines.pop();
  }

  const hadTrailingRule =
    bodyLines.length > 0 &&
    /^\s*---+\s*$/.test(bodyLines[bodyLines.length - 1]);
  if (hadTrailingRule) {
    bodyLines.pop();
    while (bodyLines.length && !bodyLines[bodyLines.length - 1].trim()) {
      bodyLines.pop();
    }
  }

  const sortedTags = sortWorkTags([...tags]);
  if (sortedTags.length) {
    if (bodyLines.length) {
      bodyLines.push("");
    } else {
      bodyLines.push("");
    }
    bodyLines.push(sortedTags.map((tag) => `#${tag}`).join(" "));
  } else if (hadTrailingRule) {
    if (bodyLines.length) {
      bodyLines.push("", "---");
    } else {
      bodyLines.push("---");
    }
  }

  const normalizedMarkdown = `${bodyLines.join("\n").trimEnd()}\n`;
  return {
    changed: removedTag || normalizedMarkdown !== normalizeMarkdown(markdown),
    markdown: normalizedMarkdown,
    tags: sortedTags,
  };
}

function setWorkMarkdownTag(markdown = "", tag = "", enabled = true) {
  const normalizedTag = normalizeTagName(tag);
  const normalized = normalizeWorkMarkdownTags(markdown);
  if (!normalizedTag) {
    return normalized.markdown;
  }

  const tags = new Set(normalized.tags);
  if (enabled) {
    tags.add(normalizedTag);
  } else {
    tags.delete(normalizedTag);
  }

  const lines = normalized.markdown.replace(/\n$/, "").split("\n");
  const bottomTagLineIndexes = getBottomTagLineIndexes(lines);
  const bodyLines = lines.filter(
    (_, index) => !bottomTagLineIndexes.has(index),
  );
  while (bodyLines.length && !bodyLines[bodyLines.length - 1].trim()) {
    bodyLines.pop();
  }

  const sortedTags = sortWorkTags([...tags]);
  if (bodyLines.length && sortedTags.length) {
    bodyLines.push("");
  }
  if (sortedTags.length) {
    bodyLines.push(sortedTags.map((item) => `#${item}`).join(" "));
  }

  return `${bodyLines.join("\n").trimEnd()}\n`;
}

function renderInlineMarkdown(value = "") {
  const codeSpans = [];
  let text = String(value).replace(/`([^`]+)`/g, (_, code) => {
    const index = codeSpans.length;
    codeSpans.push(`<code>${escapeHtml(code)}</code>`);
    return `@@LAMANOTES_CODE_${index}@@`;
  });

  text = escapeHtml(text)
    .replace(
      /!\[([^\]]*)\]\(([^)\s]+)\)/g,
      (_, alt, src) =>
        `<img src="${escapeAttribute(src)}" alt="${alt}" loading="lazy" decoding="async">`,
    )
    .replace(
      /\[([^\]]+)\]\(([^)\s]+)\)/g,
      (_, label, href) =>
        `<a href="${escapeAttribute(href)}" rel="noopener noreferrer">${label}</a>`,
    )
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");

  codeSpans.forEach((replacement, index) => {
    text = text.replace(`@@LAMANOTES_CODE_${index}@@`, replacement);
  });

  return text;
}

function isTableSeparator(line = "") {
  return /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function splitTableRow(line = "") {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderMarkdownTable(lines, startIndex) {
  const header = splitTableRow(lines[startIndex]);
  let index = startIndex + 2;
  const rows = [];
  while (
    index < lines.length &&
    /\|/.test(lines[index]) &&
    lines[index].trim()
  ) {
    rows.push(splitTableRow(lines[index]));
    index += 1;
  }

  const headerHtml = header
    .map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`)
    .join("");
  const rowsHtml = rows
    .map(
      (row) =>
        `<tr>${row
          .map((cell) => `<td>${renderInlineMarkdown(cell)}</td>`)
          .join("")}</tr>`,
    )
    .join("\n");

  return {
    html: `<table><thead><tr>${headerHtml}</tr></thead><tbody>${rowsHtml}</tbody></table>`,
    nextIndex: index,
  };
}

function renderMarkdownToHtml(markdown = "") {
  const lines = normalizeMarkdown(markdown).split("\n");
  const blocks = [];
  let index = 0;

  const collectParagraph = () => {
    const paragraph = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^(#{1,6})\s+/.test(lines[index]) &&
      !/^\s*[-*+]\s+/.test(lines[index]) &&
      !/^\s*\d+[.)]\s+/.test(lines[index]) &&
      !/^\s*>/.test(lines[index]) &&
      !/^\s*`{3,}/.test(lines[index]) &&
      !/^\s*---+\s*$/.test(lines[index])
    ) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    if (paragraph.length) {
      blocks.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
    }
  };

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    const fence = trimmed.match(/^(`{3,})([a-zA-Z0-9_-]+)?\s*$/);
    if (fence) {
      const fenceMarker = fence[1];
      const language = fence[2] || "";
      index += 1;
      const codeLines = [];
      while (
        index < lines.length &&
        !(() => {
          const closingFence = lines[index].trim().match(/^(`{3,})\s*$/);
          return closingFence?.[1].length >= fenceMarker.length;
        })()
      ) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      const languageClass = language
        ? ` class="language-${escapeAttribute(language)}"`
        : "";
      blocks.push(
        `<pre><code${languageClass}>${escapeHtml(codeLines.join("\n"))}</code></pre>`,
      );
      continue;
    }

    if (
      index + 1 < lines.length &&
      /\|/.test(line) &&
      isTableSeparator(lines[index + 1])
    ) {
      const table = renderMarkdownTable(lines, index);
      blocks.push(table.html);
      index = table.nextIndex;
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const level = heading[1].length;
      blocks.push(
        `<h${level}>${renderInlineMarkdown(heading[2].trim())}</h${level}>`,
      );
      index += 1;
      continue;
    }

    if (/^\s*---+\s*$/.test(line)) {
      blocks.push("<hr>");
      index += 1;
      continue;
    }

    if (/^\s*>/.test(line)) {
      const quote = [];
      while (index < lines.length && /^\s*>/.test(lines[index])) {
        quote.push(lines[index].replace(/^\s*>\s?/, ""));
        index += 1;
      }
      blocks.push(
        `<blockquote>${renderMarkdownToHtml(quote.join("\n"))}</blockquote>`,
      );
      continue;
    }

    const listMatch = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
    if (listMatch) {
      const ordered = /\d/.test(listMatch[2]);
      const tag = ordered ? "ol" : "ul";
      const items = [];
      while (index < lines.length) {
        const itemMatch = lines[index].match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
        if (!itemMatch || /\d/.test(itemMatch[2]) !== ordered) {
          break;
        }
        let item = itemMatch[3];
        const task = item.match(/^\[( |x|X)\]\s+(.*)$/);
        if (task) {
          const checked = task[1].toLowerCase() === "x";
          items.push(
            `<li class="task-list-item${checked ? " checked" : ""}" data-task-checked="${checked ? "true" : "false"}"><input class="lamanotes-task-checkbox" type="checkbox"${checked ? " checked" : ""}> ${renderInlineMarkdown(task[2])}</li>`,
          );
        } else {
          items.push(`<li>${renderInlineMarkdown(item)}</li>`);
        }
        index += 1;
      }
      blocks.push(`<${tag}>${items.join("")}</${tag}>`);
      continue;
    }

    collectParagraph();
  }

  return blocks.join("\n");
}

function extractTagsFromMarkdown(markdown = "") {
  return normalizeWorkMarkdownTags(markdown).tags;
}

function isWorkNoteHtml(value = "") {
  if (!value) {
    return false;
  }

  if (
    /data-lamanotes-note-kind=["']work["']/i.test(value) ||
    /<meta[^>]+name=["']lamanotes-note-kind["'][^>]+content=["']work["']/i.test(
      value,
    )
  ) {
    return true;
  }

  try {
    const documentValue = parseHtml(value);
    return Boolean(
      documentValue.querySelector(workNoteSelector) ||
        documentValue.querySelector(
          "meta[name='lamanotes-note-kind'][content='work']",
        ),
    );
  } catch {
    return false;
  }
}

function isChecklistNoteHtml(value = "") {
  const taskItems = String(value).match(/<li\b[^>]*\btask-list-item\b/gi);
  return (
    (taskItems?.length || 0) >= 2 &&
    /<input\b[^>]*\btype\s*=\s*["']?checkbox\b/i.test(value) &&
    !/\blamanote-(?:article|research)\b/i.test(value) &&
    !/<(?:audio|canvas|code|figure|iframe|pre|svg|table|video)\b/i.test(value)
  );
}

function htmlChecklistToWorkMarkdown(value = "", title = "") {
  if (!isChecklistNoteHtml(value)) {
    return normalizeMarkdown(value);
  }

  const documentValue = parseHtml(value);
  const root =
    documentValue.querySelector("article, main") || documentValue.body;
  const lines = [];

  const appendText = (text = "") => {
    const normalized = String(text).replace(/\s+/g, " ").trim();
    if (normalized) {
      lines.push(normalized, "");
    }
  };

  const appendList = (list) => {
    const ordered = list.tagName === "OL";
    [...list.children].forEach((item, index) => {
      if (item.tagName !== "LI") {
        return;
      }
      const checkbox = item.querySelector(":scope > input[type='checkbox']");
      const copy = item.cloneNode(true);
      copy
        .querySelectorAll(
          ":scope > input[type='checkbox'], :scope > ul, :scope > ol",
        )
        .forEach((element) => element.remove());
      const text = copy.textContent.replace(/\s+/g, " ").trim();
      if (!text) {
        return;
      }
      if (checkbox) {
        const checked =
          checkbox.checked ||
          checkbox.hasAttribute("checked") ||
          item.dataset.taskChecked === "true" ||
          item.classList.contains("checked");
        lines.push(`- [${checked ? "x" : " "}] ${text}`);
      } else {
        lines.push(`${ordered ? `${index + 1}.` : "-"} ${text}`);
      }
    });
    lines.push("");
  };

  const visit = (element) => {
    const tag = element.tagName;
    if (/^H[1-6]$/.test(tag)) {
      const text = element.textContent.replace(/\s+/g, " ").trim();
      if (text && !(tag === "H1" && text === title)) {
        lines.push(`${"#".repeat(Number(tag.slice(1)))} ${text}`, "");
      }
      return;
    }
    if (tag === "P") {
      appendText(element.textContent);
      return;
    }
    if (tag === "UL" || tag === "OL") {
      appendList(element);
      return;
    }
    if (tag === "HR") {
      lines.push("---", "");
      return;
    }
    if (["SCRIPT", "STYLE", "TEMPLATE"].includes(tag)) {
      return;
    }
    [...element.children].forEach(visit);
  };

  [...root.children].forEach(visit);
  return normalizeMarkdown(lines.join("\n"));
}

function extractWorkMarkdown(value = "") {
  if (!value) {
    return "";
  }

  if (!isWorkNoteHtml(value)) {
    return normalizeMarkdown(value);
  }

  const documentValue = parseHtml(value);
  const template = documentValue.querySelector(markdownTemplateSelector);
  if (template) {
    return normalizeMarkdown(
      template.content?.textContent || template.innerHTML || "",
    );
  }

  const fallback = documentValue.querySelector("[data-lamanotes-work-source]");
  if (fallback) {
    return normalizeMarkdown(fallback.textContent || "");
  }

  return normalizeMarkdown(documentValue.body?.textContent || "");
}

function buildWorkNoteHtml(title = "Untitled", markdown = "", options = {}) {
  const normalized = normalizeWorkMarkdownTags(markdown);
  const normalizedMarkdown = normalized.markdown;
  const tags = normalized.tags;
  const escapedTitle = escapeHtml(title || "Untitled");
  const rendered = renderMarkdownToHtml(normalizedMarkdown);
  const metaTags = sortWorkTags([
    ...new Set([
      ...tags,
      ...(options.systemTags || []).map(normalizeTagName).filter(Boolean),
    ]),
  ]).join(",");

  return `<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8">
    <meta name="lamanotes-note-kind" content="work">
    <meta name="lamanotes-tags" content="${escapeAttribute(metaTags)}">
    <title>${escapedTitle}</title>
  </head>
  <body>
    <article class="lamanote lamanote-work-note" data-lamanotes-note-kind="work">
      <h1>${escapedTitle}</h1>
      <section class="lamanote-work-rendered" data-lamanotes-component="work-body">
${rendered}
      </section>
      <template data-lamanotes-work-markdown>${escapeHtml(normalizedMarkdown)}</template>
    </article>
  </body>
</html>`;
}

export {
  buildWorkNoteHtml,
  extractTagsFromMarkdown,
  extractWorkMarkdown,
  hasMovableWorkMarkdownTags,
  htmlChecklistToWorkMarkdown,
  isChecklistNoteHtml,
  isWorkNoteHtml,
  normalizeWorkMarkdownTags,
  renderMarkdownToHtml,
  setWorkMarkdownTag,
};
