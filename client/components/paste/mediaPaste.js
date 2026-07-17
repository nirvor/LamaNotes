const urlPattern = /^https?:\/\/[^\s<>"']+$/i;
const imageUrlPattern = /\.(?:avif|gif|jpe?g|png|svg|webp)(?:[?#].*)?$/i;

function normalizeText(value = "") {
  return String(value).replace(/\r\n?/g, "\n");
}

function safeUrl(value = "") {
  const trimmed = String(value || "").trim();
  if (!urlPattern.test(trimmed)) {
    return "";
  }

  try {
    const parsed = new URL(trimmed);
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? parsed.href
      : "";
  } catch {
    return "";
  }
}

function urlLabel(url) {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^www\./, "");
    if (/maps\.google|google\.[^/]+\/maps|openstreetmap|organicmaps/i.test(url)) {
      return "Map link";
    }

    return host || "Link";
  } catch {
    return "Link";
  }
}

function markdownLabel(value = "Link") {
  return String(value || "Link")
    .replace(/\s+/g, " ")
    .replace(/[[\]\\]/g, "\\$&")
    .trim();
}

function codeScore(text) {
  const normalized = normalizeText(text).trim();
  if (!normalized || normalized.length < 18) {
    return 0;
  }

  const lines = normalized.split("\n");
  if (lines.length < 2) {
    return 0;
  }

  let score = 0;
  if (/^\s*(?:\{[\s\S]*\}|\[[\s\S]*\])\s*$/.test(normalized)) score += 2;
  if (/<\/?[a-z][\s\S]*>/i.test(normalized)) score += 2;
  if (/(?:^|\n)\s*(?:import|export|class|function|const|let|var|def|return|from|SELECT|WITH|CREATE|UPDATE|async|await)\b/i.test(normalized)) score += 2;
  if (/[{}()[\];]|=>|==|!=|<=|>=|:=|\bNone\b|\btrue\b|\bfalse\b/.test(normalized)) score += 1;
  if (lines.some((line) => /^\s{2,}\S/.test(line) || /^\t+\S/.test(line))) score += 1;
  if (lines.some((line) => /^\s*(?:\$|PS>|>|curl |git |npm |python |docker |tailscale )\b/i.test(line))) score += 2;
  if (lines.some((line) => /^\s*(?:Traceback|Error:|WARN|INFO|DEBUG)\b/.test(line))) score += 1;
  if (lines.filter((line) => /^\s*[-*]\s+\S/.test(line)).length > lines.length / 2) score -= 2;

  return score;
}

function guessLanguage(text = "") {
  const normalized = normalizeText(text).trim();
  if (!normalized) {
    return "text";
  }

  try {
    JSON.parse(normalized);
    return "json";
  } catch {
    // Keep using lightweight heuristics below.
  }

  if (/^<\/?[a-z][\s\S]*>/i.test(normalized)) return "html";
  if (/\b(?:import|export|const|let|=>|interface|type)\b/.test(normalized)) return "javascript";
  if (/\b(?:def|import|from|None|elif|self)\b/.test(normalized)) return "python";
  if (/\b(?:SELECT|FROM|WHERE|JOIN|WITH|INSERT|UPDATE)\b/i.test(normalized)) return "sql";
  if (/\b(?:docker|tailscale|git|npm|curl|python|pwsh|powershell)\b/i.test(normalized)) return "shell";
  if (/(?:^|\n)\s*[.#]?[a-z0-9_-]+\s*\{[^}]*:/i.test(normalized)) return "css";
  if (/(?:^|\n)\s*[a-z0-9_-]+:\s+.+/i.test(normalized)) return "yaml";
  return "text";
}

export function getClipboardImageFile(clipboardData) {
  const files = [...(clipboardData?.files || [])];
  const file = files.find((item) => item.type?.startsWith("image/"));
  if (file) {
    return file;
  }

  const items = [...(clipboardData?.items || [])];
  const imageItem = items.find((item) => item.type?.startsWith("image/"));
  return imageItem?.getAsFile?.() || null;
}

export function classifyPastedText(value = "") {
  const text = normalizeText(value);
  const trimmed = text.trim();
  const url = safeUrl(trimmed);

  if (url) {
    return {
      type: imageUrlPattern.test(url) ? "image-url" : "url",
      url,
      label: urlLabel(url),
    };
  }

  if (codeScore(text) >= 2) {
    return {
      type: "code",
      text,
      language: guessLanguage(text),
    };
  }

  return { type: "text", text };
}

export function markdownForPaste(classification, selection = "") {
  if (!classification || classification.type === "text") {
    return "";
  }

  if (classification.type === "image-url") {
    return `\n![Image](${classification.url})\n`;
  }

  if (classification.type === "url") {
    const label = markdownLabel(
      selection.trim() || classification.label || classification.url,
    );
    return `\n[${label}](${classification.url})\n`;
  }

  if (classification.type === "code") {
    return `\n\`\`\`${classification.language || "text"}\n${normalizeText(classification.text).trimEnd()}\n\`\`\`\n`;
  }

  return "";
}

export function markdownImageSnippet(url, altText = "Image") {
  return `\n![${markdownLabel(altText || "Image")}](${url})\n`;
}
