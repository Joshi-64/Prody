"""Shared helpers: auth decorators, AI client, gamification stats."""
import apptime
import os
from datetime import date, datetime, timedelta
from functools import wraps
import threading
import time

import requests
from flask import flash, redirect, session, url_for

from db import get_db_connection

SUBJECTS = ['Computer Science', 'Mathematics', 'Biology', 'Chemistry', 'Physics', 'English',
            'History', 'Psychology', 'Economics', 'Business', 'Art', 'Other']
def null_colour_map(user_id):
    """r9 display-only: course_id -> palette colour for this user's classes whose stored colour is NULL/empty.
    Walks the user's classes in creation order (course_id) and hands each blank one the next palette colour not
    already stored/assigned (cycles once all are taken). Never writes to the database."""
    rows = query('SELECT course_id, color FROM usercourses WHERE id = %s ORDER BY course_id', (user_id,)) or []
    used = [(r['color'] or '').upper() for r in rows if r['color']]
    out = {}
    for r in rows:
        if not r['color']:
            c = next((p for p in COURSE_COLORS if p.upper() not in used), COURSE_COLORS[len(used) % len(COURSE_COLORS)])
            out[r['course_id']] = c; used.append(c.upper())
    return out


def fill_display_colours(rows, user_id):
    """r9: rows carrying course_id + a blank color get their display palette colour (in place); returns rows."""
    rows = rows or []
    if any(r.get('course_id') and not r.get('color') for r in rows):
        m = null_colour_map(user_id)
        for r in rows:
            if r.get('course_id') and not r.get('color') and r['course_id'] in m:
                r['color'] = m[r['course_id']]
    return rows


COURSE_COLORS = ['#CFDCC6', '#EADCC2', '#F0D3C3', '#C9DAEC', '#DCCFEA', '#F0CBD6', '#C4E0DC', '#F0E6B8']  # calm course tints (dark text stays AA); r3: 8 distinct hues so branch flowers differ


# --- Simple in-process rate limiter (Bark). Per worker; good enough for one Render
# instance. Swap for a shared store if we ever run several workers.
_RL = {}
_RL_LOCK = threading.Lock()


def rate_limit_hit(key, limit, window, peek=False):
    """Record one hit for key (unless peek) and return True if key is over limit within window seconds."""
    now = time.time()
    with _RL_LOCK:
        hits = [t for t in _RL.get(key, []) if now - t < window]
        if not peek:
            hits.append(now)
        _RL[key] = hits
        return len(hits) >= limit if peek else len(hits) > limit


def rate_limit_reset(key):
    with _RL_LOCK:
        _RL.pop(key, None)


def _session_user_ok():
    """True only if the session names a user that still exists. A stale cookie (user deleted,
    or a preview DB without that user) is cleared so pages never render an empty frame."""
    uid = session.get('user_id')
    if uid is not None and query('SELECT id FROM users WHERE id = %s', (uid,), one=True):
        return True
    session.clear()
    return False


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _session_user_ok():
            flash('You need to log in first.', 'warning')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        from flask import abort
        if not _session_user_ok():
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Access restricted to administrators.', 'danger')
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def query(sql, params=(), one=False, commit=False):
    """Run one statement and always close the connection.

    Always goes through db.get_db_connection(), so mysql / sqlite / libsql(Turso)
    are selected by db.DB_BACKEND — rooms, whiteboard strokes, social, DMs, boards,
    and every other module that imports helpers.query hit the same backend.
    """
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        if commit:
            conn.commit()
            _clear_stats_cache(sql)
            return cur.lastrowid
        return cur.fetchone() if one else cur.fetchall()
    finally:
        cur.close()
        _release(conn)


def _release(conn):
    """Hand a connection back with no open transaction: rollback (a no-op after commit) then close.
    The MySQL pool runs with pool_reset_session=False, so this rollback is what keeps it clean."""
    try:
        conn.rollback()
    except Exception:
        pass
    conn.close()


def _req_cached(key, uid, loader):
    """Per-request cache for whole-user reads shared by several helpers (dashboard: stats, plant, week chart).
    Cleared with the stats cache on every committed write."""
    try:
        from flask import g, has_request_context
        if has_request_context():
            cache = g.setdefault(key, {})
            if uid not in cache:
                cache[uid] = loader()
            return cache[uid]
    except ImportError:
        pass
    return loader()


def user_sessions(uid):
    """All of a user's study sessions (course_id, minutes, started_at, completed), one read per request."""
    return _req_cached('_user_sessions', uid, lambda: query(
        'SELECT course_id, minutes, started_at, completed FROM studysessions WHERE user_id = %s', (uid,)))


def user_todos(uid):
    """All of a user's tasks with their class colour, one read per request. Callers must not mutate rows."""
    return _req_cached('_user_todos', uid, lambda: query(
        'SELECT t.*, c.color FROM todolist t LEFT JOIN usercourses c ON c.course_id = t.course_id '
        'WHERE t.user_id = %s ORDER BY t.is_completed, t.due_date', (uid,)))


def as_dt(v):
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    if isinstance(v, str) and v:
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
            try:
                return datetime.strptime(v[:19], fmt)
            except ValueError:
                pass
    return None


