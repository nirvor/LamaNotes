export function dataTransferTypes(dataTransfer) {
  return Array.from(dataTransfer?.types || [], (type) =>
    String(type).toLowerCase(),
  );
}

export function isFileTransfer(dataTransfer) {
  return dataTransferTypes(dataTransfer).includes("files");
}

export function isPlainTextTransfer(dataTransfer) {
  if (!dataTransfer || isFileTransfer(dataTransfer)) {
    return false;
  }
  const types = dataTransferTypes(dataTransfer);
  return types.includes("text/plain") || types.includes("text");
}

export function normalizeDroppedText(value) {
  return String(value ?? "").replace(/\r\n?/g, "\n");
}

export function readPlainTextTransfer(dataTransfer) {
  if (!isPlainTextTransfer(dataTransfer)) {
    return "";
  }
  return normalizeDroppedText(
    dataTransfer.getData?.("text/plain") || dataTransfer.getData?.("Text"),
  );
}
