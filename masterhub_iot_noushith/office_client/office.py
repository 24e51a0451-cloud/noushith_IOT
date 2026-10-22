"""Office operations adapted from the Python team's 15-10 Office handlers.

Only documents created by this session may be changed. Never use ActiveDocument
or quit an application: PowerPoint may share its process with the user's work.
"""
import atexit
from concurrent.futures import Future
from pathlib import Path
from queue import Queue, Full
import re
from threading import Thread

from office_client import content


ACTIONS = {
    'excel': ('open', 'sheet1', 'sheet2', 'save', 'edit', 'delete', 'close'),
    'powerpoint': ('open', 'title', 'slide', 'save', 'edit', 'delete', 'close'),
    'word': ('open', 'save', 'insert', 'replace', 'delete', 'close'),
}
OFFICE_ACTIONS = frozenset(f'office_{app}_{op}' for app, ops in ACTIONS.items() for op in ops)


def validate(action, params):
    if action not in OFFICE_ACTIONS or not isinstance(params, dict):
        raise ValueError('Unsupported Office action or invalid parameters')
    for key in ('text', 'find', 'replacement'):
        if key in params and (not isinstance(params[key], str) or len(params[key]) > 20000):
            raise ValueError(f'{key} must be text of at most 20000 characters')
    if action.endswith('_replace') and not params.get('find'):
        raise ValueError('Enter the text to find')
    for key in ('confirm', 'discard'):
        if key in params and not isinstance(params[key], bool):
            raise ValueError(f'{key} must be a boolean')
    if action.endswith(('_delete', '_edit', '_replace')) and params.get('confirm') is not True:
        raise ValueError('Confirm this document change before executing it')
    if 'sheet' in params and params['sheet'] not in ('Sheet1', 'Sheet2'):
        raise ValueError('sheet must be Sheet1 or Sheet2')
    if 'slide' in params and (type(params['slide']) is not int or not 1 <= params['slide'] <= 1000):
        raise ValueError('slide must be an integer from 1 to 1000')
    if 'filename' in params and params['filename']:
        name = params['filename']
        if (not isinstance(name, str) or len(name) > 120 or
                not re.fullmatch(r'[\w .-]+', name) or name.endswith((' ', '.')) or
                name.startswith('.') or re.match(r'(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', name)):
            raise ValueError('Use a filename only, without a directory or special characters')


