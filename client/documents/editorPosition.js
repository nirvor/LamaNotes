export function findEditAnchor(source, text) {
  const value = String(text || "").trim();
  if (!value) return null;
  const candidates = [
    value,
    ...value.split(/[\n\r]+/).map((line) => line.trim()),
  ]
    .filter((part) => part.length >= 3)
    .sort((a, b) => b.length - a.length);
  for (const candidate of candidates) {
    const position = source.indexOf(candidate);
    if (position >= 0 && position === source.lastIndexOf(candidate))
      return position;
  }
  return null;
}
