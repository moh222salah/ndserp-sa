export function parseErrorMessage(e) {
  if (e._server_messages) {
    try {
      const messages = JSON.parse(e._server_messages);
      return messages.map((m) => JSON.parse(m).message).join("; ");
    } catch {}
  }
  return e.message || e.exc || String(e);
}