class OfficeSession:
    """Called on one COM-initialized worker thread."""
    def __init__(self, output_dir=None, dispatch=None):
        self.output_dir = Path(output_dir or Path.home() / 'Documents' / 'Masterhub').resolve()
        self.dispatch = dispatch
        self.documents = {}
        self.applications = {}
        self.paths = {}
        self.slide_index = 0

    def execute(self, action, params):
        try:
            validate(action, params)
            _, app, op = action.split('_')
            if op == 'close':
                return self.close(app, params)
            if op != 'open' and app not in self.documents:
                raise ValueError(f'Open the managed {app} document first')
            doc = self.document(app)
            if op == 'save':
                path = self.save(app, doc, params.get('filename'))
                return {'success': True, 'status': 'SUCCESS', 'path': str(path), 'message': f'Saved {path.name}'}
            if app == 'excel':
                self.excel(doc, op, params)
            elif app == 'powerpoint':
                self.powerpoint(doc, op, params)
            else:
                self.word(doc, op, params)
            return {'success': True, 'status': 'SUCCESS', 'message': f'{app.title()}: {op} completed'}
        except Exception as error:
            return {'success': False, 'status': 'FAILED', 'error': str(error)}

    def document(self, app):
        if app in self.documents:
            try:
                _ = self.documents[app].Name
            except Exception as error:
                raise RuntimeError('The managed document was closed. Restart the client to create a new session.') from error
            return self.documents[app]
        dispatch = self.dispatch
        if dispatch is None:
            from win32com.client import DispatchEx
            dispatch = DispatchEx
        progid, collection = {
            'excel': ('Excel.Application', 'Workbooks'),
            'word': ('Word.Application', 'Documents'),
            'powerpoint': ('PowerPoint.Application', 'Presentations'),
        }[app]
        application = self.applications.get(app)
        if application is None:
            application = dispatch(progid)
            self.applications[app] = application
        application.Visible = True
        doc = getattr(application, collection).Add()
        self.documents[app] = doc
        if app == 'word':
            doc.Content.Text = content.INITIAL_WORD_TEXT
        if app == 'powerpoint':
            self.slide_index = 0
        return doc

    def save(self, app, doc, filename=None):
        extension, file_format = {'excel': ('.xlsx', 51), 'word': ('.docx', 16), 'powerpoint': ('.pptx', 24)}[app]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        old_path = self.paths.get(app)
        if filename:
            name = filename if Path(filename).suffix else filename + extension
            if Path(name).suffix.lower() != extension:
                raise ValueError(f'Use a {extension} filename')
            path = (self.output_dir / name).resolve()
        elif old_path:
            path = old_path
        else:
            from uuid import uuid4
            path = self.output_dir / f'Masterhub-{app}-{uuid4().hex[:10]}{extension}'
        if path.parent != self.output_dir:
            raise ValueError('Output must stay in the configured document folder')
        if path.exists() and path != old_path:
            raise ValueError('That file already exists; choose another filename')
        if path == old_path:
            doc.Save()
        elif app == 'word':
            doc.SaveAs2(str(path), FileFormat=file_format)
        else:
            doc.SaveAs(str(path), FileFormat=file_format)
        self.paths[app] = path
        return path

    def close(self, app, params):
        doc = self.documents.get(app)
        if doc is None:
            return {'success': True, 'status': 'SUCCESS', 'message': 'No managed document is open'}
        if not doc.Saved and not params.get('discard'):
            return {'success': False, 'status': 'NEEDS_USER_ACTION', 'error': 'Unsaved changes: save first, or explicitly enable discard'}
        if app == 'powerpoint':
            if params.get('discard'):
                doc.Saved = True
            doc.Close()
        else:
            doc.Close(SaveChanges=0)
        del self.documents[app]
        self.paths.pop(app, None)
        return {'success': True, 'status': 'SUCCESS', 'message': 'Managed document closed'}

    def excel(self, doc, op, params):
        if op == 'open':
            return
        name = params.get('sheet', 'Sheet1') if op in ('edit', 'delete') else ('Sheet1' if op == 'sheet1' else 'Sheet2')
        sheet = next((doc.Worksheets(i) for i in range(1, doc.Worksheets.Count + 1)
                      if doc.Worksheets(i).Name == name), None)
        if op == 'delete':
            if sheet is None or doc.Worksheets.Count <= 1:
                raise ValueError('The sheet must exist and at least one worksheet must remain')
            app = self.applications['excel']
            alerts = app.DisplayAlerts
            try:
                app.DisplayAlerts = False
                sheet.Delete()
            finally:
                app.DisplayAlerts = alerts
            return
        if sheet is None:
            sheet = doc.Worksheets.Add()
            sheet.Name = name
        sheet.Activate()
        if op != 'edit' and sheet.Application.WorksheetFunction.CountA(sheet.UsedRange) > 0:
            return
        headers, rows = ((content.SHEET1_STOCK_HEADERS, content.SHEET1_STOCK_DATA) if name == 'Sheet1'
                         else (content.SHEET2_DEGREE_HEADERS, content.SHEET2_DEGREE_DATA))
        if op == 'edit':
            sheet.Cells.ClearContents()
        sheet.Range(f'A1:E{len(rows) + 1}').Value = [headers] + rows
        sheet.Range('A1:E1').Font.Bold = True
        sheet.Columns.AutoFit()

    def powerpoint(self, doc, op, params):
        if op == 'open':
            return
        if op in ('edit', 'delete'):
            number = params.get('slide', doc.Slides.Count)
            if not 1 <= number <= doc.Slides.Count:
                raise ValueError('Select an existing slide number')
            slide = doc.Slides(number)
            if op == 'delete':
                slide.Delete()
                return
            data = content.POWERPOINT_TECHNICAL_APPROACH
        elif op == 'title':
            if doc.Slides.Count:
                return
            slide = doc.Slides.Add(1, 1)
            data = content.POWERPOINT_BCI_TITLE
        else:
            data = content.POWERPOINT_PYTHON_DOMAIN_SLIDES[self.slide_index % len(content.POWERPOINT_PYTHON_DOMAIN_SLIDES)]
            slide = doc.Slides.Add(doc.Slides.Count + 1, 2)
        slide.Shapes.Title.TextFrame.TextRange.Text = data['title']
        slide.Shapes.Placeholders(2).TextFrame.TextRange.Text = data.get('subtitle') or '\r'.join(data['bullets'])
        if op == 'slide':
            self.slide_index += 1

    def word(self, doc, op, params):
        if op == 'open':
            return
        if op == 'insert':
            doc.Content.InsertAfter(params.get('text') or content.SYNAPTIMESH_WORD_TEXT)
        elif op == 'replace':
            find = params.get('find', '')
            if not find:
                raise ValueError('Enter the text to find')
            found = doc.Content.Find.Execute(FindText=find, ReplaceWith=params.get('replacement', ''),
                                             Replace=2, MatchWildcards=False, Wrap=0)
            if not found:
                raise ValueError('Text was not found in the managed document')
        elif op == 'delete':
            doc.Content.Text = ''


class OfficeWorker:
    """Keep COM objects on their owning thread, outside transport callbacks."""
    def __init__(self, output_dir=None):
        self.queue = Queue(maxsize=32)
        self.thread = Thread(target=self._run, args=(output_dir,), daemon=True)
        self.thread.start()
        atexit.register(self.stop)

    def _run(self, output_dir):
        session = OfficeSession(output_dir)
        com = None
        try:
            try:
                import pythoncom
                pythoncom.CoInitialize()
                com = pythoncom
                error = None
            except Exception as exc:
                error = f'Office automation requires Windows and pywin32: {exc}'
            while True:
                item = self.queue.get()
                if item is None:
                    break
                action, params, future = item
                future.set_result({'success': False, 'status': 'FAILED', 'error': error} if error else session.execute(action, params))
        finally:
            session.documents.clear()
            session.applications.clear()
            if com:
                com.CoUninitialize()

    def execute(self, action, params):
        future = Future()
        try:
            self.queue.put_nowait((action, params, future))
        except Full:
            return {'success': False, 'status': 'FAILED', 'error': 'Office queue is full'}
        return future.result()

    def stop(self):
        try:
            self.queue.put_nowait(None)
        except Full:
            pass
        self.thread.join(timeout=2)
