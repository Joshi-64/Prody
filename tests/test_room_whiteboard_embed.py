"""Room embeds shared whiteboard tools; legacy /whiteboard URL redirects into the room."""
import json
import re
import app as prody_app
from helpers import query


def _client(name):
    if not query('SELECT id FROM users WHERE username=%s', (name,), one=True):
        query("INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)",
              (name, name + '@example.com', 'x', 'student'), commit=True)
    uid = query('SELECT id FROM users WHERE username=%s', (name,), one=True)['id']
    c = prody_app.app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid
        s['username'] = name
    return c


def _make_room(c, title='Board room'):
    r = c.post('/rooms/new', data={'title': title})
    assert r.status_code == 302
    return int(re.search(r'/rooms/(\d+)', r.headers['Location']).group(1))


def test_room_page_embeds_restored_tools_and_prejoin_config(csrf_off, monkeypatch):
    monkeypatch.setenv('ROOM_VIDEO', 'jitsi')
    c = _client('wb_embed_u')
    rid = _make_room(c)
    html = c.get(f'/rooms/{rid}').get_data(as_text=True)
    assert 'id="wb"' in html and 'wb-tools' in html
    for tool in ('pen', 'hl', 'erase', 'line', 'arrow', 'rect', 'ellipse', 'text', 'note'):
        assert f'data-t="{tool}"' in html
    assert 'prejoinConfig' in html and 'enabled:false' in html.replace(' ', '')
    assert 'rm-video' in html and 'rm-board' in html


def test_legacy_room_whiteboard_redirects(csrf_off):
    c = _client('wb_redir_u')
    rid = _make_room(c)
    r = c.get(f'/rooms/{rid}/whiteboard', follow_redirects=False)
    assert r.status_code in (302, 303)
    assert f'/rooms/{rid}' in (r.headers.get('Location') or '')


def test_stroke_accepts_shape_payload(csrf_off):
    c = _client('wb_shape_u')
    rid = _make_room(c)
    r = c.post(f'/rooms/{rid}/strokes', json={
        't': 'rect', 'x0': 0.1, 'y0': 0.1, 'x1': 0.4, 'y1': 0.5, 'c': '#2f5d46', 'w': 3})
    assert r.status_code == 200
    assert r.get_json().get('id')
    rows = query('SELECT data FROM studyroom_strokes WHERE room_id=%s ORDER BY stroke_id DESC LIMIT 1', (rid,))
    assert json.loads(rows[0]['data'])['t'] == 'rect'
