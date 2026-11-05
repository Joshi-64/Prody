"""nav-perf: Me tab links straight to /u/<name>, WebKit fetch prefetch, hashed kit.json URL."""
import os, re, tempfile
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from _jobs_helpers import app, client_for, make_user, query  # noqa: E402
import assets  # noqa: E402


def _client():
    u = make_user()
    name = query('SELECT username FROM users WHERE id=%s', (u,), one=True)['username']
    c = client_for(u)
    with c.session_transaction() as s:
        s['username'] = name
    return c, name


def test_me_tab_points_at_profile_url_without_redirect():
    c, name = _client()
    html = c.get('/dashboard', follow_redirects=True).get_data(as_text=True)
    m = re.search(r'<a href="([^"]+)" class="tab[^"]*"[^>]*>(?:(?!</a>).)*?>Me</span>', html, re.S)
    assert m and m.group(1) == '/u/' + name
    assert 'href="/profile"' not in html
    assert c.get('/u/' + name).status_code == 200


def test_old_profile_link_still_redirects():
    c, name = _client()
    r = c.get('/profile')
    assert r.status_code == 302 and r.headers['Location'].endswith('/u/' + name)


def test_prefetch_request_gets_short_private_cache():
    c, name = _client()
    assert c.get('/u/' + name).headers['Cache-Control'] == 'no-cache'
    r = c.get('/u/' + name, headers={'X-Prody-Prefetch': '1'})
    assert r.headers['Cache-Control'] == 'private, max-age=10'


def test_shell_js_has_fetch_fallback():
    js = open(os.path.join(app.static_folder, 'js', 'shell.js')).read()
    assert "'X-Prody-Prefetch':'1'" in js and "credentials:'same-origin'" in js and 'no-store' not in js


def test_kit_json_preload_uses_content_hash_and_is_immutable():
    # garden home: the scene engine is content-hashed and cached forever, like the kit was
    c, _ = _client()
    html = c.get('/dashboard', follow_redirects=True).get_data(as_text=True)
    m = re.search(r'garden/tree-scene\.js\?v=([0-9a-f]{10})"', html)
    assert m and m.group(1) == assets.file_hash('garden/tree-scene.js')
    r = c.get('/static/garden/tree-scene.js?v=' + m.group(1))
    assert 'immutable' in r.headers['Cache-Control'] and 'max-age=31536000' in r.headers['Cache-Control']


def _points(html):
    m = re.search(r'<div class="stat-val">([\d,]+)</div><div class="stat-label">points', html)
    return int(m.group(1).replace(',', ''))


def test_home_prefetched_before_task_completion_shows_new_state_after_it():
    """Leader/Critic: prefetch Home, complete a task, then the next Home load (shell.js revalidates with
    cache:'reload', no prefetch header) must show the new state, not the warmed copy."""
    c, _ = _client()
    with c.session_transaction() as s:
        u = s['user_id']
    tid = query("INSERT INTO todolist (user_id, task_name, due_date, category, course_id, progress) "
                "VALUES (%s, 'nav-perf task', NULL, 'task', NULL, 0)", (u,), commit=True)
    pre = c.get('/dashboard', headers={'X-Prody-Prefetch': '1'})
    assert pre.headers['Cache-Control'] == 'private, max-age=10'
    # the garden home draws from /api/tree, which must never serve a warmed copy
    assert c.get('/api/tree').headers['Cache-Control'] == 'no-cache'
    assert c.post('/tasks/complete/%d' % tid).status_code == 302
    fresh = c.get('/dashboard')  # the revalidating fetch / tap
    assert fresh.headers['Cache-Control'] == 'no-cache'
    assert query('SELECT is_completed FROM todolist WHERE task_id=%s', (tid,), one=True)['is_completed']


def test_server_ignores_prefetch_header_off_allowlist():
    c, _ = _client()
    for path in ('/logout', '/profile', '/tasks/complete/1', '/api/tree'):
        r = c.get(path, headers={'X-Prody-Prefetch': '1'})
        assert 'max-age=10' not in r.headers.get('Cache-Control', ''), path


def test_shell_js_clears_prefetch_on_writes():
    js = open(os.path.join(app.static_folder, 'js', 'shell.js')).read()
    assert "addEventListener('submit',stale,true)" in js and "cache:'reload'" in js and "m!=='GET'" in js
    assert 'logout' not in js.split('var OK=')[1].split(',K=')[0]
