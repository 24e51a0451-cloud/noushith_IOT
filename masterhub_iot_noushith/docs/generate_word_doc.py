"""
Script to generate the complete, professional Word Document (.docx)
for Smart Ecosystem Architecture & Scenario Planning in Master Hub.
"""

import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

DOC_DIR = r"d:\GALATICX\masterhub_main\docs"
DIAG_DIR = os.path.join(DOC_DIR, "diagrams")
DOCX_PATH = os.path.join(DOC_DIR, "Smart_Ecosystem_Architecture_and_Scenario_Planning.docx")

def set_cell_background(cell, fill_hex):
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def add_callout(doc, text, title="NOTE"):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, "F1F5F9")
    set_cell_margins(cell, top=140, bottom=140, left=200, right=200)
    
    # Left border styling
    tcPr = cell._element.get_or_add_tcPr()
    borders = parse_xml(f'<w:tcBorders {nsdecls("w")}><w:top w:val="none"/><w:left w:val="single" w:sz="24" w:space="0" w:color="0284C7"/><w:bottom w:val="none"/><w:right w:val="none"/></w:tcBorders>')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run_title = p.add_run(f"[{title}] ")
    run_title.bold = True
    run_title.font.color.rgb = RGBColor(2, 132, 199)
    run_title.font.name = "Calibri"
    run_title.font.size = Pt(10)
    
    run_text = p.add_run(text)
    run_text.font.name = "Calibri"
    run_text.font.size = Pt(10)
    run_text.font.color.rgb = RGBColor(30, 41, 59)
    doc.add_paragraph() # Spacing

def format_table_headers(table, col_widths=None):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr_cells = table.rows[0].cells
    for idx, cell in enumerate(hdr_cells):
        set_cell_background(cell, "0F172A")
        set_cell_margins(cell, top=120, bottom=120, left=140, right=140)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.bold = True
            run.font.color.rgb = RGBColor(248, 250, 252)
            run.font.name = "Calibri"
            run.font.size = Pt(9.5)
            
    for row in table.rows[1:]:
        for idx, cell in enumerate(row.cells):
            set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
            p = cell.paragraphs[0]
            for run in p.runs:
                run.font.name = "Calibri"
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(51, 65, 85)

    if col_widths:
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = width

