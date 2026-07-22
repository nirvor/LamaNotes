const markdownLanguages = new Set(["md", "markdown"]);
const textLanguages = new Set(["text", "txt", "log"]);

const actions = {
  "clean-markdown": {
    id: "clean-markdown",
    label: "Clean Markdown",
    detail: "Headings, spacing and repeated separators",
  },
  "align-tables": {
    id: "align-tables",
    label: "Align tables",
    detail: "Pad Markdown table columns without changing values",
  },
  "repair-markdown": {
    id: "repair-markdown",
    label: "Repair syntax",
    detail: "Fix heading markers and close an unfinished code fence",
  },
  "format-json": {
    id: "format-json",
    label: "Format JSON",
    detail: "Validate and indent with two spaces",
  },
  "tidy-text": {
    id: "tidy-text",
    label: "Tidy text",
    detail: "Remove stray line endings and excessive blank space",
  },
};

export function availableDocumentAutomations(language, source = "") {
  const normalized = String(language || "text").toLowerCase();
  if (markdownLanguages.has(normalized)) {
    const result = [actions["clean-markdown"]];
    if (findMarkdownTableRanges(source).length) {
      result.push(actions["align-tables"]);
    }
    result.push(actions["repair-markdown"]);
    return result;
  }
  if (normalized === "json") {
    return [actions["format-json"]];
  }
  if (textLanguages.has(normalized)) {
    return [actions["tidy-text"]];
  }
  return [];
}

export function runDocumentAutomation(actionId, source = "") {
  const input = String(source ?? "");
  let output;
  if (actionId === "clean-markdown") {
    output = cleanMarkdown(input);
  } else if (actionId === "align-tables") {
    output = alignMarkdownTables(input);
  } else if (actionId === "repair-markdown") {
    output = repairMarkdown(input);
  } else if (actionId === "format-json") {
    output = formatJson(input);
  } else if (actionId === "tidy-text") {
    output = tidyText(input);
  } else {
    throw new Error("Unknown note tool.");
  }

  return {
    output,
    changed: output !== input,
    changedLines: countChangedLines(input, output),
    preview: buildAutomationPreview(input, output),
  };
}

export function cleanMarkdown(source = "") {
  const repaired = normalizeMarkdownLines(source, { closeFence: false });
  const lines = repaired.split("\n");
  const output = [];
  let inFence = false;
  let lastContentWasRule = false;

  for (let rawLine of lines) {
    const fence = rawLine.match(/^\s*(```+|~~~+)/);
    if (fence) {
      inFence = !inFence;
      output.push(rawLine.replace(/[ \t]+$/, ""));
      lastContentWasRule = false;
      continue;
    }
    if (inFence) {
      output.push(rawLine);
      continue;
    }

    rawLine = trimMarkdownLineEnd(rawLine);
    const isRule = /^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$/.test(rawLine);
    if (isRule && lastContentWasRule) {
      while (output.at(-1) === "") {
        output.pop();
      }
      continue;
    }

    if (/^\s{0,3}#{1,6}\s+/.test(rawLine)) {
      if (output.length && output.at(-1) !== "") {
        output.push("");
      }
      output.push(rawLine);
      lastContentWasRule = false;
      continue;
    }

    if (rawLine === "") {
      if (output.at(-1) !== "" && output.length) {
        output.push("");
      }
      continue;
    }

    output.push(rawLine);
    lastContentWasRule = isRule;
    if (!isRule) {
      lastContentWasRule = false;
    }
  }

  return finishText(output.join("\n"));
}

export function repairMarkdown(source = "") {
  return normalizeMarkdownLines(source, { closeFence: true });
}

export function alignMarkdownTables(source = "") {
  const normalized = String(source).replace(/\r\n?/g, "\n");
  const lines = normalized.split("\n");
  const ranges = findMarkdownTableRanges(normalized);
  if (!ranges.length) {
    return source;
  }

  for (const range of [...ranges].reverse()) {
    lines.splice(
      range.start,
      range.end - range.start,
      ...formatMarkdownTable(lines.slice(range.start, range.end)),
    );
  }
  return finishText(lines.join("\n"));
}

export function findMarkdownTableRanges(source = "") {
  const lines = String(source).replace(/\r\n?/g, "\n").split("\n");
  const ranges = [];
  let index = 0;
  let inFence = false;
  while (index < lines.length) {
    if (/^\s*(```+|~~~+)/.test(lines[index])) {
      inFence = !inFence;
      index += 1;
      continue;
    }
    if (
      !inFence &&
      lines[index].includes("|") &&
      isMarkdownTableSeparator(lines[index + 1])
    ) {
      let end = index + 2;
      while (end < lines.length && lines[end].includes("|")) {
        end += 1;
      }
      ranges.push({ start: index, end });
      index = end;
      continue;
    }
    index += 1;
  }
  return ranges;
}

