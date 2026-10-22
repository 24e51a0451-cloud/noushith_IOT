from tools.package_release import release_files, ROOT


def test_release_includes_runtime_without_private_or_generated_data():
    paths = {p.relative_to(ROOT).as_posix() for p in release_files()}
    assert {'app.py', 'serve.py', 'templates/dashboard.html', 'services/web_security.py'} <= paths
    assert all((ROOT / name).is_file() for name in paths)
    assert '.env' not in paths
    assert not any(name.startswith(('.runtime/', 'logs/', 'artifacts/')) for name in paths)
    assert not any(name.endswith(('.backup', '.pyc', '.log')) for name in paths)
