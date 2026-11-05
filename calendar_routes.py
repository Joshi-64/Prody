import apptime
from datetime import datetime, timedelta

import requests
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from ics import Calendar

from db import get_db_connection
from helpers import ai_available, ai_chat, as_dt, login_required, fill_display_colours, query

# Create the blueprint object for calendar object
from profiles import class_dot_colour
calendar_bp = Blueprint('calendar_bp', __name__)


def _load_events(user_id):
    events = query('SELECT * FROM calendarevents WHERE user_id = %s ORDER BY event_date', (user_id,))
    dl_rows = query(
        'SELECT d.deadline_name, d.deadline_date, c.course_id, c.course_name, c.color FROM coursedeadlines d JOIN usercourses c '
        'ON c.course_id = d.course_id WHERE c.id = %s', (user_id,)) or []
    fill_display_colours(dl_rows, user_id)
    deadline_names = {(d['deadline_name'], as_dt(d['deadline_date'])) for d in dl_rows}
    # class-owned events: dot colour from the ONE shared helper (stored pastel -> mapped/deepened)
    course_for = {(d['deadline_name'], as_dt(d['deadline_date'])): d.get('course_name') or '' for d in dl_rows}
    class_dot_for = {(d['deadline_name'], as_dt(d['deadline_date'])): class_dot_colour(d.get('color')) for d in dl_rows}
    dot_by_course = {(d.get('course_name') or ''): class_dot_colour(d.get('color')) for d in dl_rows}
    open_dls = query(
        'SELECT d.deadline_id, d.deadline_name, d.deadline_date, c.course_id, c.course_name, c.color FROM coursedeadlines d JOIN usercourses c '
        'ON c.course_id = d.course_id WHERE c.id = %s AND d.is_completed = 0', (user_id,)) or []
    fill_display_colours(open_dls, user_id)
    out = []
    for ev in events:
        start = as_dt(ev['event_date'])
        if not start:
            continue
        dur = int(ev.get('duration_minutes') or 60)
        pending = ev.get('flag_status') == 'is_pending'
        kind = 'ai' if ev['is_ai_recommended'] else ('deadline' if (ev['event_name'], start) in deadline_names else 'event')
        course = course_for.get((ev['event_name'], start)) or ''
        dot = class_dot_for.get((ev['event_name'], start)) or ''
        label = ev['event_name']
        if kind == 'ai':
            course, label = _split_study_title(ev['event_name'])
            dot = dot_by_course.get(course) or ''
        out.append({
            'id': ev['event_id'], 'title': ev['event_name'], 'start': start.isoformat(),
            'end': (start + timedelta(minutes=dur)).isoformat(),
            'classNames': [f'ev-{kind}'] + (['ev-pending'] if pending else []),
            'extendedProps': {'kind': kind, 'pending': pending, 'when': start.strftime('%a %b %d, %I:%M %p'),
                              'classDot': dot, 'course': course, 'label': label,
                              'day': _day_label(start), 'range': _time_range(start, dur), 'minutes': dur,
                              'days': (start.date() - apptime.today_local()).days},
        })
    seen = {(ev['event_name'], as_dt(ev['event_date'])) for ev in events}
    for d in open_dls:
        start = as_dt(d['deadline_date'])
        if not start or (d['deadline_name'], start) in seen:
            continue
        out.append({
            'id': f"dl-{d['deadline_id']}", 'title': d['deadline_name'], 'start': start.isoformat(),
            'end': (start + timedelta(minutes=60)).isoformat(), 'classNames': ['ev-deadline'],
            'extendedProps': {'kind': 'deadline', 'pending': False, 'when': start.strftime('%a %b %d, %I:%M %p'),
                              'classDot': class_dot_colour(d.get('color')) or '', 'course': d.get('course_name') or '',
                              'color': d.get('color') or '', 'days': (start.date() - apptime.today_local()).days},
        })
    out.sort(key=lambda e: e['start'])
    return out


def _split_study_title(title):
    """'Study: CS 101 – Midterm' -> ('CS 101', 'Midterm'). Anything else -> ('', title)."""
    t = (title or '').strip()
    if t.lower().startswith('study:'):
        rest = t[6:].strip()
        for sep in (' – ', ' - ', ' — '):
            if sep in rest:
                c, d = rest.split(sep, 1)
                return c.strip(), d.strip()
        return rest, ''
    return '', t


def _fmt_clock(dt):
    return dt.strftime('%I:%M').lstrip('0')


def _time_range(start, minutes):
    end = start + timedelta(minutes=minutes)
    a, b = start.strftime('%p'), end.strftime('%p')
    return f"{_fmt_clock(start)}{'' if a == b else ' ' + a}–{_fmt_clock(end)} {b}"


def _day_label(dt):
    return dt.strftime('%a %b %d').replace(' 0', ' ')


