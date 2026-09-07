import { createSmallTextEdit } from "../work/workNote.js";

const escapeAttribute = (value) =>
  String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");

export function safeEditorLink(value) {
  const url = String(value || "").trim();
  return /^(https?:\/\/|mailto:|#|\/(?!\/))/i.test(url) && !/[\s<>]/.test(url)
    ? url
    : "";
}

export function formattingEdit(
  source,
  selection,
  kind,
  language = "markdown",
  url = "",
) {
  const start = Math.max(
    0,
    Math.min(selection?.start ?? source.length, source.length),
  );
  const end = Math.max(start, Math.min(selection?.end ?? start, source.length));
  const selected = source.slice(start, end);
  const html = language === "html";
  const result = (
    from,
    to,
    text,
    anchorOffset = 0,
    headOffset = text.length,
  ) => ({ from, to, text, anchorOffset, headOffset });
  if (kind === "small" && !html)
    return createSmallTextEdit(source, { start, end });
  if (["bold", "italic", "small", "code"].includes(kind)) {
    const [open, close] = html
      ? {
          bold: ["<strong>", "</strong>"],
          italic: ["<em>", "</em>"],
          small: ["<small>", "</small>"],
          code: ["<code>", "</code>"],
        }[kind]
      : { bold: ["**", "**"], italic: ["_", "_"], code: ["`", "`"] }[kind];
    if (
      selected.startsWith(open) &&
      selected.endsWith(close) &&
      selected.length >= open.length + close.length
    ) {
      return result(start, end, selected.slice(open.length, -close.length));
    }
    if (
      source.slice(start - open.length, start) === open &&
      source.slice(end, end + close.length) === close
    ) {
      return result(start - open.length, end + close.length, selected);
    }
    return result(
      start,
      end,
      open + selected + close,
      open.length,
      open.length + selected.length,
    );
  }
  if (kind === "link") {
    const safeUrl = safeEditorLink(url);
    if (!safeUrl) return null;
    const label = selected || safeUrl;
    if (html) {
      const open = `<a href="${escapeAttribute(safeUrl)}">`;
      return result(
        start,
        end,
        `${open}${label}</a>`,
        open.length,
        open.length + label.length,
      );
    }
    const text = `[${label}](${safeUrl.replace(/\)/g, "%29")})`;
    return result(start, end, text, 1, 1 + label.length);
  }
  if (kind === "list" || kind === "checklist") {
    const from = source.lastIndexOf("\n", start - 1) + 1;
    const lineEnd = source.indexOf(
      "\n",
      end > start && source[end - 1] === "\n" ? end - 1 : end,
    );
    const to = lineEnd < 0 ? source.length : lineEnd;
    const lines = source.slice(from, to).split("\n");
    if (html) {
      const task = kind === "checklist";
      const block = source.slice(from, to);
      const wrapper = task
        ? /^<ul class="task-list">\n([\s\S]*)\n<\/ul>$/
        : /^<ul>\n([\s\S]*)\n<\/ul>$/;
      const existing = block.match(wrapper);
      if (existing) {
        const rows = existing[1].split("\n");
        const item = task
          ? /^<li class="task-list-item"><input type="checkbox">(.*)<\/li>$/
          : /^<li>(.*)<\/li>$/;
        if (rows.every((row) => item.test(row)))
          return result(
            from,
            to,
            rows.map((row) => row.match(item)[1]).join("\n"),
          );
      }
      const text = `<ul${task ? ' class="task-list"' : ""}>\n${lines.map((line) => (task ? `<li class="task-list-item"><input type="checkbox">${line}</li>` : `<li>${line}</li>`)).join("\n")}\n</ul>`;
      return result(from, to, text);
    }
    const marker = kind === "checklist" ? "- [ ] " : "- ";
    const pattern =
      kind === "checklist"
        ? /^(\s*)[-*+] \[[ xX]\] /
        : /^(\s*)[-*+] (?!\[[ xX]\] )/;
    const remove = lines.every((line) => !line.trim() || pattern.test(line));
    const text = lines
      .map((line) =>
        remove
          ? line.replace(pattern, "$1")
          : line.replace(/^(\s*)(?:[-*+] (?:\[[ xX]\] )?)?/, `$1${marker}`),
      )
      .join("\n");
    const caret = Math.max(
      0,
      Math.min(text.length, start - from + text.length - (to - from)),
    );
    return result(
      from,
      to,
      text,
      start === end ? caret : 0,
      start === end ? caret : text.length,
    );
  }
  return null;
}
