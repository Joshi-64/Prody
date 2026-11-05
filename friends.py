import apptime
import hashlib
"""Friends: requests by exact username, accept/decline/cancel/remove, online status (last_seen_at)."""
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import IntegrityError
from helpers import login_required, query

friends_bp = Blueprint('friends_bp', __name__)

ONLINE_WINDOW = timedelta(minutes=5)
SEEN_THROTTLE = timedelta(seconds=60)
STUDY_WINDOW = timedelta(minutes=60)
REQ_LIMIT_PER_HOUR = 20


def _as_dt(v):
    if v is None or isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v))
    except ValueError:
        return None


def is_online(last_seen, now=None):
    t = _as_dt(last_seen)
    return bool(t and t >= (now or apptime.now_utc_naive()) - ONLINE_WINDOW)


@friends_bp.before_app_request
def touch_last_seen():
    uid = session.get('user_id')
    if not uid or (request.endpoint or '') == 'static':
        return
    now = apptime.now_utc_naive()
    last = session.get('_seen_ts')
    if last and now.timestamp() - last < SEEN_THROTTLE.total_seconds():
        return
    try:
        query('UPDATE users SET last_seen_at = %s WHERE id = %s', (now, uid), commit=True)
        session['_seen_ts'] = now.timestamp()
    except Exception:
        pass  # never block a page on presence


@friends_bp.app_context_processor
def _friend_globals():
    def friend_requests_count():
        uid = session.get('user_id')
        if not uid:
            return 0
        try:
            return query("SELECT COUNT(*) AS n FROM friendships WHERE addressee_id = %s AND status = 'pending'",
                         (uid,), one=True)['n']
        except Exception:
            return 0
    return {'friend_requests_count': friend_requests_count}


def pair(a, b):
    """The friendship row between a and b in either direction, or None."""
    return query('SELECT id, requester_id, addressee_id, status FROM friendships WHERE '
                 '(requester_id = %s AND addressee_id = %s) OR (requester_id = %s AND addressee_id = %s)',
                 (a, b, b, a), one=True)


def relation(viewer, other):
    """'self' | 'none' | 'friends' | 'requested' (viewer sent) | 'incoming' (other sent)."""
    if viewer == other:
        return 'self', None
    r = pair(viewer, other)
    if not r:
        return 'none', None
    if r['status'] == 'accepted':
        return 'friends', r
    return ('requested' if r['requester_id'] == viewer else 'incoming'), r


def _accept(fid):
    query("UPDATE friendships SET status = 'accepted', accepted_at = %s WHERE id = %s AND status = 'pending'",
          (apptime.now_utc_naive(), fid), commit=True)


def _display(uid, username):
    try:
        from profiles import decorate
        return decorate({'id': uid, 'username': username}).get('display') or username
    except Exception:
        return username


def accepted_friends(uid):
    rows = query("SELECT u.id, u.username, u.last_seen_at FROM friendships f JOIN users u ON u.id = "
                 "CASE WHEN f.requester_id = %s THEN f.addressee_id ELSE f.requester_id END "
                 "WHERE (f.requester_id = %s OR f.addressee_id = %s) AND f.status = 'accepted' ORDER BY u.username",
                 (uid, uid, uid))
    now = apptime.now_utc_naive()
    return [dict(r, online=is_online(r['last_seen_at'], now), display=_display(r['id'], r['username'])) for r in rows]


def online_friends_for_park(uid, cap):
    """Park contract: online accepted friends, most recently seen first, capped to the visitor spot count."""
    if cap <= 0:
        return []
    now = apptime.now_utc_naive()
    on = [f for f in accepted_friends(uid) if f['online']]
    on.sort(key=lambda f: _as_dt(f['last_seen_at']), reverse=True)
    out = []
    for f in on[:cap]:
        s = query('SELECT COUNT(*) AS n FROM studysessions WHERE user_id = %s AND started_at >= %s',
                  (f['id'], now - STUDY_WINDOW), one=True)
        out.append({'username': f['username'], 'display': f['display'], 'online': True,
                    'activity': 'studying' if s and s['n'] else 'walking',
                    'color': FRIEND_COLORS[int(hashlib.md5(f['username'].lower().encode()).hexdigest(), 16) % len(FRIEND_COLORS)]})
    return out


FRIEND_COLORS = ['#C9805A', '#6E8FB8', '#8A6BB0', '#D4A63A', '#5E9E7A', '#C46B8A', '#4F8C9C', '#B5654A']  # stable per-username shirt tint


def _back(default='friends_bp.friends'):
    nxt = request.form.get('next') or ''
    return redirect(nxt if nxt.startswith('/') and not nxt.startswith('//') else url_for(default))


def _seen_line(f, now):
    if f['online']:
        s = query('SELECT COUNT(*) AS n FROM studysessions WHERE user_id = %s AND started_at >= %s',
                  (f['id'], now - STUDY_WINDOW), one=True)
        return 'Studying' if s and s['n'] else 'Online'
    t = _as_dt(f.get('last_seen_at'))
    if not t:
        return 'Not seen yet'
    d = now - t
    if d < timedelta(hours=1):
        return f'Last seen {max(1, int(d.total_seconds() // 60))}m ago'
    if d < timedelta(days=1):
        return f'Last seen {int(d.total_seconds() // 3600)}h ago'
    if d < timedelta(days=2):
        return 'Last seen yesterday'
    return f'Last seen {d.days} days ago'


