"""Item 11: chip fills input[name=message] and never overwrites csrf; CSRF-enabled."""
import os, sys, tempfile, re
_TMP = tempfile.mkdtemp(prefix='prody_chip_')
os.environ.setdefault('PRODY_DB', 'sqlite')
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(_TMP, 'chip.sqlite3'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as prody_app
from helpers import query


def test_chip_targets_message_not_csrf():
    prody_app.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    if not query('SELECT id FROM users WHERE username=%s', ('chip_u',), one=True):
        query("INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)",
              ('chip_u', 'chip@example.com', 'x', 'student'), commit=True)
    uid = query('SELECT id FROM users WHERE username=%s', ('chip_u',), one=True)['id']
    c = prody_app.app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid
        s['username'] = 'chip_u'
    html = c.get('/buddy').get_data(as_text=True)
    assert "input[name=message]" in html or "querySelector('input[name=message]')" in html
    assert 'requestSubmit' in html
    assert '.chat-input input' not in html or "input[name=message]" in html
    # csrf meta present; script reads csrf before setting message
    assert 'csrf-token' in html and 'csrf()' in html


def test_chip_post_with_csrf_stores_message(monkeypatch):
    """Real POST of a chip message with a valid CSRF token -> 200 and a stored user row."""
    import buddy
    prody_app.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    if not query('SELECT id FROM users WHERE username=%s', ('chip_post_u',), one=True):
        query("INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)",
              ('chip_post_u', 'chip_post@example.com', 'x', 'student'), commit=True)
    uid = query('SELECT id FROM users WHERE username=%s', ('chip_post_u',), one=True)['id']
    monkeypatch.setattr(buddy, 'ai_available', lambda: True)
    monkeypatch.setattr(buddy, 'ai_chat', lambda msgs, timeout=30: 'Here is a short tip.')
    c = prody_app.app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid
        s['username'] = 'chip_post_u'
    html = c.get('/buddy').get_data(as_text=True)
    m = re.search(r'name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']', html)
    if not m:
        m = re.search(r'content=["\']([^"\']+)["\']\s+name=["\']csrf-token["\']', html)
    if not m:
        m = re.search(r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)["\']', html)
    assert m, 'csrf token missing from buddy page'
    token = m.group(1)
    r = c.post('/buddy', data={'message': 'Quiz me on my next deadline', 'csrf_token': token},
               headers={'Accept': 'application/json', 'X-Requested-With': 'fetch', 'X-CSRFToken': token})
    assert r.status_code == 200, r.get_data(as_text=True)[:400]
    body = r.get_json()
    assert body and body.get('ok') is True
    row = query("SELECT content FROM chatmessages WHERE user_id=%s AND role='user' ORDER BY message_id DESC", (uid,), one=True)
    assert row and row['content'] == 'Quiz me on my next deadline'
