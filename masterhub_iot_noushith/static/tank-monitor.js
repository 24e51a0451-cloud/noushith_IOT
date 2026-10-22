/* Tank monitoring shares the dashboard status poll; it never sends device commands. */
var tankSaving = false;
var tankFormLoaded = false;
var tankFormDirty = false;
var tankPreviousUnit = 'cm';

function tankNumber(value) { return Number(value.toFixed(2)).toLocaleString(); }

function renderTank(tank) {
  if (!tank || !byId('tankMonitor')) return;
  var config = tank.config;
  if (!tankFormLoaded && !tankFormDirty) {
    byId('tankHeight').value = config.height == null ? '' : config.height;
    byId('tankUnit').value = config.unit;
    tankPreviousUnit = config.unit;
    tankFormLoaded = true;
  }
  var percent = tank.percent;
  var label = percent == null ? '—' : tankNumber(percent) + '%';
  text('tankPercent', label);
  text('tankLevelValue', label);
  var fill = byId('tankFill');
  fill.hidden = percent == null;
  fill.style.height = percent == null ? '0%' : percent + '%';
  byId('tankGraphic').setAttribute('aria-label', percent == null ? 'Water level unavailable' : 'Water level ' + label + (tank.status === 'stale' ? ', stale reading' : ''));
  text('tankDevice', tank.device_id);
  text('tankDepth', tank.water_depth_cm == null ? 'Water depth unavailable' : 'Water depth: ' + tankNumber(tank.water_depth_cm) + ' cm / ' + tankNumber(tank.water_depth_cm / 30.48) + ' ft');
  text('tankDistance', tank.distance_cm == null ? 'Distance unavailable' : tankNumber(tank.distance_cm) + ' cm sensor-to-water distance');
  text('tankCalibration', config.height_cm == null ? 'Tank height not configured' : 'Using tank height: ' + tankNumber(config.height_cm) + ' cm');
  text('tankFloat', tank.float_value === 1 ? '1 · Overflow' : tank.float_value === 0 ? '0 · Not triggered' : 'Unknown');
  text('tankPump', tank.pump || 'Unavailable');
  text('tankRssi', tank.rssi == null ? 'Unavailable' : tankNumber(tank.rssi) + ' dBm');
  text('tankGateway', tank.mqtt_connected ? 'Connected' : 'Disconnected');
  text('tankReceived', tank.received_at == null ? 'Unknown / never' : new Date(tank.received_at * 1000).toLocaleString());
  var labels = {live: 'Live', stale: 'Stale / unverified', no_data: 'No sensor data', invalid: 'Invalid reading'};
  text('tankStatus', (labels[tank.status] || 'Unknown') + (tank.age_seconds == null ? '' : ' · ' + Math.floor(tank.age_seconds) + ' s ago'));
  text('tankWarning', tank.warnings.join(' '));
  byId('tankWarning').hidden = !tank.warnings.length;
}

function initTank() {
  var form = byId('tankHeightForm');
  if (!form) return;
  var height = byId('tankHeight'), unit = byId('tankUnit');
  height.addEventListener('input', function() { tankFormDirty = true; text('tankSaved', 'Unsaved height'); });
  unit.addEventListener('change', function() {
    var value = height.valueAsNumber;
    if (Number.isFinite(value)) {
      height.value = Number((value * (tankPreviousUnit === 'ft' ? 30.48 : 1) / (unit.value === 'ft' ? 30.48 : 1)).toFixed(10));
    }
    tankPreviousUnit = unit.value;
    tankFormDirty = true;
    text('tankSaved', 'Unit converted; save to keep this setting.');
  });
  form.addEventListener('submit', async function(event) {
    event.preventDefault();
    if (tankSaving) return;
    var value = height.valueAsNumber;
    var cm = Math.round(value * (unit.value === 'ft' ? 30.48 : 1) * 1e8) / 1e8;
    var error = byId('tankHeightError');
    error.hidden = true;
    height.removeAttribute('aria-invalid');
    if (!Number.isFinite(cm) || cm < 5 || cm > 5000) {
      text('tankHeightError', 'Enter a height between 5 and 5000 cm (approximately 0.164–164.042 ft).');
      error.hidden = false;
      height.setAttribute('aria-invalid', 'true');
      return;
    }
    tankSaving = true;
    byId('tankSave').disabled = height.disabled = unit.disabled = true;
    text('tankSaved', 'Saving…');
    try {
      var result = await post('/api/iot/tank-height', {height: value, unit: unit.value});
      tankFormDirty = false;
      tankFormLoaded = false;
      renderTank(result.tank);
      text('tankSaved', 'Height saved. Level recalculates with each sensor reading.');
    } catch (err) {
      text('tankHeightError', err.message);
      error.hidden = false;
      text('tankSaved', 'Height not saved.');
    } finally {
      tankSaving = false;
      byId('tankSave').disabled = height.disabled = unit.disabled = false;
    }
  });
}
