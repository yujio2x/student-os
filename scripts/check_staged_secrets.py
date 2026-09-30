"""Scan staged text blobs; report file/rule only, never matched values."""
import re
import subprocess
import sys

PATTERNS = {
    'OpenAI key': r'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}',
    'Telegram token': r'\b[0-9]{6,12}:[A-Za-z0-9_-]{30,}\b',
    'GitHub token': r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b',
    'Private key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'Database credentials': r'postgres(?:ql)?://[^\s/:]+:[^\s@]+@(?!localhost[:/]|127\.0\.0\.1[:/])',
}


def main():
    names = subprocess.check_output(['git','diff','--cached','--name-only','--diff-filter=ACMR','-z']).decode().split('\0')
    findings=[]
    for name in filter(None,names):
        if name == '.env' or name.endswith(('.db','.pem','.key')):
            findings.append((name,'private file'))
            continue
        data=subprocess.check_output(['git','show',':'+name])
        if b'\0' in data:
            continue
        body=data.decode('utf-8',errors='replace')
        for label,pattern in PATTERNS.items():
            if re.search(pattern,body):
                findings.append((name,label))
    for name,label in findings:
        print(f'{name}: {label}')
    print(f'Staged secret-pattern scan: {len(findings)} findings')
    return bool(findings)


if __name__ == '__main__':
    sys.exit(main())
