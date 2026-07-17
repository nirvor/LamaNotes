export const publicationPendingStates = new Set([
  "preparing",
  "uploading-assets",
  "deploying",
  "verifying",
]);

export function isPublicationPending(state) {
  return publicationPendingStates.has(String(state || ""));
}

export function publicationToolbarMode(publication) {
  const state = publication?.state;
  if (!publication?.eligible || !state || state === "ineligible") {
    return null;
  }
  if (isPublicationPending(state)) {
    return "publishing";
  }
  if (state === "current" && publication.canonicalUrl) {
    return "show";
  }
  if (["stale", "failed-update"].includes(state) && publication.canonicalUrl) {
    return "update";
  }
  return "publish";
}

export function publicationPollDelay(attempt, retryAfterMs = 0) {
  const base = Number(attempt) < 5 ? 2000 : 5000;
  const requested = Number.isFinite(Number(retryAfterMs))
    ? Number(retryAfterMs)
    : 0;
  return Math.min(10000, Math.max(base, requested));
}

export function validatePublicationSlug(value) {
  const slug = String(value || "").trim();
  if (!slug) {
    return "Enter a public URL name.";
  }
  if (slug.length > 80) {
    return "Use no more than 80 characters.";
  }
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
    return "Use lowercase letters, numbers and single hyphens.";
  }
  if (["404", "api", "assets", "catalog", "guide", "pages"].includes(slug)) {
    return "This URL name is reserved.";
  }
  return "";
}

export function publicationProblemMessage(problem) {
  if (!problem) {
    return "Publishing could not be completed.";
  }
  const messages = {
    asset_mismatch: "A referenced media file is invalid.",
    asset_missing: "A referenced media file could not be found.",
    asset_too_large: "A referenced media file is too large.",
    consumer_unavailable: "Publishing is temporarily unavailable.",
    deploy_failed: "The public page could not be deployed.",
    invalid_slug: "The public URL name is invalid.",
    note_changed: "The note changed. Review it before publishing again.",
    publication_busy: "An update for this page is already running.",
    publication_too_large: "This note is too large to publish.",
    publisher_forbidden: "This NirvNotes server is not allowed to publish.",
    publisher_unauthorized: "Publishing authentication needs attention.",
    public_asset_verification_failed:
      "A public media file could not be verified.",
    runtime_component:
      "Replace interactive media with a static image or diagram.",
    slug_conflict: "This public URL name is already in use.",
    slug_locked: "This note already owns a fixed public URL.",
    unsafe_public_content:
      "The note contains private or unsafe public content.",
    verification_timeout: "Public verification is taking longer than expected.",
  };
  return messages[problem.code] || problem.detail || "Publishing failed.";
}
