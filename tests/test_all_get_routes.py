"""Every GET route without URL params must not 500 for seed_demo's student (or admin). Catches rebase leftovers pytest never loads."""
import runpy, os, tempfile
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from _jobs_helpers import app, query

SKIP = {'/logout', '/static/<path:filename>'}


def _get_routes():
    return sorted({r.rule for r in app.url_map.iter_rules()
                   if 'GET' in r.methods and not r.arguments and r.rule not in SKIP})


def test_every_get_route_no_500():
    app.config['WTF_CSRF_ENABLED'] = False
    os.environ.setdefault('PRODY_ADMIN_PASSWORD', 'test-only-admin-pw')
    os.environ.setdefault('PRODY_STUDENT_PASSWORD', 'test-only-student-pw')
    if not query("SELECT id FROM users WHERE username = 'demo_student'", one=True):
        runpy.run_path(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'seed_demo.py'), run_name='seed_demo')
    bad = []
    for name in ('demo_student', 'demo_admin'):
        u = query('SELECT id, role FROM users WHERE username = %s', (name,), one=True)
        if not u:
            continue
        c = app.test_client()
        with c.session_transaction() as s:
            s['user_id'] = u['id']; s['role'] = u['role']
        for rule in _get_routes():
            code = c.get(rule).status_code
            if code >= 500:
                bad.append((name, rule, code))
    assert not bad, bad
    assert len(_get_routes()) > 10
