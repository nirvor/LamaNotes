export function isEditableShortcutTarget(target) {
  const tagName = String(target?.tagName || "").toLowerCase();
  if (["input", "textarea", "select"].includes(tagName)) {
    return true;
  }
  return Boolean(
    target?.isContentEditable ||
      target?.closest?.('[contenteditable="true"], [role="textbox"]'),
  );
}

export function isPlainKey(event, key) {
  return (
    String(event?.key || "").toLowerCase() === String(key).toLowerCase() &&
    !event.ctrlKey &&
    !event.altKey &&
    !event.metaKey &&
    !event.shiftKey
  );
}
