export function scheduleIdleWork(
  callback,
  { delay = 0, timeout = 1500, host = globalThis } = {},
) {
  let cancelled = false;
  let idleHandle = null;

  const run = () => {
    if (!cancelled) {
      callback();
    }
  };
  const beginIdleWait = () => {
    if (cancelled) {
      return;
    }
    if (typeof host.requestIdleCallback === "function") {
      idleHandle = host.requestIdleCallback(run, { timeout });
    } else {
      run();
    }
  };
  const timerHandle = host.setTimeout(beginIdleWait, Math.max(0, delay));

  return () => {
    cancelled = true;
    host.clearTimeout(timerHandle);
    if (idleHandle != null && typeof host.cancelIdleCallback === "function") {
      host.cancelIdleCallback(idleHandle);
    }
  };
}

export function createDebouncedWork(callback, delay = 200, host = globalThis) {
  let timerHandle = null;
  let latestArgs = [];

  function run() {
    if (timerHandle == null) {
      return false;
    }
    host.clearTimeout(timerHandle);
    timerHandle = null;
    callback(...latestArgs);
    latestArgs = [];
    return true;
  }

  return {
    schedule(...args) {
      latestArgs = args;
      if (timerHandle != null) {
        host.clearTimeout(timerHandle);
      }
      timerHandle = host.setTimeout(run, Math.max(0, delay));
    },
    flush: run,
    cancel() {
      if (timerHandle != null) {
        host.clearTimeout(timerHandle);
      }
      timerHandle = null;
      latestArgs = [];
    },
    pending() {
      return timerHandle != null;
    },
  };
}
