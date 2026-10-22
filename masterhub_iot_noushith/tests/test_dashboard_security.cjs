// Run with: node --test tests/test_dashboard_security.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element(tagName = 'div') {
  return {
    tagName, children: [], textContent: '', className: '',
    replaceChildren(...nodes) { this.children = nodes; },
    set innerHTML(value) { throw new Error('Unsafe HTML sink: ' + value); }
  };
}

function dashboard() {
  const nodes = {};
  const context = vm.createContext({
    document: {
      createElement: element,
      createTextNode: text => ({ textContent: text }),
      getElementById: id => nodes[id] || null,
      addEventListener() {}
    },
    window: { addEventListener() {} },
    setTimeout() {},
    console
  });
  const source = fs.readFileSync(path.join(__dirname, '../static/masterhub.js'), 'utf8');
  vm.runInContext(source, context);
  return { context, nodes };
}

const payload = '<img src=x onerror="alert(1)">';

test('dashboard polling waits for requests and pauses in hidden tabs', async () => {
  const { context } = dashboard();
  let calls = 0, timers = 0, finish;
  context.setTimeout = () => { timers++; };
  context.refreshConnections = () => { calls++; return new Promise(resolve => { finish = resolve; }); };
  context.syncActivityLogs = async () => { calls++; };
  const polling = context.pollDashboard();
  assert.equal(calls, 2);
  assert.equal(timers, 0);
  finish();
  await polling;
  assert.equal(timers, 1);
  context.document.hidden = true;
  await context.pollDashboard();
  assert.equal(calls, 2);
  assert.equal(timers, 2);
});

test('sidebar statuses refresh on success and clear stale values on failure', async () => {
  const { context, nodes } = dashboard();
  for (const id of ['sideMqttStatus', 'sideUartStatus', 'sideBciStatus', 'sideHealthStatus', 'sideActiveFsmMode']) {
    nodes[id] = element();
  }
  context.syncBciMode = () => {};
  context.renderChoices = () => {};
  context.updatePhaseButtons = () => {};
  context.getJson = async url => ({
    '/api/workflow': { state_mode: 'IOT_MODE', domains: [] },
    '/api/iot/status': { mqtt_connected: true },
    '/api/usb/status': { connected: true, port: 'COM7' },
    '/cortex/state': { state: { status: { connected: true } } },
    '/api/health': {}
  }[url] || {});
  await context.refreshConnections();
  assert.equal(nodes.sideMqttStatus.textContent, 'Connected');
  assert.equal(nodes.sideUartStatus.textContent, 'COM7');
  assert.equal(nodes.sideBciStatus.textContent, 'Connected');
  assert.equal(nodes.sideHealthStatus.textContent, 'OK');
  assert.equal(nodes.sideActiveFsmMode.textContent, 'IOT_MODE');
  context.getJson = async () => { throw new Error('offline'); };
  await context.refreshConnections();
  for (const node of Object.values(nodes)) assert.equal(node.textContent, 'Unavailable');
});

test('mobile registration sends the category and media capabilities', async () => {
  const { context, nodes } = dashboard();
  nodes.regDeviceCategory = { value: 'mobile' };
  nodes.regDeviceId = { value: 'PHONE_TEST' };
  nodes.regCapDesktop = { checked: true };
  nodes.regCapMedia = { checked: true };
  context.updateRegistrationCategory();
  assert.equal(nodes.regCapDesktop.disabled, true);
  let sent;
  context.post = async (url, body) => { sent = body; return { success: true }; };
  context.addActivityLog = () => {};
  context.refreshConnections = async () => {};
  context.renderPcAgentCard = () => {};
  await context.submitRegisterDevice();
  assert.equal(sent.device_category, 'mobile');
  assert.deepEqual(Array.from(sent.capabilities), ['ai_ml']);
});

test('dynamic labels, feedback and status preserve markup as literal text', () => {
  const { context } = dashboard();
  const target = element();
  context.setLabeledText(target, 'Target: ', payload, payload);
  assert.equal(target.children[1].tagName, 'strong');
  assert.equal(target.children[1].textContent, payload);
  assert.equal(target.children[2].textContent, payload);
  context.setFeedback(target, 'error-msg', payload);
  assert.equal(target.children[0].className, 'error-msg');
  assert.equal(target.children[0].textContent, payload);
  context.setStatusText(target, payload);
  assert.equal(target.children[0].className, 'dot');
  assert.equal(target.children[1].textContent, payload);
});

