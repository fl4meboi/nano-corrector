"""Build the portable skill ZIP; exclude data, environments and caches."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib

root = Path(__file__).resolve().parents[1]
source = root / 'package' / 'nano-corrector'
out = root / 'releases' / 'nano-corrector-skill-v1.0.0.zip'
files = sorted(p for p in source.rglob('*') if p.is_file()
               and not any(part.startswith('.') or part == '__pycache__' for part in p.relative_to(source).parts)
               and (p.suffix in {'.py', '.md', '.yaml', '.txt'} or p.name == 'LICENSE'))
out.parent.mkdir(parents=True, exist_ok=True)
with ZipFile(out, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
    for p in files:
        archive.write(p, p.relative_to(source.parent))
with ZipFile(out) as archive:
    if archive.testzip() is not None:
        raise RuntimeError('Archive integrity check failed')
print(f'{out.name}: {len(files)} files, {out.stat().st_size:,} bytes')
print('SHA256:', hashlib.sha256(out.read_bytes()).hexdigest())
