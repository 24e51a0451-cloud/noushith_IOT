"""Keep credential API tests away from the user's real .env file."""
import pytest


@pytest.fixture(autouse=True)
def isolated_cortex_settings(tmp_path, monkeypatch):
    from cortex import config, dashboard

    env_file = tmp_path / '.env'
    env_file.write_text("CORTEX_CLIENT_ID='test-client'\nCORTEX_CLIENT_SECRET='test-secret'\n", encoding='utf-8')
    monkeypatch.setattr(config, '_ENV_FILE', env_file)
    monkeypatch.setattr(dashboard, '_ENV_FILE', env_file)
    for name in ('CLIENT_ID', 'CLIENT_SECRET', 'LICENSE', 'CORTEX_URL'):
        monkeypatch.setattr(config, name, getattr(config, name))
    return env_file
