"""
Generates high-resolution diagrams including the updated USB-to-TTL, udev, and desktop registration architecture.
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches

DIAG_DIR = r"d:\GALATICX\masterhub_main\docs\diagrams"
os.makedirs(DIAG_DIR, exist_ok=True)

def save_fig(fig, filename):
    path = os.path.join(DIAG_DIR, filename)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"Saved: {path}")

def generate_raspi5_serial_arch():
    fig, ax = plt.subplots(figsize=(16, 9.0), facecolor="#F8FAFC")
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9.0)
    ax.axis("off")

    ax.text(8.0, 8.6, "Raspberry Pi 5 (udev) <-> Desktop (COM Auto-Registration) via USB-to-TTL Serial Bridge", 
            ha="center", va="center", fontsize=14.5, fontweight="bold", color="#0F172A")

    def draw_box(x, y, w, h, title, subtitle, color, text_color="#0F172A", border_color=None):
        border = border_color or color
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.15",
                                      facecolor=color, edgecolor=border, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h*0.65, title, ha="center", va="center", fontsize=9.5, fontweight="bold", color=text_color)
        if subtitle:
            ax.text(x + w/2, y + h*0.30, subtitle, ha="center", va="center", fontsize=7.8, color=text_color)

    def draw_arrow(x1, y1, x2, y2, label="", color="#475569"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", lw=2, color=color, shrinkA=4, shrinkB=4))
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.12, label, ha="center", va="bottom", fontsize=7.8, color="#1E293B", fontweight="bold")

    # Left: Raspberry Pi 5
    pi_box = patches.FancyBboxPatch((0.4, 0.6), 4.5, 7.6, boxstyle="round,pad=0.15,rounding_size=0.2",
                                    facecolor="#FDF4FF", edgecolor="#C026D3", linewidth=2.0)
    ax.add_patch(pi_box)
    ax.text(2.65, 7.9, "RASPBERRY PI 5 (LINUX EDGE HUB)", ha="center", va="center", fontsize=11, fontweight="bold", color="#701A75")
    ax.text(2.65, 7.55, "udev Persistent Symlink: /dev/masterhub_serial", ha="center", va="center", fontsize=8, color="#86198F")

    draw_box(0.7, 6.1, 3.9, 1.2, "udev Rule Daemon (systemd)", "SUBSYSTEM=='tty', ATTRS{idVendor}=='10c4'\nSYMLINK+='masterhub_serial', MODE='0666'", "#FAF5FF", "#701A75", "#E879F9")
    draw_box(0.7, 4.6, 3.9, 1.2, "Pi 5 UART0 / GPIO Pinout", "Pin 8 (GPIO 14 - TXD) | Pin 10 (GPIO 15 - RXD)\nPin 6 (GND - Common Reference Rail)", "#FAF5FF", "#701A75", "#E879F9")
    draw_box(0.7, 3.1, 3.9, 1.2, "Edge AI/ML Pre-Processor", "BCI 128Hz Ingestion -> ONNX Feature Extract\nSliding FFT Bandpass (4-30Hz Beta/Mu)", "#FAF5FF", "#701A75", "#E879F9")
    draw_box(0.7, 1.3, 3.9, 1.5, "PySerial Daemon (FreeRTOS Core 3)", "COBS / Binary Framed Protocol (921.6k Baud)\nRingBuffer RX/TX with DMA Interrupt Support", "#FAE8FF", "#86198F", "#D946EF")

    # Middle: USB-to-TTL Hardware Adapter & Wiring
    ttl_box = patches.FancyBboxPatch((5.4, 1.2), 5.2, 6.4, boxstyle="round,pad=0.15,rounding_size=0.2",
                                     facecolor="#FEF3C7", edgecolor="#F59E0B", linewidth=2.0)
    ax.add_patch(ttl_box)
    ax.text(8.0, 7.3, "USB-TO-TTL ADAPTER & PINOUT WIRING", ha="center", va="center", fontsize=10.5, fontweight="bold", color="#92400E")
    ax.text(8.0, 6.95, "CP2102 / FT232RL / CH340 Bridge (921,600 Baud)", ha="center", va="center", fontsize=8.0, color="#B45309")

    draw_box(5.7, 5.2, 4.6, 1.5, "Physical Cross-Over Pinout Matrix", "• Adapter TXD -> Pi 5 RXD (GPIO 15 / Pin 10)\n• Adapter RXD -> Pi 5 TXD (GPIO 14 / Pin 8)\n• Adapter GND -> Pi 5 GND (Pin 6 Common)\n• VCC 5V/3.3V: Left Disconnected (No Back-feed)", "#FFFBEB", "#92400E", "#FCD34D")

    draw_box(5.7, 3.3, 4.6, 1.6, "Binary Framed Packet Protocol", "[SOF: 0xAA 0x55] [LEN: 2B] [SEQ: 2B]\n[DOMAIN: 1B] [CMD: 2B] [PAYLOAD: N Bytes]\n[CRC16-CCITT: 2B] [EOF: 0x0D 0x0A]\nPacket Transit Time: ~0.69ms at 921.6k Baud", "#FFFBEB", "#92400E", "#FCD34D")

    draw_box(5.7, 1.6, 4.6, 1.4, "Electrical & Signal Characteristics", "• 3.3V LVTTL Logic Levels (Direct Pi 5 Safety)\n• Max Slew Rate: 1 Mbps | Bit Time: 1.085 us\n• Parity: None (8N1) | Buffer: 1024 Bytes Ring", "#FFFBEB", "#92400E", "#FCD34D")

    # Right: Desktop Workstation
    pc_box = patches.FancyBboxPatch((11.1, 0.6), 4.5, 7.6, boxstyle="round,pad=0.15,rounding_size=0.2",
                                    facecolor="#F0F9FF", edgecolor="#0284C7", linewidth=2.0)
    ax.add_patch(pc_box)
    ax.text(13.35, 7.9, "DESKTOP WORKSTATION (WINDOWS HOST)", ha="center", va="center", fontsize=11, fontweight="bold", color="#0369A1")
    ax.text(13.35, 7.55, "Dynamic COM Port Discovery & HWID Registration", ha="center", va="center", fontsize=8, color="#0284C7")

    draw_box(11.4, 6.1, 3.9, 1.2, "Desktop Port Registration Module", "Auto-Scans VID:PID (e.g. 10C4:EA60 CP2102)\nRegisters Active COM Port into config.py / .env", "#E0F2FE", "#0369A1", "#38BDF8")
    draw_box(11.4, 4.6, 3.9, 1.2, "Desktop Master Hub Engine", "FSM State / Router / Priority Arbiter (P0-P3)\nDynamic Scenario Orchestrator (scenarios.json)", "#E0F2FE", "#0369A1", "#38BDF8")
    draw_box(11.4, 3.1, 3.9, 1.2, "High-Compute AI/ML Pipeline", "Emotiv Cortex Suite / Deep Neural Classifiers\nMultimodal Prediction Fusion Engine", "#E0F2FE", "#0369A1", "#38BDF8")
    draw_box(11.4, 1.3, 3.9, 1.5, "Multi-Threaded Serial Manager", "Dedicated TX Worker & RX Parser Threads\nAuto-Reconnect Watchdog on COM Disconnect", "#BAE6FD", "#075985", "#0284C7")

    # Inter-block connections
    draw_arrow(4.9, 5.0, 5.4, 5.0, "Telemetry TX", "#9333EA")
    draw_arrow(5.4, 4.2, 4.9, 4.2, "Control RX", "#2563EB")
    draw_arrow(10.6, 5.0, 11.1, 5.0, "Telemetry RX", "#9333EA")
    draw_arrow(11.1, 4.2, 10.6, 4.2, "Control TX", "#2563EB")

    save_fig(fig, "raspi5_desktop_serial_arch.png")

if __name__ == "__main__":
    generate_raspi5_serial_arch()

