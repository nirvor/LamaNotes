export function createQuicknotesCapture({
  store,
  getTarget,
  sendEntry,
  onChange = () => {},
  onSaved = () => {},
  online = () => globalThis.navigator?.onLine !== false,
  now = () => new Date(),
  uuid = () => crypto.randomUUID(),
}) {
  let target = null;
  let running = null;
  let flushAgain = false;
  let draftWrite = Promise.resolve();
  let revision = 0;
  const state = {
    draft: "",
    pendingCount: 0,
    busy: false,
    status: "",
    message: "",
  };
  const emit = () => onChange({ ...state });
  function failure(error) {
    const status = error?.response?.status;
    state.status =
      status === 401 || status === 403 || status === 409
        ? "blocked"
        : "pending";
    state.message =
      status === 401 || status === 403
        ? "Saved on this device. Sign in to send."
        : status === 409 || status === 404
          ? "Saved on this device. Open Quicknotes to reconnect."
          : status && status !== 408 && status !== 429 && status < 500
            ? "Saved on this device. Could not send this entry."
            : "Saved on this device. Waiting for connection.";
    emit();
  }
  async function refreshCount() {
    state.pendingCount = (await store.list()).length;
  }
  async function initialize() {
    try {
      const initialRevision = revision;
      const [savedDraft, savedTarget] = await Promise.all([
        store.get("draft"),
        store.get("target"),
      ]);
      target = savedTarget;
      if (initialRevision === revision && typeof savedDraft === "string")
        state.draft = savedDraft;
      await refreshCount();
      if (state.pendingCount) {
        state.status = "pending";
        state.message = "Saved on this device. Waiting for connection.";
      }
      emit();
      void flush();
    } catch {
      state.status = "error";
      state.message = "Local saving is unavailable. Keep this page open.";
      emit();
    }
  }
  function editDraft(text) {
    state.draft = String(text);
    revision += 1;
    const value = state.draft;
    draftWrite = draftWrite
      .catch(() => {})
      .then(() => store.set("draft", value));
    draftWrite.catch(() => {
      state.status = "error";
      state.message = "Could not save on this device. Keep your text here.";
      emit();
    });
    if (!state.pendingCount) {
      state.status = "";
      state.message = "";
    }
    emit();
  }
  async function submit(text = state.draft) {
    if (state.busy || !String(text).trim()) return false;
    state.busy = true;
    emit();
    try {
      if (text.length > 10000) throw new Error("Too much text");
      await draftWrite;
      if (!target && online()) {
        target = await getTarget();
        await store.set("target", target);
      }
      if (!target?.noteId) {
        state.status = "error";
        state.message =
          "Connect once to link these Quicknotes. Your text stays here.";
        return false;
      }
      const entry = {
        entryId: uuid(),
        noteId: target.noteId,
        text,
        capturedAt: now().toISOString(),
        queuedAt: now().getTime(),
      };
      await store.enqueue(entry, text);
      if (state.draft === text) {
        state.draft = "";
        revision += 1;
      }
      state.status = "pending";
      state.message = "Saved on this device. Waiting for connection.";
      await refreshCount();
      void flush();
      return true;
    } catch {
      state.status = "error";
      state.message = "Could not save this entry. Your text is still here.";
      return false;
    } finally {
      state.busy = false;
      emit();
    }
  }
  function flush() {
    if (running) {
      flushAgain = true;
      return running;
    }
    if (!online()) return Promise.resolve();
    const sendPending = async () => {
      try {
        const current = await getTarget();
        if (!current?.noteId) throw { response: { status: 409 } };
        target = current;
        await store.set("target", current);
        const entries = await store.list();
        for (const entry of entries) {
          if (!online()) break;
          if (entry.noteId !== current.noteId)
            throw { response: { status: 409 } };
          const result = await sendEntry({
            entryId: entry.entryId,
            noteId: entry.noteId,
            text: entry.text,
            capturedAt: entry.capturedAt,
          });
          if (
            result.entryId !== entry.entryId ||
            result.noteId !== entry.noteId
          )
            throw new Error("Unexpected save receipt");
          await store.remove(entry.entryId);
          onSaved(result);
        }
        await refreshCount();
        if (entries.length && !state.pendingCount) {
          state.status = "saved";
          state.message = "Saved to Quicknotes";
        } else if (state.pendingCount) {
          state.status = "pending";
          state.message = "Saved on this device. Waiting for connection.";
        }
        emit();
      } catch (error) {
        await refreshCount().catch(() => {});
        if (state.pendingCount) failure(error);
      }
    };
    running = (async () => {
      do {
        flushAgain = false;
        await sendPending();
      } while (flushAgain && online());
    })().finally(() => {
      running = null;
    });
    return running;
  }
  return {
    initialize,
    editDraft,
    submit,
    flush,
    getState: () => ({ ...state }),
  };
}
