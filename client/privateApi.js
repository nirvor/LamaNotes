import { getStoredToken } from "./tokenStorage.js";

export async function privateRequest(path, { method = "GET", body, key } = {}) {
  const headers = {};
  const token = getStoredToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (key) headers["Idempotency-Key"] = key;
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  const response = await fetch(`/api/private/v1${path}`, {
    method,
    body,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    const detail = result.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : detail?.message ||
          "Could not complete this action. Please reload and try again.",
    );
  }
  return response.status === 204 ? null : response.json();
}
