"""Login/session hardening tests (Bark). Run: /workspace/venv/bin/python -m pytest tests/test_security.py -q"""
import os, sys, tempfile, re
_TMP = tempfile.mkdtemp(prefix='prody_sec_')
os.environ.setdefault('PRODY_DB', 'sqlite')
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(_TMP, 'sec.sqlite3'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402
import app as prody_app  # noqa: E402
import helpers  # noqa: E402
from helpers import query  # noqa: E402

PW = 'Correct-Horse-9'


@pytest.fixture(autouse=True)
def setup():
    helpers._RL.clear()
    prody_app.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    if not query('SELECT id FROM users WHERE username = %s', ('sec_user',), one=True):
        query('INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)',
              ('sec_user', 'sec@example.com', generate_password_hash(PW), 'student'), commit=True)
    yield
    # config (incl. WTF_CSRF_ENABLED) restored by conftest._restore_app_config


def login(c, pw=PW, user='sec_user'):
    return c.post('/login', data={'username': user, 'password': pw})


def test_cookie_flags_and_lifetime():
    cfg = prody_app.app.config
    assert cfg['SESSION_COOKIE_HTTPONLY'] and cfg['SESSION_COOKIE_SAMESITE'] == 'Lax'
    assert cfg['PERMANENT_SESSION_LIFETIME'].days == 14
    r = login(prody_app.app.test_client())
    cookie = r.headers.get('Set-Cookie', '')
    assert 'HttpOnly' in cookie and 'SameSite=Lax' in cookie and 'Expires=' in cookie


def test_session_rotated_at_login():
    c = prody_app.app.test_client()
    with c.session_transaction() as s:
        s['planted'] = 'attacker'
    assert login(c).status_code == 302
    with c.session_transaction() as s:
        assert 'planted' not in s and s['username'] == 'sec_user' and s.permanent


def test_login_rate_limited_per_user():
    c = prody_app.app.test_client()
    for _ in range(5):
        assert login(c, pw='wrong').status_code == 401
    assert login(c).status_code == 429  # even correct password is blocked while locked


def test_success_resets_user_counter():
    c = prody_app.app.test_client()
    for _ in range(4):
        login(c, pw='wrong')
    assert login(c).status_code == 302
    for _ in range(4):
        assert login(prody_app.app.test_client(), pw='wrong').status_code == 401


def test_csrf_required_on_post_forms():
    """Missing CSRF must never show raw text; redirect to styled login with a flash."""
    prody_app.app.config['WTF_CSRF_ENABLED'] = True
    c = prody_app.app.test_client()
    r = c.post('/login', data={'username': 'sec_user', 'password': PW})
    assert r.status_code == 302 and '/login' in r.headers.get('Location', '')
    page = c.get('/login').get_data(as_text=True)
    assert 'Your sign-in form expired, please try again.' in page
    assert 'The CSRF tokens do not match' not in page
    assert 'Welcome back' in page  # styled form, not a bare error page
    tok = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    assert c.post('/login', data={'username': 'sec_user', 'password': PW, 'csrf_token': tok}).status_code == 302


def test_hosted_refuses_dev_secret(monkeypatch):
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, RENDER='1')
    env.pop('PRODY_SECRET_KEY', None)
    r = subprocess.run([sys.executable, '-c', 'import app'], cwd=root, env=env, capture_output=True, text=True)
    assert r.returncode != 0 and 'PRODY_SECRET_KEY' in r.stderr

def test_hosted_refuses_short_or_empty_secret():
    """Vercel cold starts must share one fixed key; refuse empty/short secrets."""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for bad in ('', 'short-key-11'):  # 11 chars like the old Preview value
        env = dict(os.environ, VERCEL='1', PRODY_SECRET_KEY=bad)
        r = subprocess.run([sys.executable, '-c', 'import app'], cwd=root, env=env, capture_output=True, text=True)
        assert r.returncode != 0 and 'PRODY_SECRET_KEY' in r.stderr, bad


def test_spoofed_forwarded_for_cannot_bypass_ip_limit():
    c = prody_app.app.test_client()
    for i in range(20):  # different usernames so only the per-IP limit applies
        r = c.post('/login', data={'username': f'nobody{i}', 'password': 'x'},
                   headers={'X-Forwarded-For': f'10.0.0.{i}'})
        assert r.status_code == 401
    r = c.post('/login', data={'username': 'sec_user', 'password': PW}, headers={'X-Forwarded-For': '203.0.113.9'})
    assert r.status_code == 429


def test_proxyfix_trusts_one_hop_only():
    from werkzeug.middleware.proxy_fix import ProxyFix
    from werkzeug.test import EnvironBuilder
    seen = {}
    fixed = ProxyFix(lambda env, sr: seen.update(ip=env['REMOTE_ADDR']) or [], x_for=1)
    env = EnvironBuilder(headers={'X-Forwarded-For': '6.6.6.6, 198.51.100.7'}).get_environ()
    fixed(env, lambda *a: None)
    assert seen['ip'] == '198.51.100.7'  # attacker-supplied left entry ignored


def test_missing_user_redirects_to_login():
    """A session whose user no longer exists must land on /login, not an empty page."""
    import app as _a
    c = _a.app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = 987654321
        s['username'] = 'ghost'
    for path in ['/dashboard', '/friends', '/zen', '/analytics', '/achievements']:
        r = c.get(path)
        assert r.status_code == 302 and '/login' in r.headers['Location'], path
    with c.session_transaction() as s:
        assert 'user_id' not in s  # stale session was cleared
    r = c.get('/dashboard')  # and no session at all also redirects
    assert r.status_code == 302 and '/login' in r.headers['Location']


def test_real_user_still_gets_page():
    c = prody_app.app.test_client()
    login(c)
    assert c.get('/dashboard').status_code == 200


def test_csrf_token_reinjected_after_failed_login():
    """iPhone bug: a wrong password re-rendered /login (401) without csrf_token, so the retry 400'd."""
    prody_app.app.config['WTF_CSRF_ENABLED'] = True
    c = prody_app.app.test_client()
    tok = re.search(r'name="csrf_token" value="([^"]+)"', c.get('/login').get_data(as_text=True)).group(1)
    r = c.post('/login', data={'username': 'sec_user', 'password': 'wrong', 'csrf_token': tok})
    assert r.status_code == 401
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.get_data(as_text=True))
    assert m, 'failed-login page must carry a CSRF token'
    assert c.post('/login', data={'username': 'sec_user', 'password': PW, 'csrf_token': m.group(1)}).status_code == 302


def test_wrong_password_stays_on_styled_form():
    """Wrong password and unknown user both stay on the styled form with a clear message."""
    c = prody_app.app.test_client()
    for user, pw in (('sec_user', 'wrong-password-xx'), ('no_such_user_zzz', PW)):
        r = c.post('/login', data={'username': user, 'password': pw})
        assert r.status_code == 401
        html = r.get_data(as_text=True)
        assert 'Wrong username or password' in html
        assert 'The CSRF tokens do not match' not in html
        assert 'Welcome back' in html  # styled card, not bare text / 500
        assert f'value="{user}"' in html  # username kept
        assert r.status_code != 500


def test_login_page_is_no_store():
    """Login HTML must not be cacheable (stale CSRF on iPhone Safari)."""
    r = prody_app.app.test_client().get('/login')
    assert r.headers.get('Cache-Control') == 'no-store'
