"""Functionality fn-features: DMs, boards, admin login/moderation, Turso wiring."""
import os, sys, tempfile, uuid
from unittest import mock

os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(prefix='prody_fn_'), 'fn.sqlite3'))
# Ensure Turso env does not force libsql during normal tests
os.environ.pop('TURSO_DATABASE_URL', None)
os.environ.pop('TURSO_AUTH_TOKEN', None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest  # noqa: E402
import app as prody_app  # noqa: E402
from helpers import query  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app = prody_app.app
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False


def _user(role='student', tag=None):
    tag = tag or uuid.uuid4().hex[:8]
    uid = query(
        'INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)',
        (f'u_{tag}', f'{tag}@test.invalid', generate_password_hash('pw'), role), commit=True)
    return uid, f'u_{tag}'


def _friend(a, b):
    lo, hi = (a, b) if a < b else (b, a)
    query(
        "INSERT INTO friendships (requester_id, addressee_id, status, accepted_at, user_lo, user_hi) "
        "VALUES (%s,%s,'accepted',CURRENT_TIMESTAMP,%s,%s)",
        (a, b, lo, hi), commit=True)


def _client(uid, username=None, role='student'):
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid
        if username:
            s['username'] = username
        s['role'] = role
    return c


def _set_demo_label(on: bool):
    """Opt-in/out DEMO_LABEL at runtime (fn_flags is imported into dm/forums at load)."""
    import fn_flags, dm, forums
    os.environ['PRODY_DEMO_LABEL'] = '1' if on else '0'
    fn_flags.DEMO_LABEL = bool(on)
    dm.DEMO_LABEL = bool(on)
    forums.DEMO_LABEL = bool(on)


def _assert_demo_chrome(html: bytes | str, *, expect_on: bool):
    raw = html if isinstance(html, str) else html.decode('utf-8', 'replace')
    if expect_on:
        assert 'Demo only' in raw and 'chip demo' in raw
    else:
        assert 'Demo only' not in raw and 'chip demo' not in raw



def test_dm_requires_friendship():
    a, an = _user()
    b, bn = _user()
    c = _client(a, an)
    r = c.get(f'/messages/{bn}', follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers['Location'].endswith('/messages') or '/messages' in r.headers['Location']
    landed = c.get(f'/messages/{bn}', follow_redirects=True)
    assert landed.status_code == 200
    assert b'accepted friends' in landed.data or b'You can only message' in landed.data
    assert c.post(f'/messages/{bn}', data={'body': 'hi'}).status_code == 403
    r2 = c.post(f'/messages/{bn}/send', json={'body': 'hi'}, headers={'Accept': 'application/json'})
    assert r2.status_code == 403


def test_dm_send_and_poll():
    a, an = _user()
    b, bn = _user()
    _friend(a, b)
    ca = _client(a, an)
    r = ca.post(f'/messages/{bn}/send', json={'body': 'hello friend'}, headers={'Accept': 'application/json'})
    assert r.status_code == 200 and r.get_json()['ok']
    mid = r.get_json()['message']['id']
    cb = _client(b, bn)
    poll = cb.get(f'/messages/{an}/poll?since_id=0', headers={'Accept': 'application/json'})
    assert poll.status_code == 200
    bodies = [m['body'] for m in poll.get_json()['messages']]
    assert 'hello friend' in bodies
    # since_id filters
    poll2 = cb.get(f'/messages/{an}/poll?since_id={mid}', headers={'Accept': 'application/json'})
    assert poll2.get_json()['messages'] == []
    # inbox renders — design hooks always; demo chip only when opted in
    inbox = ca.get('/messages')
    assert inbox.status_code == 200
    assert b'class="fnx"' in inbox.data
    _assert_demo_chrome(inbox.data, expect_on=False)
    _set_demo_label(True)
    try:
        inbox_on = ca.get('/messages')
        assert inbox_on.status_code == 200
        assert b'class="fnx"' in inbox_on.data
        _assert_demo_chrome(inbox_on.data, expect_on=True)
    finally:
        _set_demo_label(False)
    assert ca.get(f'/messages/{bn}').status_code == 200


def test_boards_create_reply_and_tabs():
    """Smoke boards on a private board (university/course) — never Global."""
    uid, name = _user()
    cid = query(
        'INSERT INTO usercourses (id, course_name, course_code, subject, branch_slot, verified) '
        "VALUES (%s,'Calc','MATH 2211','Mathematics',0,0)", (uid,), commit=True)
    query("INSERT INTO userprofiles (user_id, university) VALUES (%s,'Georgia State University')",
          (uid,), commit=True)
    c = _client(uid, name)
    boards = c.get('/boards?tab=university')
    assert boards.status_code == 200
    assert b'class="fnx"' in boards.data
    _assert_demo_chrome(boards.data, expect_on=False)
    _set_demo_label(True)
    try:
        boards_on = c.get('/boards?tab=university')
        assert boards_on.status_code == 200
        assert b'class="fnx"' in boards_on.data
        _assert_demo_chrome(boards_on.data, expect_on=True)
    finally:
        _set_demo_label(False)
    r = c.post('/boards/new', data={'scope': 'university', 'title': 'Hello board', 'body': 'First post'},
               follow_redirects=False)
    assert r.status_code == 302
    tid = int(r.headers['Location'].rstrip('/').split('/')[-1])
    assert c.post(f'/boards/{tid}/reply', data={'body': 'A reply'}).status_code == 302
    page = c.get(f'/boards/{tid}')
    assert b'Hello board' in page.data and b'A reply' in page.data
    # author row links to /u/<username> with peach initial avatar (list + post + reply)
    html = page.get_data(as_text=True)
    assert f'href="/u/{name}"' in html
    assert 'fn-author' in html and 'av-init' in html
    assert name[0].upper() in html
    lst = c.get('/boards?tab=university').get_data(as_text=True)
    assert f'href="/u/{name}"' in lst and 'fn-author' in lst
    assert c.post('/boards/new', data={'scope': 'course', 'course_id': cid, 'title': 'HW', 'body': 'q1'}).status_code == 302
    assert c.get('/boards?tab=course&course_id=%s' % cid).status_code == 200


def test_board_author_non_friend_sees_private_tree_gate():
    """Non-friends hitting author /u/<username> get the existing private-tree copy."""
    author, an = _user(tag='bauth')
    viewer, vn = _user(tag='bview')
    query("INSERT INTO userprofiles (user_id, university, display_name) VALUES (%s,'Georgia State University','Board Auth')",
          (author,), commit=True)
    tid = query(
        "INSERT INTO forum_threads (scope, author_id, title, body, created_at, university) "
        "VALUES ('university',%s,'Campus tip','hi',CURRENT_TIMESTAMP,'Georgia State University')",
        (author,), commit=True)
    c = _client(viewer, vn)
    page = c.get(f'/boards/{tid}').get_data(as_text=True)
    assert f'href="/u/{an}"' in page
    prof = c.get(f'/u/{an}').get_data(as_text=True)
    assert 'Add' in prof and 'friend' in prof and 'tree' in prof


def test_admin_delete_thread_forbidden_for_student():
    uid, name = _user()
    c = _client(uid, name)
    tid = query(
        "INSERT INTO forum_threads (scope, author_id, title, body, created_at, university) "
        "VALUES ('global',%s,'t','b',CURRENT_TIMESTAMP,'')", (uid,), commit=True)
    r = c.post(f'/admin/boards/thread/{tid}/delete')
    assert r.status_code == 403
    assert query('SELECT id FROM forum_threads WHERE id=%s', (tid,), one=True)


def test_student_moderation_and_verify_are_403():
    uid, name = _user()
    c = _client(uid, name)
    tid = query(
        "INSERT INTO forum_threads (scope, author_id, title, body, created_at, university, pinned, hidden) "
        "VALUES ('global',%s,'x','y',CURRENT_TIMESTAMP,'',0,0)", (uid,), commit=True)
    assert c.post(f'/admin/boards/thread/{tid}/hide').status_code == 403
    assert c.post(f'/admin/boards/thread/{tid}/pin').status_code == 403
    cid = query(
        'INSERT INTO usercourses (id, course_name, course_code, subject, branch_slot, verified) '
        "VALUES (%s,'X','X 1','Other',0,0)", (uid,), commit=True)
    assert c.post(f'/admin/courses/{cid}/verify', data={'action': 'verify'}).status_code == 403
    assert c.get('/admin/courses').status_code == 403


def test_admin_moderation_and_verify():
    admin, an = _user(role='admin')
    stu, sn = _user()
    cid = query(
        'INSERT INTO usercourses (id, course_name, course_code, subject, branch_slot, verified) '
        "VALUES (%s,'SE','CSC 4350','Computer Science',0,0)", (stu,), commit=True)
    tid = query(
        "INSERT INTO forum_threads (scope, author_id, title, body, created_at, university) "
        "VALUES ('global',%s,'zap','bye',CURRENT_TIMESTAMP,'')", (stu,), commit=True)
    rid = query(
        "INSERT INTO forum_replies (thread_id, author_id, body, created_at) VALUES (%s,%s,'r',CURRENT_TIMESTAMP)",
        (tid, stu), commit=True)
    c = _client(admin, an, role='admin')
    assert c.post(f'/admin/boards/reply/{rid}/delete').status_code == 302
    assert not query('SELECT id FROM forum_replies WHERE id=%s', (rid,), one=True)
    assert c.post(f'/admin/boards/thread/{tid}/delete').status_code == 302
    assert not query('SELECT id FROM forum_threads WHERE id=%s', (tid,), one=True)
    assert c.get('/admin/courses').status_code == 200
    assert c.post(f'/admin/courses/{cid}/verify', data={'action': 'verify'}).status_code == 302
    assert query('SELECT verified FROM usercourses WHERE course_id=%s', (cid,), one=True)['verified'] in (1, True)
    assert c.post(f'/admin/courses/{cid}/verify', data={'action': 'unverify'}).status_code == 302


def test_admin_login_rejects_student_and_accepts_admin():
    _user(role='student', tag='stuadm')
    query("UPDATE users SET password_hash=%s WHERE username='u_stuadm'",
          (generate_password_hash('secret'),), commit=True)
    _user(role='admin', tag='realadm')
    query("UPDATE users SET password_hash=%s WHERE username='u_realadm'",
          (generate_password_hash('secret'),), commit=True)
    c = app.test_client()
    r = c.post('/admin/login', data={'username': 'u_stuadm', 'password': 'secret'})
    assert r.status_code == 403
    with c.session_transaction() as s:
        assert 'user_id' not in s
    r2 = c.post('/admin/login', data={'username': 'u_realadm', 'password': 'secret'})
    assert r2.status_code == 302
    with c.session_transaction() as s:
        assert s.get('role') == 'admin'


def test_turso_set_selects_libsql_without_ping(monkeypatch):
    """Opted-in preview + complete TURSO_* → libsql; no startup reachability ping."""
    import db as dbmod
    monkeypatch.delenv('PRODY_DB', raising=False)
    monkeypatch.setenv('PRODY_USE_TURSO', '1')
    monkeypatch.setenv('VERCEL_ENV', 'preview')
    monkeypatch.setattr(dbmod, 'TURSO_DATABASE_URL', 'libsql://demo.turso.io')
    monkeypatch.setattr(dbmod, 'TURSO_AUTH_TOKEN', 'tok')
    assert dbmod._pick_backend() == 'libsql'



def test_admin_pin_and_hide():
    admin, an = _user(role='admin')
    stu, sn = _user()
    tid = query(
        "INSERT INTO forum_threads (scope, author_id, title, body, created_at, university, pinned, hidden) "
        "VALUES ('global',%s,'pinme','body',CURRENT_TIMESTAMP,'',0,0)", (stu,), commit=True)
    c = _client(admin, an, role='admin')
    page = c.get(f'/boards/{tid}')
    assert b'fn-amenu' in page.data and b'Hide' in page.data and b'Pin' in page.data and b'Delete' in page.data
    assert c.post(f'/admin/boards/thread/{tid}/pin').status_code == 302
    assert query('SELECT pinned FROM forum_threads WHERE id=%s', (tid,), one=True)['pinned'] in (1, True)
    assert b'Pinned' in c.get(f'/boards/{tid}').data
    assert c.post(f'/admin/boards/thread/{tid}/hide').status_code == 302
    assert query('SELECT hidden FROM forum_threads WHERE id=%s', (tid,), one=True)['hidden'] in (1, True)
    # students no longer see hidden
    cs = _client(stu, sn)
    assert cs.get(f'/boards/{tid}').status_code == 404


def test_design_classes_on_pages():
    """Production design contract: .fnx / layout hooks always; demo chip is opt-in only."""
    a, an = _user(); b, bn = _user(); _friend(a, b)
    c = _client(a, an)
    # default DEMO_LABEL off
    _set_demo_label(False)
    inbox = c.get('/messages').get_data(as_text=True)
    assert 'class="fnx"' in inbox, 'inbox must expose .fnx design hook'
    assert 'card li' in inbox
    _assert_demo_chrome(inbox, expect_on=False)
    thread = c.get(f'/messages/{bn}').get_data(as_text=True)
    assert 'class="fnx' in thread  # fnx or fnx fnx-thread-page
    assert 'bub' in thread and 'comp' in thread and 'arrow_back' in thread
    boards = c.get('/boards?tab=university').get_data(as_text=True)
    assert 'class="fnx"' in boards, 'boards must expose .fnx design hook'
    assert 'seg' in boards
    _assert_demo_chrome(boards, expect_on=False)
    # opt-in DEMO_LABEL shows demo chrome without losing hooks
    _set_demo_label(True)
    try:
        inbox_on = c.get('/messages').get_data(as_text=True)
        assert 'class="fnx"' in inbox_on and 'card li' in inbox_on
        _assert_demo_chrome(inbox_on, expect_on=True)
        boards_on = c.get('/boards?tab=university').get_data(as_text=True)
        assert 'class="fnx"' in boards_on and 'seg' in boards_on
        _assert_demo_chrome(boards_on, expect_on=True)
    finally:
        _set_demo_label(False)


def test_turso_arg_float_is_json_number_not_string():
    """Regression: Turso /v2/pipeline rejects float args with string values
    (HTTP 400: invalid type: string "12.5", expected f64). Dashboard Home
    hits this via plant.record_milestones INSERT plantmilestones.hours_at.
    """
    from decimal import Decimal
    import db as dbmod
    f = dbmod._turso_arg(12.5)
    assert f == {'type': 'float', 'value': 12.5}, f
    assert isinstance(f['value'], float) and not isinstance(f['value'], str)
    d = dbmod._turso_arg(Decimal('0.5'))
    assert d['type'] == 'float' and isinstance(d['value'], float) and d['value'] == 0.5
    i = dbmod._turso_arg(7)
    assert i == {'type': 'integer', 'value': '7'}