# ------------------------------------------------------------------ AI
def _ai_settings():
    key = os.environ.get('PRODY_AI_KEY') or os.environ.get('OPENAI_API_KEY')
    base = os.environ.get('PRODY_AI_BASE_URL')
    model = os.environ.get('PRODY_AI_MODEL')
    if not key:
        try:
            from config_ai import prody_ai_key  # legacy Sprint 3 config, gitignored
            key = prody_ai_key
            base = base or 'https://openrouter.ai/api/v1'
            model = model or 'openrouter/free'
        except ModuleNotFoundError:
            return None
    return key, (base or 'https://api.openai.com/v1').rstrip('/'), model or 'gpt-4o-mini'


def ai_available():
    return _ai_settings() is not None


def ai_chat(messages, timeout=45):
    """Return assistant text, or raise RuntimeError if AI is unavailable."""
    settings = _ai_settings()
    if not settings:
        raise RuntimeError('not configured')
    key, base, model = settings
    resp = requests.post(f'{base}/chat/completions', timeout=timeout,
                         headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                         json={'model': model, 'messages': messages})
    if resp.status_code != 200:
        raise RuntimeError(f'status {resp.status_code}')
    return resp.json()['choices'][0]['message']['content'].strip()


# ------------------------------------------------------------------ gamification
BADGES = [
    ('first_focus', 'First Focus', 'Complete your first study session', 'bolt'),
    ('five_hours', 'Deep Diver', 'Study 5 hours total', 'waves'),
    ('twenty_hours', 'Scholar', 'Study 20 hours total', 'school'),
    ('streak3', 'On a Roll', '3-day study streak', 'local_fire_department'),
    ('streak7', 'Unstoppable', '7-day study streak', 'whatshot'),
    ('tasks10', 'Task Crusher', 'Complete 10 tasks', 'task_alt'),
    ('planner', 'Planner', 'Keep an AI study plan', 'auto_awesome'),
    ('graded', 'Grade Keeper', 'Log 5 grades', 'grade'),
]


def _clear_stats_cache(sql=None):
    """Drop per-request caches after a write. With the statement known, the session/task row caches survive
    writes that can't touch them (e.g. last_seen, milestones); with no statement, everything goes."""
    from flask import g, has_request_context
    if has_request_context():
        g.pop('_user_stats', None)
        low = (sql or '').lower()
        if sql is None or 'studysessions' in low or 'usercourses' in low or 'delete from users' in low:
            g.pop('_user_sessions', None)
        if sql is None or 'todolist' in low or 'usercourses' in low or 'delete from users' in low:
            g.pop('_user_todos', None)


def user_stats(user_id):
    # Cached per request: several templates/context processors ask for the same stats.
    try:
        from flask import g, has_request_context
        if has_request_context():
            cache = g.setdefault('_user_stats', {})
            if user_id not in cache:
                cache[user_id] = _user_stats(user_id)
            return cache[user_id]
    except ImportError:
        pass
    return _user_stats(user_id)


def _user_stats(user_id):
    sessions = user_sessions(user_id)
    total_min = sum(int(s['minutes']) for s in sessions)
    days = {apptime.local_date(as_dt(s['started_at'])) for s in sessions if as_dt(s['started_at'])}
    streak, d = 0, apptime.today_local()
    if d not in days:
        d -= timedelta(days=1)  # streak survives until the end of today
    while d in days:
        streak += 1
        d -= timedelta(days=1)
    week_start = apptime.today_local() - timedelta(days=6)
    week_min = sum(int(s['minutes']) for s in sessions
                   if as_dt(s['started_at']) and apptime.local_date(as_dt(s['started_at'])) >= week_start)
    done = sum(1 for t in user_todos(user_id) if t['is_completed'])
    kept = query("SELECT COUNT(*) AS n FROM calendarevents WHERE user_id = %s AND is_ai_recommended = 1 "
                 "AND flag_status = 'confirmed'", (user_id,), one=True)['n']
    grades = query('SELECT COUNT(*) AS n FROM grades WHERE user_id = %s', (user_id,), one=True)['n']
    earned = {
        'first_focus': len(sessions) >= 1, 'five_hours': total_min >= 300, 'twenty_hours': total_min >= 1200,
        'streak3': streak >= 3, 'streak7': streak >= 7, 'tasks10': done >= 10, 'planner': kept >= 1,
        'graded': grades >= 5,
    }
    earned_pts = total_min + done * 10 + kept * 5 + streak * 15 + sum(earned.values()) * 50
    spent = query('SELECT COALESCE(SUM(price_paid), 0) AS n FROM userinventory WHERE user_id = %s', (user_id,), one=True)['n']
    points = earned_pts - int(spent)  # spendable balance in the Store
    level = earned_pts // 500 + 1
    return {
        'total_minutes': total_min, 'week_minutes': week_min, 'sessions': len(sessions), 'streak': streak,
        'tasks_done': int(done), 'points': points, 'earned_points': earned_pts, 'level': level,
        'level_progress': int((earned_pts % 500) / 5), 'earned_count': sum(earned.values()),
        'badges': [dict(key=k, name=n, desc=ds, icon=i, earned=earned[k]) for k, n, ds, i in BADGES],
    }
