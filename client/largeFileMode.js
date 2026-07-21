export const LARGE_FILE_BYTE_THRESHOLD = 1024 * 1024;
export const LARGE_FILE_LINE_THRESHOLD = 20000;
export const LARGE_FILE_PREVIEW_CHARACTER_LIMIT = 256 * 1024;
export const LARGE_FILE_PREVIEW_LINE_LIMIT = 4000;

export function shouldUseLargeFileMode(source, byteSize = 0) {
  if (Number(byteSize) >= LARGE_FILE_BYTE_THRESHOLD) {
    return true;
  }

  const text = String(source || "");
  let lines = text ? 1 : 0;
  for (let index = 0; index < text.length; index += 1) {
    if (text[index] === "\n") {
      lines += 1;
      if (lines > LARGE_FILE_LINE_THRESHOLD) {
        return true;
      }
    }
  }
  return false;
}

export function buildLargeFilePreview(source) {
  const text = String(source || "");
  let end = Math.min(text.length, LARGE_FILE_PREVIEW_CHARACTER_LIMIT);
  let lines = text ? 1 : 0;

  for (let index = 0; index < end; index += 1) {
    if (text[index] === "\n") {
      lines += 1;
      if (lines > LARGE_FILE_PREVIEW_LINE_LIMIT) {
        end = index;
        break;
      }
    }
  }

  return {
    content: text.slice(0, end),
    truncated: end < text.length,
  };
}
