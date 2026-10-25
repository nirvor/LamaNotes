export function createFocusQuicknotesRefresher(post, now = Date.now) {
  let pending = null;
  let attemptedAt = -Infinity;
  return function refreshFocusQuicknotesIntegration() {
    if (pending) return pending;
    if (now() - attemptedAt < 5 * 60 * 1000) return Promise.resolve(null);
    attemptedAt = now();
    pending = Promise.resolve()
      .then(post)
      .catch(() => null)
      .finally(() => { pending = null; });
    return pending;
  };
}
