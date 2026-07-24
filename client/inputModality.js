export function shouldAutoFocusSearch(host = globalThis) {
  return !Boolean(
    host?.matchMedia?.("(pointer: coarse), (hover: none)")?.matches,
  );
}
