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
