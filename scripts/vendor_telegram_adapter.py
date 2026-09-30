"""Explicit source snapshot, no build-time credentials or private Git dependency."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = ('bridge_handlers.py', 'bridge_client.py', 'payment_outbox.py', 'postgres_outbox.py')


def main():
    source = Path(sys.argv[1])
    target = ROOT / 'student_telegram'
    target.mkdir(exist_ok=True)
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    manifest = {'repository': 'yujio2x/student-ai-bot', 'commit': commit, 'files': {}}
    for name in FILES:
        original = (source / 'app' / name).read_text(encoding='utf-8')
        vendored = original
        for module in ('bridge_client', 'payment_outbox', 'postgres_outbox'):
            vendored = vendored.replace(f'from app.{module} ', f'from student_telegram.{module} ')
        (target / name).write_text(vendored, encoding='utf-8')
        manifest['files'][name] = hashlib.sha256(vendored.encode()).hexdigest()
    (target / '__init__.py').write_text('"""Pinned Bot-owned transport adapter; Core owns business semantics."""\n', encoding='utf-8')
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
