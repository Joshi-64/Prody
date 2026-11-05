"""Study Session focus timer, Time Studied analytics, and achievements."""
import apptime
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from helpers import as_dt, login_required, fill_display_colours, query, user_stats

study_bp = Blueprint('study_bp', __name__)


@study_bp.route('/study')
@study_bp.route('/focus')
def focus_redirect():
    """Focus merged into Zen (one page). Old links 302 to /zen, keeping any query string."""
    qs = request.query_string.decode()
    return redirect(url_for('study_bp.timer') + ('?' + qs if qs else ''), code=302)


@study_bp.before_app_request
def _old_zen_path():
    # profiles.py still owns /coming-soon/zen; send it to the merged page without editing that file
    if request.path.rstrip('/') == '/coming-soon/zen':
        return redirect(url_for('study_bp.timer'), code=302)


@study_bp.route('/zen')
@login_required
def timer():
    uid = session['user_id']
    courses = query('SELECT course_id, course_name, color FROM usercourses WHERE id = %s ORDER BY course_name', (uid,))
    recent = query('SELECT s.*, c.course_name, c.color FROM studysessions s LEFT JOIN usercourses c '
                   'ON c.course_id = s.course_id WHERE s.user_id = %s ORDER BY s.started_at DESC LIMIT 6', (uid,))
    fill_display_colours(courses, uid); fill_display_colours(recent, uid)
    from plant import plant_state
    return render_template('zen.html', courses=courses, recent=recent, stats=user_stats(uid), st=plant_state(uid),
                           grew=session.pop('plant_grew', False))


@study_bp.route('/study/log', methods=['POST'])
@login_required
def log_session():
    data = request.get_json(silent=True) or request.form
    try:
        minutes = int(float(data.get('minutes', 0)))
    except (TypeError, ValueError):
        minutes = 0
    if not 1 <= minutes <= 600:
        msg = 'Sessions must be between 1 and 600 minutes.'
        return (jsonify(ok=False, error=msg), 400) if request.is_json else (flash(msg, 'warning') or redirect(url_for('study_bp.timer')))
    course_id = data.get('course_id') or None
    if course_id and not query('SELECT course_id FROM usercourses WHERE course_id = %s AND id = %s',
                               (course_id, session['user_id']), one=True):
        course_id = None
    label = (data.get('label') or 'Focus session').strip()[:255]
    # completed=true only when the focus timer reached 0 (not 'Finish early' or a manual log): that session blooms a flower
    completed = 1 if str(data.get('completed', '')).lower() in ('1', 'true', 'on', 'yes') else 0
    from plant import plant_state, record_milestones, render_plant
    before = {b['key'] for b in user_stats(session['user_id'])['badges'] if b['earned']}
    p_before = plant_state(session['user_id'])
    query('INSERT INTO studysessions (user_id, course_id, label, minutes, started_at, completed) VALUES (%s, %s, %s, %s, %s, %s)',
          (session['user_id'], course_id, label, minutes, apptime.now_utc_naive() - timedelta(minutes=minutes), completed), commit=True)
    watered = False
    if completed:  # a finished focus session waters the plant, at most once a day
        from profiles import water_today
        watered = water_today(session['user_id'], data.get('tz_offset'))
    stats = user_stats(session['user_id'])
    if request.is_json:
        new = [b['name'] for b in stats['badges'] if b['earned'] and b['key'] not in before]
        p_after = plant_state(session['user_id'])
        record_milestones(session['user_id'], p_after)
        return jsonify(ok=True, minutes=minutes, flower={'course_id': int(course_id)} if (completed and course_id) else None, points=stats['points'], streak=stats['streak'], new_badges=new, watered=watered,
                       plant={'svg': str(render_plant(p_after, grow=True)), 'stage': p_after['stage'],
                              'stage_up': p_after['stage_idx'] > p_before['stage_idx'],
                              'gain': round(100 * (p_after['growth'] - p_before['growth']), 1),
                              'to_next': p_after['to_next'], 'next_stage': p_after['next_stage'],
                              'hours': p_after['hours'], 'revived': p_before['mood'] != 'happy',
                              'name': p_after['name']})
    session['celebrate'] = True
    session['plant_grew'] = True
    flash(f'Logged {minutes} minutes. Your plant soaked it up.', 'success')
    return redirect(url_for('study_bp.timer'))


