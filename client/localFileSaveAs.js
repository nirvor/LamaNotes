import { fileFromNativePayload } from "./externalFiles.js";
import { createLocalFileStorageAdapter } from "./documents/storageAdapters.js";

export async function saveLocalFileAs(
  file,
  content,
  {
    nativeApi = globalThis.window?.pywebview?.api,
    pickFile = globalThis.window?.showSaveFilePicker?.bind(globalThis.window),
  } = {},
) {
  if (file.nativeFileId && nativeApi) {
    if (!nativeApi.save_native_file_as)
      throw new Error("Update LamaNotes to use Save as.");
    const payload = await nativeApi.save_native_file_as(
      file.nativeFileId,
      content,
      file.version || "",
    );
    if (payload?.cancelled) return null;
    if (payload?.conflict || payload?.deleted) {
      const error = new Error("The original file changed outside LamaNotes.");
      error.code = payload.conflict ? "external-conflict" : "external-deleted";
      error.external = payload.external;
      throw error;
    }
    if (!payload?.ok)
      throw new Error(payload?.error || "The file could not be saved.");
    const selected = fileFromNativePayload(payload);
    if (!selected) throw new Error("The saved file could not be reopened.");
    return selected;
  }
  if (!pickFile)
    throw new Error(
      "Save as needs the Windows app or a browser with local file access.",
    );
  try {
    const handle = await pickFile({ suggestedName: file.name });
    const saved = await createLocalFileStorageAdapter().save({
      handle,
      content,
    });
    return { file: saved, handle };
  } catch (error) {
    if (error?.name === "AbortError") return null;
    throw error;
  }
}
