"""GET /profile for a brand-new user with no profile row and only user_id in the session must render (no KeyError)."""
import os, tempfile
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from _jobs_helpers import client_for, make_user, query  # noqa: E402


def test_profile_empty_user_renders():
    u = make_user()
    assert query('SELECT COUNT(*) AS n FROM userprofiles WHERE user_id=%s', (u,), one=True)['n'] == 0
    r = client_for(u).get('/profile', follow_redirects=True)
    assert r.status_code == 200
    assert 'Garden medals' in r.get_data(as_text=True)
