export function createVpsNoteStorageAdapter({ create, update }) {
  return {
    async save({ isNew, sourceTitle, title, content, format = "html" }) {
      if (isNew) {
        return create(title, content, format);
      }

      return update(sourceTitle, title, content, format);
    },
  };
}

export function createLocalFileStorageAdapter() {
  return {
    async save({ handle, content, force = false }) {
      if (!handle) {
        throw new Error("This file does not have a writable handle.");
      }

      if (handle.saveContent) {
        return handle.saveContent(content, { force });
      }

      const permission = await ensureWritePermission(handle);
      if (!permission) {
        const error = new Error("Save permission denied.");
        error.code = "permission-denied";
        throw error;
      }

      const writable = await handle.createWritable();
      await writable.write(content);
      await writable.close();
      return handle.getFile();
    },
  };
}

async function ensureWritePermission(handle) {
  const options = { mode: "readwrite" };
  if (handle.queryPermission) {
    const permission = await handle.queryPermission(options);
    if (permission === "granted") {
      return true;
    }
  }

  if (handle.requestPermission) {
    return (await handle.requestPermission(options)) === "granted";
  }

  return true;
}
