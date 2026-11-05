"""Account wipe removes studyrooms/members/strokes in one transaction."""
import json
import app as prody_app
from helpers import query
from account_data import delete_user_data


def _user(name):
    if not query('SELECT id FROM users WHERE username=%s', (name,), one=True):
        query("INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)",
              (name, name + '@example.com', 'x', 'student'), commit=True)
    return query('SELECT id FROM users WHERE username=%s', (name,), one=True)['id']


def test_delete_user_data_clears_owned_rooms_and_strokes():
    uid = _user('wipe_host')
    rid = query(
        'INSERT INTO studyrooms (owner_id, title, course_id, jitsi_name, join_token) VALUES (%s,%s,NULL,%s,%s)',
        (uid, 'Cram', 'Prody-x', 'tok-wipe-1'), commit=True)
    query('INSERT INTO studyroom_members (room_id, user_id) VALUES (%s,%s)', (rid, uid), commit=True)
    query('INSERT INTO studyroom_strokes (room_id, user_id, data) VALUES (%s,%s,%s)',
          (rid, uid, json.dumps({'pts': [[0.1, 0.2]], 'c': '#000', 'w': 3})), commit=True)
    delete_user_data(uid)
    assert query('SELECT id FROM users WHERE id=%s', (uid,), one=True) is None
    assert query('SELECT COUNT(*) AS n FROM studyrooms WHERE room_id=%s', (rid,), one=True)['n'] == 0
    assert query('SELECT COUNT(*) AS n FROM studyroom_members WHERE room_id=%s', (rid,), one=True)['n'] == 0
    assert query('SELECT COUNT(*) AS n FROM studyroom_strokes WHERE room_id=%s', (rid,), one=True)['n'] == 0


def test_delete_user_data_clears_membership_when_not_owner():
    host = _user('wipe_owner2')
    guest = _user('wipe_guest')
    rid = query(
        'INSERT INTO studyrooms (owner_id, title, course_id, jitsi_name, join_token) VALUES (%s,%s,NULL,%s,%s)',
        (host, 'Host room', 'Prody-y', 'tok-wipe-2'), commit=True)
    query('INSERT INTO studyroom_members (room_id, user_id) VALUES (%s,%s)', (rid, host), commit=True)
    query('INSERT INTO studyroom_members (room_id, user_id) VALUES (%s,%s)', (rid, guest), commit=True)
    query('INSERT INTO studyroom_strokes (room_id, user_id, data) VALUES (%s,%s,%s)',
          (rid, guest, json.dumps({'pts': [[0.5, 0.5]], 'c': '#111', 'w': 2})), commit=True)
    delete_user_data(guest)
    assert query('SELECT id FROM users WHERE id=%s', (guest,), one=True) is None
    assert query('SELECT COUNT(*) AS n FROM studyrooms WHERE room_id=%s', (rid,), one=True)['n'] == 1
    assert query('SELECT COUNT(*) AS n FROM studyroom_members WHERE user_id=%s', (guest,), one=True)['n'] == 0
    assert query('SELECT COUNT(*) AS n FROM studyroom_strokes WHERE user_id=%s', (guest,), one=True)['n'] == 0
