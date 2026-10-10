#!/usr/bin/env python3
"""Reject non-home Markdown, credential containers, and private-key blocks in the public tree."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
blocked_suffixes = {'.pk8', '.p7b', '.pem', '.key', '.p12', '.pfx', '.jks', '.keystore', '.apk', '.aab'}
allowed_markdown = {
    'README.md',
}
private_block = re.compile(rb'-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{40,}')
failures = []
for name in filter(None, names):
    path = root / name
    if path.suffix.lower() == '.md' and name not in allowed_markdown:
        failures.append(name)
        continue
    if not path.is_file():
        continue
    if '.private' in path.relative_to(root).parts or path.suffix.lower() in blocked_suffixes:
        failures.append(name)
    elif private_block.search(path.read_bytes()):
        failures.append(name)
if failures:
    raise SystemExit('Credential or distribution files are forbidden in the public tree:\n' + '\n'.join(failures))
print('Public tree check passed: no credential containers or private-key blocks.')
