/* ==========================================================================
   MasterHub — Dashboard Controller
   Classic & Simple UI · Premium Dark Theme
   ========================================================================== */

var ui = {
  catalog: null,
  domain: null,
  device: null,
  command: null,
  phase: 1,
  busy: false,
  temporalWindow: null,
  frame: null
};

var executionLog = [];
var executionCounter = 0;

/* --- Helpers --- */
function gestureLabel(value) { if (!value) return 'Manual control'; return value.split('+').map(function(v) { return v.charAt(0).toUpperCase() + v.slice(1); }).join(' + '); }

function byId(id) { return document.getElementById(id); }
function setLabeledText(element, label, value, suffix) {
  var strong = document.createElement('strong');
  strong.textContent = value;
  element.replaceChildren(document.createTextNode(label), strong, document.createTextNode(suffix || ''));
}

function setFeedback(element, className, message) {
  var span = document.createElement('span');
  span.className = className;
  span.textContent = message;
  element.replaceChildren(span);
}

function setStatusText(element, message) {
  var dot = document.createElement('span');
  dot.className = 'dot';
  element.replaceChildren(dot, document.createTextNode(message));
}

function text(id, value) {
  var el = byId(id);
  if (el) el.textContent = value != null ? value : '—';
}

async function getJson(path, options) {
  options = options || {};
  var response = await fetch(path, Object.assign({ signal: AbortSignal.timeout(path === '/api/command' ? 60000 : 12000) }, options));
  var data = await response.json();
  if (!response.ok || data.success === false) {
    throw new Error(data.error || data.message || 'Request failed (' + response.status + ')');
  }
  return data;
}

function post(path, data) {
  return getJson(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
}

function currentDomain() {
  return ui.catalog ? ui.catalog.domains.find(function(d) { return d.id === ui.domain; }) : null;
}
function currentDevice() {
  var d = currentDomain();
  return d ? d.devices.find(function(dv) { return dv.id === ui.device; }) : null;
}
function currentCommand() {
  var dev = currentDevice();
  return dev ? dev.commands.find(function(c) { return c.id === ui.command; }) : null;
}

/* --- Render --- */
function renderChoices() {
  if (!ui.catalog) return;

  /* Phase 1: Domains */
  var domainGrid = byId('domainGrid');
  if (domainGrid && ui.catalog.domains) {
    domainGrid.replaceChildren();
    ui.catalog.domains.forEach(function(d) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'domain-card' + (ui.domain === d.id ? ' active' : '');
      btn.setAttribute('aria-pressed', String(ui.domain === d.id));
      btn.disabled = ui.busy;

      var icon = document.createElement('span');
      icon.className = 'domain-icon';
      icon.textContent = d.icon || '📦';
      var name = document.createElement('span');
      name.className = 'domain-name';
      name.textContent = d.label;
      var gesture = document.createElement('span');
      gesture.className = 'bci-gesture';
      gesture.textContent = gestureLabel(d.gesture);
      var desc = document.createElement('span');
      desc.className = 'domain-desc';
      desc.textContent = d.description;
      var status = document.createElement('span');
      status.className = 'domain-status ' + (d.connection && d.connection.ready ? 'ready' : 'offline');
      status.textContent = d.connection ? (d.connection.ready ? '● Connected' : '○ Disconnected') : '○ Unknown';

      btn.append(icon, name, gesture, desc, status);
      btn.addEventListener('click', function() { selectDomain(d.id); });
      domainGrid.appendChild(btn);
    });
  }

  /* Phase 2: Devices */
  var pcCard = byId('pcAgentControlCard');
  if (pcCard) {
    pcCard.hidden = (ui.phase !== 2) || !['desktop', 'ai_ml'].includes(ui.domain);
    if (['desktop', 'ai_ml'].includes(ui.domain)) {
      renderPcAgentCard();
    }
  }

  var deviceGrid = byId('deviceButtons');
  if (deviceGrid) {
    deviceGrid.replaceChildren();
    var dom = currentDomain();
    if (dom && dom.devices) {
      dom.devices.forEach(function(dv) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'choice-btn' + (ui.device === dv.id ? ' selected' : '');
        btn.setAttribute('aria-pressed', String(ui.device === dv.id));
        btn.disabled = ui.busy;

        var label = document.createElement('span');
        label.textContent = dv.label;
        var detail = document.createElement('span');
        detail.className = 'choice-detail';
        detail.textContent = gestureLabel(dv.gesture);
        detail.className = 'bci-gesture';

        btn.append(label, detail);
        btn.addEventListener('click', function() { selectDevice(dv.id); });
        deviceGrid.appendChild(btn);
      });
    }
  }

  /* Phase 3: Commands */
  var commandGrid = byId('commandButtons');
  if (commandGrid) {
    commandGrid.replaceChildren();
    var dev = currentDevice();
    if (dev && dev.commands) {
      dev.commands.forEach(function(c) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'choice-btn' + (ui.command === c.id ? ' selected' : '');
        btn.setAttribute('aria-pressed', String(ui.command === c.id));
        btn.disabled = ui.busy;

        var label = document.createElement('span');
        label.textContent = c.label;
        if (!c.immediate) {
          var detail = document.createElement('span');
          detail.className = 'choice-detail';
          detail.textContent = gestureLabel(c.gesture);
          detail.className = 'bci-gesture';
          btn.append(label, detail);
        } else {
          btn.textContent = c.label;
        }

        btn.addEventListener('click', function() { selectCommand(c.id); });
        commandGrid.appendChild(btn);
      });
    }
  }

  updateConnectionLabels();
  updatePhaseButtons();
}

function updateConnectionLabels() {
  if (!ui.catalog) return;
  ui.catalog.domains.forEach(function(d) {
    var el = byId('domainGrid') && byId('domainGrid').querySelector('[data-domain="' + d.id + '"] .domain-status');
    if (el) {
      el.textContent = d.connection ? (d.connection.ready ? '● Connected' : '○ Disconnected') : '○ Unknown';
      el.className = 'domain-status ' + (d.connection && d.connection.ready ? 'ready' : 'offline');
    }
  });
}

function updatePhaseButtons() {
  var p1 = byId('phase1Btn');
  var p2 = byId('phase2Btn');
  var p3 = byId('phase3Btn');
  if (p1) { p1.className = 'phase-btn' + (ui.phase === 1 ? ' active' : ''); p1.disabled = false; }
  if (p2) { p2.className = 'phase-btn' + (ui.phase === 2 ? ' active' : ''); p2.disabled = false; }
  if (p3) { p3.className = 'phase-btn' + (ui.phase === 3 ? ' active' : ''); p3.disabled = false; }

  var phase1 = byId('phase1');
  var phase2 = byId('phase2');
  var phase3 = byId('phase3');
  if (phase1) phase1.hidden = ui.phase !== 1;
  if (phase2) phase2.hidden = ui.phase !== 2;
  if (phase3) phase3.hidden = ui.phase !== 3;

  var pcCard = byId('pcAgentControlCard');
  if (pcCard) {
    pcCard.hidden = ui.phase !== 2 || !['desktop', 'ai_ml'].includes(ui.domain);
  }

  text('selectedDomainLabel', currentDomain() ? currentDomain().label : '');
  text('selectedDeviceLabel', currentDevice() ? currentDomain().label + ' / ' + currentDevice().label : '');

  var executeBtn = byId('executeBtn');
  if (executeBtn) {
    executeBtn.disabled = ui.busy || !currentCommand() || ui.temporalWindow === null;
  }
}

