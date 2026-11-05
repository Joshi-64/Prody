"""One-command fresh setup:  python seed.py
Builds the database from scratch (schema + migrations; store items load from static/shop/items.json and
profiles.CATALOG, so they need no rows), then creates prody_admin and prody_student.
Passwords come from PRODY_ADMIN_PASSWORD / PRODY_STUDENT_PASSWORD, or from .secrets/test_accounts.env
(KEY=VALUE) when those are not set. Defaults to SQLite (prody_dev.sqlite3); set PRODY_DB=mysql to seed MySQL."""
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('PRODY_DB', 'sqlite')
secrets = os.path.join(HERE, '.secrets', 'test_accounts.env')
if os.path.exists(secrets):
    for line in open(secrets):
        if '=' in line and not line.lstrip().startswith('#'):
            k, v = line.strip().split('=', 1)
            os.environ.setdefault(k, v)
os.chdir(HERE)
runpy.run_path(os.path.join(HERE, 'seed_testers.py'), run_name='__main__')