export function buildAutomationPreview(before = "", after = "", limit = 80) {
  if (before === after) {
    return ["No changes needed."];
  }
  const left = String(before).replace(/\r\n?/g, "\n").split("\n");
  const right = String(after).replace(/\r\n?/g, "\n").split("\n");
  let prefix = 0;
  while (
    prefix < left.length &&
    prefix < right.length &&
    left[prefix] === right[prefix]
  ) {
    prefix += 1;
  }
  let leftEnd = left.length;
  let rightEnd = right.length;
  while (
    leftEnd > prefix &&
    rightEnd > prefix &&
    left[leftEnd - 1] === right[rightEnd - 1]
  ) {
    leftEnd -= 1;
    rightEnd -= 1;
  }

  const preview = [];
  left
    .slice(Math.max(0, prefix - 2), prefix)
    .forEach((line) => preview.push(`  ${line}`));
  left.slice(prefix, leftEnd).forEach((line) => preview.push(`- ${line}`));
  right.slice(prefix, rightEnd).forEach((line) => preview.push(`+ ${line}`));
  right
    .slice(rightEnd, Math.min(right.length, rightEnd + 2))
    .forEach((line) => preview.push(`  ${line}`));
  if (preview.length <= limit) {
    return preview;
  }
  const half = Math.max(2, Math.floor((limit - 1) / 2));
  return [...preview.slice(0, half), "  ...", ...preview.slice(-half)];
}

function normalizeMarkdownLines(source, { closeFence }) {
  const lines = String(source).replace(/\r\n?/g, "\n").split("\n");
  let inFence = false;
  let fenceMarker = "```";
  const output = lines.map((line) => {
    const fence = line.match(/^\s*(```+|~~~+)/);
    if (fence) {
      if (!inFence) {
        fenceMarker = fence[1][0].repeat(Math.max(3, fence[1].length));
      }
      inFence = !inFence;
      return line.replace(/[ \t]+$/, "");
    }
    if (inFence) {
      return line;
    }
    return trimMarkdownLineEnd(line).replace(
      /^(\s{0,3}#{1,6})([^#\s])/,
      "$1 $2",
    );
  });
  if (closeFence && inFence) {
    if (output.at(-1) !== "") {
      output.push("");
    }
    output.push(fenceMarker);
  }
  return finishText(output.join("\n"));
}

function trimMarkdownLineEnd(line) {
  const trailing = line.match(/[ \t]+$/)?.[0] || "";
  if (!trailing) {
    return line;
  }
  const replacement =
    !trailing.includes("\t") && trailing.length >= 2 ? "  " : "";
  return line.slice(0, -trailing.length) + replacement;
}

function tidyText(source) {
  const lines = String(source)
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.replace(/[ \t]+$/, ""));
  const output = [];
  for (const line of lines) {
    if (line === "" && output.at(-1) === "" && output.at(-2) === "") {
      continue;
    }
    output.push(line);
  }
  return finishText(output.join("\n"));
}

function formatJson(source) {
  let parsed;
  try {
    parsed = JSON.parse(String(source));
  } catch (error) {
    throw new Error(`Invalid JSON: ${error.message}`);
  }
  return `${JSON.stringify(parsed, null, 2)}\n`;
}

function isMarkdownTableSeparator(line = "") {
  const cells = splitMarkdownRow(line);
  return (
    cells.length >= 2 && cells.every((cell) => /^:?-{3,}:?$/.test(cell.trim()))
  );
}

function splitMarkdownRow(line = "") {
  const trimmed = String(line).trim().replace(/^\|/, "").replace(/\|$/, "");
  const cells = [];
  let cell = "";
  let escaped = false;
  for (const character of trimmed) {
    if (character === "|" && !escaped) {
      cells.push(cell.trim());
      cell = "";
      continue;
    }
    cell += character;
    escaped = character === "\\" && !escaped;
    if (character !== "\\") {
      escaped = false;
    }
  }
  cells.push(cell.trim());
  return cells;
}

function formatMarkdownTable(lines) {
  const rows = lines.map(splitMarkdownRow);
  const width = Math.max(...rows.map((row) => row.length));
  const columns = Array(width).fill(3);
  rows.forEach((row, rowIndex) => {
    if (rowIndex === 1) {
      return;
    }
    row.forEach((cell, column) => {
      columns[column] = Math.max(columns[column], cell.length);
    });
  });
  return rows.map((row, rowIndex) => {
    const cells = Array.from({ length: width }, (_, column) => {
      const cell = row[column] || "";
      if (rowIndex !== 1) {
        return cell.padEnd(columns[column]);
      }
      const left = cell.startsWith(":");
      const right = cell.endsWith(":");
      const dashes = "-".repeat(
        Math.max(3, columns[column] - Number(left) - Number(right)),
      );
      return `${left ? ":" : ""}${dashes}${right ? ":" : ""}`.padEnd(
        columns[column],
      );
    });
    return `| ${cells.join(" | ")} |`;
  });
}

function countChangedLines(before, after) {
  const left = String(before).split(/\r?\n/);
  const right = String(after).split(/\r?\n/);
  const length = Math.max(left.length, right.length);
  let count = 0;
  for (let index = 0; index < length; index += 1) {
    if (left[index] !== right[index]) {
      count += 1;
    }
  }
  return count;
}

function finishText(source) {
  const content = String(source).replace(/\n+$/, "");
  return content ? `${content}\n` : "";
}