@friends_bp.route('/friends')
@login_required
def friends():
    uid = session['user_id']
    now = apptime.now_utc_naive()
    incoming = query("SELECT f.id, u.id AS uid, u.username FROM friendships f JOIN users u ON u.id = f.requester_id "
                     "WHERE f.addressee_id = %s AND f.status = 'pending' ORDER BY f.created_at DESC", (uid,))
    incoming = [dict(r, display=_display(r['uid'], r['username'])) for r in incoming]
    outgoing = query("SELECT f.id, u.username FROM friendships f JOIN users u ON u.id = f.addressee_id "
                     "WHERE f.requester_id = %s AND f.status = 'pending' ORDER BY f.created_at DESC", (uid,))
    fl = [dict(f, seen=_seen_line(f, now)) for f in accepted_friends(uid)]
    q = (request.args.get('u') or '').strip().lstrip('@')[:255]
    lookup = None
    if q:  # exact-username lookup on submit only (no live search)
        o = query('SELECT id, username FROM users WHERE LOWER(username) = LOWER(%s)', (q,), one=True)
        if o:
            rel, row = relation(uid, o['id'])
            lookup = {'username': o['username'], 'display': _display(o['id'], o['username']),
                      'rel': rel, 'fid': row['id'] if row else None}
    return render_template('friends.html', friends=fl, incoming=incoming, outgoing=outgoing, q=q, lookup=lookup)


@friends_bp.route('/friends/request', methods=['POST'])
@login_required
def send_request():
    uid = session['user_id']
    name = (request.form.get('username') or '').strip().lstrip('@')[:255]
    if not name:
        flash('Type a username to add.', 'warning')
        return _back()
    other = query('SELECT id, username FROM users WHERE LOWER(username) = LOWER(%s)', (name,), one=True)
    if not other:
        flash('No user found', 'warning')
        return _back()
    oid = other['id']
    if oid == uid:
        flash("You can't add yourself as a friend.", 'warning')
        return _back()
    rel, row = relation(uid, oid)
    if rel == 'friends':
        flash(f"You and @{other['username']} are already friends.", 'info')
        return _back()
    if rel == 'requested':
        flash(f"Your request to @{other['username']} is still waiting.", 'info')
        return _back()
    if rel == 'incoming':
        _accept(row['id'])
        flash(f"@{other['username']} had already asked. You're friends now.", 'success')
        return _back()
    now = apptime.now_utc_naive()
    n = query('SELECT COUNT(*) AS n FROM friend_request_log WHERE user_id = %s AND created_at >= %s',
              (uid, now - timedelta(hours=1)), one=True)['n']
    if n >= REQ_LIMIT_PER_HOUR:
        flash('You have sent a lot of friend requests this hour. Try again a little later.', 'warning')
        return _back()
    query('INSERT INTO friend_request_log (user_id, created_at) VALUES (%s, %s)', (uid, now), commit=True)
    try:
        query("INSERT INTO friendships (requester_id, addressee_id, user_lo, user_hi, status, created_at) "
              "VALUES (%s, %s, %s, %s, 'pending', %s)", (uid, oid, min(uid, oid), max(uid, oid), now), commit=True)
        flash(f"Friend request sent to @{other['username']}.", 'success')
    except IntegrityError:  # a simultaneous request landed first (UNIQUE user_lo, user_hi)
        rel, row = relation(uid, oid)
        if rel == 'incoming':
            _accept(row['id'])
            flash(f"You and @{other['username']} are friends now.", 'success')
        elif rel == 'friends':
            flash(f"You and @{other['username']} are friends now.", 'success')
        else:
            flash(f"Your request to @{other['username']} is already in.", 'info')
    return _back()


@friends_bp.route('/friends/<int:fid>/accept', methods=['POST'])
@login_required
def accept(fid):
    r = query("SELECT id FROM friendships WHERE id = %s AND addressee_id = %s AND status = 'pending'",
              (fid, session['user_id']), one=True)
    if r:
        _accept(fid)
        flash('Friend request accepted.', 'success')
    else:
        flash('That request is no longer there.', 'warning')
    return _back()


@friends_bp.route('/friends/<int:fid>/decline', methods=['POST'])
@login_required
def decline(fid):
    """Decline an incoming request or cancel your own outgoing one (row is deleted)."""
    uid = session['user_id']
    r = query("SELECT id, requester_id FROM friendships WHERE id = %s AND status = 'pending' AND "
              "(addressee_id = %s OR requester_id = %s)", (fid, uid, uid), one=True)
    if r:
        query('DELETE FROM friendships WHERE id = %s', (fid,), commit=True)
        flash('Request cancelled.' if r['requester_id'] == uid else 'Request declined.', 'success')
    return _back()


@friends_bp.route('/friends/<username>/remove', methods=['POST'])
@login_required
def remove(username):
    uid = session['user_id']
    other = query('SELECT id, username FROM users WHERE LOWER(username) = LOWER(%s)', (username,), one=True)
    if other:
        query('DELETE FROM friendships WHERE (requester_id = %s AND addressee_id = %s) OR '
              '(requester_id = %s AND addressee_id = %s)', (uid, other['id'], other['id'], uid), commit=True)
        flash(f"Removed @{other['username']} from your friends.", 'success')
    return _back()
