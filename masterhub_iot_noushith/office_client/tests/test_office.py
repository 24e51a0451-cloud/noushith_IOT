import json
from pathlib import Path
import time
from unittest.mock import MagicMock

import pytest

from office_client.office import OfficeSession, OFFICE_ACTIONS, validate
from office_client.protocol import CommandReceiver, MAX_FRAME
from services import office_results


def command(command_id='office_test', **changes):
    return {'protocol': 'masterhub', 'version': '1.0', 'message_type': 'command',
            'command_id': command_id, 'target': 'PC_TEST', 'domain': 'desktop',
            'action': 'office_excel_open', 'params': {}, 'timestamp': time.time(), **changes}


@pytest.fixture
def receiver(tmp_path):
    execute = MagicMock(return_value={'success': True, 'status': 'SUCCESS'})
    item = CommandReceiver('PC_TEST', execute, tmp_path / 'journal.db')
    yield item
    item.close()


def test_same_command_from_mqtt_and_uart_executes_once(receiver):
    payload = json.dumps(command())
    first = receiver.handle(payload)
    assert first == receiver.handle(payload.encode())
    assert first['command_id'] == 'office_test'
    receiver.execute.assert_called_once_with('office_excel_open', {})


def test_intentional_repeats_have_distinct_ids(receiver):
    assert receiver.handle(json.dumps(command('one')))['success']
    assert receiver.handle(json.dumps(command('two')))['success']
    assert receiver.execute.call_count == 2


@pytest.mark.parametrize('changes', [
    {'target':'OTHER'}, {'version':'2.0'}, {'domain':'iot'}, {'params':[]},
    {'action':'office_excel_unknown'}, {'action':[]}, {'command_id':''},
    {'timestamp':0}, {'timestamp':float('nan')}, {'timestamp':time.time()+1000},
    {'action':'office_word_delete'}, {'params':{'filename':'../secret.xlsx'}},
])
def test_invalid_envelopes_do_not_execute(receiver, changes):
    assert not receiver.handle(json.dumps(command(**changes)))['success']
    receiver.execute.assert_not_called()


@pytest.mark.parametrize('payload', ['[]', '{broken', 'x' * (MAX_FRAME+1), b'\xff'], ids=['array','broken','oversized','encoding'])
def test_bad_frames_fail(receiver, payload):
    assert not receiver.handle(payload)['success']
    receiver.execute.assert_not_called()


def test_retained_command_rejected(receiver):
    assert not receiver.handle(json.dumps(command()), retained=True)['success']
    receiver.execute.assert_not_called()


def test_id_collision_is_not_silently_accepted(receiver):
    receiver.handle(json.dumps(command()))
    result = receiver.handle(json.dumps(command(action='office_word_open')))
    assert not result['success']
    assert receiver.execute.call_count == 1


def test_completed_and_interrupted_commands_survive_restart(tmp_path):
    path = tmp_path / 'journal.db'
    execute = MagicMock(return_value={'success':True,'status':'SUCCESS'})
    first = CommandReceiver('PC_TEST', execute, path)
    first.handle(json.dumps(command()))
    body = json.dumps(['PC_TEST','office_excel_open',{}], sort_keys=True)
    first.db.execute('INSERT INTO commands VALUES (?, ?, NULL, ?)', ('interrupted', body, time.time()))
    first.db.commit()
    first.close()
    second = CommandReceiver('PC_TEST', execute, path)
    assert second.handle(json.dumps(command()))['success']
    assert second.handle(json.dumps(command('interrupted')))['status'] == 'NEEDS_USER_ACTION'
    execute.assert_called_once()
    second.close()


def test_execution_error_is_returned_not_success(receiver):
    receiver.execute.side_effect = RuntimeError('Office unavailable')
    result = receiver.handle(json.dumps(command()))
    assert result['status'] == 'FAILED'
    assert 'Office unavailable' in result['error']


@pytest.fixture
def session(tmp_path):
    dispatch = MagicMock()
    return OfficeSession(tmp_path, dispatch)


@pytest.mark.parametrize('app,collection', [('excel','Workbooks'),('word','Documents'),('powerpoint','Presentations')])
def test_open_creates_owned_document_and_reuses_it(session, app, collection):
    assert session.execute(f'office_{app}_open', {})['success']
    assert session.execute(f'office_{app}_open', {})['success']
    session.dispatch.assert_called_once()
    getattr(session.dispatch.return_value, collection).Add.assert_called_once()
    session.dispatch.return_value.GetActiveObject.assert_not_called()


def test_failed_save_never_closes_document(session):
    session.execute('office_word_open', {})
    doc = session.documents['word']
    doc.Saved = False
    doc.SaveAs2.side_effect = RuntimeError('disk full')
    assert not session.execute('office_word_save', {'filename':'test.docx'})['success']
    assert session.execute('office_word_close', {})['status'] == 'NEEDS_USER_ACTION'
    doc.Close.assert_not_called()


def test_close_only_owned_document_and_requires_discard(session):
    session.execute('office_word_open', {})
    doc = session.documents['word']; doc.Saved = False
    assert session.execute('office_word_close', {'discard': True})['success']
    doc.Close.assert_called_once_with(SaveChanges=0)
    session.dispatch.return_value.Quit.assert_not_called()


def test_save_never_overwrites_existing_file(session):
    session.execute('office_word_open', {})
    (session.output_dir / 'existing.docx').write_text('keep')
    result = session.execute('office_word_save', {'filename':'existing.docx'})
    assert not result['success']
    session.documents['word'].SaveAs2.assert_not_called()
    assert (session.output_dir / 'existing.docx').read_text() == 'keep'


