import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid
from zipfile import ZipFile

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import requests

root = Path(__file__).resolve().parents[1]
target = root / '.runtime' / ('release-smoke-' + uuid.uuid4().hex)
target.mkdir()
with ZipFile(root / 'dist/masterhub.zip') as archive:
    archive.extractall(target)
base = 'postgresql://postgres@127.0.0.1:55447/postgres?sslmode=disable'
schema = 'smoke_' + uuid.uuid4().hex
with psycopg.connect(base, autocommit=True) as db:
    db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
env = dict(os.environ, DATABASE_URL=make_conninfo(base, options='-c search_path=' + schema),
           MASTERHUB_OPERATOR_USER='smoke', MASTERHUB_OPERATOR_PASSWORD=secrets.token_urlsafe(32),
           MASTERHUB_HOST='127.0.0.1', MASTERHUB_PORT='55448',
           MQTT_HOST='127.0.0.1', BCI_MOBILE_MQTT_HOST='127.0.0.1')
process = None
try:
    with (root / '.runtime/quality-smoke.log').open('w') as output:
        process = subprocess.Popen([sys.executable, 'serve.py'], cwd=target, env=env,
                                   stdout=output, stderr=output, creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('Production server exited; inspect quality-smoke.log')
            try:
                response = requests.get('http://127.0.0.1:55448/healthz', timeout=.5)
                if response.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(.1)
        else:
            raise RuntimeError('Production server did not become ready')
        url = 'http://127.0.0.1:55448/dashboard'
        assert requests.get(url, timeout=5).status_code == 401
        response = requests.get(url, auth=('smoke', env['MASTERHUB_OPERATOR_PASSWORD']), timeout=5)
        assert response.status_code == 200 and 'MasterHub' in response.text
        assert response.headers['X-Frame-Options'] == 'DENY'
        assert requests.get('http://127.0.0.1:55448/static/masterhub.css',
                            auth=('smoke', env['MASTERHUB_OPERATOR_PASSWORD']), timeout=5).status_code == 200
        print('PASS: extracted release, Waitress startup, liveness, authentication, dashboard and stylesheet')
finally:
    if process is not None:
        process.terminate()
        process.wait(timeout=10)
    with psycopg.connect(base, autocommit=True) as db:
        db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
