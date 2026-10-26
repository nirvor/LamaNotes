const databaseName = "lamanotes-quicknotes-v1";

export function createQuicknotesStore(factory = globalThis.indexedDB) {
  let connection;
  function open() {
    if (!factory) return Promise.reject(new Error("Local storage unavailable"));
    if (!connection) {
      connection = new Promise((resolve, reject) => {
        const request = factory.open(databaseName, 1);
        request.onupgradeneeded = () => {
          request.result.createObjectStore("entries", { keyPath: "entryId" });
          request.result.createObjectStore("state", { keyPath: "key" });
        };
        request.onerror = () => {
          connection = null;
          reject(request.error);
        };
        request.onblocked = () => {
          connection = null;
          reject(new Error("Local storage busy"));
        };
        request.onsuccess = () => {
          const db = request.result;
          db.onversionchange = () => {
            db.close();
            connection = null;
          };
          resolve(db);
        };
      });
    }
    return connection;
  }
  async function transaction(names, mode, run) {
    const db = await open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(names, mode);
      let result;
      tx.oncomplete = () => resolve(result);
      tx.onabort = () => reject(tx.error || new Error("Local save failed"));
      tx.onerror = () => {};
      try {
        run(tx, (value) => {
          result = value;
        });
      } catch (error) {
        tx.abort();
        reject(error);
      }
    });
  }
  return {
    get: (key) =>
      transaction(["state"], "readonly", (tx, done) => {
        const request = tx.objectStore("state").get(key);
        request.onsuccess = () => done(request.result?.value ?? null);
      }),
    set: (key, value) =>
      transaction(["state"], "readwrite", (tx) => {
        const store = tx.objectStore("state");
        if (value == null) store.delete(key);
        else store.put({ key, value });
      }),
    list: () =>
      transaction(["entries"], "readonly", (tx, done) => {
        const request = tx.objectStore("entries").getAll();
        request.onsuccess = () =>
          done(request.result.sort((a, b) => a.queuedAt - b.queuedAt));
      }),
    enqueue: (entry, draft) =>
      transaction(["entries", "state"], "readwrite", (tx) => {
        tx.objectStore("entries").add(entry);
        const state = tx.objectStore("state");
        const request = state.get("draft");
        request.onsuccess = () => {
          if (request.result?.value === draft) state.delete("draft");
        };
      }),
    remove: (entryId) =>
      transaction(["entries"], "readwrite", (tx) =>
        tx.objectStore("entries").delete(entryId),
      ),
  };
}

export { databaseName as quicknotesDatabaseName };
