"""Server stamps (naive UTC) display in ET; user-entered times display as typed. Age checks vs UTC stamps."""
import os, tempfile, time
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from datetime import datetime, timedelta
import pytest
import apptime
import friends
import app as app_module
from _jobs_helpers import app, make_user, query

FRI_830PM_ET = datetime(2026, 10, 23, 20, 30)
STAMP = datetime(2026, 10, 24, 0, 30)  # naive UTC == Fri Oct 23 8:30 PM ET


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    monkeypatch.setattr(apptime, 'now_local', lambda: FRI_830PM_ET)


def _client(uid):
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid; s['role'] = 'student'
    return c


def test_filters_split():
    assert app_module.nice_stamp(STAMP, '%a %b %d %I:%M %p') == 'Fri Oct 23 8:30 PM'
    assert app_module.nice_dt(FRI_830PM_ET, '%a %b %d %I:%M %p') == 'Fri Oct 23 8:30 PM'


def test_study_page_shows_session_in_et():
    uid = make_user()
    query('INSERT INTO studysessions (user_id, label, minutes, started_at, completed) VALUES (%s,%s,%s,%s,1)',
          (uid, 'LateBlock', 25, STAMP), commit=True)
    html = _client(uid).get('/zen').get_data(as_text=True)
    assert 'LateBlock' in html and 'Oct 23, 8:30 PM' in html and 'Oct 24, 12:30 AM' not in html


def test_user_event_stays_as_typed():
    uid = make_user()
    query('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes) VALUES (%s,%s,%s,60)',
          (uid, 'Dinner', datetime(2026, 10, 23, 20, 30)), commit=True)
    html = _client(uid).get('/dashboard').get_data(as_text=True)
    assert '08:30 PM' in html or '8:30 PM' in html
    assert '04:30 PM' not in html and '4:30 PM' not in html


@pytest.mark.parametrize('tz', ['America/New_York', 'UTC'])
def test_online_window_age_check_ignores_server_tz(monkeypatch, tz):
    # No password-reset tokens on this base; the stamp-age checks are friends' online window.
    monkeypatch.setenv('TZ', tz); time.tzset()
    try:
        now = apptime.now_utc_naive()
        win = friends.ONLINE_WINDOW
        assert friends.is_online(now - win + timedelta(seconds=1), now)
        assert not friends.is_online(now - win - timedelta(seconds=1), now)
        assert friends.is_online(now - win + timedelta(seconds=1))  # default 'now' is UTC too
    finally:
        monkeypatch.undo(); time.tzset()
