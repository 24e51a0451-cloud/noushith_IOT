"""Browser-origin protections, with no hardware or live network side effects."""
import ast
from pathlib import Path

import pytest
from flask import Flask

from services.web_security import reject_cross_origin_mutation


@pytest.fixture
def client():
    app = Flask(__name__)
    app.before_request(reject_cross_origin_mutation)
    app.add_url_rule('/mutation', view_func=lambda: {'success': True}, methods=['POST', 'DELETE', 'PATCH'])
    return app.test_client()


@pytest.mark.parametrize('headers', [
    {'Origin': 'https://attacker.example'},
    {'Origin': 'null'},
    {'Origin': 'http://localhost:5001'},
    {'Origin': 'http://localhost:bad'},
    {'Referer': 'https://attacker.example/form'},
    {'Sec-Fetch-Site': 'cross-site'},
    {'Sec-Fetch-Site': 'same-site'},
    {'Origin': '', 'Sec-Fetch-Site': 'same-origin'},
])
@pytest.mark.parametrize('method', ['POST', 'DELETE', 'PATCH'])
def test_foreign_browser_mutations_are_rejected(client, headers, method):
    assert client.open('/mutation', method=method, headers=headers).status_code == 403


@pytest.mark.parametrize('headers', [
    {},  # Existing native API clients do not send browser headers.
    {'Origin': 'http://localhost'},
    {'Origin': 'http://localhost:80', 'Sec-Fetch-Site': 'same-origin'},
    {'Referer': 'http://localhost/dashboard'},
])
def test_same_origin_and_native_clients_still_work(client, headers):
    assert client.post('/mutation', headers=headers).status_code == 200


def test_app_registers_protection_and_defaults_to_no_debug():
    from app import create_app
    app = create_app()
    assert not app.debug
    assert reject_cross_origin_mutation in app.before_request_funcs[None]
    tree = ast.parse(Path('app.py').read_text(encoding='utf-8'))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == 'run']
    assert calls
    for call in calls:
        debug = next(k.value for k in call.keywords if k.arg == 'debug')
        assert isinstance(debug, ast.Constant) and debug.value is False
