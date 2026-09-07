export function markdownTasks(source = "") {
  const lines = source.split("\n");
  const tasks = [];
  let offset = 0;
  let fence = null;
  lines.forEach((line, lineIndex) => {
    const delimiter = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (delimiter) {
      if (!fence) fence = delimiter[1];
      else if (
        delimiter[1][0] === fence[0] &&
        delimiter[1].length >= fence.length
      )
        fence = null;
    } else if (!fence) {
      const match = line.match(
        /^(\s*(?:>\s*)*(?:[-*+]|\d+[.)])\s+)\[([ xX])\](\s*)(.*)$/,
      );
      if (match)
        tasks.push({
          offset,
          lineIndex,
          prefix: match[1],
          marker: offset + match[1].length + 1,
          checked: match[2].toLowerCase() === "x",
          text: match[4],
        });
    }
    offset += line.length + 1;
  });
  return tasks;
}

export function toggleMarkdownTask(source, index, checked) {
  const task = markdownTasks(source)[index];
  return task
    ? source.slice(0, task.marker) +
        (checked ? "x" : " ") +
        source.slice(task.marker + 1)
    : null;
}

export function appendMarkdownTask(source, index, value) {
  const text = String(value || "")
    .trim()
    .replace(/[\r\n]+/g, " ");
  const task = markdownTasks(source)[index];
  if (!text || !task) return null;
  const lines = source.split("\n");
  let after = task.lineIndex + 1;
  const indent = task.prefix.match(/^\s*/)[0].length;
  while (
    after < lines.length &&
    lines[after].trim() &&
    lines[after].match(/^\s*/)[0].length > indent
  )
    after++;
  const prefix = task.prefix.replace(/\d+([.)])/, (_, end) => `1${end}`);
  lines.splice(after, 0, `${prefix}[ ] ${text}`);
  return lines.join("\n");
}
