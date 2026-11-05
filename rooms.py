"""Video study rooms (Jitsi / JaaS) and a per-room shared whiteboard.
Storage goes through helpers.query (the app's normal DB connection).

Video is on only when JaaS is fully configured (JAAS_APP_ID + JAAS_KID + private key)
or when ROOM_VIDEO=jitsi (public meet.jit.si, no JWT). Otherwise the room shows a calm card.
"""
import json
import os
import secrets
import time
from pathlib import Path as _Path

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for

from helpers import login_required, query

rooms_bp = Blueprint('rooms_bp', __name__)


def active_room_for(uid):
    """Most recently joined open room for profile chip, or None."""
    return query(
        'SELECT r.room_id, r.title, COALESCE(r.friends_can_join, 1) AS friends_can_join, r.owner_id '
        'FROM studyroom_members m JOIN studyrooms r ON r.room_id = m.room_id '
        'WHERE m.user_id = %s ORDER BY m.joined_at DESC, r.room_id DESC LIMIT 1',
        (uid,), one=True)


_ALMOST = "Video calls are almost ready — the whiteboard works now"


def _jaas_private_key_pem():
    """PEM from JAAS_PRIVATE_KEY (literal, \\n-escaped OK) or JAAS_PRIVATE_KEY_PATH. Never logs the key."""
    raw = (os.environ.get('JAAS_PRIVATE_KEY') or '').strip()
    if raw:
        return raw.replace('\\n', '\n')
    path = (os.environ.get('JAAS_PRIVATE_KEY_PATH') or '').strip()
    if path:
        try:
            return _Path(path).read_text()
        except OSError:
            return ''
    return ''


def video_enabled():
    """True when JaaS triad is set, or ROOM_VIDEO=jitsi for the public meet.jit.si embed."""
    if (os.environ.get('ROOM_VIDEO') or '').strip().lower() == 'jitsi':
        return True
    app_id = (os.environ.get('JAAS_APP_ID') or '').strip()
    kid = (os.environ.get('JAAS_KID') or '').strip()
    return bool(app_id and kid and _jaas_private_key_pem())


def jitsi_target(room_name):
    """(domain, full room name). JAAS_APP_ID set -> 8x8.vc with the '<app id>/' prefix; else JITSI_DOMAIN."""
    app_id = (os.environ.get('JAAS_APP_ID') or '').strip()
    if app_id:
        return '8x8.vc', f'{app_id}/{room_name}'
    return (os.environ.get('JITSI_DOMAIN') or 'meet.jit.si').strip(), room_name


def mint_jaas_jwt(display_name, user_id, *, room, moderator=False, ttl_sec=2 * 60 * 60):
    """RS256 JaaS JWT scoped to one room + user. Returns None if signing material is missing.
    Token is never logged. `room` must be the study room's jitsi_name (not a wildcard).
    """
    app_id = (os.environ.get('JAAS_APP_ID') or '').strip()
    kid = (os.environ.get('JAAS_KID') or '').strip()
    pem = _jaas_private_key_pem()
    room = (room or '').strip()
    if not (app_id and kid and pem and room) or room == '*':
        return None
    try:
        import jwt  # PyJWT
    except ImportError:
        return None
    now = int(time.time())
    ttl = max(60, min(int(ttl_sec), 6 * 60 * 60))  # 1 min .. 6 h
    payload = {
        'aud': 'jitsi',
        'iss': 'chat',
        'sub': app_id,
        'room': room,
        'nbf': now - 10,
        'exp': now + ttl,
        'context': {
            'user': {
                'id': str(user_id),
                'name': (display_name or 'Student')[:80],
                'moderator': bool(moderator),
            }
        },
    }
    return jwt.encode(payload, pem, algorithm='RS256', headers={'alg': 'RS256', 'kid': kid, 'typ': 'JWT'})


def _room(rid):
    r = query('SELECT * FROM studyrooms WHERE room_id=%s', (rid,), one=True)
    if not r:
        abort(404)
    return r


def _is_member(rid, uid):
    return bool(query('SELECT 1 AS x FROM studyroom_members WHERE room_id=%s AND user_id=%s', (rid, uid), one=True))


def _member_room(rid):
    r = _room(rid)
    if not _is_member(rid, session['user_id']):
        abort(403)
    return r


