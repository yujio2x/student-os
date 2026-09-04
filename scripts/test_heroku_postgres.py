"""Local test runner: Heroku-managed URL -> child environment, never stdout/files.

Runs only schema-isolated tests against the explicitly named staging database.
No polling, paid AI, production/public table writes or credential copying to Doppler.
"""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CLI = Path(r"C:\Program Files\heroku\bin\heroku.cmd")

def main():
    result = subprocess.run([str(CLI), "config:get", "DATABASE_URL", "--app", "student-os-ernar-beta"],
                            capture_output=True, text=True, timeout=30)
    if result.returncode or not result.stdout.strip().startswith(("postgres://", "postgresql://")):
        print("Heroku-managed PostgreSQL configuration unavailable; no values printed")
        return 1
    environment = os.environ.copy()
    environment["STUDENT_OS_TEST_DATABASE_URL"] = result.stdout.strip()
    result = None
    return subprocess.run([sys.executable, "-m", "pytest", "tests/test_postgres.py", "-q",
                           "-p", "no:cacheprovider", "--tb=short", *sys.argv[1:]], cwd=ROOT, env=environment).returncode

if __name__ == "__main__":
    raise SystemExit(main())
