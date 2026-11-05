"""Shared test setup: one fresh SQLite DB per run, and app config restored after every test.

Never hit shared preview Turso from the suite — even if TURSO_* is exported in the
shell, force SQLite/temp and strip Turso env before importing db/app.
Opt-in live checks (tests/test_turso_live.py with RUN_TURSO_LIVE=1) reload TURSO_*
from the secrets file inside their own fixture after clearing modules.
"""
import os, sys, tempfile

# Force offline SQLite for the normal suite (preview Turso is shared — do not pollute it).
for _k in list(os.environ):
    if _k.startswith('TURSO_') or _k in ('LIBSQL_URL', 'LIBSQL_AUTH_TOKEN', 'PRODY_USE_TURSO'):
        os.environ.pop(_k, None)
os.environ['PRODY_DB'] = 'sqlite'
os.environ['PRODY_SQLITE_PATH'] = os.path.join(tempfile.mkdtemp(prefix='prody_tests_'), 'prody_test.sqlite3')
# Drop MySQL/TiDB overrides too so picker cannot leave sqlite.
for _k in list(os.environ):
    if _k.startswith('PRODY_DB_') and _k != 'PRODY_DB':
        os.environ.pop(_k, None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest  # noqa: E402
import app as prody_app  # noqa: E402  (init_db runs once on the shared temp DB)
import db as _db  # noqa: E402
assert _db.DB_BACKEND == 'sqlite', f'tests must use sqlite, got {_db.DB_BACKEND}'


@pytest.fixture(autouse=True)
def _restore_app_config():
    """Tests may flip TESTING / WTF_CSRF_ENABLED; put them back so nothing leaks into the next test."""
    saved = dict(prody_app.app.config)
    yield
    prody_app.app.config.clear()
    prody_app.app.config.update(saved)


@pytest.fixture
def csrf_off():
    """Turn CSRF off for one test (route logic under test); _restore_app_config puts it back afterwards."""
    prody_app.app.config['WTF_CSRF_ENABLED'] = False
    yield