@pytest.mark.parametrize('name', ['../x.docx','C:\\x.docx','CON.docx','file.docx:stream','file.','.hidden'])
def test_unsafe_filenames_rejected(name):
    with pytest.raises(ValueError):
        validate('office_word_save', {'filename':name})


def test_word_replace_is_explicit_and_stays_in_document(session):
    assert not session.execute('office_word_replace', {'find':'old'})['success']
    session.dispatch.assert_not_called()
    session.execute('office_word_open', {})
    assert session.execute('office_word_replace', {'find':'old', 'replacement':'new', 'confirm':True})['success']
    session.documents['word'].Content.Find.Execute.assert_called_once_with(
        FindText='old', ReplaceWith='new', Replace=2, MatchWildcards=False, Wrap=0)


def test_excel_populate_does_not_overwrite_existing_cells(session):
    session.execute('office_excel_open', {})
    doc = session.documents['excel']; doc.Worksheets.Count = 1
    sheet = doc.Worksheets.return_value; sheet.Name = 'Sheet1'
    sheet.Application.WorksheetFunction.CountA.return_value = 2
    assert session.execute('office_excel_sheet1', {})['success']
    sheet.Range.assert_not_called()


def test_excel_restores_alerts_on_delete_failure(session):
    session.execute('office_excel_open', {})
    doc = session.documents['excel']; doc.Worksheets.Count = 2
    sheet = doc.Worksheets.return_value; sheet.Name = 'Sheet1'
    sheet.Delete.side_effect = RuntimeError('protected sheet')
    app = session.applications['excel']; app.DisplayAlerts = True
    assert not session.execute('office_excel_delete', {'confirm': True})['success']
    assert app.DisplayAlerts is True


def test_operations_require_open_document(session):
    assert not session.execute('office_word_save', {})['success']
    assert not session.execute('office_excel_edit', {'confirm':True})['success']
    session.dispatch.assert_not_called()


@pytest.mark.parametrize('app,extension,format_id', [('excel','.xlsx',51),('word','.docx',16),('powerpoint','.pptx',24)])
def test_save_uses_correct_format_and_then_saves_same_document(session, app, extension, format_id):
    session.execute(f'office_{app}_open', {})
    first = session.execute(f'office_{app}_save', {'filename':'demo' + extension})
    assert first['success']
    doc = session.documents[app]
    method = doc.SaveAs2 if app == 'word' else doc.SaveAs
    method.assert_called_once_with(str(session.output_dir / ('demo' + extension)), FileFormat=format_id)
    assert session.execute(f'office_{app}_save', {})['success']
    doc.Save.assert_called_once()


def test_powerpoint_title_is_not_duplicated_and_slides_cycle(session):
    session.execute('office_powerpoint_open', {})
    doc = session.documents['powerpoint']; doc.Slides.Count = 0
    assert session.execute('office_powerpoint_title', {})['success']
    doc.Slides.Add.assert_called_once_with(1, 1)
    doc.Slides.Count = 1
    assert session.execute('office_powerpoint_title', {})['success']
    assert doc.Slides.Add.call_count == 1
    assert session.execute('office_powerpoint_slide', {})['success']
    assert session.slide_index == 1
    assert doc.Slides.Add.call_args.args == (2, 2)


def test_missing_ack_is_unknown_not_success(monkeypatch):
    office_results.expect('missing-ack', 'PC_TEST', 'office_word_open')
    future = time.monotonic() + 100
    monkeypatch.setattr(office_results.time, 'monotonic', lambda: future)
    result = office_results.get('missing-ack')
    assert result['status'] == 'UNKNOWN' and not result['success']


def test_results_reject_wrong_source_and_action():
    office_results.expect('result-test','PC_TEST','office_excel_open')
    reply = {'protocol':'masterhub','version':'1.0','message_type':'command_result',
             'domain':'desktop','source':'OTHER','command_id':'result-test',
             'action':'office_excel_open','status':'SUCCESS','success':True}
    assert not office_results.receive(reply)
    reply['source'] = 'PC_TEST'
    assert not office_results.receive(reply, 'OTHER')
    reply['action'] = 'office_word_open'
    assert not office_results.receive(reply)
    reply['action'] = 'office_excel_open'
    assert office_results.receive(reply, 'PC_TEST')
    assert office_results.get('result-test')['status'] == 'SUCCESS'


def test_all_office_actions_and_gestures_are_reachable():
    root = Path(__file__).resolve().parents[2] / 'mappings'
    load = lambda name: json.loads((root / name).read_text(encoding='utf-8'))
    routes = load('command_map.json'); modes = load('mode_map.json')['modes']
    workflow = load('workflow_map.json'); gestures = load('gesture_map.json')
    assert OFFICE_ACTIONS <= routes.keys()
    shown = set()
    for key, device in workflow['devices'].items():
        if not key.startswith('office_'): continue
        mode = device['mode']
        assert device['launch_command'] is None
        assert device['parent'] == 'office'
        assert gestures[device['gesture']]['OFFICE_MODE'] == modes[mode]['switch_command']
        assert gestures['push+right'][mode] == 'mode_office'
        assert gestures['push+left'][mode] == 'mode_idle'
        for item in workflow['bci_workflow'][key]:
            shown.add(item['id'])
            if item['gesture']: assert gestures[item['gesture']][mode] == item['id']
    assert shown == OFFICE_ACTIONS
    assert gestures['left']['DESKTOP_MODE'] == 'mode_office'
    assert gestures['left+right']['DESKTOP_MODE'] == 'mode_notepad'
    assert gestures['push+right']['OFFICE_MODE'] == 'mode_desktop'
