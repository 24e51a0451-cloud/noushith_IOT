(function () {
  'use strict';
  var seen = new Map();
  async function refreshMobile() {
    var panel = document.getElementById('mobileJiosaavnStatus');
    if (!panel) return;
    try {
      var response = await fetch('/api/jiosaavn/status');
      if (!response.ok) throw new Error('Status unavailable');
      var data = await response.json();
      panel.textContent = data.online ? (data.phone.control_enabled ? 'Phone online · Control enabled' : 'Phone online · Control disabled') : 'Phone offline';
      var media = data.media || {};
      document.getElementById('mobileJiosaavnTrack').textContent = data.online && media.session_available
        ? [media.title || 'Unknown track', media.artist, media.playing ? 'Playing' : 'Paused'].filter(Boolean).join(' · ')
        : 'Open JioSaavn on the phone and start playback to share now-playing information.';
      (data.commands || []).forEach(function (command) {
        if (seen.get(command.command_id) === command.status) return;
        seen.set(command.command_id, command.status);
        var detail = command.ack && command.ack.detail || (command.status === 'PENDING' ? 'Awaiting phone ACK' : command.status === 'TIMEOUT' ? 'No phone ACK; execution unknown' : command.status);
        document.getElementById('mobileJiosaavnAck').textContent = command.command + ': ' + command.status + ' — ' + detail;
        if (typeof renderActivityLogEntry === 'function') {
          renderActivityLogEntry(new Date().toLocaleTimeString(), 'PHONE', command.status === 'EXECUTED' ? 'success' : command.status === 'FAILED' ? 'error' : 'info', command.command + ': ' + command.status + ' — ' + detail);
        }
      });
      if (seen.size > 250) seen.clear();
    } catch (error) { panel.textContent = 'Phone status unavailable'; }
    finally { window.setTimeout(refreshMobile, 2000); }
  }
  document.addEventListener('DOMContentLoaded', refreshMobile);
})();
