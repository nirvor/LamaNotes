export function createSaveCheckpoint(readSnapshot) {
  const before = readSnapshot?.();
  return () => !readSnapshot || readSnapshot() === before;
}

export function acceptFileSave(file, savedContent) {
  file.content = savedContent;
  file.dirty = file.draftContent !== savedContent;
  return !file.dirty;
}
