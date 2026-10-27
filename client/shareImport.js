const storageKey = "lamanotes:share-import:v1";
const ticketPattern = /^lst_[A-Za-z0-9_-]{43}$/;
const lifetimeMs = 10 * 60 * 1000;

export function retainShareTicket(fragment, host = window, now = Date.now()) {
  if (!fragment) return;
  // Keep the ticket out of login redirects, history entries and copied URLs.
  host.history.replaceState(
    host.history.state,
    "",
    host.location.pathname + host.location.search,
  );
  try {
    host.sessionStorage.removeItem(storageKey);
  } catch {
    return;
  }
  const params = new URLSearchParams(fragment.replace(/^#/, ""));
  const ticket = params.get("ticket");
  if ([...params.keys()].length !== 1 || !ticketPattern.test(ticket || ""))
    return;
  try {
    host.sessionStorage.setItem(
      storageKey,
      JSON.stringify({ ticket, expiresAt: now + lifetimeMs }),
    );
  } catch {}
}

export function pendingShareTicket(storage = sessionStorage, now = Date.now()) {
  try {
    const pending = JSON.parse(storage.getItem(storageKey));
    if (
      pending &&
      ticketPattern.test(pending.ticket) &&
      pending.expiresAt > now &&
      pending.expiresAt <= now + lifetimeMs
    ) {
      return pending.ticket;
    }
  } catch {}
  try {
    storage.removeItem(storageKey);
  } catch {}
  return null;
}

export function clearShareTicket(storage = sessionStorage) {
  try {
    storage.removeItem(storageKey);
  } catch {}
}

export async function importSharedItem(
  ticket,
  { token, fetcher = fetch } = {},
) {
  let response;
  try {
    response = await fetcher("/api/private/v1/share-import", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "X-LamaNotes-Share": "1",
        ...(token ? { Authorization: "Bearer " + token } : {}),
      },
      body: JSON.stringify({ ticket }),
    });
  } catch {
    throw new Error(
      "Could not connect to LamaNotes. Your original remains in LamaShare. Please try again.",
    );
  }
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      typeof result.detail === "string"
        ? result.detail
        : "The import could not finish. Your original remains in LamaShare.",
    );
    error.status = response.status;
    throw error;
  }
  if (!/^ln-[a-f0-9]{32}$/.test(result.noteId || ""))
    throw new Error(
      "LamaNotes did not confirm the saved note. Please try again.",
    );
  return result;
}
