"""Direct messages between accepted friends. Poll JSON every 3s; CSRF on POSTs."""
import apptime
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for

from friends import accepted_friends, relation
from fn_flags import DEMO_LABEL
from helpers import login_required, query

dm_bp = Blueprint('dm_bp', __name__)
MAX_BODY = 2000

def _rel_time(v):
    from helpers import as_dt
    d = as_dt(v)
    if not d:
        return ''
    delta = apptime.now_utc_naive() - d
    secs = max(0, int(delta.total_seconds()))
    if secs < 60: return 'now'
    if secs < 3600: return f'{secs // 60}m'
    if secs < 86400: return f'{secs // 3600}h'
    if secs < 86400 * 7: return d.strftime('%a')
    return d.strftime('%b %d')

AV_PALETTE = ['#E8BFC6', '#DDE7D3', '#CBBBD8', '#F2E2CB', '#C9DAEC', '#F0CBD6']


def av_color(name):
    return AV_PALETTE[sum(ord(c) for c in (name or '')) % len(AV_PALETTE)]


def _friends_only(uid, other_id):
    rel, _ = relation(uid, other_id)
    return rel == 'friends'


def _user_by_name(username):
    return query('SELECT id, username FROM users WHERE username = %s', (username,), one=True)


@dm_bp.route('/messages')
@login_required
def inbox():
    uid = session['user_id']
    friends = accepted_friends(uid)
    # Latest message preview per friend (either direction)
    threads = []
    for f in friends:
        last = query(
            'SELECT id, sender_id, body, created_at FROM dm_messages WHERE '
            '(sender_id = %s AND recipient_id = %s) OR (sender_id = %s AND recipient_id = %s) '
            'ORDER BY id DESC LIMIT 1',
            (uid, f['id'], f['id'], uid), one=True)
        unread = 0
        if last and last['sender_id'] != uid:
            # no read-receipts yet: badge when the latest message is from them
            unread = query(
                'SELECT COUNT(*) AS n FROM dm_messages WHERE sender_id = %s AND recipient_id = %s AND id >= %s',
                (f['id'], uid, last['id']), one=True)['n']
        threads.append({**f, 'last': last, 'av': av_color(f.get('display') or f.get('username')),
                        'when': _rel_time(last['created_at']) if last else '', 'unread': unread})
    threads.sort(key=lambda t: (t['last'] or {}).get('id') or 0, reverse=True)
    return render_template('dm_inbox.html', threads=threads, demo_label=DEMO_LABEL)


@dm_bp.route('/messages/<username>', methods=['GET', 'POST'])
@login_required
def thread(username):
    uid = session['user_id']
    other = _user_by_name(username)
    if not other or other['id'] == uid:
        flash('No such friend.', 'warning')
        return redirect(url_for('dm_bp.inbox'))
    if not _friends_only(uid, other['id']):
        flash('You can only message accepted friends.', 'warning')
        if request.method == 'POST':
            abort(403)
        return redirect(url_for('dm_bp.inbox'))
    if request.method == 'POST':
        # Form fallback (non-JS)
        body = (request.form.get('body') or '').strip()[:MAX_BODY]
        if body:
            query('INSERT INTO dm_messages (sender_id, recipient_id, body, created_at) VALUES (%s,%s,%s,%s)',
                  (uid, other['id'], body, apptime.now_utc_naive()), commit=True)
        return redirect(url_for('dm_bp.thread', username=username))
    msgs = query(
        'SELECT m.*, u.username AS sender_name FROM dm_messages m JOIN users u ON u.id = m.sender_id '
        'WHERE (m.sender_id = %s AND m.recipient_id = %s) OR (m.sender_id = %s AND m.recipient_id = %s) '
        'ORDER BY m.id ASC LIMIT 200',
        (uid, other['id'], other['id'], uid))
    return render_template('dm_thread.html', other=other, messages=msgs, demo_label=DEMO_LABEL,
                           other_av=av_color(other['username']), me_id=uid)


@dm_bp.route('/messages/<username>/send', methods=['POST'])
@login_required
def send(username):
    uid = session['user_id']
    other = _user_by_name(username)
    if not other or other['id'] == uid:
        return jsonify(ok=False, error='not_found'), 404
    if not _friends_only(uid, other['id']):
        return jsonify(ok=False, error='not_friends'), 403
    data = request.get_json(silent=True) or {}
    body = (data.get('body') or request.form.get('body') or '').strip()[:MAX_BODY]
    if not body:
        return jsonify(ok=False, error='empty'), 400
    mid = query('INSERT INTO dm_messages (sender_id, recipient_id, body, created_at) VALUES (%s,%s,%s,%s)',
                (uid, other['id'], body, apptime.now_utc_naive()), commit=True)
    row = query('SELECT id, sender_id, recipient_id, body, created_at FROM dm_messages WHERE id = %s', (mid,), one=True)
    return jsonify(ok=True, message={'id': row['id'], 'sender_id': row['sender_id'], 'body': row['body'],
                                     'created_at': str(row['created_at']), 'mine': True})


@dm_bp.route('/messages/<username>/poll')
@login_required
def poll(username):
    uid = session['user_id']
    other = _user_by_name(username)
    if not other or not _friends_only(uid, other['id']):
        return jsonify(ok=False, error='forbidden'), 403
    try:
        since = int(request.args.get('since_id') or 0)
    except ValueError:
        since = 0
    rows = query(
        'SELECT id, sender_id, body, created_at FROM dm_messages WHERE id > %s AND '
        '((sender_id = %s AND recipient_id = %s) OR (sender_id = %s AND recipient_id = %s)) '
        'ORDER BY id ASC LIMIT 50',
        (since, uid, other['id'], other['id'], uid))
    return jsonify(ok=True, messages=[{
        'id': r['id'], 'sender_id': r['sender_id'], 'body': r['body'],
        'created_at': str(r['created_at']), 'mine': r['sender_id'] == uid
    } for r in rows])