def build_docx():
    doc = Document()

    # Page setup
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Base Styles
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = RGBColor(30, 41, 59)
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(6)

    # ==========================================
    # COVER / TITLE BLOCK
    # ==========================================
    p_pre = doc.add_paragraph()
    p_pre.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_pre = p_pre.add_run("MASTER HUB TECHNICAL SPECIFICATION & RESEARCH REPORT")
    r_pre.font.size = Pt(10)
    r_pre.font.bold = True
    r_pre.font.color.rgb = RGBColor(2, 132, 199)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_title.add_run("Smart Ecosystem Architecture &\nScenario Planning")
    r_title.font.size = Pt(24)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(15, 23, 42)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_sub.add_run("Multi-Domain IoT Coordination, MQTT Concurrency Analysis, Execution Sequencing & Python Core Integration Blueprint")
    r_sub.font.size = Pt(12)
    r_sub.font.color.rgb = RGBColor(71, 85, 105)

    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_meta.paragraph_format.space_after = Pt(20)
    r_meta = p_meta.add_run("Author: Master Hub Core & IoT Team  |  Status: Final Deliverable  |  Version: 2.0")
    r_meta.font.size = Pt(9.5)
    r_meta.font.italic = True
    r_meta.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_page_break()

    # ==========================================
    # 1. EXECUTIVE SUMMARY & OBJECTIVES
    # ==========================================
    h1 = doc.add_heading("1. Executive Summary & Context", level=1)
    h1.style.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph(
        "Master Hub serves as an intelligent multimodal orchestrator that bridges Brain-Computer Interface (BCI) neural telemetry, "
        "IoT Smart Home Actuators, Embedded Mobility Systems (Wheelchair & Robotic Scout Car), and Desktop Automation Environments. "
        "As the system scales from single-device, single-command operations (e.g., 'turn on left light') into complex multi-domain smart ecosystem scenarios, "
        "a standardized architectural and coordination framework is required."
    )

    doc.add_paragraph(
        "This research deliverable addresses key technical requirements for multi-device orchestration: reviewing existing system architecture, "
        "defining device groupings, planning automation scenarios, optimizing MQTT concurrency flows, formalizing dependency execution sequences, "
        "and providing concrete schema contracts for the Python development team."
    )

    add_callout(
        doc,
        "Deliverable Target: Finalized smart ecosystem scenario definitions, asynchronous MQTT concurrency models, and IoT execution requirements for seamless Master Hub integration.",
        "GOAL"
    )

    # ==========================================
    # 2. REVIEW OF EXISTING IOT & MASTER HUB ARCHITECTURE
    # ==========================================
    h1 = doc.add_heading("2. Review of Existing IoT & Master Hub Architecture", level=1)
    h1.style.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph(
        "Master Hub's core engine employs a modular, pipeline-driven architecture consisting of four core decoupled layers:"
    )

    doc.add_paragraph(
        "1. Ingestion & Normalization Layer (core/input_processor.py): Ingests heterogeneous payloads (BCI raw EEG windows, recorded predictions, or direct REST API command strings) and normalizes them into standard command tokens using mappings/gesture_map.json.\n"
        "2. State & Mode Management Layer (core/state.py): Thread-safe Finite State Machine (FSM) maintaining operational contexts (IDLE, IOT_MODE, DESKTOP_MODE, EMBEDDED_MODE, MEDIA_MODE, CHAIR_MODE, CAR_MODE) dynamically populated from mappings/mode_map.json.\n"
        "3. Router & Execution Engine (core/router.py & core/engine.py): Performs non-blocking dictionary lookups against mappings/command_map.json to resolve domain and action targets without hardcoded if/else branches.\n"
        "4. IoT Action Handler (actions/iot/handler.py & services/mqtt_service.py): Wraps action payloads in JSON envelopes ({\"command\": \"...\", \"command_id\": \"...\"}) and publishes them over MQTT topic iot/device/{device_id}/action to broker host 52.21.249.6:1883."
    )

    # Insert Architecture Diagram
    img_arch = os.path.join(DIAG_DIR, "arch_flowchart.png")
    if os.path.exists(img_arch):
        doc.add_paragraph()
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.add_run().add_picture(img_arch, width=Inches(6.2))
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_cap = p_cap.add_run("Figure 1: Master Hub End-to-End Multimodal System Architecture Flowchart")
        r_cap.font.size = Pt(9)
        r_cap.font.italic = True
        r_cap.font.color.rgb = RGBColor(71, 85, 105)

    doc.add_heading("2.1 Architectural Bottlenecks Identified in Current Implementation", level=2)
    doc.add_paragraph(
        "• Single-Device Bias: actions/iot/handler.py defaults to get_first_online_device(), lacking native support for multi-target fanout or broadcast addressing.\n"
        "• Synchronous Blocking Publish: MQTTService.publish() holds a mutex lock and synchronously waits on result.wait_for_publish(), causing N-device executions to block the calling thread for N x RTT.\n"
        "• Single-Action Dispatch Constraint: The current FSM processes one atomic command per cycle, requiring an orchestration layer to coordinate compound scenarios."
    )

    # ==========================================
    # 3. SMART HOME DEVICES IN MULTI-DOMAIN SCENARIOS
    # ==========================================
    h1 = doc.add_heading("3. Smart Home Devices & Multi-Domain Matrix", level=1)
    h1.style.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph(
        "The smart ecosystem spans four physical and virtual device domains that interact across complex scenarios:"
    )

    # Insert Topology Diagram
    img_top = os.path.join(DIAG_DIR, "device_topology.png")
    if os.path.exists(img_top):
        doc.add_paragraph()
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.add_run().add_picture(img_top, width=Inches(6.2))
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_cap = p_cap.add_run("Figure 2: Smart Ecosystem Multi-Domain Device Topology Matrix")
        r_cap.font.size = Pt(9)
        r_cap.font.italic = True
        r_cap.font.color.rgb = RGBColor(71, 85, 105)

    doc.add_paragraph("Table 1 outlines the complete hardware catalog and protocol interfaces across domains:")

    # Table 1: Device Catalog
    tbl_dev = doc.add_table(rows=7, cols=5)
    headers = ["Device Domain", "Device Identifier / Node", "Protocol", "Topic / Target", "Primary Capabilities"]
    for idx, name in enumerate(headers):
        tbl_dev.cell(0, idx).paragraphs[0].text = name

    dev_data = [
        ("IoT Appliances", "ESP32 Node A (ESP32_RELAY_01)", "MQTT (JSON)", "iot/device/{id}/action", "Left Light On/Off, Right Light On/Off"),
        ("IoT Climate", "ESP32 Node B (Ventilation)", "MQTT (JSON)", "iot/device/{id}/action", "Left Fan On/Off, Right Fan On/Off"),
        ("IoT Hydraulic", "ESP32 Relay Actuator", "MQTT (JSON)", "iot/device/{id}/action", "Left Pump On/Off, Pump Cutoff"),
        ("Embedded Mobility", "Smart Wheelchair (ESP32/ARM)", "MQTT (Raw)", "wheelchair/{id}/control", "CHAIRFORWARD, CHAIRBACKWARD, CHAIRSTOP"),
        ("Embedded Robotics", "Robotic Scout Car", "MQTT (Raw)", "robotcar/{id}/control", "LIFTCARFORWARD, LIFTCARSTOP, 360_TURNS"),
        ("Desktop / OS", "Windows Host Workstation", "PyAutoGUI IPC", "Local System", "Chrome Web Workspace, Notepad, Outlook SOS"),
    ]

    for row_idx, row in enumerate(dev_data, start=1):
        for col_idx, text in enumerate(row):
            tbl_dev.cell(row_idx, col_idx).paragraphs[0].text = text

    format_table_headers(tbl_dev, [Inches(1.2), Inches(1.5), Inches(1.0), Inches(1.4), Inches(1.4)])
    doc.add_paragraph()

    # ==========================================
    # 4. GROUPED DEVICE CONTROL REQUIREMENTS
    # ==========================================
    h1 = doc.add_heading("4. Grouped Device Control Requirements", level=1)
    h1.style.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph(
        "To manage multiple devices seamlessly, the ecosystem requires three distinct grouping paradigms:\n"
        "1. Spatial Grouping (Zone-Based): Encapsulates devices co-located in a physical space (e.g., Zone_Desk containing Left Light, Left Fan, and Host Display; Zone_Room containing all ambient lights and fans).\n"
        "2. Functional Grouping (Subsystem Clusters): Encapsulates devices sharing operational types across different zones (e.g., Group_All_Lights, Group_Climate, Group_Mobility).\n"
        "3. Dynamic / Scenario Grouping: Ad-hoc sets assembled at runtime to execute specific routines (e.g., Set_Workstation_Active, Set_Emergency_Halt)."
    )

    doc.add_heading("4.1 Core Execution Requirements for Group Control", level=2)
    doc.add_paragraph(
        "• Atomic Multi-Device Dispatch: A single high-level command trigger must initiate parallel fanout across all target hardware nodes without serial delay.\n"
        "• Aggregated Acknowledgment (Group ACK): Master Hub must collect ACKs on iot/device/+/ack and return an aggregated receipt (COMPLETED or PARTIAL_SUCCESS with degraded node metrics).\n"
        "• Fault Isolation & Non-Blocking Resilience: If 1 out of 4 grouped devices is unreachable or powered down, the remaining 3 devices must execute immediately without pipeline timeout."
    )

    # ==========================================
    # 5. AUTOMATION SCENARIOS INVOLVING MULTIPLE IOT DEVICES
    # ==========================================
    h1 = doc.add_heading("5. Automation Scenarios & Multi-Device Execution", level=1)
    h1.style.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph(
        "Five comprehensive production scenarios have been designed and finalized for Master Hub integration:"
    )

    # Insert Sequence Diagram
    img_seq = os.path.join(DIAG_DIR, "scenario_sequence.png")
    if os.path.exists(img_seq):
        doc.add_paragraph()
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.add_run().add_picture(img_seq, width=Inches(6.2))
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_cap = p_cap.add_run("Figure 3: Multi-Domain Scenario Execution Flowchart (Workstation Focus Mode)")
        r_cap.font.size = Pt(9)
        r_cap.font.italic = True
        r_cap.font.color.rgb = RGBColor(71, 85, 105)

    doc.add_heading("5.1 Scenario Detailed Specifications", level=2)

    scenarios = [
        ("Scenario 1: Workstation Focus & Productivity Mode",
         "Trigger: BCI Gesture 'push' from IDLE or API payload {'scenario': 'focus_mode'}.\n"
         "Flow: (1) FSM transitions to DESKTOP_MODE. (2) IoT layer dispatches parallel Left_light_on and Left_fan_on. (3) Desktop layer sequentially launches Chrome dashboard and Notepad editor.\n"
         "Outcome: Immediate workstation illumination, cooling comfort, and active desktop productivity environment."),
        
        ("Scenario 2: Night / Sleep Mode (All-Off & Security Lock)",
         "Trigger: BCI Long Neutral gesture or Dashboard button 'Night Mode'.\n"
         "Flow: (1) IoT broadcast turns off all lights (Left_light_off, Right_light_off, pump_off) and sets fan to low quiet mode. (2) Mobility layer sends hard stops (CHAIRSTOP, LIFTCARSTOP) and engages electronic brakes. (3) AI/ML media paused, audio muted, host display locked.\n"
         "Outcome: Complete dark state, safety lockdown, quiet climate, zero battery drain."),
        
        ("Scenario 3: Smart Mobility Pathway (Dynamic Illumination)",
         "Trigger: Wheelchair forward command (chair_forward).\n"
         "Flow: (1) Pre-condition check verifies corridor lights ON. (2) Dispatch CHAIRFORWARD over MQTT. (3) Continuous sonar telemetry check on iot/device/+/sensor (auto-halts if obstacle < 30cm).\n"
         "Outcome: Dynamic illuminated pathway ensuring collision-free mobility navigation."),
        
        ("Scenario 4: Emergency Safety Interlock (Fall / Panic / Collision)",
         "Trigger: High-confidence BCI distress state, crash sensor alert, or UI SOS button.\n"
         "Flow: (1) Priority 0: Immediate zero-velocity cutoff (CHAIRSTOP, LIFTCARSTOP). (2) Priority 1: All lights to 100% illuminance, water pumps cut off. (3) Priority 2: Audible PC siren engaged and SOS dispatch email sent via Outlook.\n"
         "Outcome: Immediate vehicle arrest in < 100ms, maximum situational visibility, automated alert dispatch."),
        
        ("Scenario 5: Environmental Microclimate Regulation",
         "Trigger: Telemetry threshold breach (Temperature > 32°C or Soil Moisture < 20%).\n"
         "Flow: (1) Background evaluator activates Left_fan_on and Right_fan_on. (2) 1.5s delay to prevent inrush electrical surge. (3) Turn on pump_on for 15s irrigation/cooling cycle, followed by automatic pump_off.\n"
         "Outcome: Autonomous climate stabilization without requiring manual user intervention.")
    ]

    for title, desc in scenarios:
        p = doc.add_paragraph()
        r_t = p.add_run(title + "\n")
        r_t.bold = True
        r_t.font.color.rgb = RGBColor(15, 23, 42)
        p.add_run(desc)

    # ==========================================
    # 6. MQTT COMMUNICATION FLOW FOR SIMULTANEOUS OPERATIONS
    # ==========================================
    h1 = doc.add_heading("6. MQTT Communication Flow for Simultaneous Operations", level=1)
    h1.style.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph(
        "Executing simultaneous multi-device operations over MQTT requires an optimized topic hierarchy and non-blocking asynchronous publisher architecture."
    )

    # Insert MQTT Concurrency Diagram
    img_mqtt = os.path.join(DIAG_DIR, "mqtt_concurrency.png")
    if os.path.exists(img_mqtt):
        doc.add_paragraph()
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.add_run().add_picture(img_mqtt, width=Inches(6.2))
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_cap = p_cap.add_run("Figure 4: Asynchronous Multi-Topic MQTT Concurrency & Fan-Out Architecture")
        r_cap.font.size = Pt(9)
        r_cap.font.italic = True
        r_cap.font.color.rgb = RGBColor(71, 85, 105)

    doc.add_heading("6.1 Standardized Topic Architecture", level=2)

    # Table 2: MQTT Topics
    tbl_top = doc.add_table(rows=6, cols=4)
    headers_top = ["Topic Channel", "Target Level", "Payload Format", "QoS & Purpose"]
    for idx, name in enumerate(headers_top):
        tbl_top.cell(0, idx).paragraphs[0].text = name

    top_data = [
        ("iot/device/{device_id}/action", "Unicast Node", "{\"command\": \"Left_light_on\", \"command_id\": \"a1b2\"}", "QoS 1 — Direct device actuation"),
        ("iot/group/{group_id}/action", "Multicast Group", "{\"group_command\": \"all_lights_on\", \"command_id\": \"c3d4\"}", "QoS 1 — Simultaneous zone control"),
        ("iot/broadcast/all/action", "Global Broadcast", "{\"command\": \"EMERGENCY_STOP\", \"command_id\": \"e5f6\"}", "QoS 2 — Preemptive system-wide halt"),
        ("iot/device/{device_id}/ack", "Feedback Channel", "{\"command_id\": \"a1b2\", \"status\": \"OK\"}", "QoS 1 — Device state confirmation"),
        ("iot/device/{device_id}/sensor", "Telemetry Feed", "{\"temp\": 28.4, \"humidity\": 65, \"distance_cm\": 120}", "QoS 0 — High-frequency sensor feed")
    ]

    for row_idx, row in enumerate(top_data, start=1):
        for col_idx, text in enumerate(row):
            tbl_top.cell(row_idx, col_idx).paragraphs[0].text = text

    format_table_headers(tbl_top, [Inches(1.8), Inches(1.2), Inches(2.2), Inches(1.3)])
    doc.add_paragraph()

    # ==========================================
    # 7. DEVICE DEPENDENCIES & EXECUTION SEQUENCES
    # ==========================================
    h1 = doc.add_heading("7. Device Dependencies & Execution Sequences", level=1)
    h1.style.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph(
        "Complex smart ecosystem routines require strict dependency management to ensure safety, avoid electrical overload, and maintain state coherence."
    )

    # Insert Dependency Tree Diagram
    img_dep = os.path.join(DIAG_DIR, "dependency_tree.png")
    if os.path.exists(img_dep):
        doc.add_paragraph()
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.add_run().add_picture(img_dep, width=Inches(6.2))
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_cap = p_cap.add_run("Figure 5: Device Dependency, Safety Interlock & Execution Flow Decision Tree")
        r_cap.font.size = Pt(9)
        r_cap.font.italic = True
        r_cap.font.color.rgb = RGBColor(71, 85, 105)

    doc.add_paragraph(
        "Execution paradigms are classified into four distinct operational rules:\n"
        "1. Parallel Independent (Fork-Join): Actions execute concurrently at t=0 without inter-device blocking (e.g., Left Light ON + Fan ON).\n"
        "2. Strict Sequential Pipeline (with Verification): Action B is blocked until Device A returns status ACK_OK (e.g., Verify Door Open before Wheelchair Moves).\n"
        "3. Delayed Staggered Dispatch: High-power inductive actuators are staggered by 500ms–1500ms to eliminate inrush current spikes on shared electrical rails (e.g., Fan ON -> 1.0s delay -> Pump ON).\n"
        "4. Preemptive Safety Overrides: High-priority events immediately preempt normal execution queues and trigger hard motor halts in < 100ms."
    )

    # ==========================================
    # 8. PYTHON TEAM COORDINATION & IMPLEMENTATION BLUEPRINT
    # ==========================================
    h1 = doc.add_heading("8. Python Team Coordination & Implementation Blueprint", level=1)
    h1.style.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph(
        "To enable seamless implementation by the Python Core development team, the following deliverables and integration contracts are finalized:"
    )

    doc.add_heading("8.1 Declarative Schema: mappings/scenarios.json", level=2)
    doc.add_paragraph(
        "Scenarios must be configured declaratively to ensure zero code modification when adding new multi-device routines:"
    )

    schema_sample = (
        "{\n"
        '  "scenarios": {\n'
        '    "focus_mode": {\n'
        '      "name": "Workstation Focus Mode",\n'
        '      "target_mode": "DESKTOP_MODE",\n'
        '      "steps": [\n'
        '        { "domain": "iot", "action": "left_light_on", "execution": "parallel" },\n'
        '        { "domain": "iot", "action": "left_fan_on", "execution": "parallel" },\n'
        '        { "domain": "desktop", "action": "open_chrome", "execution": "sequential", "delay_ms": 200 },\n'
        '        { "domain": "desktop", "action": "open_notepad", "execution": "sequential", "delay_ms": 500 }\n'
        '      ]\n'
        '    }\n'
        '  }\n'
        '}'
    )
    p_code = doc.add_paragraph()
    p_code.paragraph_format.left_indent = Inches(0.4)
    r_c = p_code.add_run(schema_sample)
    r_c.font.name = "Consolas"
    r_c.font.size = Pt(8.5)
    r_c.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_heading("8.2 Extended REST API Endpoints (api/routes.py)", level=2)
    doc.add_paragraph(
        "• POST /api/scenario/run — Executes a scenario routine by ID ({'scenario_id': 'focus_mode'}).\n"
        "• GET /api/scenarios — Returns all registered scenarios and execution metadata.\n"
        "• POST /api/group/action — Dispatches an ad-hoc action across an array of target devices.\n"
        "• GET /api/iot/devices — Returns live online device registry and telemetry status."
    )

    doc.add_heading("8.3 Scenario Orchestrator Module (core/scenario_runner.py)", level=2)
    doc.add_paragraph(
        "A dedicated ScenarioRunner class will handle step iteration, dispatch parallel actions via ThreadPoolExecutor, "
        "manage sequential interlock timers, and generate aggregated execution receipts with individual device statuses."
    )

    # Save Document
    doc.save(DOCX_PATH)
    print(f"Document successfully created at: {DOCX_PATH}")

if __name__ == "__main__":
    build_docx()
