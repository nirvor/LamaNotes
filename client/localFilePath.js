function normalizedPath(value = "") {
  return String(value)
    .trim()
    .replace(/\\/g, "/")
    .replace(/\/{2,}/g, "/");
}

export function localFileDirectory(filePath = "") {
  const normalized = normalizedPath(filePath).replace(/\/$/, "");
  const separator = normalized.lastIndexOf("/");
  return separator > 1 ? normalized.slice(0, separator) : "";
}

export function abbreviatedLocalDirectory(filePath = "") {
  const directory = localFileDirectory(filePath);
  if (!directory) {
    return "";
  }

  const segments = directory.split("/").filter(Boolean);
  const desktopIndex = segments.findIndex(
    (segment) => segment.toLowerCase() === "desktop",
  );
  const preferredStart =
    desktopIndex >= 0 ? desktopIndex : Math.max(0, segments.length - 3);
  const visible = segments.slice(preferredStart);

  if (visible.length > 4) {
    return `.../${visible.slice(0, 3).join("/")}/.../${visible.at(-1)}/`;
  }

  return `.../${visible.join("/")}/`;
}

export function localFilePathContext(filePath = "") {
  const fullPath = String(filePath).trim();
  const label = abbreviatedLocalDirectory(fullPath);
  if (!label) {
    return null;
  }

  return { label, fullPath };
}