def _friend_open_rooms(uid):
    """Accepted friends' rooms with friends_can_join on that the viewer is not already in."""
    rows = query(
        "SELECT r.room_id, r.title, r.owner_id, u.username AS host_username, "
        "COALESCE(p.display_name, u.username) AS host_display, u.last_seen_at, "
        "(SELECT COUNT(*) FROM studyroom_members sm WHERE sm.room_id = r.room_id) AS member_count "
        "FROM studyrooms r "
        "JOIN users u ON u.id = r.owner_id "
        "LEFT JOIN userprofiles p ON p.user_id = u.id "
        "JOIN friendships f ON f.status = 'accepted' AND ("
        "  (f.requester_id = %s AND f.addressee_id = r.owner_id) OR "
        "  (f.addressee_id = %s AND f.requester_id = r.owner_id)"
        ") "
        "WHERE COALESCE(r.friends_can_join, 1) = 1 AND r.owner_id <> %s "
        "AND NOT EXISTS (SELECT 1 FROM studyroom_members m WHERE m.room_id = r.room_id AND m.user_id = %s) "
        "ORDER BY u.last_seen_at DESC, r.room_id DESC",
        (uid, uid, uid, uid),
    ) or []
    from friends import is_online
    import apptime
    now = apptime.now_utc_naive()
    out = []
    for r in rows:
        d = dict(r)
        d['host_online'] = is_online(d.get('last_seen_at'), now)
        out.append(d)
    return out


@rooms_bp.route('/rooms')
@login_required
def rooms():
    uid = session['user_id']
    mine = query('SELECT r.room_id, r.title, r.course_id, c.course_name, '
                 'COALESCE(r.friends_can_join, 1) AS friends_can_join FROM studyrooms r '
                 'JOIN studyroom_members m ON m.room_id=r.room_id '
                 'LEFT JOIN usercourses c ON c.course_id=r.course_id WHERE m.user_id=%s ORDER BY r.room_id DESC', (uid,))
    courses = query('SELECT course_id, course_name FROM usercourses WHERE id=%s ORDER BY course_name', (uid,))
    return render_template('rooms.html', rooms=mine, courses=courses, friend_rooms=_friend_open_rooms(uid))


@rooms_bp.route('/rooms/new', methods=['POST'])
@login_required
def create_room():
    uid = session['user_id']
    title = (request.form.get('title') or '').strip()[:120] or 'Study room'
    cid = request.form.get('course_id') or None
    if cid and not query('SELECT 1 AS x FROM usercourses WHERE course_id=%s AND id=%s', (cid, uid), one=True):
        abort(400)
    rid = query('INSERT INTO studyrooms (owner_id, title, course_id, jitsi_name, join_token) VALUES (%s,%s,%s,%s,%s)',
                (uid, title, cid, 'Prody-' + secrets.token_hex(16), secrets.token_urlsafe(24)), commit=True)
    query('INSERT INTO studyroom_members (room_id, user_id) VALUES (%s,%s)', (rid, uid), commit=True)
    return redirect(url_for('rooms_bp.room', rid=rid))


@rooms_bp.route('/rooms/join/<token>')
@login_required
def join_room(token):
    r = query('SELECT room_id FROM studyrooms WHERE join_token=%s', (token,), one=True)
    if not r:
        abort(404)
    if not _is_member(r['room_id'], session['user_id']):
        query('INSERT INTO studyroom_members (room_id, user_id) VALUES (%s,%s)', (r['room_id'], session['user_id']), commit=True)
    return redirect(url_for('rooms_bp.room', rid=r['room_id']))




@rooms_bp.route('/rooms/<int:rid>/join-friend', methods=['POST'])
@login_required
def join_friend_room(rid):
    """Accepted friends of the host may join when friends_can_join is on — no invite token."""
    from friends import relation
    r = _room(rid)
    uid = session['user_id']
    if _is_member(rid, uid):
        return redirect(url_for('rooms_bp.room', rid=rid))
    if not int(r.get('friends_can_join') if r.get('friends_can_join') is not None else 1):
        abort(403)
    rel, _ = relation(uid, r['owner_id'])
    if rel != 'friends':
        abort(403)
    query('INSERT INTO studyroom_members (room_id, user_id) VALUES (%s,%s)', (rid, uid), commit=True)
    return redirect(url_for('rooms_bp.room', rid=rid))


@rooms_bp.route('/rooms/<int:rid>/settings', methods=['POST'])
@login_required
def room_settings(rid):
    """Owner-only: friends_can_join toggle (default on)."""
    r = _room(rid)
    if r['owner_id'] != session['user_id']:
        abort(403)
    on = 1 if request.form.get('friends_can_join') in ('1', 'on', 'true', 'yes') else 0
    query('UPDATE studyrooms SET friends_can_join = %s WHERE room_id = %s', (on, rid), commit=True)
    flash('Room settings saved.', 'success')
    return redirect(url_for('rooms_bp.room', rid=rid))

