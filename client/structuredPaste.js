import { detectCsvDelimiter, parseDelimitedRows } from "./csvPreview.js";
import {
  classifyPastedText,
  markdownForPaste,
} from "./components/paste/mediaPaste.js";

export function structuredPasteOptions(source = "") {
  const text = String(source).replace(/\r\n?/g, "\n");
  if (!text.trim()) {
    return [];
  }

  const options = [];
  const table = markdownTableFromDelimitedText(text);
  if (table) {
    options.push({ id: "table", label: "Table", content: table });
  }

  const classification = classifyPastedText(text);
  if (classification.type === "code" && !/^\s*(```|~~~)/.test(text)) {
    const code = markdownForPaste(classification, "");
    if (code && code !== text) {
      options.push({ id: "code", label: "Code", content: code });
    }
  }

  const nonEmptyLines = text.split("\n").filter((line) => line.trim());
  if (!table && classification.type !== "code" && nonEmptyLines.length >= 2) {
    options.push({
      id: "quote",
      label: "Quote",
      content: text
        .split("\n")
        .map((line) => (line ? `> ${line}` : ">"))
        .join("\n"),
    });
  }

  return options;
}

export function fitStructuredPasteToContext(
  document = "",
  from = 0,
  to = from,
  content = "",
) {
  const source = String(document);
  const start = Math.max(0, Math.min(Number(from) || 0, source.length));
  const end = Math.max(start, Math.min(Number(to) || start, source.length));
  const before = source.slice(0, start);
  const after = source.slice(end);
  const prefix = blockBoundaryBefore(before);
  const suffix = blockBoundaryAfter(after);
  return `${prefix}${String(content)}${suffix}`;
}

function blockBoundaryBefore(source) {
  if (!source || source.endsWith("\n\n")) {
    return "";
  }
  return source.endsWith("\n") ? "\n" : "\n\n";
}

function blockBoundaryAfter(source) {
  if (!source || source.startsWith("\n\n")) {
    return "";
  }
  return source.startsWith("\n") ? "\n" : "\n\n";
}

export function markdownTableFromDelimitedText(source = "") {
  const text = String(source).trim();
  if (!text || !/[,;\t]/.test(text)) {
    return "";
  }
  const delimiter = detectCsvDelimiter(text);
  const { rows } = parseDelimitedRows(text, delimiter, 40);
  const meaningful = rows.filter((row) => row.some((cell) => cell.trim()));
  if (meaningful.length < 2) {
    return "";
  }
  const width = meaningful[0].length;
  if (width < 2 || meaningful.some((row) => row.length !== width)) {
    return "";
  }

  const escaped = meaningful.map((row) =>
    row.map((cell) => String(cell).trim().replace(/\|/g, "\\|")),
  );
  const header = `| ${escaped[0].join(" | ")} |`;
  const separator = `| ${Array(width).fill("---").join(" | ")} |`;
  const body = escaped.slice(1).map((row) => `| ${row.join(" | ")} |`);
  return [header, separator, ...body].join("\n");
}
