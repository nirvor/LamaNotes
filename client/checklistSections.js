import { appendMarkdownTask, markdownTasks } from "./checklists.js";
import { renderMarkdownToHtml } from "./components/work/workNote.js";

const headingTags = new Set(["h2", "h3", "h4", "h5", "h6"]);
const voidTags = new Set(
  "area base br col embed hr img input link meta param source track wbr".split(
    " ",
  ),
);
const tagFooter = /^(?:#[\p{L}\p{N}_-]+\s*)+$/u;
const normalizeLabel = (value) =>
  String(value || "")
    .replace(/\s+/g, " ")
    .trim();
const escapeHtml = (value) =>
  String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

function fragment(value) {
  const element = document.createElement("div");
  element.innerHTML = value;
  return element;
}

function htmlTree(source) {
  const root = {
    name: "root",
    children: [],
    start: 0,
    openEnd: 0,
    closeStart: source.length,
    end: source.length,
  };
  const stack = [root];
  const tags =
    /<!--[\s\S]*?-->|<![^>]*>|<\/?[a-zA-Z][\w:-]*(?:\s+(?:[^"'<>]|"[^"]*"|'[^']*')*)?\s*\/?>/g;
  let match;
  while ((match = tags.exec(source))) {
    const token = match[0];
    if (/^<!/.test(token)) continue;
    const name = token.match(/^<\/?([\w:-]+)/)[1].toLowerCase();
    if (token.startsWith("</")) {
      const index = stack.findLastIndex((node) => node.name === name);
      if (index > 0) {
        const node = stack[index];
        node.closeStart = match.index;
        node.end = tags.lastIndex;
        stack.length = index;
      }
      continue;
    }
    const parent = stack.at(-1);
    const node = {
      name,
      token,
      parent,
      children: [],
      start: match.index,
      openEnd: tags.lastIndex,
      closeStart: tags.lastIndex,
      end: tags.lastIndex,
    };
    parent.children.push(node);
    if (voidTags.has(name) || /\/>$/.test(token)) continue;
    if (["script", "style", "template", "textarea"].includes(name)) {
      const closing = new RegExp(`</${name}\\s*>`, "ig");
      closing.lastIndex = tags.lastIndex;
      const end = closing.exec(source);
      if (!end) return null;
      node.closeStart = end.index;
      node.end = closing.lastIndex;
      tags.lastIndex = closing.lastIndex;
    } else stack.push(node);
  }
  return stack.length === 1 ? root : null;
}

function descendants(node) {
  return node.children.flatMap((child) => [child, ...descendants(child)]);
}

function htmlLabel(node, source) {
  if (headingTags.has(node.name))
    return normalizeLabel(
      fragment(source.slice(node.openEnd, node.closeStart)).textContent,
    );
  if (node.name !== "p") return null;
  const element = fragment(
    source.slice(node.start, node.end),
  ).firstElementChild;
  const strong = element?.querySelector(":scope > strong:only-child");
  const text = normalizeLabel(element?.textContent);
  return strong &&
    text.length < 100 &&
    text === normalizeLabel(strong.textContent)
    ? text
    : null;
}

function isHtmlFooter(node, source) {
  return (
    node.name === "p" &&
    tagFooter.test(
      normalizeLabel(
        fragment(source.slice(node.openEnd, node.closeStart)).textContent,
      ),
    )
  );
}

function htmlRange(source, section) {
  const tree = htmlTree(source);
  if (!tree) return null;
  const nodes = descendants(tree);
  const headings = nodes.filter(
    (node) =>
      htmlLabel(node, source) !== null &&
      !inside(node, ["li", "blockquote", "table", "head"]),
  );
  let start, end;
  if (Number.isInteger(section?.headingIndex)) {
    const heading = headings[section.headingIndex];
    if (
      !heading ||
      htmlLabel(heading, source) !== normalizeLabel(section.heading)
    )
      return null;
    const siblings = heading.parent.children;
    const boundary = siblings
      .slice(siblings.indexOf(heading) + 1)
      .find(
        (node) =>
          /^h[1-6]$/.test(node.name) ||
          htmlLabel(node, source) !== null ||
          node.name === "hr" ||
          isHtmlFooter(node, source),
      );
    start = heading.end;
    end = boundary?.start ?? heading.parent.closeStart;
  } else {
    const item = nodes.filter(
      (node) => node.name === "li" && /\btask-list-item\b/.test(node.token),
    )[section?.taskIndex];
    let list = item?.parent;
    if (!list || !["ul", "ol"].includes(list.name)) return null;
    while (list.parent && ["li", "ul", "ol"].includes(list.parent.name))
      list = list.parent;
    if (!["ul", "ol"].includes(list.name)) return null;
    start = list.start;
    end = list.end;
  }
  return {
    start,
    end,
    html: source.slice(start, end),
    nodes: nodes.filter((node) => node.start >= start && node.end <= end),
  };
}

function inside(node, names) {
  for (let parent = node.parent; parent; parent = parent.parent)
    if (names.includes(parent.name)) return true;
  return false;
}

function markdownRanges(source) {
  const lines = source.match(/[^\r\n]*(?:\r\n|\n|\r|$)/g).filter(Boolean);
  let offset = 0,
    fence = null;
  const headings = [],
    boundaries = [];
  for (const raw of lines) {
    const line = raw.replace(/[\r\n]+$/, "");
    const delimiter = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (delimiter) {
      if (!fence) fence = delimiter[1];
      else if (
        delimiter[1][0] === fence[0] &&
        delimiter[1].length >= fence.length
      )
        fence = null;
    } else if (!fence) {
      const atx = line.match(/^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);
      const bold = line.match(/^\s*(?:\*\*([^*]+)\*\*|__([^_]+)__)\s*$/);
      const label =
        atx && atx[1].length >= 2 ? atx[2] : bold ? bold[1] || bold[2] : null;
      if (label !== null)
        headings.push({
          start: offset,
          end: offset + raw.length,
          label: normalizeLabel(
            fragment(renderMarkdownToHtml(label)).textContent,
          ),
        });
      if (
        atx ||
        bold ||
        /^\s*(?:---+|\*\*\*+)\s*$/.test(line) ||
        tagFooter.test(line.trim())
      )
        boundaries.push(offset);
    }
    offset += raw.length;
  }
  return { lines, headings, boundaries };
}

function markdownRange(source, section) {
  const parsed = markdownRanges(source);
  if (Number.isInteger(section?.headingIndex)) {
    const heading = parsed.headings[section.headingIndex];
    if (!heading || heading.label !== normalizeLabel(section.heading))
      return null;
    return {
      start: heading.end,
      end:
        parsed.boundaries.find((offset) => offset >= heading.end) ??
        source.length,
    };
  }
  const task = markdownTasks(source)[section?.taskIndex];
  if (!task) return null;
  const lines = source.split("\n");
  let first = task.lineIndex,
    last = first + 1;
  while (first > 0 && /^\s*(?:[-*+]|\d+[.)])\s+/.test(lines[first - 1]))
    first--;
  while (
    last < lines.length &&
    (lines[last].trim() === "" ||
      /^\s*(?:[-*+]|\d+[.)])\s+/.test(lines[last]) ||
      /^\s+\S/.test(lines[last]))
  )
    last++;
  const start = lines.slice(0, first).join("\n").length + (first ? 1 : 0);
  const end =
    lines.slice(0, last).join("\n").length + (last < lines.length ? 1 : 0);
  return { start, end };
}

function htmlToMarkdown(value) {
  const root = fragment(value);
  if (
    root.querySelector(
      "audio,canvas,iframe,object,pre,script,style,svg,table,template,video",
    )
  )
    return null;
  const inline = (node) => {
    if (node.nodeType === 3)
      return node.textContent.replace(/([\\`*_\[\]])/g, "\\$1");
    if (node.nodeType !== 1 || node.matches("input[type=checkbox]")) return "";
    const text = [...node.childNodes].map(inline).join("");
    if (node.tagName === "STRONG" || node.tagName === "B") return `**${text}**`;
    if (node.tagName === "EM" || node.tagName === "I") return `*${text}*`;
    if (node.tagName === "CODE") return `\`${node.textContent}\``;
    if (node.tagName === "BR") return "\n";
    if (node.tagName === "A")
      return `[${text}](${node.getAttribute("href") || ""})`;
    if (node.tagName === "IMG")
      return `![${node.getAttribute("alt") || ""}](${node.getAttribute("src") || ""})`;
    return text;
  };
  const block = (node, depth = 0) => {
    if (node.nodeType === 3)
      return node.textContent.trim() ? `${inline(node)}\n\n` : "";
    if (node.nodeType !== 1) return "";
    if (node.matches("ul,ol"))
      return (
        [...node.children]
          .filter((item) => item.tagName === "LI")
          .map((item, index) => {
            const checkbox = item.querySelector(
              ":scope > input[type=checkbox]",
            );
            const checked =
              checkbox?.checked ||
              item.dataset.taskChecked === "true" ||
              item.classList.contains("checked");
            const text = [...item.childNodes]
              .filter((child) => !child.matches?.("ul,ol"))
              .map(inline)
              .join("")
              .trim();
            const marker =
              checkbox || item.classList.contains("task-list-item")
                ? `- [${checked ? "x" : " "}]`
                : node.tagName === "OL"
                  ? `${index + 1}.`
                  : "-";
            const nested = [...item.children]
              .filter((child) => child.matches("ul,ol"))
              .map((child) => block(child, depth + 1))
              .join("");
            return `${"  ".repeat(depth)}${marker} ${text}\n${nested}`;
          })
          .join("") + (depth ? "" : "\n")
      );
    if (/^H[1-6]$/.test(node.tagName))
      return `${"#".repeat(Number(node.tagName[1]))} ${inline(node)}\n\n`;
    if (node.tagName === "HR") return "---\n\n";
    if (node.matches("div,section,article"))
      return [...node.childNodes].map((child) => block(child, depth)).join("");
    return `${inline(node)}\n\n`;
  };
  return [...root.childNodes]
    .map((node) => block(node))
    .join("")
    .trim();
}

function renderSectionMarkdown(markdown) {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const output = [];
  const listItem = (line) => line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
  let cursor = 0;
  const renderList = (indent) => {
    const ordered = /\d/.test(listItem(lines[cursor])[2]);
    const tag = ordered ? "ol" : "ul";
    const items = [];
    while (cursor < lines.length) {
      const match = listItem(lines[cursor]);
      if (
        !match ||
        match[1].length !== indent ||
        /\d/.test(match[2]) !== ordered
      )
        break;
      cursor++;
      const task = match[3].match(/^\[([ xX])\]\s*(.*)$/);
      const text = task ? task[2] : match[3];
      const inline = renderEscapedMarkdown(text).replace(/^<p>|<\/p>$/g, "");
      let nested = "";
      while (
        cursor < lines.length &&
        listItem(lines[cursor])?.[1].length > indent
      )
        nested += renderList(listItem(lines[cursor])[1].length);
      const checked = task && task[1].toLowerCase() === "x";
      items.push(
        task
          ? `<li class="task-list-item${checked ? " checked" : ""}" data-task-checked="${checked ? "true" : "false"}"><input type="checkbox"${checked ? " checked" : ""}>${inline}${nested}</li>`
          : `<li>${inline}${nested}</li>`,
      );
    }
    return `<${tag}>${items.join("")}</${tag}>`;
  };
  while (cursor < lines.length) {
    if (listItem(lines[cursor]))
      output.push(renderList(listItem(lines[cursor])[1].length));
    else {
      const start = cursor++;
      while (cursor < lines.length && !listItem(lines[cursor])) cursor++;
      output.push(renderEscapedMarkdown(lines.slice(start, cursor).join("\n")));
    }
  }
  return output.filter(Boolean).join("\n");
}

function renderEscapedMarkdown(markdown) {
  const literals = [];
  const protectedMarkdown = markdown.replace(/\\([\\`*_\[\]])/g, (_, value) => {
    const key = `@@LAMANOTES_SECTION_LITERAL_${literals.length}@@`;
    literals.push({ key, value });
    return key;
  });
  return literals.reduce(
    (html, { key, value }) => html.split(key).join(escapeHtml(value)),
    renderMarkdownToHtml(protectedMarkdown),
  );
}

function workSource(content, format) {
  if (
    format !== "html" ||
    !/data-lamanotes-note-kind=["']work["']/i.test(content)
  )
    return null;
  const tree = htmlTree(content);
  const nodes = tree ? descendants(tree) : [];
  const template = nodes.find(
    (node) =>
      node.name === "template" &&
      /data-lamanotes-work-markdown\b/.test(node.token),
  );
  const body = nodes.find((node) =>
    /data-lamanotes-component=["']work-body["']/.test(node.token),
  );
  if (!template || !body) return null;
  const raw = content.slice(template.openEnd, template.closeStart);
  let markdown = "",
    positions = [],
    cursor = 0;
  for (const match of raw.matchAll(
    /&(?:#\d+|#x[\da-f]+|[a-z][\w]+);|[\s\S]/gi,
  )) {
    const decoded = match[0].startsWith("&")
      ? fragment(match[0]).textContent
      : match[0];
    for (let index = 0; index < decoded.length; index++) positions.push(cursor);
    markdown += decoded;
    cursor += match[0].length;
  }
  positions.push(raw.length);
  return { template, body, markdown, positions };
}

export function readChecklistSection(
  content,
  section,
  { format = "markdown" } = {},
) {
  const work = workSource(content, format);
  if (work) return readChecklistSection(work.markdown, section);
  const range =
    format === "html"
      ? htmlRange(content, section)
      : markdownRange(content, section);
  if (!range) return null;
  const markdown =
    format === "html"
      ? htmlToMarkdown(range.html)
      : content.slice(range.start, range.end).trim();
  return markdown === null ? null : { markdown };
}

function spliceBody(content, range, replacement) {
  const original = content.slice(range.start, range.end);
  const leading = original.match(/^\s*/)[0];
  const trailing = original.trim() ? original.match(/\s*$/)[0] : "";
  return (
    content.slice(0, range.start) +
    leading +
    replacement +
    (trailing || (replacement ? "\n\n" : "")) +
    content.slice(range.end)
  );
}

export function replaceChecklistSection(
  content,
  section,
  markdown,
  { format = "markdown" } = {},
) {
  const current = readChecklistSection(content, section, { format });
  if (!current || typeof markdown !== "string" || markdown.length > 100000)
    return null;
  if (current.markdown === markdown.trim()) return content;
  const work = workSource(content, format);
  if (work) {
    const markdownBody = markdownRange(work.markdown, section);
    const nextMarkdown = replaceChecklistSection(
      work.markdown,
      section,
      markdown,
    );
    const bodyRange = htmlRange(
      content.slice(work.body.openEnd, work.body.closeStart),
      section,
    );
    if (nextMarkdown === null || !bodyRange || !markdownBody) return null;
    const absoluteRange = {
      start: work.body.openEnd + bodyRange.start,
      end: work.body.openEnd + bodyRange.end,
    };
    const newSection = nextMarkdown.slice(
      markdownBody.start,
      nextMarkdown.length - (work.markdown.length - markdownBody.end),
    );
    const html = spliceBody(
      content,
      absoluteRange,
      renderSectionMarkdown(markdown.trim()),
    );
    const changes = [
      {
        start: work.template.openEnd + work.positions[markdownBody.start],
        end: work.template.openEnd + work.positions[markdownBody.end],
        value: escapeHtml(newSection),
      },
      {
        start: absoluteRange.start,
        end: absoluteRange.end,
        value: html.slice(
          absoluteRange.start,
          html.length - (content.length - absoluteRange.end),
        ),
      },
    ];
    return changes
      .sort((a, b) => b.start - a.start)
      .reduce(
        (value, change) =>
          value.slice(0, change.start) + change.value + value.slice(change.end),
        content,
      );
  }
  const range =
    format === "html"
      ? htmlRange(content, section)
      : markdownRange(content, section);
  const replacement =
    format === "html"
      ? renderSectionMarkdown(markdown.trim())
      : markdown
          .trim()
          .replace(/\r?\n/g, content.includes("\r\n") ? "\r\n" : "\n");
  return spliceBody(content, range, replacement);
}

export function appendChecklistSectionItem(
  content,
  section,
  text,
  { format = "markdown" } = {},
) {
  const itemText = String(text || "")
    .trim()
    .replace(/[\r\n]+/g, " ");
  if (!itemText || itemText.length > 1000) return null;
  const work = workSource(content, format);
  if (work) {
    const current = readChecklistSection(content, section, { format });
    if (!current) return null;
    const tasks = markdownTasks(current.markdown);
    const markdown = tasks.length
      ? appendMarkdownTask(current.markdown, tasks.length - 1, itemText)
      : `${current.markdown}${current.markdown ? "\n\n" : ""}- [ ] ${itemText}`;
    return replaceChecklistSection(content, section, markdown, { format });
  }
  const range =
    format === "html"
      ? htmlRange(content, section)
      : markdownRange(content, section);
  if (!range) return null;
  if (format === "html") {
    const list = range.nodes
      .filter(
        (node) => ["ul", "ol"].includes(node.name) && !inside(node, ["li"]),
      )
      .at(-1);
    const item = `<li class="task-list-item"><input type="checkbox">${escapeHtml(itemText)}</li>`;
    const offset = list?.closeStart ?? range.end;
    return (
      content.slice(0, offset) +
      (list ? item : `<ul>${item}</ul>\n`) +
      content.slice(offset)
    );
  }
  const original = content.slice(range.start, range.end);
  const tasks = markdownTasks(original);
  const updated = tasks.length
    ? appendMarkdownTask(original, tasks.length - 1, itemText)
    : original.replace(
        /\s*$/,
        (suffix) =>
          `${original.trim() ? "\n" : ""}- [ ] ${itemText}\n${suffix}`,
      );
  return content.slice(0, range.start) + updated + content.slice(range.end);
}
