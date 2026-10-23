const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
function element() {
  return {
    children: [], style: {},
    append(...items) { this.children.push(...items); },
    appendChild(item) { this.children.push(item); },
    replaceChildren(...items) { this.children = items; },
    setAttribute() {}, addEventListener() {}, querySelector() { return null; }
  };
}
const elements = Object.fromEntries(['deviceButtons', 'commandButtons', 'phase4Btn', 'phase3', 'commandForm'].map(id => [id, element()]));
const context = vm.createContext({console, window: {}, document: {
  addEventListener() {}, getElementById(id) { return elements[id] || null; },
  createElement: element
}});
vm.runInContext(fs.readFileSync(path.join(root, 'static/masterhub.js'), 'utf8'), context);
const workflow = JSON.parse(fs.readFileSync(path.join(root, 'mappings/workflow_map.json')));
const devices = Object.entries(workflow.devices).filter(([, d]) => d.domain === 'desktop')
  .map(([id, d]) => ({...d, id, switch_command: d.mode, commands: []}));
context.ui.catalog = {domains: [{id: 'desktop', label: 'Desktop', mode: 'DESKTOP_MODE', switch_command: 'mode_desktop', devices}]};
context.ui.domain = 'desktop';
context.ui.phase = 2;
const sent = [];
context.post = async (_, body) => { sent.push(body.command); return {success: true}; };
context.updateTemporalObserverState = () => {};
context.cancelFrame = () => {};
(async () => {
  context.renderChoices();
  const labels = elements.deviceButtons.children.map(b => b.children[0].textContent);
  assert(labels.includes('Microsoft Office'));
  assert(!labels.includes('Microsoft Excel'));
  await context.commitSelectDevice('office');
  assert.equal(context.ui.phase, 3);
  assert.equal(elements.commandButtons.children.length, 3);
  assert.equal(elements.commandForm.hidden, true);
  for (const id of ['office_excel', 'office_powerpoint', 'office_word']) {
    await context.commitSelectDevice(id);
    assert.equal(context.ui.phase, 4);
    assert.equal(elements.phase4Btn.disabled, false);
    assert.equal(elements.phase3.hidden, false);
    assert.equal(elements.commandForm.hidden, false);
    await context.commitWorkflowBack();
    assert.equal(context.ui.phase, 3);
    assert.equal(context.ui.device, 'office');
  }
  await context.commitWorkflowBack();
  assert.equal(context.ui.phase, 2);
  context.syncBciMode({...context.ui.catalog, state_mode: 'OFFICE_EXCEL_MODE'});
  assert.equal(context.ui.phase, 4);
  assert.equal(context.ui.device, 'office_excel');
  assert(sent.every(command => !command.includes('close')));
  console.log('Office frontend navigation checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
