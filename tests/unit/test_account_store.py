from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
from uuid import uuid4

import pytest

from econ_sdd.accounts import (AccountStore,AccountError,IDLE_SECONDS,ABSOLUTE_SECONDS,PH,
                               initialize_files,rotate_keys,valid_username,valid_password)
from econ_sdd.security import Keyring,VaultError

PASSWORD='synthetic test password 938!'
OTHER_PASSWORD='replacement test password 593!'


@pytest.fixture
def vault(tmp_path):
    database=tmp_path/'data'/'accounts.sqlite3';keyfile=tmp_path/'keys'/'ring.json'
    store=initialize_files(database,keyfile)
    now=[1800000000];store.clock=lambda:now[0]
    return store,keyfile,now


def registered(store,name='Test_User'):
    token,recovery=store.register(name,PASSWORD,'test-client')
    return token,recovery,store.session(token)


def plan(**updates):
    value={'title':'Private reserve 492817','kind':'savings','model_version':'savings-v1',
           'inputs':{'initial_balance':'89475612.34','monthly_contribution':'100','annual_effective_rate_percent':'5','duration_months':12}}
    value.update(updates);return value


def test_encryption_uses_fresh_nonce_and_context_binding():
    keys=Keyring.generate();value={'private':'private marker 492817'}
    one=keys.encrypt(value,'owner-a/id-1/1');two=keys.encrypt(value,'owner-a/id-1/1')
    assert one!=two and keys.decrypt(one,'owner-a/id-1/1')==value
    for aad in ['owner-b/id-1/1','owner-a/id-2/1','owner-a/id-1/2','identity']:
        with pytest.raises(VaultError):keys.decrypt(one,aad)
    with pytest.raises(VaultError):Keyring.generate().decrypt(one,'owner-a/id-1/1')
    with pytest.raises(VaultError):keys.decrypt(one[:-4]+'AAAA','owner-a/id-1/1')


