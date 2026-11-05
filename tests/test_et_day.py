"""Every day calculation goes through apptime (America/New_York); stored stamps are naive UTC."""
import os, tempfile
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from datetime import date, datetime
import pytest
from flask import render_template_string
import apptime
import app as app_module
from _jobs_helpers import app, make_user, make_course, query

FRI_830PM_ET = datetime(2026, 10, 23, 20, 30)  # == 00:30 UTC Sat Oct 24


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    monkeypatch.setattr(apptime, 'now_local', lambda: FRI_830PM_ET)
    import profiles  # care uses its own UTC clock; freeze it to the same instant (00:30 UTC Sat)
    monkeypatch.setattr(profiles, '_utcnow', lambda: datetime(2026, 10, 24, 0, 30))
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)


def _client(uid):
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid; s['role'] = 'student'
    return c


def test_helper_bounds():
    assert apptime.today_local() == date(2026, 10, 23)
    assert apptime.now_utc_naive() == datetime(2026, 10, 24, 0, 30)
    assert apptime.day_bounds_utc() == (datetime(2026, 10, 23, 4, 0), datetime(2026, 10, 24, 4, 0))
    assert apptime.local_date(datetime(2026, 10, 24, 0, 30)) == date(2026, 10, 23)


def test_due_today_and_overdue():
    assert app_module.rel_day(datetime(2026, 10, 23, 23, 59)) == 'Today'
    assert app_module.rel_day(datetime(2026, 10, 22, 23, 59)) == '1d overdue'
    assert app_module.rel_day(datetime(2026, 10, 24, 9, 0)) == 'Tomorrow'


def test_tasks_page_due_days():
    uid = make_user()
    query("INSERT INTO todolist (user_id, task_name, due_date, is_completed) VALUES (%s,'FriTask',%s,0)",
          (uid, date(2026, 10, 23)), commit=True)
    query("INSERT INTO todolist (user_id, task_name, due_date, is_completed) VALUES (%s,'ThuTask',%s,0)",
          (uid, date(2026, 10, 22)), commit=True)
    import tasks as tasks_mod
    seen = {}
    orig = tasks_mod.render_template
    def spy(tpl, **kw):
        for t in kw.get('tasks') or []:
            seen[t['task_name']] = t['due_days']
        return orig(tpl, **kw)
    tasks_mod.render_template = spy
    try:
        _client(uid).get('/tasks')
    finally:
        tasks_mod.render_template = orig
    assert seen.get('FriTask') == 0 and seen.get('ThuTask') == -1


def test_week_minutes_count_friday_utc_stamp():
    uid = make_user()
    query('INSERT INTO studysessions (user_id, label, minutes, started_at, completed) VALUES (%s,%s,%s,%s,1)',
          (uid, 'late', 37, datetime(2026, 10, 24, 0, 30)), commit=True)  # naive UTC = Fri 8:30 PM ET
    import app as m
    seen = {}
    orig = m.render_template
    def spy(tpl, **kw):
        seen.update(kw); return orig(tpl, **kw)
    m.render_template = spy
    try:
        _client(uid).get('/dashboard')
    finally:
        m.render_template = orig
    week = seen['week']
    assert week[-1] == {'label': 'Fri', 'minutes': 37}
    assert sum(w['minutes'] for w in week) == 37


def test_global_today_is_oct_23():
    with app.test_request_context('/'):
        assert render_template_string('{{ today.isoformat() }}') == '2026-10-23'


def test_care_once_a_day_friday():
    uid = make_user()
    c = _client(uid)
    r = c.post('/plant/care').get_json()
    assert r.get('ok') is not False
    assert str(query('SELECT MAX(cared_on) AS d FROM plantcare WHERE user_id=%s', (uid,), one=True)['d'])[:10] == '2026-10-23'
    assert c.post('/plant/care').get_json()['ok'] is False
