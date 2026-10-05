"""Regression coverage for the maintained-source SonarQube bug findings."""
import ast
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import pytest


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_dashboard_ids_and_keyboard_controls():
    from app import create_app
    app = create_app()
    app.testing = True
    response = app.test_client().get('/dashboard')
    assert response.status_code == 200
    parser = Elements()
    parser.feed(response.get_data(as_text=True))
    counts = Counter(attrs['id'] for _, attrs in parser.elements if 'id' in attrs)
    assert all(count == 1 for count in counts.values())
    for tag, attrs in parser.elements:
        if 'onclick' in attrs:
            assert tag == 'button' or (tag == 'a' and attrs.get('href'))
        if attrs.get('id') in ('themeToggleBtn', 'pillBci', 'sidebarBackdrop',
                                'bciDrawerBackdrop', 'modalBackdrop'):
            assert tag == 'button'
            assert attrs.get('aria-hidden') != 'true'


@pytest.mark.parametrize('target', ['Local Host', 'PC_001', '  UNDISCOVERED_PC  '])
def test_explicit_targets_remain_selectable(target):
    from core.devices import DeviceRegistry
    registry = DeviceRegistry()
    assert registry.set_active_target(target) == target.strip()
    assert registry.get_active_target() == target.strip()


@pytest.mark.parametrize('value,expected', [(None, '127.0.0.1'), ('', '127.0.0.1'),
                                          ('  ', '127.0.0.1'), ('192.168.1.5', '192.168.1.5')])
def test_server_bind_default_and_explicit_override(monkeypatch, value, expected):
    import os
    if value is None:
        monkeypatch.delenv('MASTERHUB_HOST', raising=False)
    else:
        monkeypatch.setenv('MASTERHUB_HOST', value)
    tree = ast.parse(Path('app.py').read_text(encoding='utf-8'))
    assignment = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'host' for t in n.targets))
    assert eval(compile(ast.Expression(assignment.value), 'app.py', 'eval'), {'os': os}) == expected


@pytest.mark.parametrize('template', ['dashboard.html', 'cortex_classic.html'])
def test_templates_do_not_load_unverified_external_stylesheets(template):
    parser = Elements()
    parser.feed((Path('templates') / template).read_text(encoding='utf-8'))
    assert not any(tag == 'link' and attrs.get('href', '').startswith(('https://', 'http://', '//'))
                   for tag, attrs in parser.elements)
