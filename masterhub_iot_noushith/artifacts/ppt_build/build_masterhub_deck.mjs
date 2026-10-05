import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const workspaceDir = 'D:\\GALATICX\\masterhub_iot_noushith';
const SKILL_DIR = 'C:\\Users\\NOUSHITH\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.904.11930\\skills\\presentations';
const TMP_DIR = path.join(workspaceDir, 'artifacts', 'ppt_build');
const FINAL_PPTX = path.join(workspaceDir, 'artifacts', 'presentation_output', 'MasterHub_Implementation_Review_2026_v2.pptx');
const RUNTIME_PYTHON = 'C:\\Users\\NOUSHITH\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe';
const { makeNativeBulletParagraphs, finalizePresentation } = await import(pathToFileURL(path.join(SKILL_DIR, 'container_tools/artifact_tool_utils.mjs')).href);

const W = 960, H = 720;
const C = { green:'#0B7B3E', green2:'#3A9B45', pale:'#E8F1E4', pale2:'#F5F9F3', ink:'#1B2A21', gray:'#5A675D', gold:'#D3C58B', white:'#FFFFFF', line:'#BFD3B7', navy:'#101522', violet:'#6766F5', red:'#E24B4B' };
const FONT = 'Arial';
const p = Presentation.create({ slideSize: { width: W, height: H } });

function shape(slide, x, y, w, h, fill='none', line='none', geometry='rect', radius) {
  return slide.shapes.add({ geometry, position:{left:x,top:y,width:w,height:h}, fill, line:{fill:line,width:line==='none'?0:1.2}, ...(radius?{borderRadius:radius}:{}) });
}
function text(slide, value, x, y, w, h, size=18, color=C.ink, bold=false, align='left') {
  const s=shape(slide,x,y,w,h,'none','none','textbox'); s.text=value; s.text.style={typeface:FONT,fontSizePt:size,color,bold,autoFit:'shrinkText',textAlign:align,verticalAlignment:'middle'}; return s;
}
function bullets(slide, items, x, y, w, h, size=17, color=C.ink) {
  const s=shape(slide,x,y,w,h,'none','none','textbox'); s.text=makeNativeBulletParagraphs(items,{marginLeftPoints:16,hangingPoints:8,spaceAfterPoints:6}); s.text.style={typeface:FONT,fontSizePt:size,color,autoFit:'shrinkText'}; return s;
}
function header(slide, title, n) {
  slide.background.fill=C.white; shape(slide,0,0,W,42,C.green,C.green); text(slide,title.toUpperCase(),65,3,760,34,20,C.white,true,'center');
  shape(slide,844,0,72,74,C.pale,C.white); text(slide,'HITAM',849,12,62,28,12,C.green,true,'center'); text(slide,'MASTERHUB',849,41,62,16,8,C.green,false,'center');
  shape(slide,28,65,880,610,'none',C.line); text(slide,String(n).padStart(2,'0'),888,686,30,18,9,C.gray,false,'right');
}
function note(slide, value) { slide.speakerNotes.textFrame.setText(value); }
function callout(slide, label, body, x, y, w, h, accent=C.green) {
  shape(slide,x,y,w,h,C.pale2,C.line,'roundRect','rounded-lg'); text(slide,label.toUpperCase(),x+14,y+8,w-28,22,12,accent,true); text(slide,body,x+14,y+32,w-28,h-40,16,C.ink,false);
}
async function addImage(slide, file, x,y,w,h, fit='contain', alt='') { const blob=await fs.readFile(file); return slide.images.add({blob:new Uint8Array(blob),contentType:'image/png',alt,fit,position:{left:x,top:y,width:w,height:h},geometry:'roundRect',borderRadius:'rounded-lg'}); }

