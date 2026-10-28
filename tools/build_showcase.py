"""Build only the reviewed public assets; never package the application directory."""
import argparse
import ast
import html
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
PUBLIC_FILES=frozenset({'index.html','assets/styles.css','assets/showcase.js','assets/icon.svg','assets/goal.png','assets/cash-flow.png',
                        'assets/fonts/Poppins-400.ttf','assets/fonts/Poppins-600.ttf','assets/fonts/Poppins-700.ttf','assets/fonts/OFL.txt'})
REPOSITORY=re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]{1,100}\Z')


def passing_count(report):
    root=ET.parse(report).getroot()
    cases=root.findall('.//testcase')
    if root.tag not in {'testsuites','testsuite'} or not cases:raise ValueError('Use an actual passing pytest JUnit report.')
    if root.findall('.//failure') or root.findall('.//error'):raise ValueError('Failed checks cannot publish the showcase.')
    for suite in [root,*root.findall('.//testsuite')]:
        if int(suite.get('failures','0')) or int(suite.get('errors','0')):raise ValueError('Failed checks cannot publish the showcase.')
    return sum(case.find('skipped') is None for case in cases)


def version():
    module=ast.parse((ROOT/'src/econ_sdd/__init__.py').read_text())
    for node in module.body:
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='__version__' for target in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('A package version is required.')


def build(repository,report,output,*,source=ROOT/'site'):
    if not REPOSITORY.fullmatch(repository) or repository.split('/')[1] in {'.','..'}:raise ValueError('Use the verified owner/repository name.')
    count=passing_count(report)
    if count<1:raise ValueError('At least one check must have passed.')
    source=source.resolve();output=output.resolve()
    if output==source or source.is_relative_to(output) or output.is_relative_to(source):raise ValueError('Use a separate output directory.')
    actual={file.relative_to(source).as_posix() for file in source.rglob('*') if file.is_file() or file.is_symlink()}
    if actual!=PUBLIC_FILES:raise ValueError('The showcase source must match its reviewed asset allowlist exactly.')
    if any((source/path).is_symlink() or any(parent.is_symlink() for parent in (source/path).parents if parent.is_relative_to(source)) for path in actual):
        raise ValueError('Symlinks cannot enter the public artifact.')
    if output.exists():
        if output.is_symlink() or any(file.is_symlink() for file in output.rglob('*')):raise ValueError('Symlinks cannot enter the public artifact.')
        existing={file.relative_to(output).as_posix() for file in output.rglob('*') if file.is_file()}
        if not existing<=PUBLIC_FILES|{'.nojekyll'}:raise ValueError('Output contains unreviewed files; use a new empty directory.')
    output.mkdir(parents=True,exist_ok=True)
    replacements={'__REPOSITORY_URL__':html.escape('https://github.com/'+repository,quote=True),
                  '__OWNER__':html.escape(repository.split('/')[0]),'__TEST_COUNT__':str(count),'__VERSION__':html.escape(version())}
    for path in sorted(PUBLIC_FILES):
        target=output/path;target.parent.mkdir(parents=True,exist_ok=True)
        if path=='index.html':
            text=(source/path).read_text()
            for key,value in replacements.items():text=text.replace(key,value)
            if re.search(r'__[A-Z_]+__',text):raise ValueError('Unresolved publication metadata.')
            if '<form' in text or '/api/' in text:raise ValueError('The static showcase must not collect account or calculator inputs.')
            target.write_text(text)
        else:shutil.copyfile(source/path,target)
    (output/'.nojekyll').write_text('')
    return count


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',required=True);parser.add_argument('--test-report',required=True,type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'dist/showcase')
    args=parser.parse_args()
    try:count=build(args.repository,args.test_report,args.output)
    except (ValueError,OSError,ET.ParseError) as exc:parser.exit(1,str(exc)+'\n')
    print(f'Showcase built from {count} passing checks at {args.output}.')
