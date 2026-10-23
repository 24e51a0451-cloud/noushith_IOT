"""One-time integration mapping migration."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
def read(name):
    return json.loads((root / 'mappings' / name).read_text(encoding='utf-8'))
def write(name, data):
    (root / 'mappings' / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

items = [('next', 'Next song', 'right'), ('previous', 'Previous song', 'left'),
         ('play_pause', 'Play / Pause', 'push'), ('home', 'Android home', 'pull'),
         ('volume_up', 'Volume up', 'right+push'), ('volume_down', 'Volume down', 'right+pull'),
         ('search', 'Search JioSaavn', None), ('launch', 'Launch JioSaavn', None)]
routes = read('command_map.json')
gestures = read('gesture_map.json')
workflow = read('workflow_map.json')
bci = read('bci_master_map.json')
commands = {}
cards = []
for suffix, label, gesture in items:
    command = 'mobile_jiosaavn_' + suffix
    routes[command] = {'domain': 'ai_ml', 'action': command}
    cards.append(dict(id=command, label=label, gesture=gesture))
    if gesture:
        gestures[gesture]['MOBILE_JIOSAAVN_MODE'] = command
        commands[command] = dict(label=label, gesture=gesture,
                                 arrow='+'.join({'push':'ArrowUp','pull':'ArrowDown','left':'ArrowLeft','right':'ArrowRight'}[g] for g in gesture.split('+')))
workflow['devices']['mobile_jiosaavn']['launch_command'] = None
workflow['bci_workflow']['mobile_jiosaavn'] = cards
workflow['parameters']['mobile_jiosaavn_search'] = ['query']
bci['phase_2_and_3_workflows']['ai_ml']['mobile_jiosaavn']['commands'] = commands
for filename, data in [('command_map.json', routes), ('gesture_map.json', gestures),
                       ('workflow_map.json', workflow), ('bci_master_map.json', bci)]:
    write(filename, data)