async function goToPhase(phase) {
  if (!ui.catalog) return;
  cancelFrame();
  
  if (phase === 2 && !ui.domain && ui.catalog.domains && ui.catalog.domains.length > 0) {
    ui.domain = ui.catalog.domains[0].id;
  }
  if (phase === 3) {
    if (!ui.domain && ui.catalog.domains && ui.catalog.domains.length > 0) {
      ui.domain = ui.catalog.domains[0].id;
    }
    var dom = currentDomain();
    if (!ui.device && dom && dom.devices && dom.devices.length > 0) {
      ui.device = dom.devices[0].id;
    }
  }

  ui.phase = phase;
  renderChoices();

  var command = phase === 1 ? ui.catalog.reset_command : phase === 2 ? (currentDomain() ? currentDomain().switch_command : null) : (currentDevice() ? currentDevice().switch_command : null);
  var mode = phase === 1 ? 'IDLE' : phase === 2 ? (currentDomain() ? currentDomain().mode : 'IDLE') : (currentDevice() ? (currentDevice().mode || currentDomain().mode) : 'IDLE');

  if (command && mode !== lastServerMode) {
    lastServerMode = mode;
    post('/api/command', { command: command }).catch(function() {});
  }

  updateTemporalObserverState(phase, 'ARMED', {
    desc: 'Navigated to ' + (phase === 1 ? 'Domain Selection' : phase === 2 ? 'Device Selection' : 'Command Execution') + '.'
  });
}

async function workflowBack() {
  cancelFrame();
  if (ui.phase === 3) {
    ui.command = null;
    ui.phase = 2;
    var dom = currentDomain();
    if (dom && dom.switch_command) {
      lastServerMode = dom.mode;
      post('/api/command', { command: dom.switch_command }).catch(function() {});
    }
  } else if (ui.phase === 2) {
    ui.device = null;
    ui.phase = 1;
    lastServerMode = 'IDLE';
    if (ui.catalog && ui.catalog.reset_command) {
      post('/api/command', { command: ui.catalog.reset_command }).catch(function() {});
    }
  }
  updateTemporalObserverState(ui.phase, 'ARMED', {
    desc: 'Returned back to ' + (ui.phase === 1 ? 'Domain Selection' : 'Device Selection') + '.'
  });
  renderChoices();
}

async function workflowMainMenu() {
  cancelFrame();
  lastServerMode = 'IDLE';
  ui.domain = null;
  ui.device = null;
  ui.command = null;
  ui.phase = 1;
  var fields = byId('commandParams');
  if (fields) fields.replaceChildren();
  if (ui.catalog && ui.catalog.reset_command) {
    post('/api/command', { command: ui.catalog.reset_command }).catch(function() {});
  }
  updateTemporalObserverState(1, 'ARMED', {
    label: 'Ready · Select Domain or Action',
    id: 'IDLE',
    domain: 'None',
    device: 'None',
    desc: 'Reset to Main Menu (IDLE). Select domain to begin workflow.'
  });
  renderChoices();
}

/* --- Selection (Instant Single Click) --- */
async function selectDomain(id) {
  cancelFrame();
  var d = ui.catalog ? ui.catalog.domains.find(function(dom) { return dom.id === id; }) : null;
  if (!d) return;

  // Instantly open Phase 2 on single click
  ui.domain = id;
  ui.device = null;
  ui.command = null;
  ui.phase = 2;
  lastServerMode = d.mode;

  var paramsEl = byId('commandParams');
  if (paramsEl) paramsEl.replaceChildren();
  text('executionResult', '');

  renderChoices();

  updateTemporalObserverState(2, 'ARMED', {
    label: 'Domain Armed: ' + d.label,
    id: d.id,
    domain: d.label,
    device: 'None',
    target: (ui.catalog && ui.catalog.active_target) || 'Local Host',
    source: 'Manual UI',
    desc: 'Domain selected. Proceed to select target device/node.'
  });

  if (d.switch_command) {
    post('/api/command', { command: d.switch_command }).catch(function(e) {
      addActivityLog('SYSTEM', 'error', e.message);
    });
  }
}

async function selectDevice(id) {
  cancelFrame();
  var dom = currentDomain();
  var dev = dom ? dom.devices.find(function(dv) { return dv.id === id; }) : null;
  if (!dev) return;

  // Instantly open Phase 3 on single click
  ui.device = id;
  ui.command = null;
  ui.phase = 3;
  lastServerMode = dev.mode || dom.mode;

  var paramsEl = byId('commandParams');
  if (paramsEl) paramsEl.replaceChildren();
  text('executionResult', '');

  renderChoices();

  updateTemporalObserverState(3, 'ARMED', {
    label: 'Device Armed: ' + dev.label,
    id: dev.id,
    domain: dom ? dom.label : 'None',
    device: dev.label,
    target: (ui.catalog && ui.catalog.active_target) || 'Local Host',
    source: 'Manual UI',
    desc: 'Device armed. Select command below to execute.'
  });

  if (dev.switch_command) {
    post('/api/command', { command: dev.switch_command }).catch(function(e) {
      addActivityLog('SYSTEM', 'error', e.message);
    });
  }
}

async function selectCommand(id) {
  if (ui.busy) return;
  cancelFrame();
  ui.command = id;
  renderChoices();

  var fields = byId('commandParams');
  fields.replaceChildren();
  var cmd = currentCommand();
  if (cmd && cmd.parameters) {
    cmd.parameters.forEach(function(name) {
      var label = document.createElement('label');
      label.textContent = name.replace(/_/g, ' ');
      label.style.cssText = 'display:block;margin:8px 0 4px;font-size:0.78rem;color:var(--text-secondary);font-weight:600;';
      var input = document.createElement('input');
      input.id = 'param-' + name;
      input.name = name;
      input.required = true;
      input.style.cssText = 'width:100%;padding:8px 10px;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px;color:var(--text-primary);font-size:13px;';
      fields.append(label, input);
    });
  }

  updateTemporalObserverState(3, 'ARMED', {
    label: cmd ? cmd.label : id,
    id: cmd ? cmd.id : id,
    domain: currentDomain() ? currentDomain().label : 'None',
    device: currentDevice() ? currentDevice().label : 'None',
    target: (ui.catalog && ui.catalog.active_target) || 'Local Host',
    source: 'Manual UI',
    desc: cmd && cmd.parameters && cmd.parameters.length ? 'Enter command parameters and submit to execute.' : 'Command selected. Starting temporal framing delay...'
  });

  text('executionResult', cmd && cmd.parameters && cmd.parameters.length
    ? 'Enter the command details.'
    : 'Selected ' + (cmd ? cmd.label : id) + '.');
  updatePhaseButtons();

  if (cmd && (!cmd.parameters || cmd.parameters.length === 0)) {
    var dom = currentDomain();
    var payload = { command: cmd.id, params: {} };
    if (dom && dom.transport === 'target' && ui.catalog && ui.catalog.active_target) {
      payload.target = ui.catalog.active_target;
    }
    var target = payload.target || (currentDevice() ? currentDevice().label : 'unknown');
    startTemporalFraming(payload, target, cmd.label, 'Manual UI');
  }
}

/* --- Temporal Window Observer & Framing Controller --- */
var pendingExecution = null;

