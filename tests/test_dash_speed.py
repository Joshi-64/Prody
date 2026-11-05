"""Dashboard speed work: merged reads, cached _columns, clean connections after a failed buy, dateless roots."""
import os, tempfile
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'dash_speed.db'))
from datetime import datetime
import pytest
from _jobs_helpers import client_for, make_course, make_user, query
import db


def _count_sql(monkeypatch):
    seen = []
    orig = db._SqliteCursor.execute

    def ex(self, sql, params=()):
        seen.append(sql)
        return orig(self, sql, params)
    monkeypatch.setattr(db._SqliteCursor, 'execute', ex)
    return seen


def test_dashboard_reads_sessions_and_todos_once(monkeypatch):
    u = make_user()
    query('INSERT INTO studysessions (user_id, minutes, started_at, completed) VALUES (%s, 25, %s, 1)', (u, datetime.now()), commit=True)
    query('INSERT INTO todolist (user_id, task_name, is_completed) VALUES (%s, %s, 1)', (u, 'x'), commit=True)
    c = client_for(u)
    seen = _count_sql(monkeypatch)
    r = c.get('/dashboard')
    assert r.status_code == 200
    low = [s.lower() for s in seen]
    assert sum('from studysessions' in s for s in low) == 1
    assert sum('from todolist' in s for s in low) == 1


def test_api_tree_columns_cached(monkeypatch):
    import api_tree
    u = make_user(); c = client_for(u)
    c.get('/api/tree')
    seen = _count_sql(monkeypatch)
    assert c.get('/api/tree').status_code == 200
    assert not any('pragma table_info' in s.lower() for s in seen)


def test_api_tree_skips_deadline_without_date():
    u = make_user(); cid = make_course(u, 'Bio', 0)
    query('INSERT INTO coursedeadlines (course_id, deadline_name, deadline_date) VALUES (%s, %s, %s)', (cid, 'NoDate', ''), commit=True)
    r = client_for(u).get('/api/tree')
    assert r.status_code == 200
    assert 'NoDate' not in r.get_data(as_text=True)


def test_failed_buy_leaves_clean_connection(monkeypatch):
    import profiles
    u = make_user(); c = client_for(u)
    key = next(k for k in profiles.CATALOG if profiles.item(k)['type'] not in profiles.RETIRED_TYPES) \
        if hasattr(profiles, 'CATALOG') else None
    if key is None:
        pytest.skip('no store items')
    monkeypatch.setattr(profiles, 'owned_keys', lambda uid: (_ for _ in ()).throw(RuntimeError('boom mid-txn')))
    profiles_app = c.application
    profiles_app.config['PROPAGATE_EXCEPTIONS'] = False
    try:
        assert c.post(f'/store/buy/{key}').status_code == 500
    finally:
        profiles_app.config['PROPAGATE_EXCEPTIONS'] = None
    monkeypatch.undo()
    # next request: a write lock is free immediately and the new connection has no open transaction
    conn, cur = db.locked_user_txn(u)
    try:
        conn._conn.execute('PRAGMA busy_timeout = 0')
        cur.execute('SELECT 1')
        conn.rollback()
    finally:
        cur.close(); conn.close()
    nxt = db.get_db_connection()
    try:
        assert nxt._conn.in_transaction is False
    finally:
        nxt.close()
    assert query('SELECT COUNT(*) AS n FROM userinventory WHERE user_id = %s', (u,), one=True)['n'] == 0


def test_query_rolls_back_before_close(monkeypatch):
    import helpers
    calls = []

    class C:
        def cursor(self, dictionary=False):
            class K:
                lastrowid = None
                def execute(s, *a): raise RuntimeError('fail')
                def close(s): calls.append('cur.close')
            return K()
        def rollback(self): calls.append('rollback')
        def close(self): calls.append('close')
    monkeypatch.setattr(helpers, 'get_db_connection', lambda: C())
    with pytest.raises(RuntimeError):
        helpers.query('SELECT 1')
    assert calls == ['cur.close', 'rollback', 'close']


def test_mysql_pool_no_session_reset():
    import inspect
    assert 'pool_reset_session=False' in inspect.getsource(db._mysql_pool)
