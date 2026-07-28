export function createFileReplacementQueue({
  hasUnsavedChanges,
  requestDecision,
}) {
  let queue = Promise.resolve();

  function replace(action) {
    const replacement = queue.then(() => performReplacement(action));
    queue = replacement.catch(() => false);
    return replacement;
  }

  async function performReplacement(action) {
    if (!hasUnsavedChanges()) {
      const result = await action();
      return result !== false;
    }

    return new Promise((resolve, reject) => {
      requestDecision(
        async () => {
          try {
            const result = await action();
            resolve(result !== false);
          } catch (error) {
            reject(error);
          }
        },
        () => resolve(false),
      );
    });
  }

  return replace;
}