function updateTemporalObserverState(phase, status, info) {
  info = info || {};
  var phaseBadge = byId('twPhaseBadge');
  if (phaseBadge) {
    if (typeof phase === 'number') {
      phaseBadge.textContent = phase === 1 ? 'Phase 1 · Domain Selection'
        : phase === 2 ? 'Phase 2 · Device Selection'
        : 'Phase 3 · Command Execution';
    } else if (phase) {
      phaseBadge.textContent = String(phase);
    }
  }

  var pill = byId('twStatusPill');
  var pillText = byId('twStatusText');
  var card = byId('temporalWindowCard');
  if (pill && pillText) {
    pill.className = 'temporal-status-pill ' + (
      status === 'FRAMING' ? 'status-framing' :
      status === 'EXECUTING' ? 'status-executing' :
      status === 'SUCCESS' ? 'status-success' :
      status === 'ABORTED' || status === 'CANCELLED' ? 'status-aborted' :
      status === 'ERROR' || status === 'FAILED' ? 'status-error' :
      'status-armed'
    );
    pillText.textContent = status || 'ARMED';
  }

  if (card) {
    card.classList.toggle('framing-active', status === 'FRAMING');
    card.classList.toggle('status-executing', status === 'EXECUTING');
    card.classList.toggle('status-success', status === 'SUCCESS');
  }

  var icon = byId('twCmdIcon');
  if (icon) {
    icon.textContent = status === 'FRAMING' ? '⏳' :
      status === 'EXECUTING' ? '⚡' :
      status === 'SUCCESS' ? '✅' :
      status === 'ABORTED' || status === 'CANCELLED' ? '🛑' :
      status === 'FAILED' || status === 'ERROR' ? '⚠️' : '🎯';
  }

  var cmdLabel = byId('twCommandLabel');
  if (cmdLabel) {
    if (info.label) {
      cmdLabel.textContent = info.label;
    } else if (currentCommand()) {
      cmdLabel.textContent = currentCommand().label;
    } else if (currentDevice()) {
      cmdLabel.textContent = 'Armed: ' + currentDevice().label;
    } else if (currentDomain()) {
      cmdLabel.textContent = 'Armed: ' + currentDomain().label;
    } else {
      cmdLabel.textContent = 'Ready · Select Domain or Command';
    }
  }

  var cmdId = byId('twCommandId');
  if (cmdId) {
    cmdId.textContent = info.id || (currentCommand() ? currentCommand().id : (currentDevice() ? currentDevice().id : (currentDomain() ? currentDomain().id : 'IDLE')));
  }

  var metaDomain = byId('twMetaDomain');
  if (metaDomain) {
    var domName = info.domain || (currentDomain() ? currentDomain().label : 'None');
    setLabeledText(metaDomain, 'Domain: ', domName);
  }

  var metaDev = byId('twMetaDevice');
  if (metaDev) {
    var devName = info.device || (currentDevice() ? currentDevice().label : 'None');
    setLabeledText(metaDev, 'Device: ', devName);
  }

  var metaTarget = byId('twMetaTarget');
  if (metaTarget) {
    var tgtName = info.target || (ui.catalog && ui.catalog.active_target ? ui.catalog.active_target : 'Local Host');
    setLabeledText(metaTarget, 'Target: ', tgtName);
  }

  var metaSource = byId('twMetaSource');
  if (metaSource) {
    var srcName = info.source || 'Manual UI';
    setLabeledText(metaSource, 'Source: ', srcName);
  }

  var desc = byId('twDescText');
  if (desc) {
    if (info.desc) {
      desc.textContent = info.desc;
    } else if (status === 'FRAMING') {
      desc.textContent = 'Delay before command is sent. Cancel or change selection to abort, or click Execute Now.';
    } else if (status === 'SUCCESS') {
      desc.textContent = 'Command executed successfully · Acknowledged by controller (' + (info.latency || 'OK') + ').';
    } else {
      desc.textContent = 'Delay before command is sent. Live telemetry and framing countdown active for every phase.';
    }
  }

  var execNowBtn = byId('twExecuteNowBtn');
  var abortBtn = byId('twAbortBtn');
  if (execNowBtn) execNowBtn.style.display = status === 'FRAMING' ? 'inline-block' : 'none';
  if (abortBtn) abortBtn.style.display = status === 'FRAMING' ? 'inline-block' : 'none';
}

function startTemporalFraming(payload, target, commandLabel, sourceName) {
  cancelFrame(true);
  var duration = (ui.temporalWindow !== null ? ui.temporalWindow : 4.0);
  var deadline = performance.now() + duration * 1000;
  
  pendingExecution = {
    payload: payload,
    target: target,
    label: commandLabel,
    source: sourceName || 'Manual UI',
    domain: currentDomain() ? currentDomain().label : 'System',
    device: currentDevice() ? currentDevice().label : 'None'
  };

  updateTemporalObserverState(3, 'FRAMING', {
    label: 'Pending: ' + commandLabel,
    id: payload.command,
    domain: pendingExecution.domain,
    device: pendingExecution.device,
    target: target,
    source: pendingExecution.source,
    desc: 'Framing window active (' + duration.toFixed(1) + 's). Observing command before dispatch.'
  });

  text('executionResult', 'Pending: ' + commandLabel + '. Cancel to abort or click Execute Now.');
  text('twDisplay', duration.toFixed(1) + 's');
  
  var gauge = byId('twGaugeFill');
  if (gauge) gauge.style.width = '100%';

  ui.frame = setInterval(function() {
    var remaining = Math.max(0, (deadline - performance.now()) / 1000);
    text('twDisplay', remaining.toFixed(1) + 's');
    
    if (gauge) {
      var pct = Math.max(0, Math.min(100, (remaining / duration) * 100));
      gauge.style.width = pct.toFixed(1) + '%';
    }

    if (remaining <= 0) {
      cancelFrame(true);
      executePendingImmediately();
    }
  }, 40);
}

async function executePendingImmediately() {
  if (pendingExecution) {
    var exec = pendingExecution;
    pendingExecution = null;
    cancelFrame(true);
    await sendCommand(exec.payload, exec.target, exec.label, exec.source);
    return;
  }
  if (pendingTemporalGesture) {
    var execG = pendingTemporalGesture.gesture;
    var execK = pendingTemporalGesture.keys;
    var execS = pendingTemporalGesture.source;
    pendingTemporalGesture = null;
    cancelFrame(true);
    await dispatchDirectGesture(execG, execK, execS);
  }
}

/* --- Execution --- */
function cancelFrame(silent) {
  if (ui.frame) { clearInterval(ui.frame); ui.frame = null; }
  var card = byId('temporalWindowCard');
  if (card) {
    card.classList.remove('framing-active');
  }
  var gauge = byId('twGaugeFill');
  if (gauge) gauge.style.width = '100%';

  if (ui.temporalWindow !== null) {
    text('twDisplay', ui.temporalWindow.toFixed(1) + 's');
  }

  var execNowBtn = byId('twExecuteNowBtn');
  var abortBtn = byId('twAbortBtn');
  if (execNowBtn) execNowBtn.style.display = 'none';
  if (abortBtn) abortBtn.style.display = 'none';

  if (!silent) {
    text('executionResult', 'Pending command cancelled.');
    updateTemporalObserverState(ui.phase, 'ABORTED', {
      desc: 'Command was cancelled by user before the temporal window expired.'
    });
    pendingExecution = null;
    pendingTemporalGesture = null;
  }
  updatePhaseButtons();
}

async function executeWorkflow() {
  if (ui.busy || !currentCommand() || ui.temporalWindow === null) return;
  var form = byId('commandForm');
  if (form && !form.reportValidity()) return;

  cancelFrame(true);
  var c = currentCommand();
  var payload = { command: c.id, params: {} };
  var formData = new FormData(form);
  formData.forEach(function(val, key) { payload.params[key] = val; });

  var dom = currentDomain();
  if (dom && dom.transport === 'target' && ui.catalog && ui.catalog.active_target) {
    payload.target = ui.catalog.active_target;
  }

  var target = payload.target || (currentDevice() ? currentDevice().label : 'unknown');
  startTemporalFraming(payload, target, c.label, 'Manual Form');
}

async function sendCommand(payload, target, customLabel, sourceName) {
  ui.busy = true;
  renderChoices();
  var label = customLabel || (currentCommand() ? currentCommand().label : payload.command);
  var src = sourceName || 'Manual UI';
  var dom = currentDomain() ? currentDomain().label : (payload.domain || 'System');
  var dev = currentDevice() ? currentDevice().label : 'None';

  updateTemporalObserverState(ui.phase, 'EXECUTING', {
    label: 'Executing: ' + label,
    id: payload.command,
    domain: dom,
    device: dev,
    target: target,
    source: src,
    desc: 'Dispatching command to target controller...'
  });

  text('executionResult', 'Sending command…');
  var t0 = performance.now();

  try {
    var d = await post('/api/command', payload);
    var latency = (performance.now() - t0).toFixed(1) + 'ms';
    var message = d.simulated ? 'Simulation completed'
      : d.topic ? 'Published · awaiting acknowledgement'
      : d.transport === 'mqtt' ? 'Published · awaiting acknowledgement'
      : 'Command completed';
    text('executionResult', message);
    addActivityLog(d.domain || 'SYSTEM', 'success', payload.command + ': ' + message);
    recordExecutionEvent({
      command: payload.command,
      confidence: '—',
      device: target,
      action: message,
      source: src.toUpperCase()
    });

    updateTemporalObserverState(ui.phase, 'SUCCESS', {
      label: label,
      id: payload.command,
      domain: d.domain ? d.domain.toUpperCase() : dom,
      device: dev,
      target: target,
      source: src,
      latency: latency,
      desc: 'Command executed successfully in ' + latency + ' · ' + message
    });
  } catch (e) {
    text('executionResult', e.message);
    addActivityLog('SYSTEM', 'error', e.message);
    recordExecutionEvent({
      command: payload.command,
      confidence: '—',
      device: target,
      action: 'Failed: ' + e.message,
      source: src.toUpperCase()
    });

    updateTemporalObserverState(ui.phase, 'FAILED', {
      label: label,
      id: payload.command,
      domain: dom,
      device: dev,
      target: target,
      source: src,
      desc: 'Execution failed: ' + e.message
    });
  } finally {
    ui.busy = false;
    renderChoices();
  }
}

