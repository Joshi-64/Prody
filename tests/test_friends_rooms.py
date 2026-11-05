"""Friends can discover/join open rooms; non-friends stay 403 without invite."""
import apptime
import app as prody_app
from helpers import query


def _user(name):
    if not query('SELECT id FROM users WHERE username=%s', (name,), one=True):
        query("INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)",
              (name, name + '@example.com', 'x', 'student'), commit=True)
    return query('SELECT id FROM users WHERE username=%s', (name,), one=True)['id']


def _client(name):
    uid = _user(name)
    c = prody_app.app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid
        s['username'] = name
    return c, uid


def _befriend(a, b):
    query("INSERT INTO friendships (requester_id, addressee_id, status, accepted_at) VALUES (%s,%s,'accepted',%s)",
          (a, b, apptime.now_utc_naive()), commit=True)


def test_friend_sees_open_room_and_can_join(csrf_off):
    host_c, host = _client('fr_host')
    friend_c, friend = _client('fr_friend')
    _befriend(host, friend)
    r = host_c.post('/rooms/new', data={'title': 'Bio cram'})
    assert r.status_code == 302
    rid = int(r.headers['Location'].rsplit('/', 1)[-1])
    assert query('SELECT friends_can_join FROM studyrooms WHERE room_id=%s', (rid,), one=True)['friends_can_join'] in (1, True)
    page = friend_c.get('/rooms')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'Friends studying now' in html
    assert 'Bio cram' in html
    assert 'No friends studying right now' not in html
    j = friend_c.post(f'/rooms/{rid}/join-friend')
    assert j.status_code == 302
    assert query('SELECT 1 AS x FROM studyroom_members WHERE room_id=%s AND user_id=%s', (rid, friend), one=True)


def test_nonfriend_join_friend_forbidden(csrf_off):
    host_c, host = _client('nf_host')
    stranger_c, _ = _client('nf_stranger')
    host_c.post('/rooms/new', data={'title': 'Private-ish'})
    rid = query('SELECT room_id FROM studyrooms WHERE owner_id=%s ORDER BY room_id DESC', (host,), one=True)['room_id']
    assert stranger_c.post(f'/rooms/{rid}/join-friend').status_code == 403
    page = stranger_c.get('/rooms').get_data(as_text=True)
    assert 'No friends studying right now' in page
    assert 'Private-ish' not in page


def test_friends_can_join_off_hides_and_blocks(csrf_off):
    host_c, host = _client('off_host')
    friend_c, friend = _client('off_friend')
    _befriend(host, friend)
    host_c.post('/rooms/new', data={'title': 'Closed to friends'})
    rid = query('SELECT room_id FROM studyrooms WHERE owner_id=%s ORDER BY room_id DESC', (host,), one=True)['room_id']
    assert host_c.post(f'/rooms/{rid}/settings', data={}).status_code == 302
    assert query('SELECT friends_can_join FROM studyrooms WHERE room_id=%s', (rid,), one=True)['friends_can_join'] in (0, False)
    html = friend_c.get('/rooms').get_data(as_text=True)
    assert 'Closed to friends' not in html
    assert friend_c.post(f'/rooms/{rid}/join-friend').status_code == 403
