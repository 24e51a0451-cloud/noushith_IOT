const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function setup() {
  let now = 0, timer = null;
  const nodes = {};
  const c = vm.createContext({console,
    document: {getElementById: id => nodes[id] || null, addEventListener() {}, activeElement: {tagName:'BODY'}},
    window: {addEventListener() {}}, performance: {now: () => now},
    setInterval: fn => {timer = fn; return 1;}, clearInterval: () => {timer = null;}, setTimeout() {}
  });
  vm.runInContext(fs.readFileSync('static/masterhub.js','utf8'), c);
  c.renderChoices = () => {}; c.updatePhaseButtons = () => {}; c.updateTemporalObserverState = () => {};
  c.addActivityLog = () => {}; c.refreshConnections = async () => {}; c.syncActivityLogs = async () => {};
  c.ui.temporalWindow = 4;
  c.ui.catalog = {active_target:'local', reset_command:'mode_idle', domains:[
    {id:'desktop', label:'Desktop', mode:'DESKTOP_MODE', switch_command:'mode_desktop', devices:[
      {id:'chrome', label:'Chrome', mode:'CHROME_MODE', gesture:'pull', switch_command:'mode_chrome', commands:[]}
    ]}, {id:'iot',label:'IoT',mode:'IOT_MODE',switch_command:'mode_iot',devices:[]}
  ]};
  const sent = [];
  c.post = async (url, body) => {sent.push(body); return {success:true,command:body.command || 'test'};};
  return {c,nodes,sent, async tick(ms) {now += ms; if(timer) timer(); await new Promise(resolve => setImmediate(resolve));}};
}
test('domain, device, and command each require their own full window', async () => {
  const {c,sent,tick} = setup();
  c.selectDomain('desktop');
  await tick(3999); assert.equal(c.ui.phase,1); assert.equal(sent.length,0);
  await c.executePendingImmediately(); assert.equal(sent.length,0);
  await tick(1); assert.equal(c.ui.phase,2); assert.equal(sent[0].command,'mode_desktop');
  c.selectDevice('chrome'); await tick(3999); assert.equal(c.ui.phase,2);
  await tick(1); assert.equal(c.ui.phase,3); assert.equal(sent[1].command,'mode_chrome');
  c.sendCommand = async payload => sent.push(payload);
  c.startTemporalFraming({command:'chrome_scroll_down'},'local','Scroll');
  await tick(3999); assert.equal(sent.length,2);
  await tick(1); assert.equal(sent[2].command,'chrome_scroll_down');
});
test('cancel and replacement cannot dispatch stale phase selections', async () => {
  const {c,sent,tick} = setup();
  c.selectDomain('desktop'); await tick(2000); c.selectDomain('iot');
  await tick(2000); assert.equal(sent.length,0);
  c.cancelFrame(); await tick(4000); assert.equal(sent.length,0);
  c.selectDomain('desktop'); c.triggerTemporalGesture('left','ArrowLeft');
  c.dispatchDirectGesture = async gesture => sent.push(gesture);
  await tick(4000); assert.deepEqual(sent,['left']); assert.equal(c.pendingExecution,null);
});
test('keyboard combinations preserve the first deadline in all phases', async () => {
  for(const phase of [1,2,3]) {
    const {c,sent,tick} = setup(); c.ui.phase = phase;
    c.dispatchDirectGesture = async gesture => sent.push(gesture);
    c.handleArrowKeyDown({key:'ArrowUp',preventDefault(){}});
    await tick(1000);
    c.handleArrowKeyDown({key:'ArrowRight',preventDefault(){}});
    await tick(2999); assert.equal(sent.length,0);
    await tick(1); assert.deepEqual(sent,['push+right']);
  }
});
test('failed phase change retains the existing phase', async () => {
  const {c,tick} = setup(); c.post = async () => ({success:false,error:'offline'});
  c.selectDomain('desktop'); await tick(4000);
  assert.equal(c.ui.phase,1); assert.equal(c.ui.domain,null);
});
test('cube reflects gesture power and resets on neutral or disconnect', () => {
  const {c,nodes} = setup();
  nodes.hudBciCube = {style:{setProperty(name, value) {this[name] = value;}}};
  nodes.hudBciCubeStatus = {};
  c.updateCortexCube(true,'right',1); assert.match(nodes.hudBciCube.style.transform,/translate3d\(42px/);
  c.updateCortexCube(true,'push',.5); assert.match(nodes.hudBciCube.style.transform,/-50px/);
  c.updateCortexCube(true,'neutral',0); assert.match(nodes.hudBciCube.style.transform,/translate3d\(0px,0px,0px\)/);
  c.updateCortexCube(false,'right',1); assert.equal(nodes.hudBciCube.style['--cube-opacity'],'1');
  assert.match(nodes.hudBciCube.style.transform,/translate3d\(0px,0px,0px\)/);
});

test('Up then Right returns exactly one phase after the window, despite server polling', async () => {
  for (const phase of [2,3]) {
    const {c,sent,tick} = setup();
    c.ui.phase = phase; c.ui.domain = 'desktop'; c.ui.device = phase === 3 ? 'chrome' : null;
    c.lastServerMode = phase === 3 ? 'CHROME_MODE' : 'DESKTOP_MODE';
    c.post = async (url, body) => {
      sent.push(body);
      c.syncBciMode({...c.ui.catalog, state_mode: phase === 3 ? 'DESKTOP_MODE' : 'IDLE'});
      return {success:true,command:body.command};
    };
    c.handleArrowKeyDown({key:'ArrowUp',preventDefault(){}});
    c.handleArrowKeyUp({key:'ArrowUp'});
    await tick(1000);
    c.handleArrowKeyDown({key:'ArrowRight',preventDefault(){}});
    await tick(2999); assert.equal(c.ui.phase,phase); assert.equal(sent.length,0);
    await tick(1); assert.equal(c.ui.phase,phase - 1); assert.equal(sent.length,1);
    assert.equal(sent[0].command,phase === 3 ? 'mode_desktop' : 'mode_idle');
    assert.equal(c.ui.device,null);
    c.syncBciMode({...c.ui.catalog,state_mode:c.lastServerMode});
    assert.equal(c.ui.phase,phase - 1);
  }
});
test('arrow Back does not change phase when the server rejects navigation', async () => {
  const {c,tick} = setup(); c.ui.phase = 3; c.ui.domain = 'desktop'; c.ui.device = 'chrome';
  c.post = async () => ({success:false,error:'Rejected'});
  c.triggerTemporalGesture('push','ArrowUp'); c.triggerTemporalGesture('right','ArrowRight');
  await tick(4000); assert.equal(c.ui.phase,3); assert.equal(c.ui.device,'chrome');
});
test('arrow Main Menu waits once and clears all selections', async () => {
  const {c,sent,tick} = setup(); c.ui.phase = 3; c.ui.domain = 'desktop'; c.ui.device = 'chrome';
  c.triggerTemporalGesture('push','ArrowUp'); c.triggerTemporalGesture('left','ArrowLeft');
  await tick(4000); assert.equal(c.ui.phase,1); assert.equal(c.ui.domain,null);
  assert.equal(sent.length,1); assert.equal(sent[0].command,'mode_idle');
});
