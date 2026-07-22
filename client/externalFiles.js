import { shallowRef } from "vue";

export const externalFileLaunch = shallowRef(null);

export function publishExternalFileLaunch(
  files,
  message = "Opened from Windows.",
  options = {},
) {
  externalFileLaunch.value = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    files,
    message,
    tone: "info",
    ...options,
  };
}

export function publishExternalFileLaunchError(message) {
  externalFileLaunch.value = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    files: [],
    message,
    tone: "error",
  };
}

export function supportsFileHandlingLaunchQueue() {
  return Boolean(
    "launchQueue" in window &&
      "LaunchParams" in window &&
      "files" in window.LaunchParams.prototype,
  );
}

export function supportsNativeFileBridge() {
  return Boolean(window.pywebview?.api);
}

export async function filesFromLaunchParams(launchParams) {
  const handles = launchParams.files || [];
  const files = [];
  for (const handle of handles) {
    files.push({
      file: await handle.getFile(),
      handle,
    });
  }
  return files;
}

export function filesFromNativePayloads(payloads = []) {
  return payloads
    .filter((payload) => payload && typeof payload.content === "string")
    .map((payload) => {
      const handle = payload.writable ? nativeWritableHandle(payload) : null;
      return {
        file: nativePayloadFile(payload),
        handle,
        nativePayload: payload,
      };
    });
}

export function fileFromNativePayload(payload) {
  return filesFromNativePayloads([payload])[0] || null;
}

function nativePayloadFile(payload) {
  return new File([payload.content || ""], payload.name || "external.txt", {
    type: payload.type || "text/plain",
    lastModified: payload.lastModified || Date.now(),
  });
}

function nativeWritableHandle(payload) {
  const state = { ...payload };

  function applyPayload(nextPayload = {}) {
    Object.assign(state, nextPayload);
    Object.assign(payload, nextPayload);
  }

  async function getFile() {
    return nativePayloadFile(state);
  }

  async function saveContent(content, { force = false } = {}) {
    const savedPayload = await window.pywebview.api.save_native_file(
      state.id,
      String(content ?? ""),
      state.version || "",
      Boolean(force),
    );
    if (savedPayload?.conflict) {
      const error = new Error("The file changed outside LamaNotes.");
      error.code = "external-conflict";
      error.external = savedPayload.external;
      throw error;
    }
    if (savedPayload?.deleted) {
      const error = new Error("The original file no longer exists.");
      error.code = "external-deleted";
      throw error;
    }
    if (!savedPayload?.ok) {
      throw new Error("The native file could not be saved.");
    }
    applyPayload({ ...savedPayload, content: String(content ?? "") });
    return getFile();
  }

  return {
    id: state.id,
    kind: "native",
    path: state.path,
    get name() {
      return state.name;
    },
    get metadata() {
      return { ...state };
    },
    applyPayload,
    saveContent,
    getFile,
    queryPermission: async () => "granted",
    requestPermission: async () => "granted",
    createWritable: async () => {
      const chunks = [];
      return {
        write: async (content) => {
          if (content instanceof Blob) {
            chunks.push(await content.text());
            return;
          }
          chunks.push(String(content ?? ""));
        },
        close: async () => {
          const nextContent = chunks.join("");
          await saveContent(nextContent);
        },
      };
    },
  };
}
