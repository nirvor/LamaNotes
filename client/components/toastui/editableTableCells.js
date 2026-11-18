export function editableTableCell(node, { entering, origin }) {
  const token = origin();
  if (entering && token?.type === "openTag" && node.sourcepos) {
    const [[line, first], [endLine, last]] = node.sourcepos;
    if (line === endLine && first > 0 && last >= first - 1) {
      token.attributes = {
        ...token.attributes,
        "data-ln-cell": [line, first, last].join(":"),
        tabindex: "0",
        title: "Edit table cell",
      };
    }
  }
  return token;
}

export function cellRange(source, location) {
  const [line, first, last] = location.split(":").map(Number);
  if (
    ![line, first, last].every(Number.isInteger) ||
    first < 1 ||
    line < 1 ||
    last < first - 1
  )
    return null;
  const newlines = /\r\n|\r|\n/g;
  let offset = 0;
  for (let row = 1; row < line; row++) {
    if (!newlines.exec(source)) return null;
    offset = newlines.lastIndex;
  }
  const lineEnd = newlines.exec(source)?.index ?? source.length;
  if (offset + last > lineEnd) return null;
  let from = offset + first - 1;
  let to = offset + last;
  while (from < to && /[ \t]/.test(source[from])) from++;
  while (to > from && /[ \t]/.test(source[to - 1])) to--;
  return { from, to };
}

function encodeCell(value) {
  return value.replace(/(?<!\\)\|/g, "\\|");
}

export function startCellEdit(event, source, onInput, onFinish) {
  const cell = event.target.closest("td[data-ln-cell],th[data-ln-cell]");
  if (!cell || event.target.closest("input,button,a,textarea,select"))
    return false;
  const range = cellRange(source, cell.dataset.lnCell);
  if (!range) return false;
  event.preventDefault();
  event.stopPropagation();
  const before = source.slice(0, range.from);
  const original = source.slice(range.from, range.to);
  const after = source.slice(range.to);
  const input = document.createElement("input");
  input.className = "lamanotes-cell-input";
  input.setAttribute("aria-label", "Edit Markdown table cell");
  input.value = original;
  const rendered = [...cell.childNodes];
  cell.replaceChildren(input);
  cell.classList.add("lamanotes-cell-editing");
  let current = source;
  let finished = false;
  function publish(value) {
    const next = before + value + after;
    if (current !== next) {
      onInput({ before: current, after: next });
      current = next;
    }
  }
  function finish(cancel, focus) {
    if (finished) return;
    finished = true;
    publish(cancel ? original : encodeCell(input.value));
    cell.classList.remove("lamanotes-cell-editing");
    cell.replaceChildren(...rendered);
    if (focus) cell.focus();
    onFinish(cell.dataset.lnCell, focus, {
      before: source,
      after: current,
      edit: {
        ...range,
        insert: current.slice(before.length, current.length - after.length),
      },
    });
  }
  input.addEventListener("input", () => publish(encodeCell(input.value)));
  input.addEventListener("blur", () => finish(false, false));
  input.addEventListener("keydown", (key) => {
    if (key.isComposing || (key.key !== "Enter" && key.key !== "Escape"))
      return;
    key.preventDefault();
    key.stopPropagation();
    finish(key.key === "Escape", true);
  });
  input.focus();
  input.select();
  return true;
}
