const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {value:'', hidden:false, disabled:false, style:{}, handlers:{},
    addEventListener(type, fn) { this.handlers[type] = fn; },
    setAttribute(k,v) { this[k] = v; }, removeAttribute(k) { delete this[k]; },
    get valueAsNumber() { return this.value === '' ? NaN : Number(this.value); }});
  return elements.get(id);
}
const sample = {config:{height:300,unit:'cm',height_cm:300},device_id:'esp32',percent:72,
  water_depth_cm:216,distance_cm:84,float_value:0,rssi:-87,pump:null,mqtt_connected:true,
  received_at:100,age_seconds:3,status:'live',warnings:[]};
const calls=[];
const context=vm.createContext({console,Number,Date,Math,byId:element,
  text:(id,value)=>{element(id).textContent=value;},
  post:async(url,data)=>{calls.push({url,data});return {tank:sample};}});
const root=path.resolve(__dirname,'..');
vm.runInContext(fs.readFileSync(path.join(root,'static/tank-monitor.js'),'utf8'),context);
context.initTank();context.renderTank(sample);
assert.equal(element('tankPercent').textContent,'72%');
element('tankUnit').value='ft';element('tankUnit').handlers.change();
assert.ok(Math.abs(Number(element('tankHeight').value)-300/30.48)<1e-8);
element('tankHeight').value='10';element('tankHeight').handlers.input();
context.renderTank(sample);
assert.equal(element('tankHeight').value,'10','Polling must preserve edits');
(async()=>{
  await element('tankHeightForm').handlers.submit({preventDefault(){}});
  assert.equal(calls[0].url,'/api/iot/tank-height');
  assert.equal(calls[0].data.unit,'ft');assert.equal(calls[0].data.height,10);
  element('tankHeight').value='0';
  await element('tankHeightForm').handlers.submit({preventDefault(){}});
  assert.equal(calls.length,1);assert.equal(element('tankHeightError').hidden,false);
  context.renderTank({...sample,percent:null,water_depth_cm:null,float_value:null,status:'stale',warnings:['Stale']});
  assert.equal(element('tankFill').hidden,true);assert.equal(element('tankFloat').textContent,'Unknown');
  assert.equal(element('tankWarning').hidden,false);
  const controller=fs.readFileSync(path.join(root,'static/masterhub.js'),'utf8');
  const phaseFunction=controller.slice(controller.indexOf('function updatePhaseButtons()'),controller.indexOf('/* Every manual phase change'));
  Object.assign(context,{ui:{domain:'iot',phase:2,busy:false},currentDevice:()=>null,currentDomain:()=>null,currentCommand:()=>null});
  vm.runInContext(phaseFunction,context);
  context.updatePhaseButtons();assert.equal(element('tankMonitor').hidden,false);
  context.ui.phase=3;context.updatePhaseButtons();assert.equal(element('tankMonitor').hidden,false);
  context.ui.domain='desktop';context.updatePhaseButtons();assert.equal(element('tankMonitor').hidden,true);
  context.ui.domain='iot';context.ui.phase=1;context.updatePhaseButtons();assert.equal(element('tankMonitor').hidden,true);
  console.log('Tank UI: unit conversion, save, validation, stale state, draft preservation and domain visibility passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
