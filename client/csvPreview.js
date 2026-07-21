const CANDIDATE_DELIMITERS = [",", ";", "\t"];

export const CSV_PREVIEW_ROW_LIMIT = 500;

export function parseDelimitedRows(
  source,
  delimiter = ",",
  rowLimit = Infinity,
) {
  const text = String(source || "").replace(/^\uFEFF/, "");
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"' && text[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        cell += character;
      }
      continue;
    }

    if (character === '"' && cell === "") {
      quoted = true;
    } else if (character === delimiter) {
      row.push(cell);
      cell = "";
    } else if (character === "\n" || character === "\r") {
      if (character === "\r" && text[index + 1] === "\n") {
        index += 1;
      }
      row.push(cell);
      rows.push(row);
      if (rows.length >= rowLimit) {
        return { rows, truncated: index < text.length - 1 };
      }
      row = [];
      cell = "";
    } else {
      cell += character;
    }
  }

  if (cell || row.length || !rows.length) {
    row.push(cell);
    rows.push(row);
  }
  if (rows.length > 1 && rows.at(-1).every((value) => value === "")) {
    rows.pop();
  }
  return { rows, truncated: false };
}

export function detectCsvDelimiter(source) {
  let best = { delimiter: ",", score: -1 };
  for (const delimiter of CANDIDATE_DELIMITERS) {
    const { rows } = parseDelimitedRows(source, delimiter, 12);
    const widths = rows
      .filter((row) => row.some((value) => value !== ""))
      .map((row) => row.length);
    const counts = new Map();
    widths.forEach((width) => counts.set(width, (counts.get(width) || 0) + 1));
    const [width = 1, frequency = 0] =
      [...counts.entries()].sort(
        (left, right) => right[1] - left[1] || right[0] - left[0],
      )[0] || [];
    const score = width > 1 ? frequency * 100 + width : 0;
    if (score > best.score) {
      best = { delimiter, score };
    }
  }
  return best.delimiter;
}

export function buildCsvPreview(source, rowLimit = CSV_PREVIEW_ROW_LIMIT) {
  const delimiter = detectCsvDelimiter(source);
  const parsed = parseDelimitedRows(source, delimiter, rowLimit + 1);
  const truncated = parsed.truncated || parsed.rows.length > rowLimit;
  const rows = parsed.rows.slice(0, rowLimit);
  const columnCount = rows.reduce(
    (maximum, row) => Math.max(maximum, row.length),
    0,
  );
  const normalizedRows = rows.map((row) => [
    ...row,
    ...Array(Math.max(0, columnCount - row.length)).fill(""),
  ]);
  return {
    delimiter,
    delimiterLabel:
      delimiter === "\t" ? "tab" : delimiter === ";" ? "semicolon" : "comma",
    header: normalizedRows[0] || [],
    rows: normalizedRows.slice(1),
    columnCount,
    truncated,
  };
}

export function isNumericCsvValue(value) {
  const normalized = String(value || "")
    .trim()
    .replace(",", ".");
  return normalized !== "" && Number.isFinite(Number(normalized));
}
