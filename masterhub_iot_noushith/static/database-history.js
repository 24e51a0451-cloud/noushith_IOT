(() => {
  const list = document.getElementById('databaseHistory');
  if (!list) return;
  const status = document.getElementById('databaseStorageStatus');
  const older = document.getElementById('databaseOlder');
  const device = document.getElementById('databaseDevice');
  const kind = document.getElementById('databaseKind');
  let cursor = null, busy = false, browsing = false;
  async function load(append = false) {
    if (busy) return;
    busy = true;
    const params = new URLSearchParams({limit: '50'});
    if (device.value.trim()) params.set('device_id', device.value.trim());
    if (kind.value) params.set('kind', kind.value);
    if (append && cursor) params.set('before', cursor);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch('/api/database/activity?' + params, {signal: controller.signal, cache: 'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'History unavailable');
      if (!append) { list.replaceChildren(); browsing = false; }
      else browsing = true;
      for (const event of data.events) {
        const row = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = `${new Date(event.received_at).toLocaleString()} · ${event.device_id || 'Masterhub'} · ${event.kind} · ${event.status || 'RECEIVED'}`;
        const details = document.createElement('pre');
        details.textContent = JSON.stringify({command_id: event.command_id, topic: event.topic, data: event.payload}, null, 2);
        row.append(summary, details); list.append(row);
      }
      if (!list.childElementCount) list.textContent = 'No saved events yet. New activity will appear here.';
      cursor = data.next_before;
      older.hidden = !cursor;
      status.textContent = data.storage.last_error || data.storage.failed_records || data.storage.quarantined
        ? `Storage needs attention · ${data.storage.pending} queued · ${data.storage.failed_records} could not be queued · ${data.storage.quarantined} need review`
        : data.storage.pending ? `${data.storage.pending} events waiting to save` : 'PostgreSQL connected';
    } catch (_) {
      status.textContent = 'Saved history unavailable. Displayed history may be out of date.';
    } finally { clearTimeout(timeout); busy = false; }
  }
  document.getElementById('databaseRefresh').addEventListener('click', () => load());
  older.addEventListener('click', () => load(true));
  kind.addEventListener('change', () => load());
  device.addEventListener('change', () => load());
  setInterval(() => { if (!document.hidden && !browsing && !list.querySelector('details[open]')) load(); }, 5000);
  load();
})();