def test_initialization_is_idempotent_and_private(vault):
    store,keyfile,_=vault;before=keyfile.read_bytes()
    assert initialize_files(store.path,keyfile).path==store.path
    assert keyfile.read_bytes()==before
    assert stat.S_IMODE(store.path.stat().st_mode)==0o600
    assert stat.S_IMODE(keyfile.stat().st_mode)==0o600
    assert stat.S_IMODE(keyfile.parent.stat().st_mode)==0o700
    with store.db() as con:
        assert con.execute('PRAGMA foreign_keys').fetchone()[0]==1
        assert con.execute('PRAGMA user_version').fetchone()[0]==1
        tables={row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {'users','sessions','plans','metadata','attempts'}<=tables


def test_missing_keys_are_never_silently_regenerated(vault):
    store,keyfile,_=vault;registered(store)
    moved=keyfile.with_suffix('.backup');keyfile.rename(moved)
    with pytest.raises(VaultError):initialize_files(store.path,keyfile)
    assert not keyfile.exists() and moved.exists()


def test_wrong_keys_and_unknown_schema_fail_closed(vault):
    store,keyfile,_=vault
    with pytest.raises(VaultError):AccountStore(store.path,Keyring.generate())
    with store.db(write=True) as con:con.execute('PRAGMA user_version=999')
    with pytest.raises(VaultError):AccountStore(store.path,Keyring.load(keyfile))


@pytest.mark.parametrize('target',['key','key_parent','database','database_parent'])
def test_unsafe_permissions_are_rejected(vault,target):
    store,keyfile,_=vault
    path={'key':keyfile,'key_parent':keyfile.parent,'database':store.path,'database_parent':store.path.parent}[target]
    original=stat.S_IMODE(path.stat().st_mode);path.chmod(original|0o040)
    try:
        with pytest.raises(VaultError):
            if target.startswith('key'):Keyring.load(keyfile)
            else:AccountStore(store.path,store.keys)
    finally:path.chmod(original)


def test_key_symlink_and_truncated_key_file_fail(vault):
    _,keyfile,_=vault
    link=keyfile.with_name('alias.json');link.symlink_to(keyfile)
    with pytest.raises(VaultError):Keyring.load(link)
    keyfile.write_text('{"version":1}')
    with pytest.raises(VaultError):Keyring.load(keyfile)


def test_passwords_use_argon2id_and_tokens_codes_are_not_plaintext(vault):
    store,_,_=vault;token,code,session=registered(store)
    saved=store.save_plan(session,plan())
    with store.db() as con:
        user=con.execute('SELECT * FROM users').fetchone()
        assert user['password_hash'].startswith('$argon2id$v=19$m=65536,t=3,p=1$')
        assert PH.verify(user['password_hash'],PASSWORD)
        assert con.execute('SELECT token_hash FROM sessions').fetchone()[0]!=token
    raw=store.path.read_bytes()
    for marker in [PASSWORD,token,code,'Test_User','Private reserve 492817','89475612.34']:
        assert marker.encode() not in raw
    assert store.open_plan(session,saved['id'])['inputs']['initial_balance']=='89475612.34'


def test_login_case_insensitive_rotation_and_same_failure_message(vault):
    store,_,_=vault;token,_,_=registered(store)
    replacement=store.login('test_USER',PASSWORD,'test-client',token)
    assert replacement!=token and store.session(token) is None
    assert store.session(replacement).username=='Test_User'
    messages=[]
    for name in ['Test_User','Unknown_User']:
        with pytest.raises(AccountError) as exc:store.login(name,'incorrect password','test-client')
        assert exc.value.status==401;messages.append(exc.value.errors)
    assert messages[0]==messages[1]
    with pytest.raises(AccountError) as exc:store.register('TEST_USER',PASSWORD,'test-client')
    assert exc.value.status==409


def test_successful_login_rehashes_old_parameters(vault):
    from argon2 import PasswordHasher,Type
    store,_,_=vault;registered(store)
    old=PasswordHasher(time_cost=2,memory_cost=19456,parallelism=1,type=Type.ID).hash(PASSWORD)
    with store.db(write=True) as con:con.execute('UPDATE users SET password_hash=?',(old,))
    store.login('test_user',PASSWORD,'test-client')
    with store.db() as con:new=con.execute('SELECT password_hash FROM users').fetchone()[0]
    assert new!=old and not PH.check_needs_rehash(new)


@pytest.mark.parametrize('value',['ab','a b','abc@def','x'*33,'éabc',None,123,'abc\x00'])
def test_username_bounds(value):
    with pytest.raises(AccountError):valid_username(value)


@pytest.mark.parametrize('value',['x'*14,'x'*129,None,123,'\ud800'*15])
def test_password_bounds_and_no_truncation(value):
    with pytest.raises(AccountError):valid_password(value)


def test_unicode_and_spaces_allowed_without_password_normalization(vault):
    store,_,_=vault;password='  Café 🪴 password  '
    token,_=store.register('Unicode_User',password,'client')
    assert store.session(token)
    with pytest.raises(AccountError):store.login('Unicode_User',password.strip(),'client')


def test_idle_and_absolute_expiration(vault):
    store,_,now=vault;token,_,_=registered(store)
    now[0]+=IDLE_SECONDS-1;assert store.session(token)
    now[0]+=IDLE_SECONDS;assert store.session(token) is None
    token=store.login('test_user',PASSWORD,'client')
    with store.db(write=True) as con:con.execute('UPDATE sessions SET created=?,last_seen=?',(now[0]-ABSOLUTE_SECONDS,now[0]))
    assert store.session(token) is None


def test_logout_revokes_sessions_for_all_private_operations(vault):
    store,_,_=vault;token,_,session=registered(store);saved=store.save_plan(session,plan())
    store.logout(session);assert store.session(token) is None
    for operation in [lambda:store.list_plans(session),lambda:store.open_plan(session,saved['id']),
                      lambda:store.save_plan(session,plan()),lambda:store.delete_plan(session,saved['id'],1)]:
        with pytest.raises(AccountError) as exc:operation()
        assert exc.value.status==401


def test_recovery_is_one_use_revokes_all_sessions_and_preserves_plans(vault):
    store,_,_=vault;one,code,session=registered(store);saved=store.save_plan(session,plan())
    two=store.login('test_user',PASSWORD,'client')
    replacement,new_code=store.recover('TEST_USER',code,OTHER_PASSWORD,'client')
    assert new_code!=code and store.session(one) is None and store.session(two) is None
    assert store.open_plan(store.session(replacement),saved['id'])['title']==plan()['title']
    with pytest.raises(AccountError):store.recover('test_user',code,PASSWORD,'client')
    with pytest.raises(AccountError):store.login('test_user',PASSWORD,'client')
    assert store.session(store.login('test_user',OTHER_PASSWORD,'client'))


def test_password_change_requires_current_password_and_revokes_others(vault):
    store,_,_=vault;one,old_code,session=registered(store);two=store.login('test_user',PASSWORD,'client')
    with pytest.raises(AccountError):store.replace_password(session,'wrong current password',OTHER_PASSWORD)
    replacement,new_code=store.replace_password(session,PASSWORD,OTHER_PASSWORD)
    assert new_code!=old_code and store.session(one) is None and store.session(two) is None
    assert store.session(replacement)
    with pytest.raises(AccountError):store.recover('test_user',old_code,PASSWORD,'client')


def test_two_user_crud_isolation_and_optimistic_revisions(vault):
    store,_,_=vault;_,_,a=registered(store,'Alice_QA');_,_,b=registered(store,'Bob_QA')
    saved=store.save_plan(a,plan())
    assert store.list_plans(b)==[]
    for action in [lambda:store.open_plan(b,saved['id']),lambda:store.save_plan(b,plan(),plan_id=saved['id'],revision=1),
                   lambda:store.delete_plan(b,saved['id'],1),lambda:store.open_plan(b,str(uuid4()))]:
        with pytest.raises(AccountError) as exc:action()
        assert exc.value.status==404 and exc.value.errors=={'form':'Saved plan not found.'}
    updated=store.save_plan(a,plan(title='Updated'),plan_id=saved['id'],revision=1)
    assert updated['revision']==2
    for action in [lambda:store.save_plan(a,plan(),plan_id=saved['id'],revision=1),lambda:store.delete_plan(a,saved['id'],1)]:
        with pytest.raises(AccountError) as exc:action()
        assert exc.value.status==409
    store.delete_plan(a,saved['id'],2);assert store.list_plans(a)==[]


def test_concurrent_updates_allow_only_one_winner(vault):
    store,_,_=vault;_,_,user=registered(store);saved=store.save_plan(user,plan())
    def update(title):
        try:return store.save_plan(user,plan(title=title),plan_id=saved['id'],revision=1)['revision']
        except AccountError as exc:return exc.status
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(update,['One','Two']))
    assert sorted(results)==[2,409]


