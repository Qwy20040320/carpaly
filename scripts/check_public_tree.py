#!/usr/bin/env python3
"""Reject non-allow-listed Markdown, credential containers, and private-key blocks in the public tree."""
from pathlib import Path
import json
import re
import subprocess

root = Path(__file__).resolve().parents[1]
names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
blocked_suffixes = {'.pk8', '.p7b', '.pem', '.key', '.p12', '.pfx', '.jks', '.keystore', '.apk', '.aab'}
markdown_config = json.loads((root / 'config/public-markdown-allowlist.json').read_text(encoding='utf-8'))
if markdown_config.get('schemaVersion') != 1:
    raise SystemExit('Unsupported public Markdown allow-list schema')
allowed_markdown = set(markdown_config.get('publicMarkdown', []))
if 'README.md' not in allowed_markdown:
    raise SystemExit('Public Markdown allow-list must contain README.md')
if len(allowed_markdown) != len(markdown_config.get('publicMarkdown', [])):
    raise SystemExit('Public Markdown allow-list contains duplicate paths')
untracked_public_docs = allowed_markdown - set(filter(None, names))
if untracked_public_docs:
    raise SystemExit('Allow-listed public documentation must be tracked:\n' + '\n'.join(sorted(untracked_public_docs)))
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
