import base64

import pytest
from flask import Flask
from services.web_security import require_operator, security_headers


@pytest.fixture
def app():
    app = Flask(__name__)
    app.before_request(require_operator)
    app.after_request(security_headers)
    app.add_url_rule('/control', view_func=lambda: {'ok': True})
    app.add_url_rule('/healthz', endpoint='healthz', view_func=lambda: {'status': 'ok'})
    return app


def test_unconfigured_remote_access_fails_closed(app):
    client = app.test_client()
    assert client.get('/control').status_code == 200
    assert client.get('/control', environ_base={'REMOTE_ADDR': '192.0.2.1'}).status_code == 403
    assert client.get('/control', environ_base={'REMOTE_ADDR': '192.0.2.1'},
                      headers={'X-Forwarded-For': '127.0.0.1'}).status_code == 403
    assert client.get('/healthz', environ_base={'REMOTE_ADDR': '192.0.2.1'}).status_code == 200


def test_credentials_protect_local_and_remote_control(app):
    app.config.update(MASTERHUB_OPERATOR_USER='operator', MASTERHUB_OPERATOR_PASSWORD='a' * 32)
    client = app.test_client()
    assert client.get('/control').status_code == 401
    for password, status in [('wrong', 401), ('a' * 32, 200)]:
        credentials = base64.b64encode(('operator:' + password).encode()).decode()
        response = client.get('/control', headers={'Authorization': 'Basic ' + credentials})
        assert response.status_code == status
        assert response.headers['Cache-Control'] == 'no-store'
        assert response.headers['X-Frame-Options'] == 'DENY'


def test_partial_configuration_does_not_allow_local_bypass(app):
    app.config['MASTERHUB_OPERATOR_USER'] = 'operator'
    assert app.test_client().get('/control').status_code == 401


def test_production_start_requires_credentials(monkeypatch):
    import serve
    from app import app
    monkeypatch.setitem(app.config, 'MASTERHUB_OPERATOR_PASSWORD', '')
    with pytest.raises(SystemExit, match='operator password'):
        serve.main()


def test_prediction_sender_uses_operator_credentials(monkeypatch):
    from prediction_pipeline import CommandSender
    monkeypatch.setenv('MASTERHUB_OPERATOR_USER', 'operator')
    monkeypatch.setenv('MASTERHUB_OPERATOR_PASSWORD', 'a' * 32)
    assert CommandSender()._session.auth == ('operator', 'a' * 32)
