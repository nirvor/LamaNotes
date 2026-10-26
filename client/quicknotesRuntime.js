import { ref } from "vue";
import { appendQuicknoteEntry, getQuicknotesTarget } from "./api.js";
import { createQuicknotesCapture } from "./quicknotesCapture.js";
import { createQuicknotesStore } from "./quicknotesStore.js";

export const quicknotesCaptureState = ref({
  draft: "",
  busy: false,
  pendingCount: 0,
  status: "",
  message: "",
});
export const quicknotesCapture = createQuicknotesCapture({
  store: createQuicknotesStore(),
  getTarget: getQuicknotesTarget,
  sendEntry: appendQuicknoteEntry,
  onChange: (value) => {
    quicknotesCaptureState.value = value;
  },
});
let started = false;
let timer;
function retry() {
  if (quicknotesCaptureState.value.pendingCount) void quicknotesCapture.flush();
}
function resume() {
  if (document.visibilityState === "visible") retry();
}

export function startQuicknotesCapture() {
  if (started) return;
  started = true;
  void quicknotesCapture.initialize();
  window.addEventListener("online", retry);
  window.addEventListener("focus", retry);
  document.addEventListener("visibilitychange", resume);
  timer = window.setInterval(() => {
    if (
      quicknotesCaptureState.value.pendingCount &&
      document.visibilityState === "visible"
    )
      retry();
  }, 30000);
}

export function stopQuicknotesCapture() {
  window.removeEventListener("online", retry);
  window.removeEventListener("focus", retry);
  document.removeEventListener("visibilitychange", resume);
  window.clearInterval(timer);
  started = false;
}