async function resetFsmState() {
  if (ui.busy || !ui.catalog) return;
  cancelFrame();
  try {
    await post('/api/command', { command: ui.catalog.reset_command });
    ui.domain = null;
    ui.device = null;
    ui.command = null;
    ui.phase = 1;
    updateTemporalObserverState(1, 'ARMED', {
      label: 'Ready · Select Domain or Action',
      id: 'IDLE',
      domain: 'None',
      device: 'None',
      desc: 'System reset to IDLE state.'
    });
    renderChoices();
  } catch (e) {
    addActivityLog('SYSTEM', 'error', e.message);
  }
}

/* --- Temporal Window --- */
function updateTemporalDisplay(value) {
  ui.temporalWindow = value;
  text('twDisplay', value.toFixed(1) + 's');
  var presets = byId('temporalPresets');
  if (presets) {
    presets.querySelectorAll('.preset-btn').forEach(function(btn) {
      btn.classList.toggle('active', parseFloat(btn.textContent) === value);
    });
  }
  updatePhaseButtons();
}

async function setTemporalWindow(value) {
  cancelFrame();
  try {
    var d = await post('/api/config/temporal-window', { temporal_window: value });
    updateTemporalDisplay(d.temporal_window);
  } catch (e) {
    text('executionResult', e.message);
  }
}

/* Reflect BCI mode changes received outside the dashboard. */
var lastServerMode = null;
function syncBciMode(catalog) {
  var mode = catalog.state_mode;
  if (!mode || mode === lastServerMode || ui.busy) return;
  lastServerMode = mode;
  
  if (mode === 'IDLE') {
    // Only reset to phase 1 if we are not actively in Phase 2 or Phase 3
    if (!ui.domain) {
      ui.phase = 1;
      ui.device = null;
      ui.command = null;
      renderChoices();
    }
    return;
  }
  
  var matched = catalog.domains.some(function(domain) {
    if (domain.mode === mode) {
      ui.domain = domain.id;
      ui.phase = 2;
      return true;
    }
    var device = domain.devices.find(function(item) { return item.mode === mode; });
    if (device) {
      ui.domain = domain.id;
      ui.device = device.id;
      ui.phase = 3;
      return true;
    }
    return false;
  });
  
  if (matched) {
    renderChoices();
  }
}

/* --- Connections --- */
async function refreshConnections() {
  await Promise.allSettled([
    /* Workflow / catalog */
    (async function() {
      try {
        var d = await getJson('/api/workflow');
        syncBciMode(d);
        if (!ui.catalog) {
          ui.catalog = d;
          renderChoices();
          updatePhaseButtons();
        } else {
          ui.catalog = d;
          renderChoices();
        }
        var iotReady = d.domains.find(function(dm) { return dm.id === 'iot'; }) && d.domains.find(function(dm) { return dm.id === 'iot'; }).connection.ready;
      } catch (e) {
        if (!ui.catalog) text('executionResult', 'Unable to load domains.');
      }
    })(),
    /* MQTT */
    (async function() {
      try {
        var d = await getJson('/api/iot/status');
        var online = d.mqtt_connected;
        var pill = byId('pillMqtt');
        if (pill) {
          pill.className = 'status-pill ' + (online ? 'online' : 'error');
          setStatusText(pill, 'MQTT ' + (online ? 'Connected' : 'Offline'));
        }
      } catch (e) {
        var pill = byId('pillMqtt');
        if (pill) { pill.className = 'status-pill error'; setStatusText(pill, 'MQTT Unavailable'); }
      }
    })(),
    /* USB */
    (async function() {
      try {
        var d = await getJson('/api/usb/status');
        var connected = d.connected;
        var pill = byId('pillUsb');
        if (pill) {
          pill.className = 'status-pill ' + (connected ? 'online' : 'error');
          setStatusText(pill, 'USB ' + (connected ? (d.port || 'Connected') : 'Disconnected'));
        }
      } catch (e) {
        var pill = byId('pillUsb');
        if (pill) { pill.className = 'status-pill error'; setStatusText(pill, 'USB Unavailable'); }
      }
    })(),
    /* BCI */
    (async function() {
      try {
        var d = await getJson('/cortex/state');
        var connected = d.state && d.state.status && d.state.status.connected;
        var pill = byId('pillBci');
        if (pill) {
          pill.className = 'status-pill ' + (connected ? 'online' : 'error');
          setStatusText(pill, 'BCI ' + (connected ? 'Connected' : 'Disconnected'));
        }
      } catch (e) {
        var pill = byId('pillBci');
        if (pill) { pill.className = 'status-pill error'; setStatusText(pill, 'BCI Unavailable'); }
      }
    })(),
    /* System health */
    (async function() {
      try {
        await getJson('/api/health');
        var pill = byId('pillSystem');
        if (pill) { pill.className = 'status-pill online'; setStatusText(pill, 'System OK'); }
      } catch (e) {
        var pill = byId('pillSystem');
        if (pill) { pill.className = 'status-pill error'; setStatusText(pill, 'System Error'); }
      }
    })(),
    /* Metrics */
    (async function() {
      try {
        var d = await getJson('/api/metrics');
        var m = d.metrics;
        if (m.total_commands) {
          text('hudResponseLatency', Number(m.response_ms || 0).toFixed(1) + ' ms');
          text('hudProcessLatency', Number(m.process_ms || 0).toFixed(1) + ' ms');
          text('hudExecutionLatency', Number(m.execution_ms || 0).toFixed(1) + ' ms');
          text('hudFaultRecovery', m.fault_recovery || '—');
        }
      } catch (e) {
        ['hudResponseLatency', 'hudProcessLatency', 'hudExecutionLatency', 'hudFaultRecovery'].forEach(function(id) { text(id, '—'); });
      }
    })()
  ]);
}

/* --- Activity Log & BCI Real-Time Sync --- */
var lastActivityLogId = 0;