test('device registration renders hostile device IDs without HTML parsing', async () => {
  const { context, nodes } = dashboard();
  nodes.regDeviceId = { value: payload };
  nodes.regModalFeedback = element();
  context.post = async () => ({ success: true });
  context.addActivityLog = () => {};
  context.refreshConnections = async () => {};
  context.renderPcAgentCard = () => {};
  await context.submitRegisterDevice();
  assert.equal(nodes.regModalFeedback.children[0].textContent, 'Device ' + payload + ' registered successfully!');
});

test('UART errors and user-entered ports render as text', async () => {
  const { context, nodes } = dashboard();
  nodes.uartManualPort = { value: payload };
  nodes.uartModalFeedback = element();
  context.post = async () => { throw new Error(payload); };
  await context.handleUartConnect();
  assert.equal(nodes.uartModalFeedback.children[0].textContent, 'Connection failed: ' + payload);
});

test('UART registration selects the registered node before refreshing targets', async () => {
  const { context, nodes } = dashboard();
  nodes.regDeviceId = { value: 'PC_UART_001' };
  nodes.regDeviceTransport = { value: 'usb' };
  const calls = [];
  context.post = async (url, body) => {
    calls.push({ url, body });
    return { success: true, active_target: body.target };
  };
  context.addActivityLog = () => {};
  context.refreshConnections = async () => calls.push({ url: 'refresh' });
  context.renderPcAgentCard = () => {};
  await context.submitRegisterDevice();
  assert.equal(calls[0].url, '/api/devices/register');
  assert.equal(calls[0].body.transport, 'usb');
  assert.equal(calls[1].url, '/api/devices/target');
  assert.equal(calls[1].body.target, 'PC_UART_001');
  assert.equal(calls[2].url, 'refresh');
});

test('media Right opens search without dispatching an empty command', async () => {
  const { context } = dashboard();
  const device = {mode: 'MOBILE_JIOSAAVN_MODE', commands: [{id: 'mobile_jiosaavn_search', gesture: 'right'}]};
  context.ui = {phase: 3, busy: false, catalog: {active_target: 'PHONE'}};
  context.currentDevice = () => device;
  let opened;
  context.openMediaSearch = (...args) => { opened = args; };
  context.post = () => { throw new Error('Empty search dispatched'); };
  await context.dispatchDirectGesture('right', 'ArrowRight', 'manual_keyboard');
  assert.deepEqual(opened, ['mobile_jiosaavn_search', 'MOBILE_JIOSAAVN_MODE', 'PHONE']);
});

test('search chat submits once to its captured target and rejects changed context', async () => {
  const { context } = dashboard();
  const created = [];
  context.document.createElement = tag => {
    const node = {tagName: tag, style: {}, value: '', disabled: false, children: [],
      setAttribute() {}, append(...items) { this.children.push(...items); },
      addEventListener(name, fn) { this[name] = fn; },
      close() { this.closed = true; this.closeHandler?.(); }, remove() {}, showModal() {}, focus() {}};
    node.addEventListener = (name, fn) => { if (name === 'close') node.closeHandler = fn; };
    created.push(node); return node;
  };
  context.document.body = {append() {}};
  context.ui = {busy: false};
  context.cancelFrame = () => {};
  context.getJson = async () => ({state_mode: 'MOBILE_JIOSAAVN_MODE', active_target: 'PHONE'});
  const sent = [];
  context.sendCommand = async payload => { sent.push(payload); };
  context.openMediaSearch('mobile_jiosaavn_search', 'MOBILE_JIOSAAVN_MODE', 'PHONE');
  const form = created.find(n => n.tagName === 'form');
  created.find(n => n.tagName === 'input').value = '  Song name  ';
  await Promise.all([form.onsubmit({preventDefault() {}}), form.onsubmit({preventDefault() {}})]);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].target, 'PHONE');
  assert.equal(sent[0].params.query, 'Song name');
  created.length = 0;
  context.openMediaSearch('mobile_jiosaavn_search', 'MOBILE_JIOSAAVN_MODE', 'PHONE');
  context.getJson = async () => ({state_mode: 'IDLE', active_target: 'OTHER'});
  created.find(n => n.tagName === 'input').value = 'Another song';
  await created.find(n => n.tagName === 'form').onsubmit({preventDefault() {}});
  assert.equal(sent.length, 1);
  assert.match(created.find(n => n.tagName === 'p').textContent, /changed/);
});
