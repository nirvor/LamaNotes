const uuid = "[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}";
export const sharedAnchorPattern = new RegExp(
  `^<span id="quicknote-(${uuid})" data-lamanotes-share-anchor></span>\\r?\\n?`,
  "gm",
);

export function sharedEntryRequest(query = {}) {
  if (
    typeof query.entry !== "string" ||
    !new RegExp(`^${uuid}$`).test(query.entry)
  )
    return null;
  return { id: query.entry, edit: query.edit === "1" };
}

export function sharedEntryAnchor(id) {
  return new RegExp(`^${uuid}$`).test(id)
    ? `<span id="quicknote-${id}" data-lamanotes-share-anchor></span>`
    : "";
}

export function sharedAnchorRanges(markdown) {
  const ranges = [];
  let fence = null;
  let offset = 0;
  for (const line of markdown.split("\n")) {
    const delimiter = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (delimiter) {
      if (!fence) fence = delimiter[1];
      else if (
        fence[0] === delimiter[1][0] &&
        delimiter[1].length >= fence.length &&
        line.slice(delimiter[0].length).trim() === ""
      )
        fence = null;
    } else if (!fence) {
      const match = [...line.matchAll(new RegExp(sharedAnchorPattern))][0];
      if (match && match[0].length === line.length)
        ranges.push({
          id: match[1],
          from: offset,
          to:
            offset +
            line.length +
            (offset + line.length < markdown.length ? 1 : 0),
        });
    }
    offset += line.length + 1;
  }
  return ranges;
}

export function sharedEntryPosition(html, markdown, id) {
  const documentValue = new DOMParser().parseFromString(
    html || "",
    "text/html",
  );
  const markers = [
    ...documentValue.head.querySelectorAll(
      "meta[name='lamanotes-share-quicknote']",
    ),
  ].filter((node) => node.content.startsWith(id + ":"));
  const anchor = sharedEntryAnchor(id);
  if (!anchor || markers.length !== 1) return null;
  const ranges = sharedAnchorRanges(markdown).filter(
    (range) => range.id === id,
  );
  if (ranges.length !== 1) return null;
  const from = ranges[0].from;
  let caret = from + anchor.length;
  const rest = markdown.slice(caret).match(/^\s*---\s*\n+/);
  caret += rest
    ? rest[0].length
    : markdown.slice(caret).match(/^\s*/)[0].length;
  return { anchorId: `quicknote-${id}`, caret };
}

export function stableNoteDestination(title, route) {
  return {
    name: "note",
    params: { title },
    query: { ...route.query },
    hash: route.hash,
  };
}
