"""Build a source release from an allowlist; never ship credentials or runtime data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('actions', 'api', 'core', 'cortex', 'services', 'prediction_pipeline',
           'simulator', 'static', 'templates', 'mappings', 'assets', 'database', 'office_client')
FILES = ('app.py', 'serve.py', 'config.py', 'run_cortex.py', 'requirements.txt',
         'requirements-production.txt', '.env.example', '.env.mobile.example', 'README.md',
         'docs/DEPLOYMENT.md', 'docs/USER_GUIDE.md', 'docs/POSTGRESQL_WINDOWS_SETUP.md',
         'docs/POSTGRESQL_EVENT_STORAGE.md', 'tools/check_postgresql.py',
         'data/sample_signals.json', 'data/eeg_samples.json')


def release_files():
    paths = [ROOT / name for name in FILES]
    for folder in FOLDERS:
        paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file()
                     and not any(part in ('__pycache__', 'logs') for part in p.parts)
                     and p.suffix in ('.py', '.json', '.html', '.css', '.js', '.png', '.sql', '.txt', '.md'))
    return sorted(set(paths))


def main():
    destination = ROOT / 'dist/masterhub.zip'
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
        for path in release_files():
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(f'Built {destination.name}: {destination.stat().st_size:,} bytes')


if __name__ == '__main__':
    main()
