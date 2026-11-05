"""Video study rooms + shared whiteboard: auth, join by link, privacy, stroke post/fetch."""
import re
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


def _make_room(c, title='Bio cram'):
    r = c.post('/rooms/new', data={'title': title})
    assert r.status_code == 302
    rid = int(re.search(r'/rooms/(\d+)', r.headers['Location']).group(1))
    return rid


def test_rooms_require_login():
    c = prody_app.app.test_client()
    assert c.get('/rooms').status_code in (302, 401)
    assert c.post('/rooms/new', data={'title': 'x'}).status_code in (302, 400, 401)


def test_create_and_view_room(csrf_off, monkeypatch):
    monkeypatch.delenv('JAAS_APP_ID', raising=False)
    monkeypatch.delenv('JAAS_KID', raising=False)
    monkeypatch.delenv('JAAS_PRIVATE_KEY', raising=False)
    monkeypatch.delenv('JAAS_PRIVATE_KEY_PATH', raising=False)
    monkeypatch.delenv('ROOM_VIDEO', raising=False)
    c, uid = _client('room_owner')
    rid = _make_room(c)
    html = c.get(f'/rooms/{rid}').get_data(as_text=True)
    # video off by default — calm cream card, header + whiteboard + invite still work
    assert 'Video calls are almost ready — the whiteboard works now' in html
    assert 'meet.jit.si/external_api.js' not in html and 'JitsiMeetExternalAPI' not in html
    assert ('wb-tools' in html or 'Shared whiteboard' in html) and 'Invite' in html
    room = query('SELECT jitsi_name, join_token FROM studyrooms WHERE room_id=%s', (rid,), one=True)
    assert room['jitsi_name'].startswith('Prody-') and len(room['jitsi_name']) >= 38
    assert 'room_owner' in html
    wb = c.get(f'/rooms/{rid}/whiteboard', follow_redirects=True)
    assert wb.status_code == 200 and ('wb-tools' in wb.get_data(as_text=True) or 'id="wb"' in wb.get_data(as_text=True))
    assert 'Bio cram' in c.get('/rooms').get_data(as_text=True)


def test_course_must_be_own(csrf_off):
    c, _ = _client('room_course_u')
    assert c.post('/rooms/new', data={'title': 't', 'course_id': '999999'}).status_code == 400


def test_non_member_blocked_until_join(csrf_off):
    a, _ = _client('room_a')
    rid = _make_room(a)
    b, _ = _client('room_b')
    assert b.get(f'/rooms/{rid}').status_code == 403
    assert b.get(f'/rooms/{rid}/strokes').status_code == 403
    assert b.post(f'/rooms/{rid}/strokes', json={'pts': [[0.1, 0.1]]}).status_code == 403
    assert b.get(f'/rooms/{rid}/whiteboard').status_code == 403
    assert b.get('/rooms/join/not-a-real-token').status_code == 404
    tok = query('SELECT join_token FROM studyrooms WHERE room_id=%s', (rid,), one=True)['join_token']
    assert b.get(f'/rooms/join/{tok}').status_code == 302
    assert b.get(f'/rooms/{rid}').status_code == 200
    assert b.get(f'/rooms/join/{tok}').status_code == 302  # re-join is idempotent


def test_strokes_post_fetch_clear(csrf_off):
    c, _ = _client('room_strokes')
    rid = _make_room(c)
    r = c.post(f'/rooms/{rid}/strokes', json={'pts': [[0.1, 0.2], [0.3, 0.4]], 'c': '#5a7d4f', 'w': 4})
    assert r.status_code == 200
    first = r.get_json()['id']
    c.post(f'/rooms/{rid}/strokes', json={'pts': [[0.5, 0.5]]})
    got = c.get(f'/rooms/{rid}/strokes?since=0').get_json()['strokes']
    assert len(got) == 2 and got[0]['s']['pts'] == [[0.1, 0.2], [0.3, 0.4]] and got[0]['s']['w'] == 4
    assert len(c.get(f'/rooms/{rid}/strokes?since={first}').get_json()['strokes']) == 1
    assert c.post(f'/rooms/{rid}/strokes', json={'pts': 'bad'}).status_code == 400
    assert c.post(f'/rooms/{rid}/strokes', json={'clear': True}).status_code == 200
    assert c.get(f'/rooms/{rid}/strokes?since=0').get_json()['strokes'][-1]['s'] == {'clear': True}


def test_strokes_need_csrf():
    prody_app.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    c, _ = _client('room_csrf')
    prody_app.app.config['WTF_CSRF_ENABLED'] = False
    rid = _make_room(c)
    prody_app.app.config['WTF_CSRF_ENABLED'] = True
    assert c.post(f'/rooms/{rid}/strokes', json={'pts': [[0.1, 0.1]]}).status_code == 400


def test_video_off_and_jitsi_flag(csrf_off, monkeypatch):
    """Video off -> calm card; ROOM_VIDEO=jitsi -> public meet.jit.si (no JWT)."""
    for k in ('JAAS_APP_ID', 'JAAS_KID', 'JAAS_PRIVATE_KEY', 'JAAS_PRIVATE_KEY_PATH', 'ROOM_VIDEO', 'JITSI_DOMAIN'):
        monkeypatch.delenv(k, raising=False)
    c, _ = _client('room_domain')
    rid = _make_room(c)
    name = query('SELECT jitsi_name FROM studyrooms WHERE room_id=%s', (rid,), one=True)['jitsi_name']
    html = c.get(f'/rooms/{rid}').get_data(as_text=True)
    assert 'Video calls are almost ready — the whiteboard works now' in html
    assert 'external_api.js' not in html
    monkeypatch.setenv('ROOM_VIDEO', 'jitsi')
    html = c.get(f'/rooms/{rid}').get_data(as_text=True)
    assert 'https://meet.jit.si/external_api.js' in html and f'data-room="{name}"' in html
    assert 'data-domain="meet.jit.si"' in html and 'data-jwt=' not in html
    assert "'desktop'" in html


