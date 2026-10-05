# MasterHub Complete User Guide

Welcome to **MasterHub** — the unified Brain-Computer Interface (BCI), IoT Automation, Desktop Agent, and Robotics Control Center.

---

## 1. System Overview

MasterHub connects your EMOTIV Cortex BCI Headset and manual controls to 4 primary execution domains:

```
                  ┌──────────────────────────────┐
                  │      🧠 EMOTIV CORTEX BCI    │
                  │   (Push, Pull, Left, Right)  │
                  └──────────────┬───────────────┘
                                 │
                   ┌─────────────▼─────────────┐
                   │    ⚡ MasterHub Console   │
                   │    (/dashboard · FSM)     │
                   └─────────────┬─────────────┘
          ┌──────────────┬───────┴───────┬──────────────┐
          │              │               │              │
    ┌─────▼─────┐  ┌─────▼─────┐   ┌─────▼─────┐  ┌─────▼─────┐
    │   🏠 IoT  │  │ 💻 PC Agt │   │ 🤖 Mobility│ │ 🧠 AI / ML│
    │  Relays & │  │  Chrome,  │   │ Robot Car,│  │  Voice,   │
    │  Sensors  │  │  Media    │   │Wheelchair │  │ Pipeline  │
    └───────────┘  └───────────┘   └───────────┘  └───────────┘
```

---

## 2. Fast Start Guide

### Step 1: Launch MasterHub Server
```powershell
python app.py
```
Open **[http://localhost:5000/dashboard](http://localhost:5000/dashboard)** in your web browser.

### Step 2: Connect BCI Headset
1. Start **EMOTIV Launcher** on your PC and power on your headset (Insight, Epoc, Epoc X, Epoc+).
2. Click the **`[BCI]`** pill in the top header or open the sidebar and select **BCI Headset Setup** (or press `B`).
3. Click **Connect Headset** and approve access in the EMOTIV Launcher if prompted.
4. Select your trained profile from the dropdown and click **Load Selected Profile**.
5. Click **Enable Control** to allow mental commands to operate the workflow.

---

## 3. Mental Command & Navigation Mapping

| Mental Gesture | Arrow Key | Action in Domain Selection (01) | Action in Device Selection (02) | Action in Mobility Mode (Car/Chair) |
| :--- | :--- | :--- | :--- | :--- |
| **Push** | `↑ Up` | Select Highlighted Domain | Confirm & Select Device | Move Forward / Accelerate |
| **Pull** | `↓ Down` | Step Back | Back to Domain Selection | Move Reverse / Stop |
| **Left** | `← Left` | Navigate to Previous Domain | Navigate Previous Device | Turn Left / Steer Left |
| **Right** | `→ Right` | Navigate to Next Domain | Navigate Next Device | Turn Right / Steer Right |
| **Neutral** | Space / Relax | Rest state (resets hold) | Rest state | Idle / Stop motion |

### Ordered Combinations:
- **Left + Right (`← + →`)**: Stop Action (Robot Car & Wheelchair)
- **Pull + Left (`↓ + ←`)**: Left 360 Spin (Robot Car & Wheelchair)
- **Pull + Right (`↓ + →`)**: Right 360 Spin (Robot Car & Wheelchair)
- **Push + Right (`↑ + →`)**: Quick Back one level (Return)
- **Push + Left (`↑ + ←`)**: Return to Main Menu / Domain Selection
- **Right + Push (`→ + ↑`)**: Volume Up (Media Domain)
- **Right + Pull (`→ + ↓`)**: Volume Down (Media Domain)

### AI/ML Phase 2 Device Selection:
- **Push (`↑ Up`)**: Mobile JioSaavn
- **Pull (`↓ Down`)**: Desktop JioSaavn

---

## 4. Safety & Temporal Window Controls

- **Temporal Hold Window (2s / 4s / 8s)**:
  Commands require steady mental focus for the configured duration before execution triggers.
- **Immediate Abort**:
  Relaxing to **Neutral** or pressing `Esc` cancels any pending command before it sends.
- **Emergency Stop (🛑 E-Stop)**:
  Accessible in the left sidebar drawer — instantly terminates all robotics motors, wheelchair motion, and active PC automations.

---

## 5. Transports & Protocols

- **MQTT (Default)**: Publishes to topic `masterhub/commands` with JSON payloads.
- **UART / Serial**: Connects via USB serial cable (115200 baud) for direct microcontrollers (ESP32, Arduino).
- **PC Agent (`agent_H`)**: Background automation runner executing desktop tasks on target machines.