async function syncActivityLogs() {
  try {
    var data = await getJson('/api/activity-logs?since_id=' + lastActivityLogId);
    if (data.logs && data.logs.length > 0) {
      data.logs.forEach(function(item) {
        if (item.id > lastActivityLogId) {
          lastActivityLogId = item.id;
        }
        var tag = item.type === 'BCI' ? '🧠 BCI' : (item.domain ? item.domain.toUpperCase() : 'SYSTEM');
        var typeClass = item.status === 'SUCCESS' ? 'success' : (item.status === 'REJECTED' || item.status === 'FAILED' ? 'error' : 'info');

        var msg = '';
        if (item.type === 'BCI' || (item.gesture && item.gesture !== '—')) {
          msg = (item.gesture || 'mental_command') +
            (item.confidence && item.confidence !== '—' ? ' (' + item.confidence + ')' : '') +
            ' -> ' + item.command +
            ': ' + (item.acknowledgement || item.detail || 'Executed');
        } else {
          msg = item.command + ': ' + (item.acknowledgement || item.detail || 'Executed');
        }

        renderActivityLogEntry(item.time || item.timestamp, tag, typeClass, msg);

        if (item.type === 'BCI') {
          updateTemporalObserverState('Live BCI Stream', item.status === 'SUCCESS' ? 'SUCCESS' : 'FAILED', {
            label: '🧠 ' + (item.gesture || 'mental_command') + ' ➔ ' + item.command,
            id: item.command,
            domain: item.domain ? item.domain.toUpperCase() : 'BCI',
            device: 'Emotiv Cortex',
            target: 'Active Mode',
            source: 'BCI (' + (item.confidence && item.confidence !== '—' ? item.confidence : '100%') + ')',
            latency: item.acknowledgement || 'ACK OK',
            desc: 'Live BCI mental command executed: ' + (item.detail || item.command)
          });
        }

        // Status and prediction feedback are not executed commands.
        if (item.type === 'BCI' || item.type === 'COMMAND') recordExecutionEvent({
          command: item.command,
          confidence: item.confidence || '—',
          device: item.domain || 'bci',
          action: item.acknowledgement || item.detail || 'Executed',
          source: item.type === 'BCI' ? 'BCI_HEADSET' : (item.domain ? item.domain.toUpperCase() : 'SYSTEM')
        }, false);
      });
    }
  } catch (e) {}
}

function renderActivityLogEntry(timeStr, tag, typeClass, message) {
  var body = byId('consoleBody');
  if (!body) return;
  var entry = document.createElement('div');
  entry.className = 'log-entry ' + (typeClass ? 'log-' + typeClass : '');
  var time = document.createElement('span');
  time.className = 'log-time';
  time.textContent = timeStr || new Date().toLocaleTimeString();

  var tagSpan = document.createElement('span');
  tagSpan.className = 'log-tag';
  tagSpan.textContent = tag;
  tagSpan.style.cssText = 'font-weight:600;margin:0 4px;';

  entry.append(time, ' · ', tagSpan, ' · ', message);
  body.appendChild(entry);
  body.scrollTop = body.scrollHeight;
}

function addActivityLog(tag, type, message) {
  renderActivityLogEntry(new Date().toLocaleTimeString(), tag, type, message);
}

async function clearActivityLog() {
  var body = byId('consoleBody');
  if (body) body.replaceChildren();
  lastActivityLogId = 0;
  try {
    await post('/api/activity-logs/clear', {});
  } catch (e) {}
}

/* --- Export --- */
function recordExecutionEvent(event, unshift) {
  var entry = { id: ++executionCounter, timestamp: new Date().toLocaleTimeString(), command: '', confidence: '—', device: '', action: '', source: 'MANUAL' };
  Object.assign(entry, event);
  if (unshift === false) {
    executionLog.push(entry);
  } else {
    executionLog.unshift(entry);
  }
  updateRecordCount();
}

function updateRecordCount() {
  var el = byId('recordCount');
  if (el) el.textContent = executionLog.length + ' record' + (executionLog.length !== 1 ? 's' : '');
}

function exportDataLog() {
  var lines = executionLog.map(function(e) {
    return '[' + e.timestamp + '] ID:' + e.id + ' CMD:' + e.command + ' CONF:' + e.confidence + ' DEV:' + e.device + ' ACT:' + e.action;
  });
  downloadFile(lines.join('\n'), 'masterhub_telemetry.log', 'text/plain');
}

function exportDataJson() {
  downloadFile(JSON.stringify(executionLog, null, 2), 'masterhub_telemetry.json', 'application/json');
}

function exportDataCsv() {
  var headers = ['ID', 'Timestamp', 'Command', 'Confidence', 'Device', 'Action', 'Source'];
  var rows = executionLog.map(function(e) {
    return [e.id, e.timestamp, e.command, e.confidence, e.device, e.action, e.source].join(',');
  });
  downloadFile([headers.join(','), rows.join('\n')].join('\n'), 'masterhub_telemetry.csv', 'text/csv');
}

function downloadFile(content, filename, type) {
  var blob = new Blob([content], { type: type });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  addActivityLog('EXPORT', 'success', 'Downloaded ' + filename);
}

/* --- Init --- */
document.addEventListener('DOMContentLoaded', function() {
  refreshConnections();
  syncActivityLogs();

  /* Load temporal window config */
  getJson('/api/config/temporal-window').then(function(d) {
    ui.temporalWindow = d.temporal_window;
    text('twDisplay', d.temporal_window.toFixed(1) + 's');
    var presets = byId('temporalPresets');
    if (presets) {
      presets.querySelectorAll('.preset-btn').forEach(function(btn) {
        btn.classList.toggle('active', parseFloat(btn.textContent) === d.temporal_window);
      });
    }
  }).catch(function() {});

  /* Load hardware config */
  getJson('/api/hardware/config').then(function(d) {
    /* config loaded, available for future use */
  }).catch(function() {});

  /* Fast poll for activity logs and connection status */
  setTimeout(function poll() {
    refreshConnections();
    syncActivityLogs();
    setTimeout(poll, 1500);
  }, 1500);

  /* Keyboard shortcuts: ESC to close drawers/modals, B to toggle BCI drawer */
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' || e.key === 'Esc') {
      closeSidebar();
      closeBciDrawer();
      closeModals();
    } else if ((e.key === 'b' || e.key === 'B') && !e.ctrlKey && !e.metaKey && !e.altKey) {
      var tag = (document.activeElement && document.activeElement.tagName) || '';
      if (tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') {
        e.preventDefault();
        toggleBciDrawer();
      }
    }
  });

  /* Arrow keys & combination commands listener */
  window.addEventListener('keydown', handleArrowKeyDown);
  window.addEventListener('keyup', handleArrowKeyUp);
});

/* --- Keyboard Arrow & Temporal Combination Navigation --- */
var activeKeys = new Set();
var keySequence = [];
var pendingTemporalGesture = null;

function resolveSingleArrow(key) {
  if (key === 'ArrowUp') return 'push';
  if (key === 'ArrowDown') return 'pull';
  if (key === 'ArrowLeft') return 'left';
  if (key === 'ArrowRight') return 'right';
  return null;
}

function resolveArrowCombo(k1, k2) {
  var g1 = resolveSingleArrow(k1) || k1;
  var g2 = resolveSingleArrow(k2) || k2;
  if (!g1 || !g2) return null;
  return g1 + '+' + g2;
}