@pytest.mark.parametrize('tamper',['ciphertext','owner','revision'])
def test_plan_tampering_fails_authentication(vault,tamper):
    store,_,_=vault;_,_,a=registered(store,'Alice_QA');_,_,b=registered(store,'Bob_QA');saved=store.save_plan(a,plan())
    user=a
    with store.db(write=True) as con:
        if tamper=='ciphertext':con.execute('UPDATE plans SET ciphertext=?',('1:AAAA',))
        elif tamper=='owner':con.execute('UPDATE plans SET user_id=?',(b.user_id,));user=b
        else:con.execute('UPDATE plans SET revision=2')
    with pytest.raises(VaultError):store.open_plan(user,saved['id'])


def test_plan_quota_is_enforced(vault):
    store,_,_=vault;_,_,user=registered(store)
    for i in range(100):store.save_plan(user,plan(title=str(i)))
    with pytest.raises(AccountError) as exc:store.save_plan(user,plan())
    assert exc.value.status==422 and len(store.list_plans(user))==100


def test_persistent_rate_limit_expiry_and_no_plaintext_indices(vault):
    store,keyfile,now=vault
    for _ in range(5):
        with pytest.raises(AccountError) as exc:store.login('Guess_User','wrong','192.0.2.99')
        assert exc.value.status==401
    reopened=AccountStore(store.path,Keyring.load(keyfile),clock=store.clock)
    with pytest.raises(AccountError) as exc:reopened.login('Guess_User',PASSWORD,'another-client')
    assert exc.value.status==429
    raw=store.path.read_bytes();assert b'Guess_User' not in raw and b'192.0.2.99' not in raw
    now[0]+=901
    with pytest.raises(AccountError) as exc:reopened.login('Guess_User','wrong','192.0.2.99')
    assert exc.value.status==401


