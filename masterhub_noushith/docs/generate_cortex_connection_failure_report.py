"""
MasterHub Cortex Connection Architecture, Fluctuation & Failure Report Generator
-------------------------------------------------------------------------------
Generates a comprehensive, enterprise-grade Word Document (.docx) report covering:
1. Full Architecture of the Emotiv BCI to MasterHub Cortex Connection
2. Layer-by-layer Telemetry & Communication Flow
3. Analysis of Connection Fluctuations & Signal Instability (Physics to Protocol)
4. Live Diagnostic Incident Report & Log Analysis
5. Step-by-Step Remediation & Setup Guide
"""

import os
import sys
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

DOC_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(DOC_DIR)
OUTPUT_DOCX_ROOT = os.path.join(REPO_ROOT, "MasterHub_Cortex_Connection_Architecture_and_Failure_Report.docx")
OUTPUT_DOCX_DOCS = os.path.join(DOC_DIR, "MasterHub_Cortex_Connection_Architecture_and_Failure_Report.docx")


# ---------------------------------------------------------------------------
# Styling Helper Functions
# ---------------------------------------------------------------------------

def set_cell_background(cell, fill_hex):
    """Sets the background hex color for a table cell."""
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=120, bottom=120, left=150, right=150):
    """Sets internal padding (margins in dxa) for a table cell."""
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def add_callout(doc, text, title="NOTE", callout_type="info"):
    """
    Renders an executive styled callout box with a thick colored left accent bar.
    Types: 'info' (Blue), 'warning' (Amber), 'danger' (Red), 'success' (Emerald)
    """
    colors = {
        "info": {"bg": "F0F9FF", "border": "0284C7", "title": RGBColor(2, 132, 199)},
        "warning": {"bg": "FFFBEB", "border": "D97706", "title": RGBColor(217, 119, 6)},
        "danger": {"bg": "FEF2F2", "border": "DC2626", "title": RGBColor(220, 38, 38)},
        "success": {"bg": "F0FDF4", "border": "16A34A", "title": RGBColor(22, 163, 74)},
        "arch": {"bg": "F8FAFC", "border": "0F172A", "title": RGBColor(15, 23, 42)}
    }
    cfg = colors.get(callout_type, colors["info"])

    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, cfg["bg"])
    set_cell_margins(cell, top=140, bottom=140, left=200, right=160)

    tcPr = cell._element.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:left w:val="single" w:sz="36" w:space="0" w:color="{cfg["border"]}"/>'
        f'<w:top w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'<w:bottom w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(4)
    run_t = p.add_run(f"[{title.upper()}] ")
    run_t.bold = True
    run_t.font.name = 'Calibri'
    run_t.font.size = Pt(10.5)
    run_t.font.color.rgb = cfg["title"]

    run_body = p.add_run(text)
    run_body.font.name = 'Calibri'
    run_body.font.size = Pt(10)
    run_body.font.color.rgb = RGBColor(51, 65, 85)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

