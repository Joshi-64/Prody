"""Dashboard greeting and date follow America/New_York, not the UTC server clock."""
import os, tempfile
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from datetime import datetime, timezone
import app as app_module
from _jobs_helpers import app, make_user


def test_greeting_at_830pm_et(monkeypatch):
    # 00:30 UTC Sat Oct 24 == 8:30 PM EDT Fri Oct 23
    utc = datetime(2026, 10, 24, 0, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(app_module, '_local_now', lambda: utc.astimezone(app_module.APP_TZ))
    uid = make_user()
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid; s['role'] = 'student'
    html = c.get('/dashboard').get_data(as_text=True)
    assert 'Good evening · Friday, October 23' in html
    assert 'Good morning' not in html and 'Saturday, October 24' not in html


def test_local_now_is_new_york():
    assert app_module._local_now().tzinfo.key == 'America/New_York'
