// The three phases deliberately keep selection separate from physical execution.
const workflowDevices = {
  python: {YouTube:['open_youtube','youtube_play','youtube_pause','youtube_next','youtube_previous'], Notepad:['open_notepad','save_notepad'], Chrome:['open_chrome','next_tab','previous_tab','close_chrome'], Gmail:['open_gmail']},
  embedded: {'Robot car':['car_forward','car_backward','car_left','car_right','car_left360','car_right360','car_stop'], Wheelchair:['chair_forward','chair_backward','chair_left','chair_right','chair_left360','chair_right360','chair_stop']},
  iot: {Light:['left_light_on','left_light_off'], Fan:['fan_on','fan_off'], Pump:['pump_on','pump_off']},
  aiml: {Media:['media_play','media_pause','media_next','media_previous','media_volume_up','media_volume_down']}
};
let workflowPhase=1, workflowDevice='';
const baseSwitchDomain=switchDomain;
switchDomain=function(domain){
  cancelFrame(); baseSwitchDomain(domain); workflowPhase=2; workflowDevice='';
  const select=document.getElementById('workflowDevice');
  select.replaceChildren(new Option('Select a device / application',''));
  Object.keys(workflowDevices[domain]).forEach(name=>select.add(new Option(name,name)));
  document.getElementById('workflowCommand').replaceChildren(new Option('Select a device first',''));
  document.getElementById('executeWorkflow').disabled=true;
  showPhase();
};
function showPhase(){
  ['stepSelection','stepControl','stepExecution'].forEach((id,i)=>document.getElementById(id).classList.toggle('active',i+1===workflowPhase));
  const descriptions=['Choose a domain to begin.','Choose a device or application.','Choose a command and execute.'];
  document.getElementById('workflowHint').textContent=`Phase ${workflowPhase} · ${descriptions[workflowPhase-1]}`;
  document.getElementById('guideTitle').textContent=['Domain selection','Device selection','Command execution'][workflowPhase-1];
  document.getElementById('guideDesc').textContent=workflowPhase===1?'Push: Desktop · Pull: Embedded · Left: IoT · Right: AI/ML':workflowPhase===2?'Choose a device in Phase 2. No command is sent during selection.':'Choose a command in Phase 3. Execute starts the framing timer; Stop is immediate.';
}
function selectWorkflowDevice(name){
  cancelFrame(); workflowDevice=name; workflowPhase=name?3:2;
  const select=document.getElementById('workflowCommand'); select.replaceChildren();
  (workflowDevices[appState.activeDomain][name]||[]).forEach(cmd=>select.add(new Option(cmd.replaceAll('_',' '),cmd)));
  document.getElementById('executeWorkflow').disabled=!name; showPhase();
  if(name&&appState.activeDomain==='embedded')fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:name==='Wheelchair'?'mode_chair':'mode_car'})}).catch(console.warn);
}
function executeWorkflow(){
  const cmd=document.getElementById('workflowCommand').value;
  if(workflowPhase!==3||!cmd)return;
  if(cmd.endsWith('_stop')){cancelFrame();dispatchDirectCommand(cmd);}else startTemporalFramingCountdown(cmd);
}
function cancelFrame(){
  if(framingInterval)clearInterval(framingInterval); framingInterval=null;
  document.getElementById('temporalWindowCard').classList.remove('framing-active');
  document.getElementById('btnCancelFraming').style.display='none';
  document.getElementById('framingStatusPill').textContent='STANDBY';
}
resetFsmState=function(){
  cancelFrame();workflowPhase=1;workflowDevice='';
  document.querySelectorAll('.domain-nav-tab,.domain-deck').forEach(el=>el.classList.remove('active'));
  document.getElementById('workflowDevice').replaceChildren(new Option('Choose a domain first',''));
  document.getElementById('workflowCommand').replaceChildren(new Option('Select a device first',''));
  document.getElementById('executeWorkflow').disabled=true;
  fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:'mode_idle'})}).catch(console.warn);
  showPhase();
};
const oldCombo=simulateComboTrigger;
simulateComboTrigger=function(){oldCombo();resetFsmState();};
simulateGesture=function(gesture){
  document.getElementById('cmdActionText').textContent=gesture.toUpperCase();
  if(gesture==='neutral')return;
  const index=['push','pull','left','right'].indexOf(gesture);
  if(index<0)return;
  if(workflowPhase===1){switchDomain(['python','embedded','iot','aiml'][index]);return;}
  if(workflowPhase===2){const name=Object.keys(workflowDevices[appState.activeDomain])[index];if(name){document.getElementById('workflowDevice').value=name;selectWorkflowDevice(name);}return;}
  const select=document.getElementById('workflowCommand');
  if(gesture==='left')select.selectedIndex=Math.max(0,select.selectedIndex-1);
  if(gesture==='right')select.selectedIndex=Math.min(select.length-1,select.selectedIndex+1);
  if(gesture==='push')executeWorkflow();
  if(gesture==='pull')cancelFrame();
};
toggleSidebar=function(){
  if(innerWidth>=1250){document.body.classList.toggle('sidebar-collapsed');return;}
  document.getElementById('sidebarDrawer').classList.toggle('open');
  document.getElementById('sidebarBackdrop').classList.toggle('open');
};
async function getJson(path,options){const response=await fetch(path,{signal:AbortSignal.timeout(9000),...options});const data=await response.json();if(!response.ok)throw Error(data.error||data.message||`HTTP ${response.status}`);return data;}
function badge(prefix,online,label){document.getElementById(prefix+'StatusText').textContent=label;document.getElementById(prefix+'Dot').className='status-dot '+(online?'dot-online':'dot-offline');}
async function refreshConnections(){
  await Promise.allSettled([
    (async()=>{try{const d=await getJson('/api/iot/status');badge('mqtt',d.mqtt_connected,d.mqtt_connected?'CONNECTED':'DISCONNECTED');document.getElementById('sideMqttStatus').textContent=d.mqtt_connected?'CONNECTED':'OFFLINE';const online=Object.entries(d.online_devices).some(([id,v])=>(id==='esp32'||(!v.domain&&v.states))&&v.status!=='OFFLINE'&&Date.now()/1000-(v._last_seen||0)<90);badge('esp32',online,online?'ONLINE':'NO HEARTBEAT');}catch{badge('mqtt',false,'UNAVAILABLE');badge('esp32',false,'UNKNOWN');document.getElementById('sideMqttStatus').textContent='UNAVAILABLE';}})(),
    (async()=>{try{const d=await getJson('/api/usb/status');badge('usb',d.connected,d.connected?(d.port||'CONNECTED'):'DISCONNECTED');document.getElementById('sideUartStatus').textContent=d.connected?(d.port||'CONNECTED'):'DISCONNECTED';}catch{badge('usb',false,'UNAVAILABLE');document.getElementById('sideUartStatus').textContent='UNAVAILABLE';}})(),
    (async()=>{try{const d=(await getJson('/cortex/state')).state;badge('cortex',d.status.connected,d.status.connected?'CONNECTED':'DISCONNECTED');document.getElementById('sideBciStatus').textContent=d.headset.id||'NO HEADSET';document.getElementById('headsetName').textContent=d.headset.id||'No headset connected';document.getElementById('cmdActionText').textContent=(d.metrics.current_gesture||'neutral').toUpperCase();const power=Math.max(0,Math.min(100,(d.metrics.confidence||0)*100));document.getElementById('cmdPowerPercent').textContent=power.toFixed(0)+'%';document.getElementById('cmdPowerFill').style.width=power+'%';}catch{badge('cortex',false,'UNAVAILABLE');document.getElementById('sideBciStatus').textContent='UNAVAILABLE';}})(),
    (async()=>{try{const d=await getJson('/api/state');document.getElementById('sideHealthStatus').textContent='API ONLINE';document.getElementById('sideActiveFsmMode').textContent=d.state.mode;}catch{document.getElementById('sideHealthStatus').textContent='API UNAVAILABLE';}})(),
    (async()=>{try{const d=await getJson('/api/embedded/status');document.getElementById('mobilityConnection').textContent=['robot_car','wheelchair'].map(k=>{const v=d[k];const alive=d.mqtt_connected&&v.online&&Date.now()/1000-v.last_seen<90;return `${k.replace('_',' ')}: ${alive?'ONLINE':v.status==='UNKNOWN'?'NO HEARTBEAT':v.status} · ACK: ${v.last_ack?JSON.stringify(v.last_ack):'none'}`;}).join(' | ');}catch{document.getElementById('mobilityConnection').textContent='Embedded status unavailable';}})()
  ]);
}
async function saveHardwareSettings(){
  const el=document.getElementById('hardwareFeedback');el.textContent='Saving and connecting…';
  try{const d=await getJson('/api/hardware/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({host:document.getElementById('cfgMqttBroker').value.trim(),port:document.getElementById('cfgMqttPort').value,car_topic:document.getElementById('cfgCarTopic').value.trim(),chair_topic:document.getElementById('cfgChairTopic').value.trim()})});el.textContent=d.connected?'Saved · MQTT connected. Waiting for device status.':'Saved · Broker unreachable. Check host, port and network.';await refreshConnections();}catch(e){el.textContent=e.message;}
}
document.addEventListener('DOMContentLoaded',async()=>{
  const info=document.createElement('p');info.id='mobilityConnection';info.style.cssText='margin-top:14px;font-size:12px;color:var(--text-secondary)';info.textContent='Checking embedded devices…';document.getElementById('connectionWidget').append(info);
  document.querySelectorAll('.domain-nav-tab,.domain-deck').forEach(el=>el.classList.remove('active'));showPhase();
  try{const d=await getJson('/api/hardware/config');for(const [id,key] of Object.entries({cfgMqttBroker:'host',cfgMqttPort:'port',cfgCarTopic:'car_topic',cfgChairTopic:'chair_topic'}))document.getElementById(id).value=d.config[key];}catch(e){document.getElementById('hardwareFeedback').textContent=e.message;}
  const poll=async()=>{await refreshConnections();setTimeout(poll,2500);};poll();
});