def add_styled_table(doc, headers, rows_data, col_widths=None):
    """Creates a beautifully formatted modern table."""
    tbl = doc.add_table(rows=len(rows_data) + 1, cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    # Format Header Row
    hdr_cells = tbl.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "0F172A")
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=140, right=140)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.font.bold = True
            run.font.name = 'Calibri'
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(255, 255, 255)

    # Format Data Rows
    for r_idx, row in enumerate(rows_data):
        row_cells = tbl.rows[r_idx + 1].cells
        bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row):
            row_cells[c_idx].text = str(val)
            set_cell_background(row_cells[c_idx], bg_color)
            set_cell_margins(row_cells[c_idx], top=100, bottom=100, left=140, right=140)
            p = row_cells[c_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.font.name = 'Calibri'
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(30, 41, 59)

    # Apply Borders
    for row in tbl.rows:
        for cell in row.cells:
            tcPr = cell._element.get_or_add_tcPr()
            b = parse_xml(
                f'<w:tcBorders {nsdecls("w")}>'
                f'<w:top w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
                f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
                f'<w:left w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
                f'<w:right w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
                f'</w:tcBorders>'
            )
            tcPr.append(b)

    # Apply Widths
    if col_widths:
        for row in tbl.rows:
            for c_idx, w in enumerate(col_widths):
                row.cells[c_idx].width = Inches(w)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

def add_heading_1(doc, text):
    h = doc.add_paragraph()
    h.paragraph_format.space_before = Pt(16)
    h.paragraph_format.space_after = Pt(6)
    h.paragraph_format.keep_with_next = True
    run = h.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(16)
    run.font.bold = True
    run.font.color.rgb = RGBColor(15, 23, 42)
    return h

def add_heading_2(doc, text):
    h = doc.add_paragraph()
    h.paragraph_format.space_before = Pt(12)
    h.paragraph_format.space_after = Pt(4)
    h.paragraph_format.keep_with_next = True
    run = h.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(13)
    run.font.bold = True
    run.font.color.rgb = RGBColor(30, 41, 59)
    return h

def add_paragraph(doc, text, bold_prefix=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = 'Calibri'
        r_pre.font.size = Pt(10)
        r_pre.font.bold = True
        r_pre.font.color.rgb = RGBColor(15, 23, 42)
    r = p.add_run(text)
    r.font.name = 'Calibri'
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor(51, 65, 85)
    return p

def add_code_block(doc, code_text):
    """Renders a code or log snippet box."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, "1E293B")
    set_cell_margins(cell, top=100, bottom=100, left=140, right=140)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(code_text.strip())
    run.font.name = 'Consolas'
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(226, 232, 240)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)


# ---------------------------------------------------------------------------
# Report Generation Logic
# ---------------------------------------------------------------------------

def generate_report():
    doc = Document()

    # Configure Margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # -----------------------------------------------------------------------
    # Document Header / Banner
    # -----------------------------------------------------------------------
    header_tbl = doc.add_table(rows=1, cols=1)
    header_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    h_cell = header_tbl.cell(0, 0)
    h_cell.width = Inches(6.5)
    set_cell_background(h_cell, "0F172A")
    set_cell_margins(h_cell, top=200, bottom=200, left=200, right=200)

    hp = h_cell.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = hp.add_run("MASTERHUB BCI CORTEX INTEGRATION\n")
    r_title.font.name = 'Calibri'
    r_title.font.size = Pt(20)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(255, 255, 255)

    r_sub = hp.add_run("System Architecture, Signal Fluctuation Analysis & Failure Diagnostic Report\n")
    r_sub.font.name = 'Calibri'
    r_sub.font.size = Pt(12)
    r_sub.font.color.rgb = RGBColor(148, 163, 184)

    r_meta = hp.add_run("Target: Emotiv EPOC X Headset | Interface: Cortex v2 API (WSS JSON-RPC 2.0) | Host: MasterHub Engine")
    r_meta.font.name = 'Calibri'
    r_meta.font.size = Pt(9.5)
    r_meta.font.color.rgb = RGBColor(56, 189, 248)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -----------------------------------------------------------------------
    # 1. Executive Summary
    # -----------------------------------------------------------------------
    add_heading_1(doc, "1. Executive Summary")
    add_paragraph(
        doc,
        "MasterHub incorporates a real-time Brain-Computer Interface (BCI) subsystem designed to connect with an Emotiv EPOC X headset via the Emotiv Cortex v2 API. The subsystem receives live mental commands, cognitive metrics, and contact-quality diagnostics to drive multimodal actuation across Robotics, IoT Smart Home, and Assisted Living domains."
    )
    add_paragraph(
        doc,
        "Live diagnostic monitoring reveals that the Cortex connection is currently stalled in a continuous reconnection loop. While the underlying Secure WebSocket transport (wss://localhost:6868) handshakes successfully, authentication is halted at the authorization stage because the application access has not been approved in the EMOTIV Launcher and the environment configuration contains placeholder credentials. This document details the end-to-end architecture, analyzes the sources of physical and protocol connection fluctuations, presents the empirical failure trace, and provides the step-by-step remediation plan."
    )

    add_callout(
        doc,
        "Current Status: WebSocket transport active; Authorization BLOCKED due to unapproved Client ID and placeholder secret in .env. Live BCI telemetry ingestion is suspended until authorization is completed.",
        title="SYSTEM STATUS SUMMARY",
        callout_type="danger"
    )

    # -----------------------------------------------------------------------
    # 2. Cortex Connection Architecture
    # -----------------------------------------------------------------------
    add_heading_1(doc, "2. End-to-End Cortex Connection Architecture")
    add_paragraph(
        doc,
        "The connection between the Emotiv EPOC X headset and MasterHub spans five distinct layers, bridging biological neural signals to robotic and IoT domain actuators:"
    )

    arch_headers = ["Layer", "Module / Component", "Protocol / Physical Medium", "Functional Responsibility"]
    arch_data = [
        ["1. Physical / Scalp", "Emotiv EPOC X Electrodes", "14 Saline Felt Pads + 2 Mastoids", "Microvolt EEG capture, 128/256Hz ADC sampling"],
        ["2. Wireless Transport", "2.4 GHz RF / BLE Receiver", "Proprietary RF / Bluetooth USB Dongle", "Wireless packet transmission from headset to Host PC"],
        ["3. Emotiv Daemon", "EMOTIV Launcher / Cortex Service", "wss://localhost:6868 (JSON-RPC 2.0)", "Driver layer, signal decryption, FFT & ML classification"],
        ["4. MasterHub Client", "cortex/cortex_client.py & auth.py", "Secure WebSocket Client (WSS)", "RPC calls, ping/pong heartbeats, token refresh, sessions"],
        ["5. Stream & Gating", "cortex/stream.py & control.py", "Thread Queue & Normalized Schema", "Ingests 'com' stream, neutral-release gating, FSM dispatch"],
        ["6. Core Execution", "core/engine.py & core/state.py", "Internal MasterHub Router", "Translates gestures (Push, Pull, Left, Right) to domain actions"]
    ]
    add_styled_table(doc, arch_headers, arch_data, [1.2, 1.6, 1.6, 2.1])

    add_heading_2(doc, "2.1 Detailed Handshake & Connection Lifecycle")
    add_paragraph(
        doc,
        "The connection is orchestrated by the LiveRunner worker thread (cortex/run_live.py) following a strict 7-phase sequence:"
    )
    add_paragraph(doc, "1. WebSocket Connection: Establishes a TLS-encrypted WebSocket to wss://localhost:6868 with VERIFY_SSL=False (accommodating Emotiv's local self-signed certificate).")
    add_paragraph(doc, "2. Access Verification (requestAccess): Verifies that MasterHub's Client ID has been granted access by the user in the EMOTIV Launcher.")
    add_paragraph(doc, "3. Authorization (authorize): Exchanges the Client ID, Client Secret, and license key for a temporary bearer cortexToken (with a 6-hour soft TTL auto-refresh).")
    add_paragraph(doc, "4. Headset Discovery & Rescan: Queries visible headsets via queryHeadsets; executes controlDevice(command='refresh') if no headset is initially detected.")
    add_paragraph(doc, "5. Headset Pairing: Issues controlDevice(command='connect', headset=id) to establish the active RF bond.")
    add_paragraph(doc, "6. Session Creation & Stale Eviction: Opens an active session (createSession). If a previous crashed session locked the device (-32002 error), MasterHub inspects querySessions and evicts stale locks automatically.")
    add_paragraph(doc, "7. Telemetry Subscription: Subscribes to the Mental Command stream (subscribe(streams=['com'])). Incoming packets at 10-20 Hz are converted into NormalizedPrediction objects.")

    # -----------------------------------------------------------------------
    # 3. Fluctuation & Signal Instability Analysis
    # -----------------------------------------------------------------------
    add_heading_1(doc, "3. Complete Signal Fluctuation & Instability Analysis")
    add_paragraph(
        doc,
        "Users of BCI headsets frequently experience intermittent signal drops or delayed response times. These fluctuations originate across five distinct physical and algorithmic boundaries:"
    )

    fluct_headers = ["Instability Tier", "Root Mechanism", "System Impact", "Engineering Mitigation in MasterHub"]
    fluct_data = [
        ["Tier 1: Electrode Contact", "Saline felt pads drying out or poor scalp contact (>10 kOhm impedance)", "Signal quality drops; Cortex ML defaults to 'neutral' or low confidence", "Periodic 'dev' diagnostics monitoring; signal quality warnings on dashboard"],
        ["Tier 2: Wireless RF Noise", "USB 3.0 unshielded port radiation & 2.4GHz Wi-Fi congestion", "Headset state flips between 'connected' and 'discovered'; packet loss", "Use USB 2.0 port or extension cable; automatic connection pooling with 4s rescan"],
        ["Tier 3: Daemon Lockouts", "Ungraceful disconnect leaves session locked in Cortex daemon for 60s", "createSession rejected with error -32002 ('headset already in use')", "Automatic stale session query and eviction implemented in cortex/session.py"],
        ["Tier 4: Token Expiration", "Cortex tokens silently expire without machine-readable timestamps", "RPC calls suddenly fail with authentication errors", "CortexAuth proactive 6-hour soft-TTL refresh and auto-recovery thread"],
        ["Tier 5: Algorithmic Gating", "Rapid back-to-back mental commands without relaxation", "Commands dropped by stabilizer to prevent accidental runaway execution", "Neutral-Release Gating (>=0.25s neutral) and Command Hold (>=0.35s sustained hold)"]
    ]
    add_styled_table(doc, fluct_headers, fluct_data, [1.3, 1.7, 1.7, 1.8])

    add_callout(
        doc,
        "Crucial Operational Rule: BCI mental control requires the user to return to 'neutral' (relaxation) for at least 0.25 seconds between consecutive actions. Holding a continuous 'Push' will intentionally not trigger repetitive selections in MasterHub's safety state machine.",
        title="OPERATIONAL GATING REQUIREMENT",
        callout_type="warning"
    )

    # -----------------------------------------------------------------------
    # 4. Live Failure Incident Report & Evidence
    # -----------------------------------------------------------------------
    add_heading_1(doc, "4. Live Connection Failure Incident Report")
    add_paragraph(
        doc,
        "Empirical examination of the live runtime logs (cortex/logs/cortex.log) reveals that the system is currently failing at the authentication stage. Below is the exact diagnostic trace extracted from the active server:"
    )

    log_snippet = (
        "2026-09-24 09:55:58 | INFO     | cortex.cortex_client | Connected to Cortex at wss://localhost:6868\n"
        "2026-09-24 09:55:58 | DEBUG    | cortex.cortex_client | -> requestAccess (id=438) params={'clientId': '4peZxtpflilSEnDpunLvBCOImDBQOnsFkFeJzgZS', 'clientSecret': 'TEST_SECRET_KEY_XYZ_456'}\n"
        "2026-09-24 09:55:58 | DEBUG    | cortex.cortex_client | <- requestAccess (id=438) OK\n"
        "2026-09-24 09:55:58 | WARNING  | cortex.auth          | Cortex access NOT yet granted: The user has not granted access right to this application. Please use EMOTIV Launcher to proceed.\n"
        "2026-09-24 09:55:58 | WARNING  | cortex.run_live      | Cortex unavailable: Cortex access has not been granted for this CLIENT_ID. Open the EMOTIV Launcher/App, approve the access request popup for this application, then retry.\n"
        "2026-09-24 09:55:58 | INFO     | cortex.cortex_client | Cortex client closed"
    )
    add_code_block(doc, log_snippet)

    add_heading_2(doc, "4.1 Detailed Breakdown of Failure Causes")
    add_paragraph(
        doc,
        "1. Unapproved Application in EMOTIV Launcher: The requestAccess JSON-RPC call returns accessGranted: false. The Emotiv Cortex security model mandates that the desktop user must explicitly click 'Approve' on the application authorization popup inside the EMOTIV Launcher GUI."
    )
    add_paragraph(
        doc,
        "2. Invalid / Placeholder Client Secret in .env: Inspection of the .env file shows CORTEX_CLIENT_SECRET=TEST_SECRET_KEY_XYZ_456. This dummy value prevents successful cryptographic token generation (authorize method) once access is requested."
    )
    add_paragraph(
        doc,
        "3. Fail-Fast Socket Tear-Down: When LiveRunner encounters CortexAuthError, it closes the socket and triggers a 5-second backoff. Because the approval remains unhandled in the Launcher, the connection enters an infinite connect -> requestAccess -> reject -> close loop."
    )

    # -----------------------------------------------------------------------
    # 5. Step-by-Step Remediation Plan
    # -----------------------------------------------------------------------
    add_heading_1(doc, "5. Step-by-Step Remediation & Setup Guide")
    add_paragraph(
        doc,
        "To resolve the failure and achieve stable, live BCI telemetry streaming, follow these operational procedures in order:"
    )

    add_paragraph(doc, "Step 1: Retrieve Emotiv Developer Credentials", bold_prefix="• ")
    add_paragraph(doc, "Navigate to https://www.emotiv.com/my-account/cortex-apps/ in your browser. Create or select your application to copy your official Client ID and Client Secret.")

    add_paragraph(doc, "Step 2: Update the Environment Configuration (.env)", bold_prefix="• ")
    add_paragraph(doc, "Open the .env file in the MasterHub root directory and replace the placeholder values with your production credentials:")

    env_snippet = (
        "CORTEX_CLIENT_ID=your_real_emotiv_client_id\n"
        "CORTEX_CLIENT_SECRET=your_real_emotiv_client_secret\n"
        "CORTEX_URL=wss://localhost:6868\n"
        "CORTEX_VERIFY_SSL=false\n"
        "CORTEX_STREAM_NAME=com\n"
        "CORTEX_SESSION_STATUS=active\n"
        "BCI_CONFIDENCE_THRESHOLD=0.40"
    )
    add_code_block(doc, env_snippet)

    add_paragraph(doc, "Step 3: Authorize MasterHub in EMOTIV Launcher", bold_prefix="• ")
    add_paragraph(doc, "Launch the EMOTIV Launcher desktop application. Start MasterHub (python app.py). An access-request prompt will appear in the Launcher stating 'Application [App Name] is requesting access'. Click Approve.")

    add_paragraph(doc, "Step 4: Prepare and Hydrate the EPOC X Headset", bold_prefix="• ")
    add_paragraph(doc, "Ensure all 14 felt pads are saturated with saline solution. Fit the headset to ensure reference sensors (CMS/DRL) have solid contact against the mastoid bones. Verify green contact status in the EMOTIV Launcher.")

    add_paragraph(doc, "Step 5: Verify Live Ingestion via MasterHub Dashboard", bold_prefix="• ")
    add_paragraph(doc, "Open your web browser to http://127.0.0.1:5000/cortex/ or query http://127.0.0.1:5000/cortex/state to verify that status.connected=true, status.authorized=true, and live gestures are updating in real time.")

    # -----------------------------------------------------------------------
    # 6. Architectural Telemetry Schema Reference
    # -----------------------------------------------------------------------
    add_heading_1(doc, "6. Data Schema & Telemetry Reference")
    add_paragraph(
        doc,
        "The table below defines the mapping between raw Cortex JSON-RPC payloads and MasterHub's normalized internal telemetry schema:"
    )

    schema_headers = ["Field", "Raw Cortex Payload", "MasterHub Normalized Schema", "Description / Value Range"]
    schema_data = [
        ["Mental Command", "msg['com'][0]", "prediction.command / gesture", "Cognitive action: 'neutral', 'push', 'pull', 'left', 'right'"],
        ["Confidence Score", "msg['com'][1]", "prediction.confidence / power", "Normalized floating-point probability: 0.00 to 1.00"],
        ["Timestamp", "msg['time'] (Unix float)", "prediction.timestamp (ISO 8601)", "Universal UTC timestamp with microsecond resolution"],
        ["Session ID", "msg['sid'] (UUID string)", "prediction.session_id", "Unique session identifier assigned by Cortex daemon"],
        ["Battery Level", "msg['dev'][1] (Integer %)", "headset.battery_percent", "Headset battery percentage: 0% to 100%"],
        ["Signal Quality", "msg['dev'][3] (Float)", "headset.signal_quality", "Composite contact quality metric: 0.0 to 1.0 (Good > 0.8)"]
    ]
    add_styled_table(doc, schema_headers, schema_data, [1.3, 1.6, 1.8, 1.8])

    # Save Document
    doc.save(OUTPUT_DOCX_ROOT)
    doc.save(OUTPUT_DOCX_DOCS)
    print(f"Report successfully generated at:\n1. {OUTPUT_DOCX_ROOT}\n2. {OUTPUT_DOCX_DOCS}")

if __name__ == "__main__":
    generate_report()