function triggerTemporalGesture(gesture, keyName, source) {
  var duration = (ui.temporalWindow !== null ? ui.temporalWindow : 4.0);
  var deadline = performance.now() + duration * 1000;
  var src = source || 'manual_keyboard';

  // Check if there is already a pending single gesture within the active temporal window
  if (pendingTemporalGesture && pendingTemporalGesture.gesture) {
    var g1 = pendingTemporalGesture.gesture;
    var g2 = gesture;
    var k1 = pendingTemporalGesture.keys || pendingTemporalGesture.key || g1;
    var k2 = keyName || g2;

    var combo = resolveArrowCombo(k1, k2) || (g1 + '+' + g2);
    var comboKeys = (k1 && k2 && k1 !== g1) ? (k1 + '+' + k2) : combo;

    // Form combination and cancel the pending single timer
    cancelFrame(true);
    pendingTemporalGesture = null;

    updateTemporalObserverState(ui.phase, 'EXECUTING', {
      label: '⚡ Combination Formed: ' + gestureLabel(combo),
      id: combo,
      domain: currentDomain() ? currentDomain().label : 'Combination Router',
      device: currentDevice() ? currentDevice().label : 'Active Domain',
      target: (ui.catalog && ui.catalog.active_target) || 'Local Host',
      source: (src === 'bci' ? '🧠 BCI' : '⌨️ Keyboard') + ' [' + comboKeys + ']',
      desc: 'Formed combination command (' + g1 + ' + ' + g2 + ' within ' + duration.toFixed(1) + 's window).'
    });

    dispatchDirectGesture(combo, comboKeys, src);
    return;
  }

  // If no pending gesture, open the temporal window for this single gesture
  cancelFrame(true);

  pendingTemporalGesture = {
    gesture: gesture,
    keys: keyName,
    source: src,
    deadline: deadline,
    duration: duration
  };

  updateTemporalObserverState(ui.phase, 'FRAMING', {
    label: 'Pending: ' + gestureLabel(gesture) + (keyName ? ' [' + keyName + ']' : ''),
    id: gesture,
    domain: currentDomain() ? currentDomain().label : 'Gesture Router',
    device: currentDevice() ? currentDevice().label : 'Active Window',
    target: (ui.catalog && ui.catalog.active_target) || 'Local Host',
    source: (src === 'bci' ? '🧠 BCI' : '⌨️ Keyboard') + (keyName ? ' [' + keyName + ']' : ''),
    desc: 'Temporal window active (' + duration.toFixed(1) + 's). Input next gesture for combination, or wait to execute.'
  });

  text('executionResult', 'Pending: ' + gestureLabel(gesture) + '. Press next arrow for combination or wait ' + duration.toFixed(1) + 's.');
  text('twDisplay', duration.toFixed(1) + 's');

  var gauge = byId('twGaugeFill');
  if (gauge) gauge.style.width = '100%';

  ui.frame = setInterval(function() {
    var remaining = Math.max(0, (deadline - performance.now()) / 1000);
    text('twDisplay', remaining.toFixed(1) + 's');

    if (gauge) {
      var pct = Math.max(0, Math.min(100, (remaining / duration) * 100));
      gauge.style.width = pct.toFixed(1) + '%';
    }

    if (remaining <= 0) {
      cancelFrame(true);
      if (pendingTemporalGesture) {
        var execG = pendingTemporalGesture.gesture;
        var execK = pendingTemporalGesture.keys;
        var execS = pendingTemporalGesture.source;
        pendingTemporalGesture = null;
        dispatchDirectGesture(execG, execK, execS);
      }
    }
  }, 40);
}

async function dispatchDirectGesture(gesture, keysPressed, source) {
  if (ui.busy) return;
  
  var glabel = gestureLabel(gesture);
  var src = source || 'manual_keyboard';
  var isBci = src === 'bci' || src === 'cortex' || src === 'bci_mental';
  text('executionResult', (isBci ? 'BCI' : 'Keyboard') + ' gesture: ' + glabel + ' [' + keysPressed + ']');

  updateTemporalObserverState(ui.phase, 'EXECUTING', {
    label: (isBci ? '🧠 BCI: ' : '⌨️ Keyboard: ') + glabel,
    id: gesture,
    domain: currentDomain() ? currentDomain().label : 'System Router',
    device: currentDevice() ? currentDevice().label : 'Active Window',
    target: (ui.catalog && ui.catalog.active_target) || 'Local Host',
    source: (isBci ? '🧠 BCI Headset' : '⌨️ Keyboard') + ' [' + keysPressed + ']',
    desc: 'Routing gesture command to MasterHub engine...'
  });

  var t0 = performance.now();
  try {
    var res = await post('/api/command', {
      gesture: gesture,
      params: {
        source: isBci ? 'bci' : 'manual_keyboard',
        input_type: isBci ? 'bci_mental' : 'keyboard_arrow',
        keys: keysPressed
      }
    });
    var latency = (performance.now() - t0).toFixed(1) + 'ms';
    var msg = res.command + ': ' + (res.action || (res.success ? 'Executed' : res.error || 'Done'));
    addActivityLog(isBci ? 'BCI' : 'KEYBOARD', res.success ? 'success' : 'error', glabel + ' -> ' + msg);
    
    updateTemporalObserverState(ui.phase, res.success ? 'SUCCESS' : 'FAILED', {
      label: glabel + ' ➔ ' + res.command,
      id: res.command,
      domain: res.domain ? res.domain.toUpperCase() : (currentDomain() ? currentDomain().label : 'SYSTEM'),
      device: currentDevice() ? currentDevice().label : '—',
      target: (ui.catalog && ui.catalog.active_target) || 'Local Host',
      source: (isBci ? '🧠 BCI Headset' : '⌨️ Keyboard') + ' [' + keysPressed + ']',
      latency: latency,
      desc: 'Executed ' + res.command + ' in ' + latency
    });

    if (gesture === 'push+left' || res.command === 'mode_idle') {
      ui.domain = null;
      ui.device = null;
      ui.command = null;
      ui.phase = 1;
      renderChoices();
    } else if (gesture === 'push+right') {
      if (ui.phase === 3) {
        ui.command = null;
        ui.phase = 2;
        renderChoices();
      } else if (ui.phase === 2) {
        ui.device = null;
        ui.domain = null;
        ui.phase = 1;
        renderChoices();
      }
    } else if (ui.phase === 1 && res.success) {
      var gestureToDomain = {
        'push': 'desktop',
        'pull': 'embedded',
        'left': 'iot',
        'right': 'ai_ml'
      };
      var targetDom = gestureToDomain[gesture] || (res.domain && res.domain.toLowerCase());
      if (targetDom && ui.catalog && ui.catalog.domains.some(function(dm) { return dm.id === targetDom; })) {
        ui.domain = targetDom;
        ui.phase = 2;
        renderChoices();
      }
    } else if (ui.phase === 2 && res.success) {
      var dom = currentDomain();
      if (dom && dom.devices) {
        var dev = dom.devices.find(function(dv) { return dv.gesture === gesture || dv.switch_command === res.command; });
        if (dev) {
          ui.device = dev.id;
          ui.phase = 3;
          renderChoices();
        }
      }
    }

    await refreshConnections();
    await syncActivityLogs();
  } catch (err) {
    text('executionResult', err.message);
    addActivityLog(isBci ? 'BCI' : 'KEYBOARD', 'error', err.message);
    updateTemporalObserverState(ui.phase, 'FAILED', {
      label: glabel,
      id: gesture,
      source: (isBci ? '🧠 BCI Headset' : '⌨️ Keyboard') + ' [' + keysPressed + ']',
      desc: 'Execution failed: ' + err.message
    });
  }
}

function handleArrowKeyDown(e) {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
    return;
  }
  
  var key = e.key;
  if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(key)) {
    return;
  }

  e.preventDefault();

  activeKeys.add(key);
  if (!keySequence.includes(key)) {
    keySequence.push(key);
  }

  // Check simultaneous dual-key chord combination first
  if (keySequence.length >= 2 || activeKeys.size >= 2) {
    var k1 = keySequence[0];
    var k2 = keySequence[1] || Array.from(activeKeys).find(function(k) { return k !== k1; });
    var combo = resolveArrowCombo(k1, k2);
    if (combo) {
      keySequence = [];
      activeKeys.clear();
      cancelFrame(true);
      pendingTemporalGesture = null;
      dispatchDirectGesture(combo, [k1, k2].join('+'), 'manual_keyboard');
      return;
    }
  }

  // Phase 1: Single arrow selects Domain
  if (ui.phase === 1) {
    var domainMap = {
      'ArrowUp': 'desktop',
      'ArrowDown': 'embedded',
      'ArrowLeft': 'iot',
      'ArrowRight': 'ai_ml'
    };
    var targetDomain = domainMap[key];
    if (targetDomain) {
      activeKeys.clear();
      keySequence = [];
      selectDomain(targetDomain);
      return;
    }
  }

  // Phase 2: Single arrow selects Device
  if (ui.phase === 2) {
    var dom = currentDomain();
    if (dom && dom.devices && dom.devices.length > 0) {
      var singleG = resolveSingleArrow(key);
      var matchedDevice = dom.devices.find(function(dv) { return dv.gesture === singleG; });
      if (matchedDevice) {
        activeKeys.clear();
        keySequence = [];
        selectDevice(matchedDevice.id);
        return;
      }
    }
  }

  // Phase 3: Trigger single gesture into temporal window buffer
  var singleGesture = resolveSingleArrow(key);
  if (singleGesture) {
    triggerTemporalGesture(singleGesture, key, 'manual_keyboard');
  }
}

function handleArrowKeyUp(e) {
  if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
    activeKeys.delete(e.key);
  }
  if (activeKeys.size === 0) {
    keySequence = [];
  }
}

