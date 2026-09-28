"""
Script to generate high-resolution architectural diagrams for Master Hub documentation.
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches

os.makedirs(r"d:\GALATICX\masterhub_main\docs\diagrams", exist_ok=True)
DIAG_DIR = r"d:\GALATICX\masterhub_main\docs\diagrams"

def save_fig(fig, filename):
    path = os.path.join(DIAG_DIR, filename)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"Saved: {path}")

# ==========================================
# 1. Architecture Flowchart
# ==========================================
def generate_arch_flowchart():
    fig, ax = plt.subplots(figsize=(14, 8), facecolor="#F8FAFC")
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis("off")

    # Title
    ax.text(7, 7.6, "Master Hub End-to-End System Architecture Flowchart", 
            ha="center", va="center", fontsize=16, fontweight="bold", color="#0F172A")

    # Box styles
    def draw_box(x, y, w, h, title, subtitle, color, text_color="#0F172A", border_color=None):
        border = border_color or color
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.15",
                                      facecolor=color, edgecolor=border, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h*0.62, title, ha="center", va="center", fontsize=10.5, fontweight="bold", color=text_color)
        if subtitle:
            ax.text(x + w/2, y + h*0.32, subtitle, ha="center", va="center", fontsize=8.5, color=text_color)

    def draw_arrow(x1, y1, x2, y2, label=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", lw=2, color="#475569", shrinkA=4, shrinkB=4))
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.15, label, ha="center", va="bottom", fontsize=8, color="#334155", fontweight="bold")

    # Column 1: Ingestion Sources
    draw_box(0.5, 5.2, 2.4, 1.2, "Emotiv Cortex BCI", "Live EEG / Predictions", "#E0F2FE", "#0369A1", "#38BDF8")
    draw_box(0.5, 3.6, 2.4, 1.2, "REST API / Web UI", "POST /api/command", "#E0F2FE", "#0369A1", "#38BDF8")
    draw_box(0.5, 2.0, 2.4, 1.2, "Replay Simulator", "Sample Signals / JSON", "#E0F2FE", "#0369A1", "#38BDF8")

    # Column 2: Input Normalization
    draw_box(3.6, 3.3, 2.4, 1.8, "Input Processor", "core/input_processor.py\nGesture Normalizer", "#FEF3C7", "#92400E", "#FBBF24")

    # Column 3: State Manager
    draw_box(6.7, 3.3, 2.4, 1.8, "State Manager (FSM)", "core/state.py\nmode_map.json", "#FEE2E2", "#991B1B", "#F87171")

    # Column 4: Router & Engine
    draw_box(9.8, 3.3, 2.4, 1.8, "Engine & Router", "core/engine.py & router.py\ncommand_map.json", "#EDE9FE", "#5B21B6", "#A78BFA")

    # Column 5: Domain Handlers (Right side)
    draw_box(10.5, 6.0, 3.0, 1.0, "IoT Handler (actions/iot)", "MQTT -> Lights, Fans, Pumps", "#DCFCE7", "#166534", "#4ADE80")
    draw_box(10.5, 4.7, 3.0, 1.0, "Embedded (actions/embedded)", "MQTT -> Wheelchair & Car", "#F3E8FF", "#6B21A8", "#C084FC")
    draw_box(10.5, 2.1, 3.0, 1.0, "Desktop (actions/desktop)", "PyAutoGUI -> Chrome, Apps", "#E0E7FF", "#3730A3", "#818CF8")
    draw_box(10.5, 0.8, 3.0, 1.0, "AI/ML (actions/ai_ml)", "Media Playback / AI Control", "#FFEDD5", "#9A3412", "#FB923C")

    # Connectors
    draw_arrow(2.9, 5.8, 3.6, 4.5)
    draw_arrow(2.9, 4.2, 3.6, 4.2)
    draw_arrow(2.9, 2.6, 3.6, 3.9)

    draw_arrow(6.0, 4.2, 6.7, 4.2, "Normalized")
    draw_arrow(9.1, 4.2, 9.8, 4.2, "Mode Context")

    draw_arrow(12.2, 4.0, 12.2, 6.0, "Domain: iot")
    draw_arrow(12.2, 4.0, 12.2, 4.7, "Domain: embedded")
    draw_arrow(12.2, 3.3, 12.2, 2.1, "Domain: desktop")
    draw_arrow(12.2, 3.3, 12.2, 0.8, "Domain: ai_ml")

    save_fig(fig, "arch_flowchart.png")

# ==========================================
# 2. Device Domain Topology
# ==========================================
def generate_device_topology():
    fig, ax = plt.subplots(figsize=(13, 8), facecolor="#F8FAFC")
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 8)
    ax.axis("off")

    ax.text(6.5, 7.6, "Smart Ecosystem Multi-Domain Device Topology", 
            ha="center", va="center", fontsize=16, fontweight="bold", color="#0F172A")

    # Central Hub
    hub_rect = patches.FancyBboxPatch((4.8, 3.2), 3.4, 1.6, boxstyle="round,pad=0.1,rounding_size=0.2",
                                      facecolor="#0F172A", edgecolor="#38BDF8", linewidth=2.5)
    ax.add_patch(hub_rect)
    ax.text(6.5, 4.2, "MASTER HUB CORE", ha="center", va="center", fontsize=13, fontweight="bold", color="#F8FAFC")
    ax.text(6.5, 3.6, "Central Routing & FSM Engine\nBroker: 52.21.249.6:1883", ha="center", va="center", fontsize=8.5, color="#94A3B8")

    # 4 Surrounding Domains
    def draw_domain_card(x, y, w, h, title, items, bg_color, header_color):
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.15",
                                      facecolor=bg_color, edgecolor="#CBD5E1", linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h - 0.35, title, ha="center", va="center", fontsize=11, fontweight="bold", color=header_color)
        for idx, itm in enumerate(items):
            ax.text(x + 0.2, y + h - 0.7 - (idx * 0.32), f"• {itm}", ha="left", va="center", fontsize=8.5, color="#334155")

    # Top Left: IoT Smart Home
    draw_domain_card(0.6, 4.5, 3.6, 2.6, "IoT Home Actuators (ESP32)", 
                     ["Left Light / Right Light (Relays)", "Left Fan / Right Fan (PWM)", "Submersible Water Pump", "DHT22 Environmental Sensor"],
                     "#F0FDF4", "#166534")

    # Bottom Left: Embedded Mobility
    draw_domain_card(0.6, 0.8, 3.6, 2.6, "Embedded Mobility Domain",
                     ["Smart Wheelchair (ESP32/ARM)", "Robotic Scout Car", "Collision Sonar Telemetry", "Docking Station Lock"],
                     "#FAF5FF", "#6B21A8")

    # Top Right: Desktop & Workstation
    draw_domain_card(8.8, 4.5, 3.6, 2.6, "Desktop / OS Domain",
                     ["Google Chrome (Web Dashboard)", "Notepad / IDE Workspace", "Outlook Email SOS Dispatch", "Calculator & Calendar Utilities"],
                     "#EFF6FF", "#1E40AF")

    # Bottom Right: Sensory & Neural
    draw_domain_card(8.8, 0.8, 3.6, 2.6, "Neural BCI & Sensory",
                     ["Emotiv Cortex Neural Stream", "EEG Window Signal Classifier", "Ambient Room Luminance", "Simulated Telemetry Feeds"],
                     "#FFF7ED", "#9A3412")

    # Arrows to central hub
    def draw_bi_arrow(x1, y1, x2, y2, label=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="<->", lw=1.8, color="#64748B", shrinkA=6, shrinkB=6))
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2, label, ha="center", va="center", fontsize=8, color="#475569",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="#FFFFFF", edgecolor="#CBD5E1", lw=0.8))

    draw_bi_arrow(4.2, 5.5, 5.2, 4.6, "MQTT JSON")
    draw_bi_arrow(4.2, 2.2, 5.2, 3.4, "MQTT Raw")
    draw_bi_arrow(8.8, 5.5, 7.8, 4.6, "PyAutoGUI IPC")
    draw_bi_arrow(8.8, 2.2, 7.8, 3.4, "WebSocket / HTTP")

    save_fig(fig, "device_topology.png")

# ==========================================
# 3. Scenario Execution Sequence (Swimlane Flowchart)
# ==========================================
def generate_scenario_sequence():
    fig, ax = plt.subplots(figsize=(14, 8), facecolor="#F8FAFC")
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis("off")

    ax.text(7, 7.6, "Multi-Domain Scenario Execution Flow (Focus Mode)", 
            ha="center", va="center", fontsize=15, fontweight="bold", color="#0F172A")

    # Swimlane columns
    columns = [
        ("User / BCI", 1.5, "#E2E8F0"),
        ("Master Hub Engine", 4.5, "#E2E8F0"),
        ("IoT Subsystem (MQTT)", 7.5, "#DCFCE7"),
        ("Desktop Subsystem", 10.5, "#E0E7FF"),
        ("Status & Verification", 13.0, "#FEF3C7")
    ]

    for name, x, col in columns:
        ax.axvline(x, color="#CBD5E1", linestyle="--", lw=1)
        ax.text(x, 7.1, name, ha="center", va="center", fontsize=10.5, fontweight="bold", color="#334155",
                bbox=dict(boxstyle="round,pad=0.3", facecolor=col, edgecolor="#94A3B8"))

    # Event Steps
    steps = [
        (1.5, 4.5, 6.2, "1. Gesture: 'push' (from IDLE)"),
        (4.5, 4.5, 5.4, "2. FSM switches to DESKTOP_MODE"),
        (4.5, 7.5, 4.6, "3. [Parallel] MQTT: Left_light_on & Left_fan_on"),
        (7.5, 4.5, 3.8, "4. Relay Nodes ACK (iot/device/+/ack)"),
        (4.5, 10.5, 3.0, "5. [Sequential] Launch Chrome & Notepad"),
        (10.5, 4.5, 2.2, "6. Windows Focus Confirmed"),
        (4.5, 13.0, 1.4, "7. Scenario Receipt: SUCCESS (Aggregated)")
    ]

    for x1, x2, y, text in steps:
        if x1 == x2: # Internal step
            rect = patches.FancyBboxPatch((x1-1.2, y-0.25), 2.4, 0.5, boxstyle="round,pad=0.05",
                                          facecolor="#F1F5F9", edgecolor="#64748B", lw=1)
            ax.add_patch(rect)
            ax.text(x1, y, text, ha="center", va="center", fontsize=8.5, fontweight="bold", color="#0F172A")
        else:
            ax.annotate("", xy=(x2, y), xytext=(x1, y),
                        arrowprops=dict(arrowstyle="->", lw=1.8, color="#2563EB", shrinkA=5, shrinkB=5))
            ax.text((x1+x2)/2, y + 0.18, text, ha="center", va="bottom", fontsize=8.5, color="#0F172A", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#FFFFFF", edgecolor="#E2E8F0"))

    save_fig(fig, "scenario_sequence.png")

# ==========================================
# 4. MQTT Communication Flow (Concurrency)
# ==========================================
def generate_mqtt_concurrency():
    fig, ax = plt.subplots(figsize=(13, 7.5), facecolor="#F8FAFC")
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7.5)
    ax.axis("off")

    ax.text(6.5, 7.1, "Optimized Asynchronous MQTT Communication Architecture", 
            ha="center", va="center", fontsize=15, fontweight="bold", color="#0F172A")

    # Engine
    rect_eng = patches.FancyBboxPatch((0.5, 2.5), 3.0, 3.2, boxstyle="round,pad=0.1",
                                      facecolor="#EDE9FE", edgecolor="#8B5CF6", lw=2)
    ax.add_patch(rect_eng)
    ax.text(2.0, 5.2, "MASTER HUB ENGINE", ha="center", va="center", fontsize=11, fontweight="bold", color="#4C1D95")
    ax.text(2.0, 4.4, "Async Publisher Pool\n(Non-Blocking Workers)\n\nCorrelation ID Tracking\nGroup Fan-Out Logic", 
            ha="center", va="center", fontsize=8.5, color="#5B21B6")

    # Broker
    rect_brk = patches.FancyBboxPatch((4.8, 2.0), 3.4, 4.2, boxstyle="round,pad=0.1",
                                      facecolor="#0F172A", edgecolor="#38BDF8", lw=2)
    ax.add_patch(rect_brk)
    ax.text(6.5, 5.7, "MQTT BROKER", ha="center", va="center", fontsize=12, fontweight="bold", color="#F8FAFC")
    ax.text(6.5, 5.2, "52.21.249.6:1883", ha="center", va="center", fontsize=9, color="#38BDF8")
    
    topics = [
        "iot/device/{id}/action (QoS 1)",
        "iot/group/{group}/action (QoS 1)",
        "iot/broadcast/all/action (QoS 2)",
        "iot/device/+/ack (Feedback)",
        "iot/device/+/sensor (Telemetry)"
    ]
    for idx, top in enumerate(topics):
        ax.text(6.5, 4.4 - (idx*0.5), top, ha="center", va="center", fontsize=8, color="#E2E8F0",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="#1E293B", edgecolor="#334155"))

    # Hardware Nodes (Right)
    nodes = [
        ("ESP32 Relay Node 1", "Left Light & Fan", 5.4, "#DCFCE7", "#166534"),
        ("ESP32 Relay Node 2", "Right Light & Pump", 4.1, "#DCFCE7", "#166534"),
        ("Smart Wheelchair", "Mobility Controller", 2.8, "#FAF5FF", "#6B21A8"),
        ("Robotic Scout Car", "Micro-Mobility Node", 1.5, "#FAF5FF", "#6B21A8"),
    ]

    for title, sub, y, bg, border in nodes:
        rect = patches.FancyBboxPatch((9.5, y-0.45), 3.0, 0.9, boxstyle="round,pad=0.08",
                                      facecolor=bg, edgecolor=border, lw=1.5)
        ax.add_patch(rect)
        ax.text(11.0, y + 0.12, title, ha="center", va="center", fontsize=9.5, fontweight="bold", color=border)
        ax.text(11.0, y - 0.18, sub, ha="center", va="center", fontsize=8, color="#475569")

        # Arrows from broker to nodes
        ax.annotate("", xy=(9.5, y), xytext=(8.2, y),
                    arrowprops=dict(arrowstyle="<->", lw=1.5, color="#64748B", shrinkA=2, shrinkB=2))

    # Arrow from Engine to Broker
    ax.annotate("", xy=(4.8, 4.1), xytext=(3.5, 4.1),
                arrowprops=dict(arrowstyle="<->", lw=2.2, color="#7C3AED", shrinkA=4, shrinkB=4))
    ax.text(4.15, 4.4, "Parallel\nPub/Sub", ha="center", va="center", fontsize=8.5, fontweight="bold", color="#6D28D9")

    save_fig(fig, "mqtt_concurrency.png")

# ==========================================
# 5. Dependency & Interlock Decision Tree
# ==========================================
def generate_dependency_tree():
    fig, ax = plt.subplots(figsize=(13, 7.5), facecolor="#F8FAFC")
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7.5)
    ax.axis("off")

    ax.text(6.5, 7.1, "Device Dependency & Safety Interlock Decision Tree", 
            ha="center", va="center", fontsize=15, fontweight="bold", color="#0F172A")

    def draw_node(x, y, w, h, title, subtitle, bg, border, shape="round"):
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle=f"{shape},pad=0.1",
                                      facecolor=bg, edgecolor=border, lw=1.5)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h*0.62, title, ha="center", va="center", fontsize=9.5, fontweight="bold", color="#0F172A")
        if subtitle:
            ax.text(x + w/2, y + h*0.3, subtitle, ha="center", va="center", fontsize=8, color="#475569")

    # Start Event
    draw_node(0.6, 3.2, 2.2, 1.4, "Command Received", "e.g. chair_forward", "#E0F2FE", "#0284C7")

    # Decision 1: Safety Interlock Check
    draw_node(3.6, 3.2, 2.6, 1.4, "Safety Check", "Obstacle < 30cm or SOS?", "#FEF3C7", "#D97706")

    # Branch A: Safety Hazard
    draw_node(7.2, 5.0, 2.8, 1.4, "PREEMPTIVE STOP", "Zero-Velocity Lock\nAlarm & Max Lights", "#FEE2E2", "#DC2626")

    # Branch B: Normal Flow -> Pre-condition check
    draw_node(7.2, 2.0, 2.8, 1.4, "Pre-Conditions", "Pathway Illuminance\n& Door Position", "#E0E7FF", "#4338CA")

    # Execution branches
    draw_node(10.8, 3.4, 1.8, 1.2, "Parallel Exec", "Lights ON\nFans ON", "#DCFCE7", "#166534")
    draw_node(10.8, 1.0, 1.8, 1.2, "Delayed Exec", "Wheelchair Roll\n(after 500ms)", "#FAF5FF", "#7E22CE")

    # Connectors
    def connect(x1, y1, x2, y2, label=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", lw=1.8, color="#475569", shrinkA=4, shrinkB=4))
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.15, label, ha="center", va="bottom", fontsize=8, fontweight="bold", color="#0F172A")

    connect(2.8, 3.9, 3.6, 3.9)
    connect(6.2, 4.3, 7.2, 5.5, "Hazard Detected")
    connect(6.2, 3.5, 7.2, 2.7, "Clear / Safe")

    connect(10.0, 2.9, 10.8, 3.8, "Lighting")
    connect(10.0, 2.3, 10.8, 1.6, "Motion")

    save_fig(fig, "dependency_tree.png")

if __name__ == "__main__":
    generate_arch_flowchart()
    generate_device_topology()
    generate_scenario_sequence()
    generate_mqtt_concurrency()
    generate_dependency_tree()
    print("All diagrams generated successfully!")
