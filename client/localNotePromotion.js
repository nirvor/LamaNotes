import {
  buildWorkNoteHtml,
  normalizeWorkMarkdownTags,
  setWorkMarkdownTag,
} from "./components/work/workNote.js";

const primaryTags = new Set(["private", "work", "infra"]);

function getExtension(file = {}) {
  const explicit = String(file.extension || "").replace(/^\./, "");
  if (explicit) {
    return explicit.toLowerCase();
  }
  const match = String(file.name || "").match(/\.([^.]+)$/);
  return match ? match[1].toLowerCase() : "txt";
}

function maxBacktickRun(content = "") {
  return Math.max(
    0,
    ...[...String(content).matchAll(/`+/g)].map((match) => match[0].length),
  );
}

function sourceMarkdown(file = {}) {
  const extension = getExtension(file);
  const content = String(file.draftContent ?? file.content ?? "").replace(
    /\r\n?/g,
    "\n",
  );
  if (extension === "md") {
    return content;
  }

  const languageAliases = {
    cfg: "ini",
    log: "text",
    yml: "yaml",
  };
  const language = languageAliases[extension] || extension || "text";
  const fence = "`".repeat(Math.max(3, maxBacktickRun(content) + 1));
  return `${fence}${language}\n${content}\n${fence}\n`;
}

export function localFileNoteTitle(filename = "") {
  const withoutExtension = String(filename).replace(
    /\.(?:md|txt|cfg|ini|json|ya?ml|toml|xml|log)$/i,
    "",
  );
  return (
    withoutExtension
      .replace(/[<>:"/\\|?*\u0000-\u001f]/g, " ")
      .replace(/\s+/g, " ")
      .trim() || "Local Note"
  );
}

export function buildLocalLibraryNote(file = {}) {
  const title = localFileNoteTitle(file.name);
  let markdown = sourceMarkdown(file);
  const tags = normalizeWorkMarkdownTags(markdown).tags;
  if (!tags.some((tag) => primaryTags.has(tag))) {
    markdown = setWorkMarkdownTag(markdown, "work", true);
  }

  return {
    title,
    content: buildWorkNoteHtml(title, markdown),
    format: "html",
  };
}
