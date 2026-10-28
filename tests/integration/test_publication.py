from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import shutil

import pytest

ROOT=Path(__file__).resolve().parents[2]

def module(name):
    spec=spec_from_file_location(name,ROOT/'tools'/f'{name}.py');value=module_from_spec(spec);spec.loader.exec_module(value);return value


@pytest.fixture
def publication(tmp_path):
    builder=module('build_showcase');report=tmp_path/'result.xml'
    report.write_text('<testsuites><testsuite tests="2" failures="0" errors="0"><testcase name="a"/><testcase name="b"/></testsuite></testsuites>')
    source=tmp_path/'site';shutil.copytree(ROOT/'site',source)
    return builder,report,source,tmp_path/'public'


def test_build_contains_only_public_allowlist_and_verified_metadata(publication):
    builder,report,source,out=publication
    assert builder.build('owner/Econ-Sdd',report,out,source=source)==2
    actual={p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}
    assert actual==builder.PUBLIC_FILES|{'.nojekyll'}
    page=(out/'index.html').read_text()
    assert 'https://github.com/owner/Econ-Sdd/blob/main/docs/goal-spec.md' in page
    assert '__REPOSITORY_URL__' not in page and '<strong>2</strong>' in page
    assert '<form' not in page and '/api/' not in page
    assert not any(p.suffix in {'.py','.sqlite3','.key'} for p in out.rglob('*'))


@pytest.mark.parametrize('failure',['<failure/>','<error/>'])
def test_failed_test_evidence_blocks_build(publication,failure):
    builder,report,source,out=publication;report.write_text(f'<testsuites><testsuite><testcase>{failure}</testcase></testsuite></testsuites>')
    with pytest.raises(ValueError):builder.build('owner/Econ-Sdd',report,out,source=source)
    assert not out.exists()


@pytest.mark.parametrize('path',['secret.json','assets/leaked.sqlite3'])
def test_extra_source_files_never_enter_pages(publication,path):
    builder,report,source,out=publication;(source/path).parent.mkdir(exist_ok=True,parents=True);(source/path).write_text('private')
    with pytest.raises(ValueError):builder.build('owner/Econ-Sdd',report,out,source=source)
    assert not out.exists()


def test_symlink_and_unreviewed_output_block_build(publication,tmp_path):
    builder,report,source,out=publication;asset=source/'assets/styles.css';asset.unlink();secret=tmp_path/'private.txt';secret.write_text('private');asset.symlink_to(secret)
    with pytest.raises(ValueError):builder.build('owner/Econ-Sdd',report,out,source=source)
    asset.unlink();asset.write_text('body{}');out.mkdir();(out/'database.sqlite3').write_text('private')
    with pytest.raises(ValueError):builder.build('owner/Econ-Sdd',report,out,source=source)


@pytest.mark.parametrize('path',['.secrets/keyring.json','data/accounts.sqlite3','renamed.db','work/results.json','.env','/absolute/file','../secret','src/__pycache__/x.pyc'])
def test_publication_guard_blocks_private_paths(path):
    assert module('check_publication').unsafe_path(path)


def test_publication_guard_detects_renamed_db_keyring_and_tokens(tmp_path):
    checker=module('check_publication')
    for body in [b'SQLite format 3\0rest',b'{"index_key":"'+b'A'*44+b'"}',b'ghp_'+b'x'*40]:
        (tmp_path/'innocent.txt').write_bytes(body)
        assert checker.audit(['innocent.txt'],tmp_path)
    (tmp_path/'innocent.txt').write_text('ordinary source')
    assert checker.audit(['innocent.txt'],tmp_path)==[]
