/* Cortex is owned by the backend; this panel only displays samples and sends controls. */
(function () {
  'use strict';
  var snapshot = null, busy = false, requested = false, lastEvent = 0, seen = 0, profileKey = '';
  var $ = function (id) { return document.getElementById(id); };
  function text(id, value) { $(id).textContent = value == null ? '—' : value; }
  async function getJson(url, options) {
    var response = await fetch(url, Object.assign({signal: AbortSignal.timeout(15000)}, options || {}));
    var data = await response.json();
    if (!response.ok || data.success === false) throw new Error(data.error || data.message || 'Request failed');
    return data;
  }
  function post(url, data) { return getJson(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}); }
  function gestureLabel(value) { return value.split('+').map(function(v) { return v.toUpperCase(); }).join(' → '); }
  var workflowKey = '', headsetFrameVisible = false;
  function renderWorkflow(workflow) {
    if (!workflow) return;
    var path = ['Main menu'];
    if (workflow.domain) path.push(workflow.domain.label);
    if (workflow.device) path.push(workflow.device.label);
    text('bciPath', path.join(' / '));
    text('bciTarget', 'Desktop / media target: ' + (workflow.target || 'Not selected'));
    text('bciUsage', '1. Perform PUSH. 2. Add RIGHT for Back or LEFT for Main Menu before time runs out. 3. The captured command executes at zero. Neutral between gestures is optional.');
    text('bciTiming', 'Window ' + workflow.sequence_seconds + 's · Minimum power ' + Math.round(workflow.threshold * 100) + '% · No extra gesture hold');
    var pending = workflow.pending;
    text('bciPending', pending ? gestureLabel(pending.gesture) + ' → ' + pending.label + ' · ' + pending.remaining.toFixed(1) + 's' : 'Ready for a new frame');
    text('bciWorkflowHelp', snapshot.control_enabled ? workflow.message : 'Monitor mode — enable control, then return to neutral to begin.');
    var progress = $('bciFrameProgress');
    if (progress) { progress.max = pending ? pending.duration : workflow.sequence_seconds; progress.value = pending ? pending.duration - pending.remaining : 0; }
    if (typeof updateTemporalObserverState === 'function' && (pending || headsetFrameVisible)) {
      var result = workflow.last_result;
      var completed = result && (workflow.message === 'Command accepted by MasterHub.' || workflow.message === result.error);
      updateTemporalObserverState('Headset · Temporal frame', pending ? 'FRAMING' : completed ? (result.success ? 'SUCCESS' : 'FAILED') : 'CANCELLED', {
        label: pending ? gestureLabel(pending.gesture) + ' → ' + pending.label : workflow.message,
        id: pending ? pending.gesture : result ? result.command : 'No pending command',
        source: 'BCI headset', domain: workflow.domain ? workflow.domain.label : 'Main menu',
        device: workflow.device ? workflow.device.label : 'Select device',
        desc: pending ? 'Executes at zero. Add the second gesture before the window ends. Stop Control cancels. Timing changes apply to the next frame.' : workflow.message
      });
      // These buttons control browser-owned manual frames, not backend BCI frames.
      ['twExecuteNowBtn', 'twAbortBtn'].forEach(function(id) { if ($(id)) $(id).style.display = 'none'; });
      if ($('twMetaTarget')) $('twMetaTarget').textContent = 'Target: ' + (workflow.target || 'Local Host');
      if ($('twDisplay')) $('twDisplay').textContent = pending ? pending.remaining.toFixed(1) + 's' : workflow.sequence_seconds.toFixed(1) + 's';
      if ($('twGaugeFill')) $('twGaugeFill').style.width = pending ? Math.max(0, pending.remaining / pending.duration * 100) + '%' : '0%';
      headsetFrameVisible = !!pending;
    }
    var key = JSON.stringify([workflow.mode, workflow.choices]);
    if (key !== workflowKey) {
      workflowKey = key;
      $('bciDomains').replaceChildren();
      [['desktop','Desktop'],['embedded','Mobility'],['iot','IoT'],['ai_ml','AI / Media']].forEach(function(domain) {
        var item = document.createElement('span'); item.textContent = domain[1];
        item.className = workflow.domain && workflow.domain.id === domain[0] ? 'active' : '';
        $('bciDomains').appendChild(item);
      });
      $('bciChoices').replaceChildren(); $('bciInputForms').replaceChildren();
      workflow.choices.forEach(function(choice) {
        var row = document.createElement('div'), gesture = document.createElement('strong'), label = document.createElement('span');
        gesture.textContent = gestureLabel(choice.gesture); label.textContent = choice.label;
        row.append(gesture, label); $('bciChoices').appendChild(row);
        if (choice.parameters.length) {
          var form = document.createElement('form'), title = document.createElement('h4');
          title.textContent = choice.label; form.appendChild(title);
          choice.parameters.forEach(function(name) {
            var field = document.createElement('label'), input = document.createElement(name === 'body' || name === 'text' ? 'textarea' : 'input');
            field.textContent = name; input.name = name; input.required = true; input.maxLength = 10000;
            input.value = (workflow.parameters[choice.command] || {})[name] || '';
            field.appendChild(input); form.appendChild(field);
          });
          var button = document.createElement('button'); button.type = 'submit'; button.className = 'btn-secondary'; button.textContent = 'Save inputs'; form.appendChild(button);
          form.onsubmit = function(event) {
            event.preventDefault(); action(async function() {
              var params = {}; new FormData(form).forEach(function(value, name) { params[name] = value; });
              await post('/cortex/workflow', {command:choice.command, params:params}); message('Inputs saved for ' + choice.label + '.');
            });
          };
          $('bciInputForms').appendChild(form);
        }
      });
      $('bciInputs').hidden = !$('bciInputForms').children.length;
    }
    $('bciInputForms').querySelectorAll('input, textarea, button').forEach(function(input) { input.disabled = snapshot.control_enabled || busy; });
    var result = workflow.last_result;
    if (result) {
      text('bciOutcome', (result.success ? 'Accepted · ' : 'Failed · ') + result.command);
      text('bciOutcomeDetail', result.error || (result.type === 'mode_switch' ? 'Workflow selection updated.' : 'MasterHub handler accepted the action. Device completion depends on its reported feedback.'));
      $('bciOutcome').classList.toggle('error', !result.success);
    }
  }
  function message(value, error) { $('bciMessage').textContent = value || ''; $('bciMessage').classList.toggle('error', !!error); }
  function buttons() {
    var s = snapshot && snapshot.status || {};
    $('bciConnect').disabled = busy || requested || !!s.connected;
    $('bciConnect').textContent = requested ? 'Connecting…' : 'Connect headset';
    $('bciDisconnect').disabled = busy || !(requested || s.connected || s.retry_attempt);
    $('bciRefresh').disabled = busy || !s.authorized;
    $('bciLoad').disabled = busy || !s.authorized || !$('bciProfile').value;
    $('bciControl').disabled = busy || !(snapshot && (snapshot.control_enabled || (snapshot.streaming && s.current_profile)));
  }
  async function action(work) {
    if (busy) return;
    busy = true; buttons();
    try { await work(); } catch (e) { message(e.message, true); }
    finally { busy = false; buttons(); }
  }
  function profiles(items, selected) {
    var key = JSON.stringify([items, selected]);
    if (key === profileKey) return;
    profileKey = key;
    var keep = $('bciProfile').value;
    $('bciProfile').replaceChildren(new Option('Select a trained profile', ''));
    (items || []).forEach(function (name) { $('bciProfile').add(new Option(name, name)); });
    $('bciProfile').value = selected || keep;
  }
  async function refreshProfiles() {
    var data = await getJson('/cortex/profiles');
    profiles(data.profiles, data.current_profile);
    message(data.profiles.length ? 'Choose a profile, then load it.' : 'No profiles found. Train a profile in EmotivBCI, then refresh.');
  }
  function render(data) {
    snapshot = data;
    var s = data.status, h = data.headset, latest = data.predictions[data.predictions.length - 1];
    if (s.connected) requested = false;
    $('bciStreamStatus').textContent = data.streaming ? '● Live stream' : s.connected ? 'Awaiting stream' : requested ? 'Connecting' : 'Offline';
    $('bciStreamStatus').classList.toggle('live', data.streaming);
    [['Connection',s.connected],['Auth',s.authorized],['Session',s.connected && data.session.id && data.session.status !== 'closed'],['Profile',s.connected && s.current_profile]].forEach(function (stage) {
      $('bciStage' + stage[0]).classList.toggle('done', !!stage[1]);
    });
    text('bciHeadset', s.connected ? h.id || 'Discovering…' : '—');
    text('bciBattery', s.connected && h.battery_percent != null ? h.battery_percent + '%' : '—');
    text('bciSignal', s.connected && h.signal_quality != null ? String(h.signal_quality) : '—');
    text('bciAction', data.streaming && latest ? latest.action : s.connected ? 'Waiting' : 'Offline');
    var power = data.streaming && latest && Number.isFinite(latest.power) ? Math.max(0, Math.min(1, latest.power)) : 0;
    $('bciPower').value = power;
    text('bciPowerLabel', data.streaming ? Math.round(power * 100) + '%' : '—');
    text('bciSampleAge', latest ? Math.max(0, data.server_time - latest.received_at).toFixed(1) + 's ago' : 'No samples yet');
    text('bciStreamHelp', !s.connected ? 'Connect your headset to begin.' : !s.current_profile ? 'Load a trained profile for meaningful commands.' : data.streaming ? 'Live from your headset. Neutral is the resting state.' : 'Waiting for fresh mental command samples.');
    text('bciModeLabel', data.control_enabled ? 'Control mode' : 'Monitor mode');
    text('bciControl', data.control_enabled ? 'Stop control' : 'Enable control');
    $('bciControl').setAttribute('aria-pressed', String(data.control_enabled));
    text('bciRouted', data.metrics.current_routed_command || 'No action routed yet');
    profiles(s.available_profiles, s.current_profile);
    renderWorkflow(data.workflow);

    /* --- Sync to Live Neural HUD on Main Dashboard --- */
    var gestureIcons = {
      'push': '⬆️',
      'pull': '⬇️',
      'left': '⬅️',
      'right': '➡️',
      'neutral': '🧠',
      'disguise': '🎭'
    };
    var actName = data.streaming && latest ? latest.action : s.connected ? 'Waiting' : 'Offline';
    var icon = gestureIcons[actName.toLowerCase()] || '🧠';
    
    if (typeof updateCortexCube === 'function') {
      updateCortexCube(!!s.connected && !!data.streaming, actName, power);
    }
    var hudIcon = $('hudBciGestureIcon');
    if (hudIcon) hudIcon.textContent = icon;
    
    var hudName = $('hudBciGestureName');
    if (hudName) hudName.textContent = actName;
    
    var hudPowerVal = $('hudBciPowerVal');
    if (hudPowerVal) hudPowerVal.textContent = data.streaming ? Math.round(power * 100) + '%' : '—';
    
    var hudPowerFill = $('hudBciPowerFill');
    if (hudPowerFill) hudPowerFill.style.width = Math.round(power * 100) + '%';

    var hudStatusDot = $('hudBciStatusDot');
    if (hudStatusDot) {
      hudStatusDot.classList.toggle('offline', !data.streaming && !s.connected);
    }

    var hudModeChip = $('hudBciModeChip');
    if (hudModeChip) {
      hudModeChip.textContent = data.control_enabled ? 'CONTROL ACTIVE' : 'MONITOR MODE';
      hudModeChip.classList.toggle('active', !!data.control_enabled);
    }

    var hudAckMsg = $('hudBciAckMessage');
    if (hudAckMsg) {
      if (!data.control_enabled && data.streaming) {
        hudAckMsg.textContent = !s.current_profile ? 'Load a trained profile, then click Enable Control.' : 'Monitor mode: click Enable Control, relax to neutral, then perform a command.';
      } else if (data.workflow && data.workflow.pending) {
        hudAckMsg.textContent = gestureLabel(data.workflow.pending.gesture) + ' → ' + data.workflow.pending.label + ' · Executes in ' + data.workflow.pending.remaining.toFixed(1) + 's';
      } else if (data.control_enabled) {
        hudAckMsg.textContent = data.workflow.message;
      } else if (data.streaming) {
        hudAckMsg.textContent = 'Streaming live EEG samples. Enable control mode to execute workflow actions.';
      } else if (s.connected) {
        hudAckMsg.textContent = 'Headset linked. Load a trained profile in Cortex Setup to stream commands.';
      } else {
        hudAckMsg.textContent = 'Headset offline. Click "Cortex Setup" or the BCI pill to connect.';
      }
    }

    var hudHeadset = $('hudBciHeadsetLabel');
    if (hudHeadset) hudHeadset.textContent = s.connected ? (h.id || 'Cortex Link') : 'Emotiv Cortex';

    var hudBattery = $('hudBciBatteryLabel');
    if (hudBattery) hudBattery.textContent = s.connected && h.battery_percent != null ? h.battery_percent + '%' : '—';

    var hudSignal = $('hudBciSignalLabel');
    if (hudSignal) hudSignal.textContent = s.connected && h.signal_quality != null ? String(h.signal_quality) : '—';

    var hudToggleBtn = $('hudBciToggleModeBtn');
    var hudToggleText = $('hudBciToggleModeText');
    if (hudToggleBtn && hudToggleText) {
      hudToggleText.textContent = data.control_enabled ? 'Stop Control' : 'Enable Control';
      hudToggleBtn.classList.toggle('active-control', !!data.control_enabled);
      hudToggleBtn.disabled = busy || !(data.control_enabled || (data.streaming && s.current_profile));
    }

    /* Update Header BCI Pill */
    var pillBci = $('pillBci');
    if (pillBci) {
      pillBci.classList.toggle('online', !!data.streaming);
      pillBci.classList.toggle('warn', !!(s.connected && !data.streaming));
    }

    if (latest && latest.id !== seen) {
      seen = latest.id;
      $('bciHistory').replaceChildren();
      data.predictions.slice(-8).reverse().forEach(function (sample) {
        var row = document.createElement('li'), time = document.createElement('time'), name = document.createElement('span'), power = document.createElement('span');
        time.textContent = new Date(sample.received_at * 1000).toLocaleTimeString();
        name.textContent = sample.action;
        power.textContent = Number.isFinite(sample.power) ? Math.round(sample.power * 100) + '%' : '—';
        row.append(time, name, power); $('bciHistory').appendChild(row);
      });
    }
    if (s.last_error) message(s.last_error, true);
    buttons();
  }
  $('bciConnect').onclick = function () { action(async function () {
    await post('/cortex/connect', {}); requested = true; message('Connection requested. Approve access in EMOTIV Launcher if prompted.');
  }); };
  $('bciDisconnect').onclick = function () { action(async function () {
    await post('/cortex/control', {enabled:false});
    await post('/cortex/disconnect', {}); requested = false; message('Headset disconnected.');
  }); };
  $('bciRefresh').onclick = function () { action(refreshProfiles); };
  $('bciProfile').onchange = buttons;
  $('bciLoad').onclick = function () { action(async function () {
    var data = await post('/cortex/profiles/load', {profile:$('bciProfile').value}); message(data.message);
  }); };
  $('bciControl').onclick = function () { action(async function () {
    var data = await post('/cortex/control', {enabled:!snapshot.control_enabled});
    snapshot.control_enabled = data.control_enabled;
    message(data.control_enabled ? 'Control enabled. Relax to neutral first, then perform a trained command.' : 'Monitor mode. Headset commands will not execute actions.');
  }); };
  $('bciCredentialsForm').onsubmit = function (event) {
    event.preventDefault(); action(async function () {
      var data = await post('/cortex/credentials', {client_id:$('bciClientId').value, client_secret:$('bciSecret').value});
      $('bciSecret').value = ''; text('bciCredentialsStatus', data.has_credentials ? '· Saved' : '· Incomplete');
      message('Credentials saved. Connect the headset to continue.');
    });
  };
  getJson('/cortex/credentials').then(function (data) {
    $('bciClientId').value = data.client_id || '';
    text('bciCredentialsStatus', data.has_credentials ? '· Saved' : '· Setup needed');
  }).catch(function (e) { message(e.message, true); });
  var events = new EventSource('/cortex/events');
  events.onmessage = function (event) { lastEvent = Date.now(); render(JSON.parse(event.data)); };
  events.onerror = function () { offline(); };
  function offline() {
    if (typeof updateCortexCube === 'function') updateCortexCube(false, 'offline', 0);
    text('bciStreamStatus', 'Reconnecting…'); $('bciStreamStatus').classList.remove('live');
    text('bciAction', 'Unavailable'); $('bciPower').value = 0; text('bciPowerLabel', '—');
    text('bciPending', 'Connection interrupted');
    text('bciWorkflowHelp', 'Live state unavailable. Check the connection before enabling control again.');
    text('bciStreamHelp', 'Dashboard connection interrupted. Reconnecting automatically.');
    $('bciControl').disabled = true;
    if ($('hudBciToggleModeBtn')) $('hudBciToggleModeBtn').disabled = true;

    var hudStatusDot = $('hudBciStatusDot');
    if (hudStatusDot) hudStatusDot.classList.add('offline');
    var hudAckMsg = $('hudBciAckMessage');
    if (hudAckMsg) hudAckMsg.textContent = 'Dashboard BCI stream reconnecting...';
    var pillBci = $('pillBci');
    if (pillBci) {
      pillBci.classList.remove('online');
      pillBci.classList.remove('warn');
    }
  }
  setInterval(function () { if (lastEvent && Date.now() - lastEvent > 3000) offline(); }, 1000);
  window.addEventListener('pagehide', function () { events.close(); });
  buttons();
})();