@study_bp.route('/analytics')
@login_required
def analytics():
    uid = session['user_id']
    # Week / Month toggle (legacy ?range=7|14|30 still accepted)
    period = (request.args.get('period') or '').lower()
    rng = request.args.get('range', '')
    if period in ('week', 'month'):
        days = 7 if period == 'week' else 30
    else:
        days = {'7': 7, '14': 14, '30': 30}.get(rng, 7)
        period = 'week' if days <= 7 else 'month'
    start = apptime.today_local() - timedelta(days=days - 1)
    sessions = query('SELECT s.minutes, s.started_at, c.course_id, c.course_name, c.color FROM studysessions s LEFT JOIN usercourses c '
                     'ON c.course_id = s.course_id WHERE s.user_id = %s AND s.started_at >= %s',
                     (uid, apptime.day_bounds_utc(start)[0]))
    fill_display_colours(sessions, uid)
    labels, daily = [], []
    for i in range(days):
        d = start + timedelta(days=i)
        labels.append(d.strftime('%b %d') if period == 'month' else d.strftime('%a'))
        daily.append(sum(int(s['minutes']) for s in sessions if apptime.local_date(as_dt(s['started_at'])) == d))
    by_course = {}
    for s in sessions:
        k = s['course_name'] or 'General'
        by_course.setdefault(k, {'minutes': 0, 'color': s['color'] or '#94a3b8'})['minutes'] += int(s['minutes'])
    # Hours per course per day for stacked/grouped bars
    course_names = list(by_course.keys()) or ['General']
    stacked = {name: [0.0] * days for name in course_names}
    for s in sessions:
        d = apptime.local_date(as_dt(s['started_at']))
        if d is None:
            continue
        idx = (d - start).days
        if 0 <= idx < days:
            name = s['course_name'] or 'General'
            stacked.setdefault(name, [0.0] * days)
            stacked[name][idx] += int(s['minutes']) / 60.0
    course_colors = {k: by_course.get(k, {}).get('color') or '#94a3b8' for k in stacked}
    hours = [0] * 24
    for s in sessions:
        hours[apptime.to_local(as_dt(s['started_at'])).hour] += int(s['minutes'])
    total = sum(daily)
    best = max(range(24), key=lambda h: hours[h]) if total else None
    return render_template('analytics.html', labels=labels, daily=daily, by_course=by_course, hours=hours,
                           total=total, avg=total // days, best_hour=best, rng=str(days), period=period,
                           stats=user_stats(uid), active_days=sum(1 for m in daily if m),
                           stacked=stacked, course_colors=course_colors)


@study_bp.route('/achievements')
@login_required
def achievements():
    uid = session['user_id']
    # Leaderboard is opt-in: only students who switched on 'Show me on the leaderboard' are listed.
    # You always see your own rank; other names appear only if they opted in.
    rows = query("SELECT u.id, u.username, 1 AS opted FROM users u JOIN userprofiles p ON p.user_id = u.id "
                 "WHERE u.role = 'student' AND p.show_on_leaderboard = 1")
    if uid not in {u['id'] for u in rows}:
        me_row = query('SELECT id, username FROM users WHERE id = %s', (uid,), one=True)
        if me_row:
            rows.append(me_row)
    board = [{'user': u, 'uid': u['id'], 'points': user_stats(u['id'])['earned_points'], 'me': u['id'] == uid, 'opted': bool(u.get('opted'))} for u in rows]
    board.sort(key=lambda r: -r['points'])
    for i, r in enumerate(board, 1):
        r['rank'] = i
    top = board[:10]
    mine = next((r for r in board if r['me']), None)
    if mine and mine not in top:
        top.append(mine)
    from profiles import get_profile
    opted = bool(get_profile(uid).get('show_on_leaderboard'))
    return render_template('achievements.html', stats=user_stats(uid), board=top, opted_in=opted,
                           others=sum(1 for r in board if not r['me']))