@rooms_bp.route('/rooms/<int:rid>')
@login_required
def room(rid):
    r = dict(_member_room(rid))
    c = query('SELECT course_name FROM usercourses WHERE course_id=%s', (r['course_id'],), one=True) if r.get('course_id') else None
    r['course_name'] = c['course_name'] if c else None
    me = query('SELECT u.username, p.display_name FROM users u LEFT JOIN userprofiles p ON p.user_id=u.id WHERE u.id=%s', (session['user_id'],), one=True) or {}
    name = me.get('display_name') or me.get('username') or 'Student'
    members = query('SELECT u.username FROM studyroom_members m JOIN users u ON u.id=m.user_id '
                    'WHERE m.room_id=%s', (rid,))
    link = url_for('rooms_bp.join_room', token=r['join_token'], _external=True)
    on = video_enabled()
    domain = jroom = jwt_token = None
    if on:
        domain, jroom = jitsi_target(r['jitsi_name'])
        # JWT only when JaaS triad is present (ROOM_VIDEO=jitsi has no JWT)
        jwt_token = mint_jaas_jwt(
            name, session['user_id'], room=r['jitsi_name'],
            moderator=(session['user_id'] == r['owner_id']))
    r['friends_can_join'] = int(r['friends_can_join'] if r.get('friends_can_join') is not None else 1)
    return render_template('room.html', r=r, display_name=name, members=members, join_link=link,
                           video_on=on, jitsi_domain=domain, jitsi_room=jroom, jitsi_jwt=jwt_token,
                           video_almost=_ALMOST, is_owner=(session['user_id'] == r['owner_id']))


@rooms_bp.route('/rooms/<int:rid>/whiteboard')
@login_required
def room_whiteboard(rid):
    """Legacy separate-page URL — board now lives embedded in the room view."""
    _member_room(rid)
    return redirect(url_for('rooms_bp.room', rid=rid) + '#board')


@rooms_bp.route('/rooms/<int:rid>/strokes', methods=['GET'])
@login_required
def get_strokes(rid):
    _member_room(rid)
    since = request.args.get('since', 0, type=int)
    rows = query('SELECT stroke_id, data FROM studyroom_strokes WHERE room_id=%s AND stroke_id>%s '
                 'ORDER BY stroke_id LIMIT 500', (rid, since))
    out = []
    for x in rows:
        try:
            out.append({'id': x['stroke_id'], 's': json.loads(x['data'])})
        except ValueError:
            continue
    return jsonify(strokes=out)


@rooms_bp.route('/rooms/<int:rid>/strokes', methods=['POST'])
@login_required
def post_stroke(rid):
    """Persist one board action. Freehand {pts,c,w} plus restored personal-board tools
    (hl/erase mode, shapes, text, note) as JSON in studyroom_strokes.data."""
    _member_room(rid)
    s = request.get_json(silent=True) or {}
    if s.get('clear'):
        data = {'clear': True}
    else:
        tool = (s.get('t') or '').strip().lower()
        try:
            if tool in ('line', 'arrow', 'rect', 'ellipse'):
                x0, y0, x1, y1 = (round(float(s[k]), 4) for k in ('x0', 'y0', 'x1', 'y1'))
                w = max(1, min(40, int(s.get('w', 3))))
                data = {'t': tool, 'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
                        'c': str(s.get('c', '#3b3a36'))[:20], 'w': w}
            elif tool == 'text':
                text = str(s.get('text') or '')[:500]
                if not text.strip():
                    abort(400)
                data = {'t': 'text', 'x': round(float(s['x']), 4), 'y': round(float(s['y']), 4),
                        'text': text, 'c': str(s.get('c', '#3b3a36'))[:20],
                        'size': max(2, min(10, int(s.get('size', 2))))}
            elif tool == 'note':
                data = {'t': 'note', 'x': round(float(s['x']), 4), 'y': round(float(s['y']), 4),
                        'text': str(s.get('text') or '')[:1000]}
            else:
                pts = s.get('pts')
                if not isinstance(pts, list) or not pts or len(pts) > 2000:
                    abort(400)
                pts = [[round(float(p[0]), 4), round(float(p[1]), 4)] for p in pts]
                w = max(1, min(40, int(s.get('w', 3))))
                mode = (s.get('mode') or 'pen').strip().lower()
                if mode not in ('pen', 'hl', 'erase'):
                    mode = 'pen'
                data = {'pts': pts, 'c': str(s.get('c', '#3b3a36'))[:20], 'w': w, 'mode': mode}
        except (TypeError, ValueError, IndexError, KeyError):
            abort(400)
    sid = query('INSERT INTO studyroom_strokes (room_id, user_id, data) VALUES (%s,%s,%s)',
                (rid, session['user_id'], json.dumps(data)), commit=True)
    return jsonify(id=sid)
