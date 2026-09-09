"""Scan project-authored files, generated client artifacts and history without echoing secrets."""
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.git','.venv','node_modules','.worktrees','.next','.expo','.codex','data','__pycache__','.pytest_cache','.turbo','dist','coverage'}

def forbidden_endpoints(text):
    # Construct tokens to avoid embedding a prohibited endpoint in the scanner itself.
    nouns=('ord'+'ers','pos'+'itions','port'+'folio')
    return any(re.search(r'/(?:v\d+/)?'+noun+r'(?:[/\s?"\x27]|$)',text,re.I) for noun in nouns)

def scan():
    secrets=[]
    if (ROOT/'.env').exists():
        for line in (ROOT/'.env').read_text().splitlines():
            if '=' in line:
                key,value=line.split('=',1)
                if any(s in key for s in ('KEY','SECRET','PASSWORD')) and len(value.strip())>=12:secrets.append(value.strip().strip('\"\''))
    failures=[];count=0
    for path in ROOT.rglob('*'):
        if not path.is_file() or any(part in EXCLUDED for part in path.relative_to(ROOT).parts) or path.name.startswith('.env'):continue
        if path.name in ('uv.lock','package-lock.json'):continue
        try:content=path.read_text()
        except (UnicodeError,OSError):continue
        count+=1
        if forbidden_endpoints(content):failures.append(f'{path.relative_to(ROOT)}: prohibited endpoint reference')
        if any(secret in content for secret in secrets):failures.append(f'{path.relative_to(ROOT)}: credential value detected (withheld)')
    result=subprocess.run(['git','log','--all','--format=','--name-only','--','.env'],cwd=ROOT,capture_output=True,text=True)
    if result.stdout.strip():failures.append('.env appears in Git history')
    diff=subprocess.run(['git','log','--all','-p','--format='],cwd=ROOT,capture_output=True,text=True)
    if any(secret in diff.stdout for secret in secrets):failures.append('Credential value detected in Git history (withheld)')
    if failures:raise SystemExit('\n'.join(failures))
    print(f'PASS: {count} authored files scanned; no prohibited endpoints or credential values; .env absent from Git history.')

if __name__=='__main__':scan()