def _group_pending(pending):
    """Pending study blocks grouped per class, in first-block order."""
    groups = {}
    for e in pending:
        x = e['extendedProps']
        g = groups.setdefault(x.get('course') or 'Other', {'course': x.get('course') or 'Other', 'dot': x.get('classDot') or '', 'items': []})
        g['items'].append(e)
    return list(groups.values())


# View calendar, add events manually, and input events automatically
@calendar_bp.route('/calendar', methods=['GET', 'POST'])
@login_required
def view_calendar():
    user_id = session['user_id']
    try:
        events = _load_events(user_id)
    except Exception:
        flash('Error Showing Calendar', 'danger')
        events = []
    pending = [e for e in events if e['extendedProps']['pending']]
    now_iso = apptime.now_local().isoformat()
    upcoming = sum(1 for e in events if e['extendedProps']['kind'] == 'deadline' and e['start'] >= now_iso)
    return render_template('calendar.html', events=events, pending=pending, pending_groups=_group_pending(pending),
                           upcoming_deadlines=upcoming, ai_ready=ai_available())


# For manual insertion of calendar events
@calendar_bp.route('/calendar/add_manual', methods=['POST'])
@login_required
def add_manual():
    event_name = (request.form.get('event_name') or '').strip()
    event_date = as_dt(request.form.get('event_date'))
    try:
        duration = max(5, min(24 * 60, int(request.form.get('duration_minutes') or 60)))
    except ValueError:
        duration = 60
    if not event_name or not event_date:
        flash('Please give the event a name and a valid date and time.', 'warning')
        return redirect(url_for('calendar_bp.view_calendar'))
    query('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, is_ai_recommended) '
          'VALUES (%s, %s, %s, %s, %s)', (session['user_id'], event_name[:255], event_date, duration, False), commit=True)
    flash(f'Added “{event_name}” to your calendar.', 'success')
    return redirect(url_for('calendar_bp.view_calendar'))


