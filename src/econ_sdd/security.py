"""Authenticated encryption with explicit, separately stored key material."""
from dataclasses import dataclass
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class VaultError(RuntimeError):
    pass


def private_path(path: Path, *, directory=False):
    try:info=path.lstat()
    except OSError:raise VaultError('Private account files are unavailable. Restore the original database and keyring.') from None
    expected=stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not expected or stat.S_IMODE(info.st_mode)&0o077 or (hasattr(os,'getuid') and info.st_uid!=os.getuid()):
        raise VaultError('Account files must be owned by this user with private permissions.')


def private_directory(path: Path):
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    private_path(path,directory=True)


@dataclass(frozen=True)
class Keyring:
    active: str
    keys: dict[str,bytes]
    index_key: bytes

    @classmethod
    def generate(cls):
        return cls('1',{'1':secrets.token_bytes(32)},secrets.token_bytes(32))

    @classmethod
    def load(cls,path: Path):
        try:
            private_path(path);private_path(path.parent,directory=True)
            if path.stat().st_size>16384:raise ValueError()
            value=json.loads(path.read_text())
            if value['version']!=1 or type(value['version']) is not int:raise ValueError()
            keys={k:base64.b64decode(v,validate=True) for k,v in value['keys'].items()}
            index=base64.b64decode(value['index_key'],validate=True)
            if not keys or any(len(k)>16 or not k.isalnum() or len(v)!=32 for k,v in keys.items()):raise ValueError()
            if value['active'] not in keys or len(index)!=32:raise ValueError()
            return cls(value['active'],keys,index)
        except (OSError,ValueError,KeyError,TypeError,AttributeError):
            raise VaultError('Account keyring is missing or invalid. Restore the original keyring; do not regenerate it.') from None

    def write_new(self,path: Path):
        private_directory(path.parent)
        body=json.dumps({'version':1,'active':self.active,'keys':{k:base64.b64encode(v).decode() for k,v in self.keys.items()},
                         'index_key':base64.b64encode(self.index_key).decode()})+'\n'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as out:out.write(body);out.flush();os.fsync(out.fileno())

    def index(self,purpose: str,value: str)->str:
        return hmac.new(self.index_key,(purpose+'\0'+value).encode(),hashlib.sha256).hexdigest()

    def encrypt(self,value: dict,aad: str)->str:
        nonce=secrets.token_bytes(12)
        plaintext=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        encrypted=AESGCM(self.keys[self.active]).encrypt(nonce,plaintext,aad.encode())
        return self.active+':'+base64.b64encode(nonce+encrypted).decode()

    def decrypt(self,value: str,aad: str)->dict:
        try:
            key_id,encoded=value.split(':',1)
            raw=base64.b64decode(encoded,validate=True)
            if len(raw)<28:raise ValueError()
            plaintext=AESGCM(self.keys[key_id]).decrypt(raw[:12],raw[12:],aad.encode())
            data=json.loads(plaintext)
            if not isinstance(data,dict):raise ValueError()
            return data
        except (ValueError,TypeError,KeyError,InvalidTag,UnicodeError,AttributeError):
            raise VaultError('Encrypted account data could not be verified. Restore a valid database and keyring.') from None
