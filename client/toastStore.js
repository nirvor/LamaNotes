import { reactive } from "vue";

const messages = reactive([]);
const timers = new Map();
let nextToastId = 1;

function remove(id) {
  const index = messages.findIndex((message) => message.id === id);
  if (index >= 0) {
    messages.splice(index, 1);
  }
  window.clearTimeout(timers.get(id));
  timers.delete(id);
}

function add(message = {}) {
  const id = nextToastId++;
  const requestedLife = Number(message.life);
  const normalized = {
    id,
    summary: String(message.summary || ""),
    detail: String(message.detail || ""),
    severity: String(message.severity || "info"),
    closable: Boolean(message.closable),
    life: Number.isFinite(requestedLife) ? requestedLife : 5000,
  };
  messages.push(normalized);

  if (normalized.life > 0) {
    timers.set(
      id,
      window.setTimeout(() => remove(id), normalized.life),
    );
  }
  return id;
}

function clear() {
  for (const message of [...messages]) {
    remove(message.id);
  }
}

const toast = Object.freeze({ add, clear, remove, messages });

export function useToast() {
  return toast;
}
