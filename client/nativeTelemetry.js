export function reportNativeReady(metrics, host = window) {
  const send = () => {
    const reporter = host.pywebview?.api?.report_client_ready;
    if (!reporter) {
      return false;
    }
    Promise.resolve(reporter(metrics)).catch(() => {});
    return true;
  };

  if (send()) {
    return;
  }

  host.addEventListener("pywebviewready", send, { once: true });
}
