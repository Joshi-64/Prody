"""/calendar must render for explicitly seeded demo data (calendar-event deadlines had no 'days': 500 in _urgency.html).

seed_demo.py is CLI-only (__main__). Tests must not rely on import-time / non-__main__ auto-seeding.
"""
import runpy, os, tempfile, importlib.util
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from _jobs_helpers import app, query


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SEED = os.path.join(_ROOT, 'seed_demo.py')


def test_seed_demo_not_auto_on_non_main_runpy():
    """Import / runpy without __main__ must not create demo accounts (release seed strip)."""
    before = query("SELECT COUNT(*) AS n FROM users WHERE username IN ('demo_student','demo_admin')", one=True)['n']
    runpy.run_path(_SEED, run_name='seed_demo')
    after = query("SELECT COUNT(*) AS n FROM users WHERE username IN ('demo_student','demo_admin')", one=True)['n']
    assert after == before


def test_calendar_renders_with_seed_demo():
    """Explicit isolated CLI-style seed (main()) then calendar smoke."""
    app.config['WTF_CSRF_ENABLED'] = False
    os.environ.setdefault('PRODY_ADMIN_PASSWORD', 'test-only-admin-pw')
    os.environ.setdefault('PRODY_STUDENT_PASSWORD', 'test-only-student-pw')
    spec = importlib.util.spec_from_file_location('seed_demo_explicit', _SEED)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()  # explicit fixture seed — not auto boot
    u = query("SELECT id, role FROM users WHERE username = 'demo_student'", one=True)
    assert u is not None
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = u['id']; s['role'] = u['role']
    r = c.get('/calendar')
    assert r.status_code == 200 and 'ct-chip' in r.get_data(as_text=True)


def test_urgency_chip_tolerates_missing_days():
    with app.app_context():
        t = app.jinja_env.from_string('{% from "_urgency.html" import urgency_chip %}[{{ urgency_chip(x.days) }}]')
        assert t.render(x={}) == '[]'