def test_jaas_jwt_video_on(csrf_off, monkeypatch, tmp_path):
    """JAAS_APP_ID + JAAS_KID + throwaway RSA key -> 8x8.vc embed with jwt; owner is moderator."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    import jwt as pyjwt
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    app_id = 'vpaas-magic-cookie-testabc'
    kid = f'{app_id}/test-key-1'
    monkeypatch.setenv('JAAS_APP_ID', app_id)
    monkeypatch.setenv('JAAS_KID', kid)
    monkeypatch.setenv('JAAS_PRIVATE_KEY', pem)
    monkeypatch.delenv('ROOM_VIDEO', raising=False)
    c, uid = _client('room_jaas')
    rid = _make_room(c)
    name = query('SELECT jitsi_name FROM studyrooms WHERE room_id=%s', (rid,), one=True)['jitsi_name']
    html = c.get(f'/rooms/{rid}').get_data(as_text=True)
    assert f'https://8x8.vc/{app_id}/external_api.js' in html
    assert f'data-room="{app_id}/{name}"' in html and 'data-domain="8x8.vc"' in html
    assert 'data-jwt="' in html and 'Video calls are almost ready' not in html
    # extract jwt from data-jwt="..."
    import re
    m = re.search(r'data-jwt="([^"]+)"', html)
    assert m, 'jwt missing from markup'
    token = m.group(1)
    claims = pyjwt.decode(token, key.public_key(), algorithms=['RS256'], audience='jitsi')
    assert claims['iss'] == 'chat' and claims['sub'] == app_id and claims['room'] == name
    assert claims['room'] != '*'
    assert claims['exp'] - claims['nbf'] <= 2 * 60 * 60 + 20
    assert claims['context']['user']['moderator'] is True
    assert claims['context']['user']['id'] == str(uid)
    header = pyjwt.get_unverified_header(token)
    assert header.get('kid') == kid and header.get('alg') == 'RS256'
    # incomplete triad -> calm card even if APP_ID alone is set
    monkeypatch.delenv('JAAS_KID', raising=False)
    html = c.get(f'/rooms/{rid}').get_data(as_text=True)
    assert 'Video calls are almost ready — the whiteboard works now' in html
    assert 'external_api.js' not in html


def test_jaas_jwt_scoped_and_members_only(csrf_off, monkeypatch, tmp_path):
    """JWT is room-scoped; non-members get 403 and never a token. Signing material stays server-side."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    import jwt as pyjwt, re
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    app_id = 'vpaas-magic-cookie-2a1bdbb61ab94edbaefb31f7cf4c72b8'
    kid = f'{app_id}/de4fb0'
    monkeypatch.setenv('JAAS_APP_ID', app_id)
    monkeypatch.setenv('JAAS_KID', kid)
    # Prefer PATH form (matches production Preview using env PEM; path used in local tests)
    key_path = tmp_path / 'jaas.pk'
    key_path.write_text(pem)
    monkeypatch.setenv('JAAS_PRIVATE_KEY_PATH', str(key_path))
    monkeypatch.delenv('JAAS_PRIVATE_KEY', raising=False)
    monkeypatch.delenv('ROOM_VIDEO', raising=False)

    owner, oid = _client('jaas_owner')
    rid = _make_room(owner)
    jname = query('SELECT jitsi_name FROM studyrooms WHERE room_id=%s', (rid,), one=True)['jitsi_name']
    html = owner.get(f'/rooms/{rid}').get_data(as_text=True)
    assert 'data-jwt="' in html
    # page must not embed the private key / kid path
    assert 'BEGIN PRIVATE KEY' not in html and 'jaas_private' not in html and 'JAAS_PRIVATE' not in html
    tok = re.search(r'data-jwt="([^"]+)"', html).group(1)
    claims = pyjwt.decode(tok, key.public_key(), algorithms=['RS256'], audience='jitsi')
    assert claims['room'] == jname and claims['context']['user']['id'] == str(oid)

    stranger, _ = _client('jaas_stranger')
    r = stranger.get(f'/rooms/{rid}')
    assert r.status_code == 403
    assert b'data-jwt=' not in r.data
    assert b'BEGIN PRIVATE KEY' not in r.data


def test_mint_jaas_jwt_rejects_wildcard_room(monkeypatch, tmp_path):
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    import rooms as R
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    monkeypatch.setenv('JAAS_APP_ID', 'vpaas-magic-cookie-x')
    monkeypatch.setenv('JAAS_KID', 'vpaas-magic-cookie-x/k1')
    monkeypatch.setenv('JAAS_PRIVATE_KEY', pem)
    assert R.mint_jaas_jwt('A', 1, room='*') is None
    assert R.mint_jaas_jwt('A', 1, room='') is None
    tok = R.mint_jaas_jwt('A', 1, room='Prody-abc')
    assert tok and isinstance(tok, str) and tok.count('.') == 2