/* --- Sidebar Drawer Controls --- */
function openSidebar() {
  var drawer = byId('sidebarDrawer');
  var backdrop = byId('sidebarBackdrop');
  var btn = byId('hamburgerBtn');
  if (drawer) {
    drawer.classList.add('open');
    drawer.setAttribute('aria-hidden', 'false');
  }
  if (backdrop) {
    backdrop.classList.add('open');
    backdrop.setAttribute('aria-hidden', 'false');
  }
  if (btn) btn.setAttribute('aria-expanded', 'true');
}

function closeSidebar() {
  var drawer = byId('sidebarDrawer');
  var backdrop = byId('sidebarBackdrop');
  var btn = byId('hamburgerBtn');
  if (drawer) {
    drawer.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
  }
  if (backdrop) {
    backdrop.classList.remove('open');
    backdrop.setAttribute('aria-hidden', 'true');
  }
  if (btn) btn.setAttribute('aria-expanded', 'false');
}

function toggleSidebar() {
  var drawer = byId('sidebarDrawer');
  if (drawer && drawer.classList.contains('open')) {
    closeSidebar();
  } else {
    openSidebar();
  }
}

/* --- BCI Headset Slide-Out Drawer Controls --- */
function openBciDrawer() {
  var drawer = byId('bciPanel');
  var backdrop = byId('bciDrawerBackdrop');
  if (drawer) {
    drawer.classList.add('open');
    drawer.setAttribute('aria-hidden', 'false');
  }
  if (backdrop) {
    backdrop.classList.add('open');
    backdrop.setAttribute('aria-hidden', 'false');
  }
}

function closeBciDrawer() {
  var drawer = byId('bciPanel');
  var backdrop = byId('bciDrawerBackdrop');
  if (drawer) {
    drawer.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
  }
  if (backdrop) {
    backdrop.classList.remove('open');
    backdrop.setAttribute('aria-hidden', 'true');
  }
}

function toggleBciDrawer() {
  var drawer = byId('bciPanel');
  if (drawer && drawer.classList.contains('open')) {
    closeBciDrawer();
  } else {
    openBciDrawer();
  }
}

async function toggleBciControlMode() {
  var btn = byId('bciControl');
  if (btn) {
    btn.click();
  } else {
    try {
      await post('/cortex/control', { enabled: true });
    } catch (e) {}
  }
}

window.openBciDrawer = openBciDrawer;
window.closeBciDrawer = closeBciDrawer;
window.toggleBciDrawer = toggleBciDrawer;
window.toggleBciControlMode = toggleBciControlMode;

/* --- PC Agent & Transport Management for Python Domain --- */
async function renderPcAgentCard() {
  var activeTarget = (ui.catalog && ui.catalog.active_target) || 'Local Host';
  text('activeTargetBadge', activeTarget);

  var pillsRow = byId('targetPillsRow');
  if (pillsRow) {
    pillsRow.replaceChildren();
    var targets = (ui.catalog && ui.catalog.targets) || [];
    if (targets.length === 0) {
      try {
        var devRes = await getJson('/api/devices');
        targets = devRes.devices || [];
        if (devRes.active_target) {
          activeTarget = devRes.active_target;
          text('activeTargetBadge', activeTarget);
        }
      } catch (e) {}
    }

    targets.forEach(function(tgt) {
      var isSelected = tgt.device_id === activeTarget;
      var pill = document.createElement('button');
      pill.type = 'button';
      pill.className = 'target-pill' + (isSelected ? ' selected' : '');
      pill.setAttribute('aria-pressed', String(isSelected));
      pill.title = 'Set ' + tgt.device_id + ' as active dispatch target (' + (tgt.transport || 'mqtt').toUpperCase() + ')';

      var icon = document.createElement('span');
      icon.className = 'target-pill-icon';
      icon.textContent = tgt.transport === 'local' ? '🏠' : tgt.transport === 'usb' || tgt.transport === 'uart' || tgt.transport === 'serial' ? '🔌' : '📡';

      var name = document.createElement('span');
      name.className = 'target-pill-name';
      name.textContent = tgt.device_id;

      var type = document.createElement('span');
      type.className = 'target-pill-type';
      type.textContent = (tgt.transport || 'mqtt').toUpperCase();

      var statusDot = document.createElement('span');
      statusDot.className = 'target-status-dot ' + (tgt.status === 'ONLINE' ? 'online' : 'offline');

      pill.append(icon, name, type, statusDot);
      pill.addEventListener('click', function() {
        selectTargetNode(tgt.device_id);
      });
      pillsRow.appendChild(pill);
    });
  }

  // Update MQTT link status
  var mqttOnline = byId('pillMqtt') && byId('pillMqtt').classList.contains('online');
  var mqttTag = byId('agentMqttTag');
  var mqttDesc = byId('agentMqttDesc');
  if (mqttTag) {
    mqttTag.className = 'agent-status-tag ' + (mqttOnline ? 'online' : 'offline');
    mqttTag.textContent = mqttOnline ? 'ONLINE' : 'OFFLINE';
  }
  if (mqttDesc) {
    var targets = (ui.catalog && ui.catalog.targets) || [];
    var pc001 = targets.find(function(t) { return t.device_id === 'PC_001'; });
    var pc001Status = pc001 ? (pc001.status || 'OFFLINE') : 'Registered';
    setLabeledText(mqttDesc, 'Default Node: ', 'PC_001', ' (' + pc001Status + ') · ' + (mqttOnline ? 'Broker Connected' : 'Broker Offline'));
  }

  // Update UART link status
  try {
    var usbData = await getJson('/api/usb/status');
    var uartTag = byId('agentUartTag');
    var uartDesc = byId('agentUartDesc');
    if (uartTag) {
      uartTag.className = 'agent-status-tag ' + (usbData.connected ? 'online' : 'offline');
      uartTag.textContent = usbData.connected ? 'CONNECTED' : 'DISCONNECTED';
    }
    if (uartDesc) {
      uartDesc.textContent = usbData.connected
        ? 'Active Port: ' + (usbData.port || 'COM') + ' · ' + (usbData.baudrate || 115200) + ' baud'
        : 'Port: None · 115200 baud';
    }
  } catch (e) {}
}

async function selectTargetNode(targetId) {
  if (ui.busy) return;
  try {
    var res = await post('/api/devices/target', { target: targetId });
    if (ui.catalog) ui.catalog.active_target = res.active_target;
    text('activeTargetBadge', res.active_target);
    addActivityLog('AGENT', 'success', 'Active PC dispatch target set to: ' + res.active_target);
    await refreshConnections();
    renderPcAgentCard();
  } catch (e) {
    addActivityLog('AGENT', 'error', 'Failed to set target: ' + e.message);
  }
}

/* --- Modals Management --- */
function openRegisterDeviceModal() {
  var modal = byId('registerDeviceModal');
  var backdrop = byId('modalBackdrop');
  var feedback = byId('regModalFeedback');
  if (feedback) feedback.textContent = '';
  var idInput = byId('regDeviceId');
  if (idInput && !idInput.value) idInput.value = 'PC_002';
  if (modal) modal.hidden = false;
  if (backdrop) backdrop.classList.add('open');
}

function openUartConfigModal() {
  var modal = byId('uartConfigModal');
  var backdrop = byId('modalBackdrop');
  var feedback = byId('uartModalFeedback');
  if (feedback) feedback.textContent = '';
  if (modal) modal.hidden = false;
  if (backdrop) backdrop.classList.add('open');
  refreshUartPorts();
  refreshUartModalStatus();
}

function closeModals() {
  var regModal = byId('registerDeviceModal');
  var uartModal = byId('uartConfigModal');
  var cheatModal = byId('cheatSheetModal');
  var guideModal = byId('userGuideModal');
  var backdrop = byId('modalBackdrop');
  if (regModal) regModal.hidden = true;
  if (uartModal) uartModal.hidden = true;
  if (cheatModal) cheatModal.hidden = true;
  if (guideModal) guideModal.hidden = true;
  if (backdrop) backdrop.classList.remove('open');
}

