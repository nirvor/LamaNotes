export const PRODUCT_NAME = "LamaNotes";
export const PRODUCT_SLUG = "lamanotes";
export const LEGACY_PRODUCT_SLUG = "nirvnotes";

export function productEvent(name) {
  return `${PRODUCT_SLUG}:${name}`;
}

export function legacyProductEvent(name) {
  return `${LEGACY_PRODUCT_SLUG}:${name}`;
}

export function isDesktopHost() {
  return Boolean(
    window.__LAMANOTES_DESKTOP_SHELL__ || window.__NIRVNOTES_DESKTOP_SHELL__,
  );
}