def test_restart_backup_restore_and_key_rotation(vault,tmp_path):
    store,keyfile,_=vault;token,_,user=registered(store);saved=store.save_plan(user,plan())
    backup_dir=tmp_path/'backup';backup_dir.mkdir(mode=0o700)
    backup=backup_dir/'accounts.sqlite3';shutil.copy2(store.path,backup)
    reopened=AccountStore(backup,Keyring.load(keyfile),clock=store.clock)
    assert reopened.open_plan(reopened.session(token),saved['id'])['title']==plan()['title']
    old_keys=store.keys;rotated=rotate_keys(store.path,keyfile);rotated.clock=store.clock
    assert rotated.keys.active!=old_keys.active and set(old_keys.keys)<=set(rotated.keys.keys)
    assert rotated.open_plan(rotated.session(token),saved['id'])['inputs']==plan()['inputs']
    assert AccountStore(backup,Keyring.load(keyfile),clock=store.clock).session(token)
    with pytest.raises(VaultError):AccountStore(store.path,old_keys)


def test_missing_runtime_database_is_not_recreated(vault):
    store,_,_=vault;_,_,user=registered(store);moved=store.path.with_suffix('.backup');store.path.rename(moved)
    with pytest.raises(VaultError):store.list_plans(user)
    assert not store.path.exists()


def test_recovery_race_consumes_code_exactly_once(vault):
    store,_,_=vault;_,code,_=registered(store)
    def recover(_):
        try:return store.recover('test_user',code,OTHER_PASSWORD,'client')[0]
        except AccountError as exc:return exc.status
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(recover,range(2)))
    assert sum(isinstance(value,str) for value in results)==1 and 401 in results


def test_session_count_and_client_attempts_are_bounded(vault):
    store,_,_=vault;_,_,user=registered(store)
    with store.db(write=True) as con:
        for _ in range(15):store._new_session(con,user.user_id)
        assert con.execute('SELECT count(*) FROM sessions WHERE user_id=?',(user.user_id,)).fetchone()[0]==10
    for i in range(30):store._limit('login',str(i),'one-client')
    with pytest.raises(AccountError) as exc:store._limit('login','another-name','one-client')
    assert exc.value.status==429


def test_interrupted_key_rotation_rolls_back_data_but_keeps_old_keys(vault,monkeypatch):
    store,keyfile,_=vault;token,_,user=registered(store);saved=store.save_plan(user,plan())
    encrypt=Keyring.encrypt
    def interrupt(self,value,aad):
        if self.active!='1' and aad.startswith('econ/plan/'):raise VaultError('simulated interruption')
        return encrypt(self,value,aad)
    with monkeypatch.context() as context:
        context.setattr(Keyring,'encrypt',interrupt)
        with pytest.raises(VaultError):rotate_keys(store.path,keyfile)
    recovered=AccountStore(store.path,Keyring.load(keyfile),clock=store.clock)
    assert recovered.open_plan(recovered.session(token),saved['id'])['title']==plan()['title']
