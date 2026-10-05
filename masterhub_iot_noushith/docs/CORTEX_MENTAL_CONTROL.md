# Cortex mental control

Start MasterHub with `python app.py`, then open `/cortex/` or the headset panel
on `/dashboard`. Use the app's Connect button so the headset worker, manual
controls, and mental commands share the same MasterHub process and FSM.
`python run_cortex.py` is a separate diagnostic process; it cannot be armed
from a different running MasterHub process.

## Connect and operate

1. Open EMOTIV Launcher, sign in, power on the headset, and connect from Cortex.
2. Approve EMOTIV access if prompted. Select and load a trained profile.
3. Wait for fresh mental-command samples, then enable control.
4. Return to neutral for at least 0.25 seconds to arm the next command.
5. Hold the desired trained mental command above the configured minimum power
   for at least 0.35 seconds. A held command executes at most once until neutral.

The screen shows the available mappings for the current FSM mode:

- Main menu: Push = Desktop; Pull = Embedded Mobility; Left = IoT; Right = AI/Media.
- Domain menu: select the desired application/device using the displayed command.
- Device menu: execute its displayed actions with the same MasterHub handlers
  used by manual controls.
- Push, neutral, Right = Back; Push, neutral, Left = Main menu.
- JioSaavn: Right, neutral, Push = Volume up; Right, neutral, Pull = Volume down.

Prefixes used by combinations wait for the temporal window configured in
MasterHub (default 4 seconds). The screen shows the pending gesture and countdown.
Other mapped gestures execute after their hold period. Unassigned combinations
cancel rather than executing their prefix. Changing mode or target, pausing,
losing the stream, or re-enabling control cancels pending input.

For mobility, hold the direction through any countdown. Returning to neutral
sends Stop; Pause and a detected stream loss also request Stop. Releasing a
pending direction before execution cancels movement. This is application-level
control, not a replacement for the device's own watchdog or physical stop.

## Text and other action inputs

Navigate to the appropriate device, pause control, expand **Prepare command
inputs**, and save its query, filename, or compose fields. Re-enable control
and return to neutral before executing the mental command. Missing inputs
produce a visible failure without invoking the handler. Inputs are held in
server memory and must be prepared again after restarting MasterHub.

This provides mental navigation and the existing mapped actions in every domain.
It does not add mental text entry or invent mappings for the extra manual-only
buttons. The existing manual workflow and mappings remain available.

## Backend

- `cortex/control.py` assembles live gestures and calls the existing
  `InputProcessor` and `Engine` in process. It does not retry physical actions
  over HTTP.
- `cortex/run_live.py` publishes samples independently of command execution.
- `/cortex/events` includes the active workflow, pending selection, parameters,
  and execution result. `/cortex/workflow` exposes the same workflow and accepts
  command inputs only while control is paused.
- `cortex/dashboard.py` uses a reentrant lock for nested result logging, avoiding
  the previous deadlock. Freshness is checked by the backend, even without a UI.
- The separate simulator's HTTP pipeline is unchanged.

Command power is Cortex's `com` power value, not calibrated confidence. A
successful handler response means MasterHub accepted the operation; it is not
proof of physical completion. Device acknowledgement remains transport-specific.

Profile switching follows EMOTIV's [setupProfile documentation](https://emotiv.gitbook.io/cortex-api/bci/setupprofile):
unload an existing profile owned by this application before loading a different
one. Profiles loaded by another application must be unloaded there first.
Failed profile discovery does not reuse an unverified cached profile.

## Verification

Run the isolated regression checks:

```powershell
python -m pytest tests/test_cortex_control.py tests/test_bci_panel.py tests/test_bci_workflow.py tests/test_workflow.py tests/test_command_updates.py tests/test_embedded_mappings.py -q -p no:cacheprovider
node --check static/bci-panel.js
```

These tests mock device handlers and exercise actual gesture normalization,
FSM transitions, routing, and Cortex endpoints. They do not connect to a live
headset or actuate hardware. Confirm profile recognition, power/hold tuning,
device acknowledgements, and mobility stop behavior on connected hardware.
