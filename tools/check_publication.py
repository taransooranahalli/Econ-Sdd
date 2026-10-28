"""Fail closed if private runtime material enters the reviewed Git snapshot."""
from pathlib import Path,PurePosixPath
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BLOCKED_PARTS={'.secrets','.venv','.pytest_cache','__pycache__','data','exports','work','dist','build','.git'}
CREDENTIAL_PATTERNS=[re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
                     re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
                     re.compile(rb'github_pat_[A-Za-z0-9_]{30,}'),
                     re.compile(rb'AKIA[0-9A-Z]{16}')]


def unsafe_path(path):
    value=PurePosixPath(path)
    return (not path or value.is_absolute() or '..' in value.parts or bool(set(value.parts)&BLOCKED_PARTS)
            or any(part.endswith('.egg-info') for part in value.parts)
            or value.name.startswith('.env') or value.suffix.lower() in {'.sqlite','.sqlite3','.db','.pem','.key','.pyc'}
            or any(suffix in value.name for suffix in ('.sqlite3-','.sqlite-','.db-')) or value.name=='.DS_Store')


def audit(paths,root=ROOT,*,staged=False):
    errors=[]
    for path in paths:
        if unsafe_path(path):errors.append(f'Private/generated path is tracked: {path}');continue
        file=root/path
        if file.is_symlink():errors.append(f'Symlink is not allowed in the public snapshot: {path}');continue
        body=(subprocess.check_output(['git','show',':'+path],cwd=root) if staged else file.read_bytes())
        if body.startswith(b'SQLite format 3\0'):errors.append(f'Database content is tracked: {path}')
        if any(pattern.search(body) for pattern in CREDENTIAL_PATTERNS):errors.append(f'Credential-like content is tracked: {path}')
        # Keys are never allowed even if a file was renamed to an ordinary JSON name.
        if re.search(rb'"index_key"\s*:\s*"[A-Za-z0-9+/=]{40,}"',body):errors.append(f'Keyring material is tracked: {path}')
    return errors


if __name__=='__main__':
    staged='--staged' in sys.argv
    command=['git','diff','--cached','--name-only','--diff-filter=ACM','-z'] if staged else ['git','ls-files','-z']
    paths=subprocess.check_output(command,cwd=ROOT).decode().split('\0');paths=[path for path in paths if path]
    errors=audit(paths,staged=staged)
    if not paths:errors.append('No reviewed files are available to audit.')
    if errors:
        print('\n'.join(errors));raise SystemExit(1)
    print(f'Publication safety check passed: {len(paths)} reviewed files; no runtime data/key paths detected.')
