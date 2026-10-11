"""Create allowlisted deployment archives, including Composer dependencies."""
from pathlib import Path
import hashlib
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'


def add_tree(archive, folder, prefix):
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or path.is_symlink(): continue
        if '__pycache__' in path.parts or path.name in ('.DS_Store',) or path.suffix == '.pyc': continue
        archive.write(path, str(Path(prefix) / path.relative_to(folder)))


def main():
    if not (ROOT/'web/vendor/autoload.php').is_file():
        raise SystemExit('Run composer install --no-dev in web first.')
    DIST.mkdir(exist_ok=True)
    hosting = DIST/'idlaps-shared-hosting.zip'
    with zipfile.ZipFile(hosting, 'w', zipfile.ZIP_DEFLATED) as archive:
        for folder in ('app', 'public', 'vendor'):
            add_tree(archive, ROOT/'web'/folder, 'idlaps-triathlon/'+folder)
        for name in ('.htaccess', 'composer.json', 'composer.lock', 'config/example.php',
                     'storage/.htaccess', 'storage/.gitkeep'):
            archive.write(ROOT/'web'/name, 'idlaps-triathlon/'+name)
        archive.write(ROOT/'docs/PEMASANGAN.md', 'idlaps-triathlon/PANDUAN.md')
        archive.write(ROOT/'docs/PEMBARUAN-2.2.md', 'idlaps-triathlon/PEMBARUAN-2.2.md')
        archive.write(ROOT/'docs/PEMBARUAN-2.3.md', 'idlaps-triathlon/PEMBARUAN-2.3.md')
    desktop = DIST/'idlaps-desktop-windows-source.zip'
    with zipfile.ZipFile(desktop, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ('main.py', 'requirements.txt', 'build-windows.bat'):
            archive.write(ROOT/'desktop'/name, 'desktop/'+name)
        add_tree(archive, ROOT/'desktop/idlaps', 'desktop/idlaps')
        add_tree(archive, ROOT/'desktop/tests', 'desktop/tests')
        archive.write(ROOT/'docs/PEMASANGAN.md', 'PANDUAN.md')
        archive.write(ROOT/'docs/PEMBARUAN-2.3.md', 'PEMBARUAN-2.3.md')
        archive.write(ROOT/'.github/workflows/windows.yml', '.github/workflows/windows.yml')
    aia = DIST/'IDLAPSTriathlonTap-2.2.aia'
    shutil.copyfile(ROOT/'android/IDLAPSTriathlonTap.aia', aia)
    for path in (hosting, desktop, aia):
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            assert not any('/demo/' in n or n.endswith('local.php') or n.endswith('.db') for n in archive.namelist())
        print(f'{path.name}: {path.stat().st_size:,} bytes')
    (DIST/'SHA256SUMS.txt').write_text(''.join(
        f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n'
        for path in (hosting, desktop, aia)))


if __name__ == '__main__': main()