// 1 Cover
{
 const s=p.slides.add(); s.background.fill=C.green; shape(s,48,48,864,620,'none',C.white); shape(s,62,62,836,592,'none',C.white); text(s,'HYDERABAD INSTITUTE OF TECHNOLOGY\nAND MANAGEMENT',85,70,430,54,19,C.white,true);
 text(s,'MASTERHUB',85,177,490,70,42,C.gold,true); text(s,'BCI, IoT, Desktop and Mobility Control Platform',87,246,650,40,21,C.white,true);
 text(s,'IMPLEMENTATION REVIEW',87,340,360,30,21,C.white,true); text(s,'Current system architecture, dashboard and completed modules',87,378,610,52,18,C.white,false);
 text(s,'NOUSHITH  |  2451A051',87,502,420,30,19,C.white,true); text(s,'Project status deck · September 2026',87,540,420,22,13,C.white,false); text(s,'HITAM',768,83,100,34,20,C.white,true,'center');
 note(s,'Template style based on the user-supplied noushith_IOT_ppt.pptx. Project facts sourced from the current MasterHub repository and live dashboard.');
}
// 2 Contents
{
 const s=p.slides.add(); header(s,'List of contents',2); bullets(s,['Project scope and implementation status','MasterHub architecture and command lifecycle','Four control domains and supported targets','EMOTIV Cortex BCI workflow','MQTT, USB and remote-agent connectivity','Current dashboard and observability','Safety controls, validation and testing','Current limitations and future work'],110,120,700,420,19); note(s,'Contents reflect the current repository implementation.');
}
// 3 Overview
{
 const s=p.slides.add(); header(s,'MasterHub project overview',3); text(s,'A single control layer translates manual input or EMOTIV mental commands into actions across software and physical devices.',90,95,780,58,22,C.green,true,'center');
 callout(s,'Input','Dashboard controls, arrow keys, HTTP requests, recorded predictions and live Cortex mental-command samples.',80,190,380,155);
 callout(s,'Control core','Input normalization, mode state, temporal framing, command validation and domain routing.',500,190,380,155);
 callout(s,'Outputs','Desktop applications, smart-home nodes, robot car, wheelchair and media controls.',80,380,380,155);
 callout(s,'Operating model','Manual-only use works locally. Hardware, broker and headset services are connected only when needed.',500,380,380,155);
 note(s,'Source: README.md and current project structure.');
}
// 4 progress
{
 const s=p.slides.add(); header(s,'Implementation progress',4); text(s,'The project has evolved from a single IoT prototype into a modular control hub.',84,92,790,42,22,C.green,true,'center');
 const rows=[['01','IoT prototype','ESP32 relay actions, sensor telemetry and MQTT command delivery'],['02','Unified routing','JSON mappings, validation, FSM modes and reusable domain handlers'],['03','Desktop and media','Chrome, YouTube, Notepad, Gmail and JioSaavn workflows'],['04','Mobility','Robot car and wheelchair commands through configurable MQTT topics'],['05','BCI integration','Cortex authentication, profile loading, live mental stream and temporal framing'],['06','Operational dashboard','Live status, metrics, activity records, device setup and telemetry export']];
 rows.forEach((r,i)=>{const y=150+i*74; text(s,r[0],95,y,48,42,18,C.green,true,'center'); text(s,r[1],155,y,220,28,17,C.ink,true); text(s,r[2],375,y,485,42,15,C.gray,false); if(i<5) shape(s,115,y+45,2,29,C.line,C.line);}); note(s,'Implementation sequence summarized from repository history reflected in current modules and documentation.');
}
// 5 architecture image
{
 const s=p.slides.add(); header(s,'System architecture',5); await addImage(s,path.join(workspaceDir,'docs','diagrams','arch_flowchart.png'),80,105,800,490,'contain','MasterHub architecture flowchart');
 text(s,'Inputs enter one stateful routing core, then dispatch through domain-specific handlers and transport services.',95,608,770,38,17,C.green,true,'center'); note(s,'Visual source: docs/diagrams/arch_flowchart.png.');
}
// 6 command lifecycle
{
 const s=p.slides.add(); header(s,'Command lifecycle',6); const steps=[['1','Capture','Manual, API or Cortex input'],['2','Normalize','Gesture and command vocabulary'],['3','Frame','Single or paired gesture window'],['4','Resolve','Mode-specific command mapping'],['5','Validate','Allowed command and required inputs'],['6','Dispatch','Desktop, MQTT, USB or media handler'],['7','Observe','Result, latency and activity record']];
 steps.forEach((r,i)=>{const x=63+i*125; shape(s,x,190,105,150,i%2?C.pale2:C.pale,C.line,'roundRect','rounded-lg'); shape(s,x+34,204,38,38,C.green,C.green,'ellipse'); text(s,r[0],x+35,205,35,35,20,C.white,true,'center'); text(s,r[1],x+8,253,89,28,15,C.green,true,'center'); text(s,r[2],x+10,292,85,44,13,C.ink,false,'center');});
 text(s,'Mode state changes the meaning of the same gesture. Push selects Desktop at the main menu, then selects a desktop application, then triggers an application command.',95,410,770,90,19,C.ink,false,'center'); callout(s,'Temporal behavior','Dashboard actions show a countdown and support Cancel or Execute Now. Live BCI keeps the original deadline even when a second gesture arrives.',140,530,680,90); note(s,'Sources: core/input_processor.py, core/engine.py, core/router.py, static/masterhub.js and cortex/control.py.');
}
// 7 four domains
{
 const s=p.slides.add(); header(s,'Four control domains',7); const domains=[['PYTHON / DESKTOP','Chrome, YouTube, Notepad and Gmail workflows','PUSH'],['EMBEDDED MOBILITY','Robot car and wheelchair control','PULL'],['IoT SMART HOME','Light, fan and pump actions','LEFT'],['AI/ML & MEDIA','JioSaavn playback and audio control','RIGHT']];
 domains.forEach((d,i)=>{const x=75+(i%2)*420,y=150+Math.floor(i/2)*220; shape(s,x,y,365,170,C.pale2,C.line,'roundRect','rounded-xl'); text(s,d[2],x+18,y+18,80,30,15,C.white,true,'center'); shape(s,x+15,y+15,86,36,C.green,C.green,'roundRect','rounded-lg'); text(s,d[0],x+20,y+65,325,30,19,C.green,true); text(s,d[1],x+20,y+105,325,46,17,C.ink,false);}); note(s,'Source: README.md, mappings/mode_map.json and dashboard domain cards.');
}
// 8 domain implementation detail
{
 const s=p.slides.add(); header(s,'Implemented domain capabilities',8); callout(s,'Desktop','Application-specific handlers open and control Chrome, YouTube, Notepad and Gmail. Local Host runs on the MasterHub PC. Remote targets require a compatible agent.',70,115,400,215);
 callout(s,'IoT and mobility','MQTT publishes smart-home payloads and configurable robot or wheelchair commands. Status and acknowledgements provide separate readiness signals.',490,115,400,215);
 callout(s,'Media','Desktop and mobile JioSaavn paths expose playback, search and audio controls. The mobile path reports phone presence and now-playing state.',70,365,400,190);
 callout(s,'Mappings','JSON files define modes, gestures, workflows and command routes. This keeps navigation and action vocabulary separate from transport code.',490,365,400,190); text(s,'Current startup report: 17 modes · 98 command routes · 23 IoT action payloads',135,600,690,30,18,C.green,true,'center'); note(s,'Runtime counts observed when the current Flask application started for this deck.');
}
// 9 BCI
{
 const s=p.slides.add(); header(s,'EMOTIV Cortex BCI implementation',9); await addImage(s,path.join(TMP_DIR,'dashboard-bci-current.png'),445,102,430,455,'cover','Current MasterHub Cortex BCI drawer');
 bullets(s,['Local WebSocket connection to the Cortex service','Credential storage, access authorization and session creation','Headset discovery and trained profile loading','Live com stream with action and detector power','Monitor mode before explicit control enablement','Neutral rearm and duplicate suppression','Single or paired gestures resolved in the current FSM mode'],82,125,330,400,16); text(s,'Default minimum detector power: 0.20',90,560,330,30,16,C.green,true,'center'); text(s,'Default temporal window: 4 seconds',90,596,330,30,16,C.green,true,'center'); note(s,'Sources: cortex/service.py, cortex/control.py, templates/bci_panel.html and live dashboard screenshot.');
}
// 10 BCI timing
{
 const s=p.slides.add(); header(s,'BCI temporal framing and safety',10); await addImage(s,path.join(workspaceDir,'docs','diagrams','scenario_sequence.png'),80,112,800,330,'contain','Scenario sequence diagram');
 callout(s,'Frame start','A qualifying active mental command starts one timing window. Repeated packets of the held gesture do not create repeated commands.',80,470,380,130);
 callout(s,'Resolution','A mapped second gesture can form a pair. Live BCI waits until the original deadline, then validates the current direction before motion dispatch.',500,470,380,130); note(s,'Sources: cortex/control.py, tests/test_cortex_control.py and docs/diagrams/scenario_sequence.png.');
}
// 11 connectivity
{
 const s=p.slides.add(); header(s,'Hardware and connectivity layer',11); callout(s,'MQTT','Broker host and port can come from the environment or saved hardware settings. IoT and mobility topics remain independently configurable.',70,115,390,160);
 callout(s,'USB serial','UART configuration discovers ports and uses a JSON-line envelope. The default baud rate is 115200 when pyserial is installed.',500,115,390,160);
 callout(s,'Remote PC agents','The dashboard registers target IDs and transports, but each remote computer still requires its compatible agent and heartbeat.',70,310,390,160);
 callout(s,'Cortex bridge','EMOTIV Launcher and the local Cortex service provide headset access, authorization, profile data and the live command stream.',500,310,390,160);
 text(s,'Connection state is separated from device readiness. Broker online, device heartbeat and command acknowledgement are different signals.',100,530,760,65,20,C.green,true,'center'); note(s,'Sources: services/mqtt_service.py, services/usb_service.py, services/hardware_config.py and README.md.');
}
// 12 dashboard main
{
 const s=p.slides.add(); header(s,'Current MasterHub dashboard',12); await addImage(s,path.join(TMP_DIR,'dashboard-current.png'),68,88,824,535,'cover','Current MasterHub dashboard'); text(s,'Live console showing connection state, BCI status, temporal observer and the four control domains.',95,625,770,28,14,C.gray,false,'center'); note(s,'Screenshot captured from the current local application at /dashboard on 26 September 2026. Offline hardware indicators reflect the capture environment, not missing implementation.');
}
// 13 dashboard functions
{
 const s=p.slides.add(); header(s,'Dashboard controls and observability',13); const items=[['Connection matrix','MQTT, USB, BCI and system status'],['Latency HUD','Response, processing, execution and recovery indicators'],['Temporal observer','Current phase, countdown, target and input source'],['Workflow navigation','Domain, device and command phases with back and main-menu gestures'],['Activity log','Command outcomes and operator-visible feedback'],['Telemetry export','Log, JSON and CSV output for analysis'],['Hardware setup','Broker settings, UART configuration and target registration'],['Safety controls','Monitor mode, cancel, Execute Now, FSM reset and E-Stop request']];
 items.forEach((r,i)=>{const x=75+(i%2)*420,y=105+Math.floor(i/2)*132; text(s,r[0],x,y,370,28,17,C.green,true); text(s,r[1],x,y+32,350,48,15,C.ink,false); shape(s,x,y+91,350,1,C.line,C.line);}); note(s,'Source: templates/dashboard.html and static/masterhub.js.');
}
// 14 safety
{
 const s=p.slides.add(); header(s,'Safety, validation and fault handling',14); bullets(s,['Command validator rejects unknown routes before handler execution','Mode-aware mappings prevent gestures from bypassing workflow context','BCI starts in monitor mode and requires control enablement','Pending dashboard commands can be cancelled before dispatch','Software E-Stop sends stop requests and clears pending work','Motion dispatch checks the current active direction','Activity and BCI logs record outcomes for diagnosis','Hardware still requires an independent physical stop and watchdog'],95,120,470,430,17);
 callout(s,'Important boundary','Simulation Mode changes dashboard state and logging. It does not guarantee that hardware actions are isolated.',600,150,260,150,C.red);
 callout(s,'Physical safety','A successful HTTP or MQTT response does not prove that an actuator stopped. Device acknowledgements and independent safety hardware remain necessary.',600,350,260,185,C.red); note(s,'Source: README.md safety notes and current service behavior.');
}
// 15 implementation structure
{
 const s=p.slides.add(); header(s,'Software implementation structure',15); const rows=[['core/','Input processor, engine, router, state and metrics'],['actions/','Desktop, IoT, embedded and media handlers'],['cortex/','Authentication, session, profile, stream and BCI control'],['services/','MQTT, USB, logging, validation, workflow and hardware settings'],['mappings/','Command, gesture, mode and workflow JSON definitions'],['templates/ + static/','Dashboard UI, BCI drawer, scripts and styles'],['simulator/','Recorded-prediction replay and filtering tools'],['tests/','BCI, workflow, mappings, hardware and logging tests']];
 rows.forEach((r,i)=>{const y=105+i*66; text(s,r[0],85,y,205,36,17,C.green,true); text(s,r[1],300,y,565,36,16,C.ink,false); shape(s,85,y+47,780,1,C.line,C.line);}); note(s,'Source: current repository structure.');
}
// 16 verification
{
 const s=p.slides.add(); header(s,'Verification and test coverage',16); callout(s,'BCI controller tests','Temporal window behavior, gesture pairs, neutral handling, retry paths and motion stability.',70,115,390,165);
 callout(s,'Workflow tests','State transitions, mappings, command updates, embedded routes and dashboard behavior.',500,115,390,165);
 callout(s,'Service tests','Hardware status, logging, media integration and manual-versus-BCI command records.',70,320,390,165);
 callout(s,'Replay tools','Recorded predictions can exercise HTTP command paths, while focused controller tests verify live BCI framing.',500,320,390,165);
 text(s,'Verification must distinguish software dispatch from physical execution. Hardware tests require isolated devices, acknowledgements and safe movement constraints.',100,545,760,70,19,C.green,true,'center'); note(s,'Source: tests/ directory and README.md testing guidance.');
}
// 17 outputs and limits
{
 const s=p.slides.add(); header(s,'Achieved outputs and current limits',17); callout(s,'Achieved','Unified dashboard and API\nFour routed control domains\nLive Cortex mental-command path\nTemporal single and paired gestures\nMQTT, serial and remote-target setup\nActivity logs and telemetry export',80,120,390,350);
 callout(s,'Current limits','External broker and firmware remain required\nRemote target registration does not install an agent\nSimulation Mode is not an execution sandbox\nCortex depends on trained profiles and vendor access\nPhysical E-Stop and watchdog remain external\nSome actions depend on an unlocked Windows desktop',500,120,380,350,C.red);
 text(s,'The current implementation provides a working orchestration layer. Deployment readiness depends on the connected hardware, credentials and safety system.',110,535,740,70,20,C.green,true,'center'); note(s,'Source: current repository and README.md limitations.');
}
// 18 next work
{
 const s=p.slides.add(); header(s,'Conclusion and future scope',18); callout(s,'Conclusion','MasterHub now combines the original IoT work with desktop automation, embedded mobility, media control and EMOTIV BCI. A single stateful workflow translates multiple input sources into validated domain actions.',75,125,420,260);
 callout(s,'Future scope','Add device-side watchdogs and signed acknowledgements\nPackage and document the remote PC agent\nCreate a true dry-run execution backend\nCalibrate BCI thresholds per user and profile\nAdd automated end-to-end hardware test rigs\nImprove deployment packaging and secret management',520,125,365,300);
 text(s,'The project has moved from hardware control experiments to a reusable human-to-device orchestration platform.',100,525,760,60,22,C.green,true,'center'); note(s,'Future work is based on gaps documented in the current repository.');
}
// 19 thanks
{
 const s=p.slides.add(); s.background.fill=C.green; shape(s,92,210,776,265,'none',C.white); shape(s,115,232,730,220,'none',C.white); text(s,'HITAM',145,250,125,38,18,C.white,true,'center'); text(s,'THANK YOU',280,303,500,72,42,C.gold,true,'center'); text(s,'MASTERHUB IMPLEMENTATION REVIEW',280,382,500,28,14,C.white,true,'center'); note(s,'Closing slide.');
}

await fs.mkdir(path.dirname(FINAL_PPTX),{recursive:true});
const stagingDir=path.join(workspaceDir,'artifacts','ppt_build','finalizer'); await fs.mkdir(stagingDir,{recursive:true});
const candidatePath=path.join(stagingDir,'candidate.pptx'); await (await PresentationFile.exportPptx(p)).save(candidatePath);
const requirements={explicitTotalSlideCount:19,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[]};
const result=await finalizePresentation({...requirements,workspaceDir,candidatePath,finalPath:FINAL_PPTX,pythonExecutable:RUNTIME_PYTHON,integrityValidatorPath:path.join(SKILL_DIR,'container_tools','inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL_DIR,'container_tools','inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','9144000,6858000','--validate-bullet-geometry','--validate-heading-fit'],requiredNativeTableOwnerSlides:[],fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,receiptPath:path.join(stagingDir,'MasterHub_Implementation_Review_2026_v2.validation.json')});
console.log(JSON.stringify(result,null,2));
