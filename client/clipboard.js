function writeTextViaTextarea(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";
  document.body.append(textarea);
  textarea.select();

  try {
    if (!document.execCommand("copy")) {
      throw new Error("Copy command was not accepted by the browser.");
    }
  } finally {
    textarea.remove();
  }
}

export async function writePlainTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Some browser contexts expose the Clipboard API but reject writes.
      // The textarea path keeps the button useful instead of failing early.
    }
  }

  writeTextViaTextarea(text);
}

export async function writeMarkdownToClipboard(markdown) {
  if (navigator.clipboard?.write && window.ClipboardItem) {
    try {
      const plainText = new Blob([markdown], { type: "text/plain" });
      const markdownText = new Blob([markdown], { type: "text/markdown" });
      await navigator.clipboard.write([
        new ClipboardItem({
          "text/plain": plainText,
          "text/markdown": markdownText,
        }),
      ]);
      return;
    } catch {
      // Browser support for text/markdown is uneven. Plain text still preserves
      // the raw Markdown source, which is what editors and LLM prompts need.
    }
  }

  await writePlainTextToClipboard(markdown);
}

export async function writeHtmlToClipboard(html, plainText = "") {
  if (navigator.clipboard?.write && window.ClipboardItem) {
    try {
      const htmlBlob = new Blob([html], { type: "text/html" });
      const plainBlob = new Blob([plainText || html], { type: "text/plain" });
      await navigator.clipboard.write([
        new ClipboardItem({
          "text/html": htmlBlob,
          "text/plain": plainBlob,
        }),
      ]);
      return;
    } catch {
      // Rich HTML clipboard support is still uneven. Plain text keeps the copy
      // action useful in locked-down browser contexts.
    }
  }

  await writePlainTextToClipboard(plainText || html);
}
