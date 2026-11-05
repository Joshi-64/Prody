"""Live Turso/libSQL checks. Opt-in: set RUN_TURSO_LIVE=1 and TURSO_* (or secrets file).
Never prints secrets. Skipped by default so the normal suite stays offline/fast.
"""
import os, sys
from pathlib import Path

import pytest

_RUN = os.environ.get('RUN_TURSO_LIVE', '').lower() in ('1', 'true', 'yes')
pytestmark = pytest.mark.skipif(not _RUN, reason='set RUN_TURSO_LIVE=1 to hit live Turso')


def _load_secrets():
    if os.environ.get('TURSO_DATABASE_URL') and os.environ.get('TURSO_AUTH_TOKEN'):
        return
    secret = Path('/workspace/.pp_secrets/turso_preview.env')
    if not secret.is_file():
        return
    for line in secret.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@pytest.fixture(scope='module')
def turso_db():
    _load_secrets()
    if not (os.environ.get('TURSO_DATABASE_URL') and os.environ.get('TURSO_AUTH_TOKEN')):
        pytest.skip('TURSO_* not set')
    os.environ.pop('PRODY_DB', None)
    os.environ['PRODY_USE_TURSO'] = '1'
    os.environ.setdefault('VERCEL_ENV', 'preview')
    for name in list(sys.modules):
        if name in ('db', 'helpers', 'app', 'apptime', 'fn_flags', 'seed_demo') or name.startswith(('db.', 'helpers.')):
            del sys.modules[name]
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import db
    assert db.DB_BACKEND == 'libsql', db.DB_BACKEND
    db.init_db()
    from helpers import query
    return db, query


def test_helpers_query_uses_get_db_connection(turso_db):
    db, query = turso_db
    assert db.get_db_connection().__class__.__name__ == '_LibsqlConnection'
    import helpers, inspect
    src = inspect.getsource(helpers.query)
    assert 'get_db_connection' in src and 'sqlite3.connect' not in src


def test_schema_and_dm_board_roundtrip(turso_db):
    db, query = turso_db
    import apptime
    from werkzeug.security import generate_password_hash
    for t in ('users', 'dm_messages', 'forum_threads', 'forum_replies',
              'studyrooms', 'studyroom_members', 'studyroom_strokes'):
        assert 'n' in query(f'SELECT COUNT(*) AS n FROM {t}', one=True)
    tag = 'pytest_turso'
    row = query('SELECT id FROM users WHERE username=%s', (tag,), one=True)
    if not row:
        uid = query('INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,%s)',
                    (tag, 'pytest_turso@test.invalid', generate_password_hash('x'), 'student',
                     apptime.now_utc_naive()), commit=True)
    else:
        uid = int(row['id'])
    mid = query('INSERT INTO dm_messages (sender_id, recipient_id, body, created_at) VALUES (%s,%s,%s,%s)',
                (uid, uid, 'self-note', apptime.now_utc_naive()), commit=True)
    assert int(mid) >= 1
    tid = query(
        'INSERT INTO forum_threads (scope, course_id, university, author_id, title, body, created_at, pinned, hidden) '
        'VALUES (%s,NULL,%s,%s,%s,%s,%s,0,0)',
        ('global', '', uid, 'pytest', 'body', apptime.now_utc_naive()), commit=True)
    assert int(tid) >= 1


def test_seed_demo_refuses_wipe_on_libsql(turso_db):
    db, query = turso_db
    import seed_demo
    with pytest.raises(RuntimeError, match='refusing wipe'):
        seed_demo.wipe(1)


def test_plantmilestones_float_insert_and_dashboard(turso_db):
    """Home /dashboard 500'd because hours_at float was stringified for Turso."""
    db, query = turso_db
    import apptime, plant
    from werkzeug.security import generate_password_hash
    tag = 'pytest_turso_plant'
    row = query('SELECT id FROM users WHERE username=%s', (tag,), one=True)
    if not row:
        uid = query(
            'INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,%s)',
            (tag, 'pytest_turso_plant@test.invalid', generate_password_hash('x'), 'student',
             apptime.now_utc_naive()), commit=True)
    else:
        uid = int(row['id'])
    query('DELETE FROM plantmilestones WHERE user_id=%s', (uid,), commit=True)
    mid = query(
        'INSERT INTO plantmilestones (user_id, stage, hours_at, reached_at) VALUES (%s,%s,%s,%s)',
        (uid, 'Sprout', 12.5, apptime.now_utc_naive()), commit=True)
    assert int(mid) >= 1
    got = query('SELECT hours_at FROM plantmilestones WHERE milestone_id=%s', (mid,), one=True)
    assert float(got['hours_at']) == 12.5
    # plant.record_milestones path (float hours on state)
    st = {'stage_idx': 2, 'hours': 3.25}
    query('DELETE FROM plantmilestones WHERE user_id=%s', (uid,), commit=True)
    new = plant.record_milestones(uid, st)
    assert new  # Sprout (+ maybe Sapling)
    # Flask dashboard must not 500
    for name in list(__import__('sys').modules):
        if name in ('app',) or name.startswith('app.'):
            del __import__('sys').modules[name]
    from app import app
    app.config['WTF_CSRF_ENABLED'] = False
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid
        s['role'] = 'student'
    r = c.get('/dashboard')
    assert r.status_code < 500, (r.status_code, r.data[:400])
