"""/calendar must render for seed_demo data (calendar-event deadlines had no 'days': 500 in _urgency.html)."""
import runpy, os, tempfile
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from _jobs_helpers import app, query


def test_calendar_renders_with_seed_demo():
    app.config['WTF_CSRF_ENABLED'] = False
    os.environ.setdefault('PRODY_ADMIN_PASSWORD', 'test-only-admin-pw')
    os.environ.setdefault('PRODY_STUDENT_PASSWORD', 'test-only-student-pw')
    runpy.run_path(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'seed_demo.py'), run_name='seed_demo')
    u = query("SELECT id, role FROM users WHERE username = 'demo_student'", one=True)
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = u['id']; s['role'] = u['role']
    r = c.get('/calendar')
    assert r.status_code == 200 and 'ct-chip' in r.get_data(as_text=True)


def test_urgency_chip_tolerates_missing_days():
    with app.app_context():
        t = app.jinja_env.from_string('{% from "_urgency.html" import urgency_chip %}[{{ urgency_chip(x.days) }}]')
        assert t.render(x={}) == '[]'
