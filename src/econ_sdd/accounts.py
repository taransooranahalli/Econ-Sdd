"""Local account/session store. Only validated original calculator inputs are saved."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from threading import BoundedSemaphore
import time
from uuid import UUID,uuid4

from argon2 import PasswordHasher,Type
from argon2.exceptions import VerificationError,InvalidHashError

from .security import Keyring,VaultError,private_directory,private_path

SCHEMA_VERSION=1
IDLE_SECONDS=1800
ABSOLUTE_SECONDS=7*86400
USERNAME=re.compile(r'[A-Za-z0-9_.-]{3,32}\Z',re.ASCII)
TOKEN=re.compile(r'[A-Za-z0-9_-]{43}\Z',re.ASCII)
PH=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=1,type=Type.ID)
DUMMY_HASH=PH.hash(secrets.token_urlsafe(32))
HASH_SLOTS=BoundedSemaphore(2)


class AccountError(ValueError):
    def __init__(self,status,message,field='form'):
        self.status=status;self.errors={field:message};super().__init__('Account request could not be completed.')


def valid_username(value):
    if not isinstance(value,str) or not USERNAME.fullmatch(value):
        raise AccountError(422,'Use 3–32 letters, digits, periods, underscores or hyphens.','username')
    return value.lower()


def valid_password(value):
    try:valid=isinstance(value,str) and 15<=len(value)<=128 and len(value.encode('utf-8'))<=512
    except UnicodeError:valid=False
    if not valid:raise AccountError(422,'Use a password of 15–128 characters (at most 512 UTF-8 bytes).','password')
    return value


def digest(value):return hashlib.sha256(value.encode()).hexdigest()


def new_secret():return secrets.token_urlsafe(32)


def hash_password(value):
    with HASH_SLOTS:return PH.hash(value)


def verify_password(encoded,value):
    with HASH_SLOTS:
        try:return PH.verify(encoded,value)
        except (VerificationError,InvalidHashError,UnicodeError,TypeError):return False


@dataclass(frozen=True)
class Session:
    user_id: str
    username: str
    token_hash: str
    csrf: str


class AccountStore:
    def __init__(self,path: Path,keys: Keyring,*,clock=time.time):
        self.path=Path(path);self.keys=keys;self.clock=clock
        private_path(self.path);private_path(self.path.parent,directory=True)
        with self.db() as con:
            if con.execute('PRAGMA user_version').fetchone()[0]!=SCHEMA_VERSION:raise VaultError('Unsupported account database version.')
            row=con.execute("SELECT value FROM metadata WHERE key='probe'").fetchone()
            if not row or keys.decrypt(row[0],'econ/database/v1')!={'ok':True,'index':keys.index('probe','v1')}:
                raise VaultError('The database and keyring do not match.')

    @contextmanager
    def db(self,*,write=False):
        private_path(self.path);private_path(self.path.parent,directory=True)
        con=sqlite3.connect(self.path.resolve().as_uri()+"?mode=rw",uri=True,timeout=5,isolation_level=None)
        con.row_factory=sqlite3.Row
        try:
            con.execute('PRAGMA foreign_keys=ON');con.execute('PRAGMA secure_delete=ON')
            con.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield con;con.commit()
        except BaseException:con.rollback();raise
        finally:con.close()

    @classmethod
    def initialize(cls,path: Path,keys: Keyring):
        path=Path(path);private_directory(path.parent)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        con=sqlite3.connect(path)
        try:
            con.executescript('''BEGIN IMMEDIATE;
                CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE users(id TEXT PRIMARY KEY,login_index TEXT UNIQUE NOT NULL,identity TEXT NOT NULL,
                    password_hash TEXT NOT NULL,recovery_hash TEXT NOT NULL,created INTEGER NOT NULL);
                CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created INTEGER NOT NULL,last_seen INTEGER NOT NULL);
                CREATE INDEX sessions_owner ON sessions(user_id);
                CREATE TABLE plans(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    revision INTEGER NOT NULL CHECK(revision>0),ciphertext TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL);
                CREATE INDEX plans_owner ON plans(user_id);
                CREATE TABLE attempts(bucket TEXT PRIMARY KEY,count INTEGER NOT NULL,expires INTEGER NOT NULL);
                PRAGMA user_version=1;''')
            con.execute('INSERT INTO metadata VALUES(?,?)',('probe',keys.encrypt({'ok':True,'index':keys.index('probe','v1')},'econ/database/v1')))
            con.commit()
        finally:con.close()
        return cls(path,keys)

    def _limit(self,purpose,username,client):
        now=int(self.clock())
        buckets=[(self.keys.index('limit',purpose+':global'),300),
                 (self.keys.index('client',purpose+':'+client),30),
                 (self.keys.index('login',purpose+':'+username),5)]
        blocked=False
        with self.db(write=True) as con:
            con.execute('DELETE FROM attempts WHERE expires<=?',(now,))
            con.execute('DELETE FROM sessions WHERE created<=? OR last_seen<=?',(now-ABSOLUTE_SECONDS,now-IDLE_SECONDS))
            if con.execute('SELECT count(*) FROM attempts').fetchone()[0]>9997:
                raise AccountError(429,'Too many attempts. Wait 15 minutes before trying again.')
            for key,limit in buckets:
                con.execute('INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1',(key,now+900))
                if con.execute('SELECT count FROM attempts WHERE bucket=?',(key,)).fetchone()[0]>limit:blocked=True
        if blocked:raise AccountError(429,'Too many attempts. Wait 15 minutes before trying again.')

    def _identity(self,row):return self.keys.decrypt(row['identity'],'econ/user/'+row['id'])['username']

    def _new_session(self,con,user_id,old_token=None):
        now=int(self.clock());token=new_secret()
        if old_token and TOKEN.fullmatch(old_token):con.execute('DELETE FROM sessions WHERE token_hash=?',(digest(old_token),))
        # Keep a bounded number of browser sessions per account.
        existing=con.execute('SELECT token_hash FROM sessions WHERE user_id=? ORDER BY created DESC,token_hash',(user_id,)).fetchall()
        for row in existing[9:]:con.execute('DELETE FROM sessions WHERE token_hash=?',(row[0],))
        con.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),user_id,now,now))
        return token

    def register(self,username,password,client,old_token=None):
        login=valid_username(username);valid_password(password);self._limit('register',login,client)
        password_hash=hash_password(password);recovery=new_secret();user_id=str(uuid4())
        try:
            with self.db(write=True) as con:
                con.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(user_id,self.keys.index('username',login),
                    self.keys.encrypt({'username':username},'econ/user/'+user_id),password_hash,digest(recovery),int(self.clock())))
                token=self._new_session(con,user_id,old_token)
        except sqlite3.IntegrityError:raise AccountError(409,'Unable to create this account. Choose another username or sign in.') from None
        return token,recovery

    def login(self,username,password,client,old_token=None):
        login=valid_username(username);self._limit('login',login,client)
        try:bounded=isinstance(password,str) and len(password)<=128 and len(password.encode())<=512
        except UnicodeError:bounded=False
        with self.db() as con:row=con.execute('SELECT * FROM users WHERE login_index=?',(self.keys.index('username',login),)).fetchone()
        verified=verify_password(row['password_hash'] if row else DUMMY_HASH,password if bounded else '')
        if not row or not bounded or not verified:raise AccountError(401,'Username or password is incorrect.')
        new_hash=hash_password(password) if PH.check_needs_rehash(row['password_hash']) else row['password_hash']
        with self.db(write=True) as con:
            current=con.execute('SELECT password_hash FROM users WHERE id=?',(row['id'],)).fetchone()
            if not current or current[0]!=row['password_hash']:raise AccountError(401,'Sign in again with your current password.')
            con.execute('UPDATE users SET password_hash=? WHERE id=?',(new_hash,row['id']))
            return self._new_session(con,row['id'],old_token)

    def session(self,token):
        if not isinstance(token,str) or not TOKEN.fullmatch(token):return None
        now=int(self.clock())
        with self.db(write=True) as con:
            row=con.execute('SELECT u.*,s.created AS session_created,s.last_seen FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?',(digest(token),)).fetchone()
            if not row:return None
            if now-row['session_created']>=ABSOLUTE_SECONDS or now-row['last_seen']>=IDLE_SECONDS:
                con.execute('DELETE FROM sessions WHERE token_hash=?',(digest(token),));return None
            con.execute('UPDATE sessions SET last_seen=? WHERE token_hash=?',(now,digest(token)))
            return Session(row['id'],self._identity(row),digest(token),self.keys.index('csrf',token))

    def _authorize(self,con,session):
        now=int(self.clock())
        row=con.execute('SELECT created,last_seen FROM sessions WHERE token_hash=? AND user_id=?',(session.token_hash,session.user_id)).fetchone()
        if not row or now-row['created']>=ABSOLUTE_SECONDS or now-row['last_seen']>=IDLE_SECONDS:
            raise AccountError(401,'Your session expired. Sign in again.')

    def logout(self,session):
        with self.db(write=True) as con:con.execute('DELETE FROM sessions WHERE token_hash=? AND user_id=?',(session.token_hash,session.user_id))

    def replace_password(self,session,password,new_password):
        valid_password(new_password)
        self._limit('password',session.user_id,session.user_id)
        with self.db() as con:
            self._authorize(con,session)
            row=con.execute('SELECT * FROM users WHERE id=?',(session.user_id,)).fetchone()
        if not isinstance(password,str) or len(password)>128 or not verify_password(row['password_hash'],password):
            raise AccountError(401,'Current password is incorrect.')
        return self._reset(row,new_password,expected_password=row['password_hash'],session=session)

    def recover(self,username,code,password,client):
        login=valid_username(username);valid_password(password);self._limit('recover',login,client)
        with self.db() as con:row=con.execute('SELECT * FROM users WHERE login_index=?',(self.keys.index('username',login),)).fetchone()
        if not row or not isinstance(code,str) or not TOKEN.fullmatch(code) or not hmac.compare_digest(row['recovery_hash'],digest(code)):
            raise AccountError(401,'Username or recovery code is incorrect.')
        return self._reset(row,password,expected_recovery=row['recovery_hash'])

    def _reset(self,row,password,*,expected_password=None,expected_recovery=None,session=None):
        encoded=hash_password(password);recovery=new_secret()
        with self.db(write=True) as con:
            if session:self._authorize(con,session)
            current=con.execute('SELECT * FROM users WHERE id=?',(row['id'],)).fetchone()
            if (not current or (expected_password and current['password_hash']!=expected_password)
                    or (expected_recovery and current['recovery_hash']!=expected_recovery)):
                raise AccountError(401,'Credentials changed. Sign in or recover again.')
            con.execute('UPDATE users SET password_hash=?,recovery_hash=? WHERE id=?',(encoded,digest(recovery),row['id']))
            con.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],))
            return self._new_session(con,row['id']),recovery

    @staticmethod
    def _plan_aad(owner,plan_id,revision):return f'econ/plan/{owner}/{plan_id}/{revision}'

    @staticmethod
    def _plan_id(plan_id):
        try:
            if str(UUID(plan_id))!=plan_id:raise ValueError()
        except (ValueError,TypeError,AttributeError):raise AccountError(404,'Saved plan not found.') from None

    def save_plan(self,session,value,*,plan_id=None,revision=None):
        now=int(self.clock());create=plan_id is None
        if create:plan_id=str(uuid4());revision=0
        else:self._plan_id(plan_id)
        with self.db(write=True) as con:
            self._authorize(con,session)
            if create:
                if con.execute('SELECT count(*) FROM plans WHERE user_id=?',(session.user_id,)).fetchone()[0]>=100:
                    raise AccountError(422,'Your library holds up to 100 plans. Delete an unused plan before saving another.')
            else:
                row=con.execute('SELECT revision FROM plans WHERE id=? AND user_id=?',(plan_id,session.user_id)).fetchone()
                if not row:raise AccountError(404,'Saved plan not found.')
                if type(revision) is not int or row[0]!=revision:raise AccountError(409,'This plan changed in another tab. Reopen it before saving.')
            new_revision=revision+1;encrypted=self.keys.encrypt(value,self._plan_aad(session.user_id,plan_id,new_revision))
            if create:con.execute('INSERT INTO plans VALUES(?,?,?,?,?,?)',(plan_id,session.user_id,new_revision,encrypted,now,now))
            else:con.execute('UPDATE plans SET revision=?,ciphertext=?,updated=? WHERE id=? AND user_id=?',(new_revision,encrypted,now,plan_id,session.user_id))
        return {'id':plan_id,'revision':new_revision,'updated':now}

    def list_plans(self,session):
        with self.db() as con:
            self._authorize(con,session)
            rows=con.execute('SELECT * FROM plans WHERE user_id=? ORDER BY updated DESC,id',(session.user_id,)).fetchall()
        result=[]
        for row in rows:
            value=self.keys.decrypt(row['ciphertext'],self._plan_aad(session.user_id,row['id'],row['revision']))
            result.append({'id':row['id'],'revision':row['revision'],'created':row['created'],'updated':row['updated'],
                           'title':value['title'],'kind':value['kind']})
        return result

    def open_plan(self,session,plan_id):
        self._plan_id(plan_id)
        with self.db() as con:
            self._authorize(con,session)
            row=con.execute('SELECT * FROM plans WHERE id=? AND user_id=?',(plan_id,session.user_id)).fetchone()
        if not row:raise AccountError(404,'Saved plan not found.')
        value=self.keys.decrypt(row['ciphertext'],self._plan_aad(session.user_id,plan_id,row['revision']))
        return {'id':plan_id,'revision':row['revision'],'updated':row['updated'],**value}

    def delete_plan(self,session,plan_id,revision):
        self._plan_id(plan_id)
        with self.db(write=True) as con:
            self._authorize(con,session)
            row=con.execute('SELECT revision FROM plans WHERE id=? AND user_id=?',(plan_id,session.user_id)).fetchone()
            if not row:raise AccountError(404,'Saved plan not found.')
            if type(revision) is not int or row[0]!=revision:raise AccountError(409,'This plan changed in another tab. Refresh the library before deleting.')
            con.execute('DELETE FROM plans WHERE id=? AND user_id=?',(plan_id,session.user_id))


def default_paths():
    root=Path(__file__).resolve().parents[2]
    return Path(os.environ.get('ECON_DATABASE_PATH',root/'data/accounts.sqlite3')),Path(os.environ.get('ECON_KEY_FILE',root/'.secrets/keyring.json'))


def initialize_files(path,key_path):
    path,key_path=Path(path),Path(key_path)
    if path.resolve()==key_path.resolve():raise VaultError('Store keys separately from the database.')
    if path.exists() and not key_path.exists():raise VaultError('Existing database has no keyring. Restore the original keyring; do not create a new one.')
    if not key_path.exists():Keyring.generate().write_new(key_path)
    keys=Keyring.load(key_path)
    return AccountStore(path,keys) if path.exists() else AccountStore.initialize(path,keys)


def rotate_keys(path,key_path):
    # Stop the service first. Keep old keys for backup recovery; never retire them here.
    keys=Keyring.load(key_path);store=AccountStore(path,keys)
    new_id=secrets.token_hex(8)
    rotated=Keyring(new_id,{**keys.keys,new_id:secrets.token_bytes(32)},keys.index_key)
    temporary=key_path.with_name(key_path.name+'.rotation')
    rotated.write_new(temporary);os.replace(temporary,key_path)
    with store.db(write=True) as con:
        for row in con.execute('SELECT * FROM users').fetchall():
            aad='econ/user/'+row['id'];con.execute('UPDATE users SET identity=? WHERE id=?',(rotated.encrypt(keys.decrypt(row['identity'],aad),aad),row['id']))
        for row in con.execute('SELECT * FROM plans').fetchall():
            aad=store._plan_aad(row['user_id'],row['id'],row['revision'])
            con.execute('UPDATE plans SET ciphertext=? WHERE id=?',(rotated.encrypt(keys.decrypt(row['ciphertext'],aad),aad),row['id']))
        con.execute("UPDATE metadata SET value=? WHERE key='probe'",(rotated.encrypt({'ok':True,'index':rotated.index('probe','v1')},'econ/database/v1'),))
    return AccountStore(path,rotated)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Initialize or rotate local account storage. Stop Econ before rotation.')
    parser.add_argument('command',choices=['init','rotate-keys']);args=parser.parse_args();path,key_path=default_paths()
    try:
        initialize_files(path,key_path) if args.command=='init' else rotate_keys(path,key_path)
        print('Account storage ready.' if args.command=='init' else 'Data key rotated; old keys retained for backup recovery.')
    except (VaultError,OSError,sqlite3.Error):
        parser.exit(1,'Account storage could not be opened. Check private file permissions and the original database/keyring.\n')