function openCheatSheetModal() {
  closeModals();
  var modal = byId('cheatSheetModal');
  var backdrop = byId('modalBackdrop');
  if (modal) modal.hidden = false;
  if (backdrop) backdrop.classList.add('open');
}

function openUserGuideModal() {
  closeModals();
  var modal = byId('userGuideModal');
  var backdrop = byId('modalBackdrop');
  if (modal) modal.hidden = false;
  if (backdrop) backdrop.classList.add('open');
}

function quickJumpDomain(domainId) {
  closeSidebar();
  selectDomain(domainId);
  var phase2 = byId('phase2');
  if (phase2) {
    phase2.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

async function emergencyStop() {
  addActivityLog('E-STOP', 'error', '🛑 EMERGENCY ALL-STOP TRIGGERED BY USER');
  try {
    await post('/api/command', { command: 'emergency_stop' });
  } catch (e) {
    try {
      await post('/api/command', { command: 'car_stop' });
      await post('/api/command', { command: 'chair_stop' });
    } catch (err) {}
  }
  updateTemporalObserverState('Emergency Stop', 'FAILED', {
    label: '🛑 EMERGENCY ALL-STOP SENT',
    id: 'E_STOP',
    domain: 'SAFETY',
    device: 'All Nodes',
    target: 'Broadcast',
    source: 'E-STOP',
    desc: 'All mobility motors, wheelchair actuators, and pending tasks stopped immediately.'
  });
}

var isSimModeActive = false;
function toggleSimMode() {
  isSimModeActive = !isSimModeActive;
  var btn = byId('sidebarSimToggleBtn');
  var textEl = byId('sidebarSimText');
  if (btn && textEl) {
    textEl.textContent = isSimModeActive ? 'SIM: ACTIVE' : 'SIM: OFF';
    btn.classList.toggle('active', isSimModeActive);
  }
  addActivityLog('SYSTEM', 'info', 'Hardware simulation mode: ' + (isSimModeActive ? 'ENABLED' : 'DISABLED'));
}

window.openCheatSheetModal = openCheatSheetModal;
window.openUserGuideModal = openUserGuideModal;
window.quickJumpDomain = quickJumpDomain;
window.emergencyStop = emergencyStop;
window.toggleSimMode = toggleSimMode;

async function submitRegisterDevice() {
  var deviceId = byId('regDeviceId') ? byId('regDeviceId').value.trim() : '';
  var deviceName = byId('regDeviceName') ? byId('regDeviceName').value.trim() : '';
  var transport = byId('regDeviceTransport') ? byId('regDeviceTransport').value : 'mqtt';
  var capDesktop = byId('regCapDesktop') ? byId('regCapDesktop').checked : true;
  var capMedia = byId('regCapMedia') ? byId('regCapMedia').checked : true;
  var feedback = byId('regModalFeedback');

  if (!deviceId) {
    if (feedback) setFeedback(feedback, 'error-msg', 'Please enter a valid Device ID');
    return;
  }

  var capabilities = [];
  if (capDesktop) capabilities.push('desktop');
  if (capMedia) capabilities.push('ai_ml');

  try {
    if (feedback) setFeedback(feedback, 'info-msg', 'Registering device…');
    var res = await post('/api/devices/register', {
      device_id: deviceId,
      name: deviceName || deviceId,
      transport: transport,
      capabilities: capabilities,
      status: 'OFFLINE'
    });

    if (res.success) {
      if (feedback) setFeedback(feedback, 'success-msg', 'Device ' + deviceId + ' registered successfully!');
      addActivityLog('AGENT', 'success', 'Registered PC Agent: ' + deviceId + ' (' + transport.toUpperCase() + ')');
      await refreshConnections();
      renderPcAgentCard();
      setTimeout(function() {
        closeModals();
      }, 900);
    }
  } catch (e) {
    if (feedback) setFeedback(feedback, 'error-msg', 'Registration error: ' + e.message);
  }
}

async function refreshUartPorts() {
  var select = byId('uartPortSelect');
  if (!select) return;
  select.innerHTML = '<option value="">Scanning ports…</option>';
  try {
    var res = await getJson('/api/usb/ports');
    select.replaceChildren();
    if (res.ports && res.ports.length > 0) {
      var defaultOpt = document.createElement('option');
      defaultOpt.value = '';
      defaultOpt.textContent = '-- Select detected COM port --';
      select.appendChild(defaultOpt);
      res.ports.forEach(function(p) {
        var opt = document.createElement('option');
        opt.value = p.port;
        opt.textContent = p.port + (p.description ? ' (' + p.description + ')' : '');
        select.appendChild(opt);
      });
    } else {
      var opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'No physical COM ports detected (use SIMULATED for testing)';
      select.appendChild(opt);
    }
  } catch (e) {
    select.innerHTML = '<option value="">Failed to scan ports</option>';
  }
}

function onUartPortChange() {
  var select = byId('uartPortSelect');
  var manual = byId('uartManualPort');
  if (select && manual && select.value) {
    manual.value = select.value;
  }
}

async function refreshUartModalStatus() {
  try {
    var stat = await getJson('/api/usb/status');
    var badge = byId('uartModalStatusBadge');
    var portVal = byId('uartModalPortVal');
    var baudVal = byId('uartModalBaudVal');
    var txVal = byId('uartModalTxVal');
    var rxVal = byId('uartModalRxVal');
    var btnConn = byId('btnUartConnect');
    var btnDisc = byId('btnUartDisconnect');

    if (badge) {
      badge.className = 'status-badge ' + (stat.connected ? 'online' : 'offline');
      badge.textContent = stat.connected ? 'CONNECTED' : 'DISCONNECTED';
    }
    if (portVal) portVal.textContent = stat.port || '—';
    if (baudVal) baudVal.textContent = stat.baudrate ? stat.baudrate + ' bps' : '—';
    if (txVal) txVal.textContent = stat.tx_count || 0;
    if (rxVal) rxVal.textContent = stat.rx_count || 0;

    if (btnConn) btnConn.disabled = stat.connected;
    if (btnDisc) btnDisc.disabled = !stat.connected;
  } catch (e) {}
}

async function handleUartConnect() {
  var manual = byId('uartManualPort') ? byId('uartManualPort').value.trim() : '';
  var select = byId('uartPortSelect') ? byId('uartPortSelect').value.trim() : '';
  var baud = byId('uartBaudSelect') ? byId('uartBaudSelect').value : 115200;
  var port = manual || select;
  var feedback = byId('uartModalFeedback');

  if (!port) {
    if (feedback) setFeedback(feedback, 'error-msg', 'Please select or enter a COM port (e.g. COM4 or SIMULATED)');
    return;
  }

  try {
    if (feedback) setFeedback(feedback, 'info-msg', 'Connecting to ' + port + '…');
    var res = await post('/api/usb/connect', { port: port, baudrate: parseInt(baud, 10) });
    if (res.success) {
      if (feedback) setFeedback(feedback, 'success-msg', 'Connected to ' + port + ' @ ' + baud + ' baud');
      addActivityLog('UART', 'success', 'Connected to UART Serial ' + port + ' (' + baud + ' baud)');
      await refreshUartModalStatus();
      await refreshConnections();
      renderPcAgentCard();
    }
  } catch (e) {
    if (feedback) setFeedback(feedback, 'error-msg', 'Connection failed: ' + e.message);
  }
}

async function handleUartDisconnect() {
  var feedback = byId('uartModalFeedback');
  try {
    if (feedback) setFeedback(feedback, 'info-msg', 'Disconnecting…');
    var res = await post('/api/usb/disconnect', {});
    if (res.success) {
      if (feedback) setFeedback(feedback, 'success-msg', 'UART Serial disconnected');
      addActivityLog('UART', 'success', 'UART Serial disconnected');
      await refreshUartModalStatus();
      await refreshConnections();
      renderPcAgentCard();
    }
  } catch (e) {
    if (feedback) setFeedback(feedback, 'error-msg', 'Disconnect error: ' + e.message);
  }
}

