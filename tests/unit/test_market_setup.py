"""The setup command only touches synthetic temporary account/key storage."""
import json
import stat
import sys

import pytest

from econ_sdd.accounts import initialize_files
from econ_sdd.market import __main__ as cli
from econ_sdd.market.config import load_profile


@pytest.fixture
def setup_cli(tmp_path,monkeypatch):
    database,key=tmp_path/'data'/'accounts.sqlite3',tmp_path/'private'/'keyring.json'
    store=initialize_files(database,key)
    token,_=store.register('Market_QA','synthetic setup password 821!','test')
    owner=store.session(token).user_id
    profile=tmp_path/'private'/'alpaca.json'
    monkeypatch.setattr(cli,'default_paths',lambda:(database,key))
    monkeypatch.setattr(cli,'profile_path',lambda:profile)
    monkeypatch.setattr(sys.stdin,'isatty',lambda:True)
    monkeypatch.setattr(sys,'argv',['setup','setup','--username','market_qa'])
    return profile,owner


def test_setup_hides_values_binds_existing_owner_and_writes_private_profile(setup_cli,monkeypatch,capsys):
    path,owner=setup_cli
    monkeypatch.setattr('builtins.input',lambda _: 'y')
    inputs=iter(['syntheticKEY','syntheticSECRET'])
    monkeypatch.setattr(cli.getpass,'getpass',lambda _:next(inputs))
    cli.main()
    profile,error=load_profile(path)
    assert not error and profile.owner_id==owner
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    output=capsys.readouterr().out
    assert 'syntheticKEY' not in output and 'syntheticSECRET' not in output


def test_declined_setup_does_not_collect_or_write_keys(setup_cli,monkeypatch):
    path,_=setup_cli
    monkeypatch.setattr('builtins.input',lambda _: 'n')
    monkeypatch.setattr(cli.getpass,'getpass',lambda _:pytest.fail('Keys must not be requested'))
    with pytest.raises(SystemExit) as caught:cli.main()
    assert caught.value.code==0 and not path.exists()


def test_existing_profile_never_overwritten_implicitly(setup_cli):
    path,_=setup_cli;path.write_text('existing private data')
    with pytest.raises(SystemExit):cli.main()
    assert path.read_text()=='existing private data'


def test_noninteractive_setup_refused(setup_cli,monkeypatch):
    path,_=setup_cli;monkeypatch.setattr(sys.stdin,'isatty',lambda:False)
    with pytest.raises(SystemExit):cli.main()
    assert not path.exists()


def test_private_keyring_failure_has_safe_error(setup_cli,monkeypatch,capsys):
    from econ_sdd.security import VaultError
    path,_=setup_cli
    def fail(_):raise VaultError('synthetic private storage details')
    monkeypatch.setattr(cli.Keyring,'load',fail)
    with pytest.raises(SystemExit) as caught:cli.main()
    assert caught.value.code==1 and not path.exists()
    output=capsys.readouterr()
    assert 'synthetic private storage details' not in output.out+output.err
