"""/roots/data and /journal must load for a user with a study session (as_dt NameError regression)."""
import os, tempfile
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from datetime import datetime, timedelta  # noqa: E402
from _jobs_helpers import client_for, make_user, query  # noqa: E402


def test_roots_data_and_journal_load_with_sessions():
    u = make_user()
    query('INSERT INTO studysessions (user_id, course_id, label, minutes, started_at, completed) VALUES (%s, %s, %s, %s, %s, %s)',
          (u, None, 'Reading', 30, datetime.utcnow() - timedelta(hours=1), 1), commit=True)
    c = client_for(u)
    for path in ('/roots/data', '/journal'):
        r = c.get(path, follow_redirects=True)
        assert r.status_code == 200, (path, r.status_code)