# Add calendar events by linking an .ics calendar link
@calendar_bp.route('/calendar/automatic_add', methods=['POST'])
@login_required
def automatic_add():
    ical_url = (request.form.get('calendar_url') or '').strip()
    user_id = session['user_id']
    if ical_url.startswith('webcal://'):
        ical_url = 'https://' + ical_url[len('webcal://'):]
    if not ical_url.startswith(('http://', 'https://')):
        flash('Unable to link calendar. Paste a full iCal (.ics) address.', 'danger')
        return redirect(url_for('calendar_bp.view_calendar'))
    try:
        response = requests.get(ical_url, timeout=10)
        if response.status_code != 200:
            flash('Unable to link calendar. Could not fetch that link.', 'danger')
            return redirect(url_for('calendar_bp.view_calendar'))
        cal = Calendar(response.text)
        existing = {(e['event_name'], as_dt(e['event_date'])) for e in query(
            'SELECT event_name, event_date FROM calendarevents WHERE user_id = %s', (user_id,))}
        conn = get_db_connection()
        cursor = conn.cursor()
        added = 0
        try:
            sql = ('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, is_ai_recommended) '
                   'VALUES (%s, %s, %s, %s, %s)')
            for event in sorted(cal.events, key=lambda e: e.begin)[:200]:
                start = event.begin.to('local').naive
                title = (event.name or 'Untitled Event')[:255]
                if (title, start.replace(microsecond=0)) in existing:
                    continue  # skip duplicates when re-syncing
                dur = int((event.end - event.begin).total_seconds() // 60) if event.end else 60
                cursor.execute(sql, (user_id, title, start, max(15, min(dur, 1440)), False))
                added += 1
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        flash(f'Calendar successfully synced! {added} new event(s) imported.', 'success')
    except Exception:
        flash('Unable to link calendar. Make sure it is a valid iCal link.', 'danger')
    return redirect(url_for('calendar_bp.view_calendar'))


def _local_plan(user_id, constraints):
    """Deterministic fallback planner: one study block for each of the next 3 deadlines,
    placed in the evening of a free day before it."""
    now = apptime.now_local()
    deadlines = query('SELECT c.course_name, d.deadline_name, d.deadline_date FROM usercourses c JOIN coursedeadlines d '
                      'ON c.course_id = d.course_id WHERE c.id = %s AND d.deadline_date > %s ORDER BY d.deadline_date '
                      'LIMIT 3', (user_id, now))
    busy = [(as_dt(e['event_date']), int(e.get('duration_minutes') or 60)) for e in query(
        'SELECT event_date, duration_minutes FROM calendarevents WHERE user_id = %s', (user_id,))]
    late = 'morning' in (constraints or '').lower()
    blocks = []
    for d in deadlines:
        due = as_dt(d['deadline_date'])
        for back in (2, 1, 3, 4):
            day = (due - timedelta(days=back)).date()
            for hour in ((9, 10, 11) if late else (18, 19, 16, 20)):
                slot = datetime(day.year, day.month, day.day, hour)
                if slot <= now:
                    continue
                clash = any(b and b < slot + timedelta(minutes=90) and slot < b + timedelta(minutes=m) for b, m in busy)
                if not clash:
                    blocks.append((f"Study: {d['course_name']} – {d['deadline_name']}", slot))
                    busy.append((slot, 90))
                    break
            else:
                continue
            break
    return blocks


# Prompt AI to recommend study sessions; insert as pending purple events
@calendar_bp.route('/calendar/ai_reccomended_schedule', methods=['POST'])
@login_required
def ai_recomended_schedule():
    user_id = session['user_id']
    constraints_input = request.form.get('user_constraints') or 'N/A'
    blocks, source = [], 'AI'
    if ai_available():
        events = query('SELECT event_name, event_date FROM calendarevents WHERE user_id = %s AND event_date >= %s',
                       (user_id, apptime.now_utc_naive()))
        deadlines = query('SELECT c.course_name, d.deadline_name, d.deadline_date FROM usercourses c JOIN coursedeadlines d '
                          'ON c.course_id = d.course_id WHERE c.id = %s', (user_id,))
        prompt = f"""You are an automated backend data parsing engine. Today is {apptime.now_local():%Y-%m-%d %H:%M}.
Student Schedule: {[(e['event_name'], str(e['event_date'])) for e in events]}
Course Deadlines: {[(d['course_name'], d['deadline_name'], str(d['deadline_date'])) for d in deadlines]}
User Scheduling Restrictions: {constraints_input}
Generate exactly 3 future study blocks that do not overlap existing events.
Output ONLY lines formatted exactly like:
Study for Math Exam|2026-10-20 15:30:00"""
        try:
            for line in ai_chat([{'role': 'user', 'content': prompt}]).splitlines():
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 2 and as_dt(parts[1]):
                    blocks.append((parts[0][:255], as_dt(parts[1])))
        except Exception:
            flash('AI Service is temporarily unavailable, so Prody used its built-in planner instead.', 'info')
    if not blocks:
        source = 'Smart planner'
        blocks = _local_plan(user_id, constraints_input)
    if not blocks:
        flash('No upcoming deadlines to plan around yet. Add a course deadline first.', 'warning')
        return redirect(url_for('calendar_bp.view_calendar'))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for name, when in blocks[:5]:
            cursor.execute('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, '
                           'is_ai_recommended, flag_status) VALUES (%s, %s, %s, %s, %s, %s)',
                           (user_id, name, when, 90, True, 'is_pending'))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    session['review_mode_active'] = True
    flash(f'{source} suggested {len(blocks[:5])} study blocks. They are shown in purple — keep or reject them.', 'success')
    return redirect(url_for('calendar_bp.view_calendar'))


@calendar_bp.route('/ai_accept', methods=['POST'])
@calendar_bp.route('/ai_accept/<int:event_id>', methods=['POST'])
@login_required
def accept_route(event_id=None):
    sql = "UPDATE calendarevents SET flag_status='confirmed' WHERE user_id = %s AND flag_status = 'is_pending'"
    params = (session['user_id'],)
    if event_id:
        sql += ' AND event_id = %s'
        params += (event_id,)
    query(sql, params, commit=True)
    if not event_id:
        session.pop('review_mode_active', None)
    flash('AI recommendations successfully saved to your active schedule!' if not event_id else 'Study block kept.', 'success')
    return redirect(url_for('calendar_bp.view_calendar'))


@calendar_bp.route('/ai_reject', methods=['POST'])
@calendar_bp.route('/ai_reject/<int:event_id>', methods=['POST'])
@login_required
def reject_route(event_id=None):
    sql = "DELETE FROM calendarevents WHERE flag_status='is_pending' AND user_id = %s"
    params = (session['user_id'],)
    if event_id:
        sql += ' AND event_id = %s'
        params += (event_id,)
    query(sql, params, commit=True)
    if not event_id:
        session.pop('review_mode_active', None)
    flash('AI study schedule pitch discarded.' if not event_id else 'Study block rejected.', 'info')
    return redirect(url_for('calendar_bp.view_calendar'))


@calendar_bp.route('/calendar/delete/<int:record_id>', methods=['POST'])
@login_required
def delete_event_endpoint(record_id):
    try:
        # Delete exactly one row, verifying it belongs to the signed-in user
        query('DELETE FROM calendarevents WHERE event_id = %s AND user_id = %s', (record_id, session['user_id']), commit=True)
        flash('Event successfully removed from your schedule.', 'success')
    except Exception:
        flash('Event could not be removed from your schedule.', 'danger')
    return redirect(url_for('calendar_bp.view_calendar'))
