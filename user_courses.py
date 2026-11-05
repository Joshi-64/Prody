import apptime
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import IntegrityError, get_db_connection
from helpers import COURSE_COLORS, SUBJECTS, _clear_stats_cache, as_dt, login_required, query

def fill_null_slots(cursor, user_id):
    """Save the lowest free slot 0..7 for each NULL-slot class, oldest course_id first (same order as init_db).
    Idempotent: only touches rows still NULL; a slot taken concurrently (unique index) leaves that row NULL."""
    cursor.execute('SELECT course_id, branch_slot FROM usercourses WHERE id = %s ORDER BY course_id', (user_id,))
    rows = [(r['course_id'], r['branch_slot']) if isinstance(r, dict) else (r[0], r[1]) for r in cursor.fetchall()]
    used = {s for _, s in rows if s is not None}
    n = 0
    for cid, s in rows:
        if s is not None:
            continue
        free = next((i for i in range(8) if i not in used), None)
        if free is None:
            break
        try:
            cursor.execute('UPDATE usercourses SET branch_slot = %s WHERE course_id = %s AND branch_slot IS NULL', (free, cid))
            used.add(free); n += 1
        except IntegrityError:
            break
    return n


def save_null_slots(user_id):
    """fill_null_slots in its own connection + commit."""
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        n = fill_null_slots(cur, user_id)
        if n:
            conn.commit()
        return n
    finally:
        cur.close(); conn.close()


def add_course(user_id, cols, vals):
    """Insert one class with a branch slot (fills older NULL slots first) and commit. For scripts/seeds."""
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cid = _insert_course(cur, user_id, cols, vals)
        conn.commit()
        _clear_stats_cache()
        return cid
    finally:
        cur.close(); conn.close()


def next_branch_slot(cursor, user_id):
    """Lowest free tree branch slot 0..7 for this user, or None when all 8 are taken (overflow).
    Older NULL-slot classes are saved first so a new class never takes the slot they are drawn on."""
    fill_null_slots(cursor, user_id)
    cursor.execute('SELECT branch_slot FROM usercourses WHERE id = %s AND branch_slot IS NOT NULL', (user_id,))
    used = {(r['branch_slot'] if isinstance(r, dict) else r[0]) for r in cursor.fetchall()}
    return next((i for i in range(8) if i not in used), None)


def _insert_course(cursor, user_id, cols, vals):
    """INSERT into usercourses with branch_slot; falls back to NULL if a concurrent insert took the slot."""
    cols, vals = tuple(cols), tuple(vals)
    # r8/r9: a class created with no colour gets the next unused palette colour, per user,
    # read on the same cursor so several inserts in one transaction still get distinct colours
    ci = cols.index('color') if 'color' in cols else -1
    if ci < 0 or not vals[ci]:  # r9: an explicit colour (even the default) is never overridden
        colour = _next_color_cur(cursor, user_id)
        if ci < 0:
            cols, vals = cols + ('color',), vals + (colour,)
        else:
            vals = vals[:ci] + (colour,) + vals[ci + 1:]
    sql = f"INSERT INTO usercourses (id, {', '.join(cols)}, branch_slot) VALUES ({', '.join(['%s'] * (len(cols) + 2))})"
    try:
        cursor.execute(sql, (user_id, *vals, next_branch_slot(cursor, user_id)))
    except IntegrityError:
        cursor.execute(sql, (user_id, *vals, None))
    return cursor.lastrowid


# Create the blueprint object for user_courses functionality
user_courses_bp = Blueprint('user_courses_bp', __name__)


def _courses_with_deadlines(user_id):
    courses = query('SELECT * FROM usercourses WHERE id = %s ORDER BY course_name', (user_id,))
    deadlines = query('SELECT d.* FROM coursedeadlines d JOIN usercourses c ON c.course_id = d.course_id '
                      'WHERE c.id = %s ORDER BY d.deadline_date', (user_id,))
    now = apptime.now_local()
    for c in courses:
        c['deadlines'] = [d for d in deadlines if d['course_id'] == c['course_id']]
        c['upcoming'] = sum(1 for d in c['deadlines'] if not d['is_completed'] and as_dt(d['deadline_date']) >= now)
    return courses


# Let users add courses manually ("My Classes")
@user_courses_bp.route('/add_courses', methods=['GET', 'POST'])
@login_required
def add_courses():
    user_id = session['user_id']
    if request.method == 'POST':
        course_name = (request.form.get('course_name') or '').strip()
        subject = request.form.get('subject') or ''
        code = (request.form.get('course_code') or '').strip()[:100]
        if not course_name:
            flash('Please enter a course name.', 'warning')
        elif subject and subject not in SUBJECTS:
            flash('Please choose a subject from the list.', 'warning')
        else:
            try:
                if query('SELECT course_id FROM usercourses WHERE id = %s AND course_name = %s',
                         (user_id, course_name), one=True):
                    flash('You are already tracking this course!', 'warning')
                else:
                    n = len(query('SELECT course_id FROM usercourses WHERE id = %s', (user_id,)))
                    conn = get_db_connection()
                    cur = conn.cursor(dictionary=True)
                    try:
                        _insert_course(cur, user_id, ('course_name', 'course_code', 'subject', 'color'),
                                       (course_name[:255], code, subject or 'Other', _next_color(user_id, n)))
                        conn.commit()
                        _clear_stats_cache()
                    finally:
                        cur.close()
                        conn.close()
                    flash(f'Successfully added course: {course_name}', 'success')
            except Exception:
                flash('Error adding Course', 'danger')
        return redirect(url_for('user_courses_bp.add_courses'))
    return render_template('courses_and_deadlines.html', user_courses=_courses_with_deadlines(user_id),
                           subjects=SUBJECTS, now=apptime.now_local())


# Add course deadlines per course. If course not already in database, add to usercourses
@user_courses_bp.route('/add_course_deadlines', methods=['GET', 'POST'])
@login_required
def add_course_deadlines():
    user_id = session['user_id']
    if request.method != 'POST':  # only validate submissions; a direct visit just shows the Classes page
        return redirect(url_for('user_courses_bp.add_courses'))
    course_name = (request.form.get('course_name') or '').strip()
    deadline_name = (request.form.get('deadline_name') or '').strip()
    raw_date = request.form.get('deadline_date')
    deadline_date = as_dt(raw_date)
    if not (course_name and deadline_name and raw_date):
        flash('Please fill in the course, assignment name, and deadline.', 'warning')
        return redirect(url_for('user_courses_bp.add_courses'))
    if not deadline_date:
        flash('That deadline is not a valid date.', 'danger')
        return redirect(url_for('user_courses_bp.add_courses'))
    if deadline_date < apptime.now_local():
        flash('That deadline is in the past. Please pick a future date.', 'danger')
        return redirect(url_for('user_courses_bp.add_courses'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT course_id FROM usercourses WHERE id = %s AND course_name = %s', (user_id, course_name))
        course_row = cursor.fetchone()
        if course_row:
            course_id = course_row['course_id']
        else:
            course_id = _insert_course(cursor, user_id, ('course_name', 'subject'), (course_name, 'Other'))
        cursor.execute('INSERT INTO coursedeadlines (course_id, deadline_name, deadline_date) VALUES (%s, %s, %s)',
                       (course_id, deadline_name[:255], deadline_date))
        new_deadline_id = cursor.lastrowid
        # mirror into the calendar, tagged with its source deadline so deletes never touch manual events
        cursor.execute('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, is_ai_recommended, '
                       'source_deadline_id) VALUES (%s, %s, %s, %s, %s, %s)',
                       (user_id, deadline_name[:255], deadline_date, 30, False, new_deadline_id))
        conn.commit()
        flash(f'Deadline tracked successfully for {course_name}!', 'success')
    except Exception:
        conn.rollback()
        flash('Error adding course deadline', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('user_courses_bp.add_courses'))


def _delete_mirror(cur, user_id, d):
    """Delete the calendar row mirrored from deadline d. Tagged rows go by source_deadline_id; legacy untagged
    rows (created before the column existed) fall back to ONE untagged 30-min row with the same name and date,
    so a manual event that shares the name is never removed when a tagged mirror exists."""
    run = (lambda sql, p: cur.execute(sql, p)) if cur else (lambda sql, p: query(sql, p, commit=True))
    get = ((lambda sql, p: (cur.execute(sql, p), cur.fetchone())[1]) if cur else (lambda sql, p: query(sql, p, one=True)))
    if get('SELECT event_id FROM calendarevents WHERE user_id = %s AND source_deadline_id = %s', (user_id, d['deadline_id'])):
        run('DELETE FROM calendarevents WHERE user_id = %s AND source_deadline_id = %s', (user_id, d['deadline_id']))
        return
    # TODO: remove this name-match fallback once scripts/backfill_source_deadline_id.py has run --apply on the real DB.
    row = get('SELECT event_id FROM calendarevents WHERE user_id = %s AND source_deadline_id IS NULL AND event_name = %s '
              'AND event_date = %s AND duration_minutes = 30 ORDER BY event_id LIMIT 1',
              (user_id, d['deadline_name'], d['deadline_date']))
    if row:
        run('DELETE FROM calendarevents WHERE event_id = %s', (row['event_id'],))


def _owned_deadline(deadline_id, user_id):
    return query('SELECT d.* FROM coursedeadlines d JOIN usercourses c ON c.course_id = d.course_id '
                 'WHERE d.deadline_id = %s AND c.id = %s', (deadline_id, user_id), one=True)


def _next_color_cur(cursor, user_id):
    """Next palette colour (in order) this user isn't using yet, read through the caller's cursor; cycles by count."""
    cursor.execute('SELECT color FROM usercourses WHERE id = %s', (user_id,))
    rows = cursor.fetchall() or []
    used = [((r['color'] if isinstance(r, dict) else r[0]) or '').upper() for r in rows]
    return next((c for c in COURSE_COLORS if c.upper() not in used), COURSE_COLORS[len(used) % len(COURSE_COLORS)])


def _next_color(user_id, n):
    """First palette colour this user isn't using yet (distinct branch flowers); cycles once all 8 are taken."""
    used = {(r.get('color') or '').upper() for r in (query('SELECT color FROM usercourses WHERE id = %s', (user_id,)) or [])}
    return next((c for c in COURSE_COLORS if c.upper() not in used), COURSE_COLORS[n % len(COURSE_COLORS)])


@user_courses_bp.route('/deadlines/<int:deadline_id>/toggle', methods=['POST'])
@login_required
def toggle_deadline(deadline_id):
    d = _owned_deadline(deadline_id, session['user_id'])
    if d:
        done = not d['is_completed']
        query('UPDATE coursedeadlines SET is_completed = %s, completed_at = %s WHERE deadline_id = %s',
              (done, apptime.now_utc_naive() if done else None, deadline_id), commit=True)
    return redirect(url_for('user_courses_bp.add_courses'))


@user_courses_bp.route('/deadlines/<int:deadline_id>/delete', methods=['POST'])
@login_required
def delete_deadline(deadline_id):
    d = _owned_deadline(deadline_id, session['user_id'])
    if d:
        query('DELETE FROM coursedeadlines WHERE deadline_id = %s', (deadline_id,), commit=True)
        _delete_mirror(None, session['user_id'], d)
        flash('Deadline removed.', 'info')
    return redirect(url_for('user_courses_bp.add_courses'))


@user_courses_bp.route('/courses/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    uid = session['user_id']
    if query('SELECT course_id FROM usercourses WHERE course_id = %s AND id = %s', (course_id, uid), one=True):
        # One transaction: delete the class and hand its freed branch_slot to the earliest overflow class.
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute('SELECT branch_slot FROM usercourses WHERE course_id = %s AND id = %s', (course_id, uid))
            freed = cur.fetchone()['branch_slot']
            cur.execute('SELECT deadline_id, deadline_name, deadline_date FROM coursedeadlines WHERE course_id = %s', (course_id,))
            for d in cur.fetchall():
                _delete_mirror(cur, uid, d)
            cur.execute('DELETE FROM coursedeadlines WHERE course_id = %s', (course_id,))
            cur.execute('DELETE FROM courseconcepts WHERE course_id = %s', (course_id,))
            cur.execute('DELETE FROM grades WHERE course_id = %s AND user_id = %s', (course_id, uid))
            cur.execute('DELETE FROM usercourses WHERE course_id = %s AND id = %s', (course_id, uid))
            if freed is not None:
                cur.execute('SELECT course_id FROM usercourses WHERE id = %s AND branch_slot IS NULL '
                            'ORDER BY course_id LIMIT 1', (uid,))
                nxt = cur.fetchone()
                if nxt:
                    cur.execute('UPDATE usercourses SET branch_slot = %s WHERE course_id = %s AND branch_slot IS NULL',
                                (freed, nxt['course_id']))
            conn.commit()
            _clear_stats_cache()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
        flash('Course removed.', 'info')
    return redirect(url_for('user_courses_bp.add_courses'))


# --- roots card API (Functionality): JSON for Mark done / Edit on the roots map ---
@user_courses_bp.route('/api/deadlines/<int:deadline_id>/done', methods=['POST'])
@login_required
def api_deadline_done(deadline_id):
    from flask import jsonify
    d = _owned_deadline(deadline_id, session['user_id'])
    if not d:
        return jsonify(ok=False, error='not found'), 404
    data = request.get_json(silent=True) or request.form
    done = data.get('done', True)
    if not isinstance(done, bool):
        sv = str(done).strip().lower()
        if sv in ('1', 'true', 'yes'):
            done = True
        elif sv in ('0', 'false', 'no'):
            done = False
        else:
            return jsonify(ok=False, error='done must be true or false'), 400
    # idempotent "done": keep the first completion time; un-done clears it
    query('UPDATE coursedeadlines SET is_completed = %s, '
          'completed_at = CASE WHEN %s = 1 THEN COALESCE(completed_at, %s) ELSE NULL END WHERE deadline_id = %s',
          (1 if done else 0, 1 if done else 0, apptime.now_utc_naive(), deadline_id), commit=True)
    return jsonify(ok=True, id=deadline_id, is_completed=done)


@user_courses_bp.route('/api/deadlines/<int:deadline_id>', methods=['POST', 'PATCH'])
@login_required
def api_deadline_edit(deadline_id):
    from flask import jsonify
    from datetime import date
    d = _owned_deadline(deadline_id, session['user_id'])
    if not d:
        return jsonify(ok=False, error='not found'), 404
    data = request.get_json(silent=True) or request.form
    name = (data.get('name') or d['deadline_name'] or '').strip()[:100]
    due = (data.get('date') or str(d['deadline_date'])[:10]).strip()
    try:
        date.fromisoformat(due)
    except ValueError:
        return jsonify(ok=False, error='date must be YYYY-MM-DD'), 400
    if not name:
        return jsonify(ok=False, error='name required'), 400
    old_time = str(d['deadline_date'])[11:19] or '23:59:00'
    due_full = f'{due} {old_time}'
    query('UPDATE coursedeadlines SET deadline_name = %s, deadline_date = %s WHERE deadline_id = %s',
          (name, due_full, deadline_id), commit=True)
    if query('SELECT event_id FROM calendarevents WHERE user_id = %s AND source_deadline_id = %s',
             (session['user_id'], deadline_id), one=True):
        query('UPDATE calendarevents SET event_name = %s, event_date = %s WHERE user_id = %s AND source_deadline_id = %s',
              (name, due_full, session['user_id'], deadline_id), commit=True)
    else:  # legacy mirror row (no source id): match one untagged row by old name/date
        # TODO: remove this fallback once scripts/backfill_source_deadline_id.py has run --apply on the real DB.
        query('UPDATE calendarevents SET event_name = %s, event_date = %s, source_deadline_id = %s WHERE event_id = ('
              'SELECT event_id FROM (SELECT event_id FROM calendarevents WHERE user_id = %s AND source_deadline_id IS NULL '
              'AND event_name = %s AND event_date = %s AND duration_minutes = 30 ORDER BY event_id LIMIT 1) t)',
              (name, due_full, deadline_id, session['user_id'], d['deadline_name'], d['deadline_date']), commit=True)
    return jsonify(ok=True, id=deadline_id, name=name, date=due)


def _owned_course(course_id, user_id):
    return query('SELECT * FROM usercourses WHERE course_id = %s AND id = %s', (course_id, user_id), one=True)


@user_courses_bp.route('/courses/<int:course_id>/concepts', methods=['GET', 'POST'])
@login_required
def course_concepts(course_id):
    """Per-course concept checklist: add / rename / delete / toggle Mastered|Review."""
    uid = session['user_id']
    course = _owned_course(course_id, uid)
    if not course:
        flash('Class not found.', 'warning')
        return redirect(url_for('user_courses_bp.add_courses'))
    if request.method == 'POST':
        action = (request.form.get('action') or 'add').strip()
        if action == 'add':
            name = (request.form.get('name') or '').strip()[:255]
            if not name:
                flash('Enter a concept name.', 'warning')
            else:
                query('INSERT INTO courseconcepts (course_id, name, status) VALUES (%s, %s, %s)',
                      (course_id, name, 'Review'), commit=True)
                flash(f'Added “{name}”.', 'success')
        elif action == 'rename':
            cid = request.form.get('concept_id', type=int)
            name = (request.form.get('name') or '').strip()[:255]
            row = query('SELECT concept_id FROM courseconcepts WHERE concept_id = %s AND course_id = %s',
                        (cid, course_id), one=True) if cid else None
            if not row or not name:
                flash('Could not rename that concept.', 'warning')
            else:
                query('UPDATE courseconcepts SET name = %s WHERE concept_id = %s', (name, cid), commit=True)
                flash('Concept renamed.', 'success')
        elif action == 'delete':
            cid = request.form.get('concept_id', type=int)
            query('DELETE FROM courseconcepts WHERE concept_id = %s AND course_id = %s', (cid, course_id), commit=True)
            flash('Concept removed.', 'info')
        elif action == 'toggle':
            cid = request.form.get('concept_id', type=int)
            row = query('SELECT status FROM courseconcepts WHERE concept_id = %s AND course_id = %s',
                        (cid, course_id), one=True) if cid else None
            if row:
                nxt = 'Review' if row['status'] == 'Mastered' else 'Mastered'
                query('UPDATE courseconcepts SET status = %s WHERE concept_id = %s', (nxt, cid), commit=True)
        return redirect(url_for('user_courses_bp.course_concepts', course_id=course_id))
    concepts = query('SELECT * FROM courseconcepts WHERE course_id = %s ORDER BY concept_id', (course_id,))
    mastered = sum(1 for c in concepts if c['status'] == 'Mastered')
    filt = (request.args.get('filter') or 'review').lower()
    if filt not in ('mastered', 'review'):
        filt = 'review'
    return render_template('concepts.html', course=course, concepts=concepts,
                           mastered=mastered, total=len(concepts), filter=filt)


import re as _re
from datetime import date as _date

_SYLLABUS_KIND = _re.compile(r'\b(exam|midterm|final|quiz|assignment|homework|hw|project|paper|due|deadline)\b', _re.I)
_SYLLABUS_DATE = _re.compile(
    r'(?:'
    r'(?P<mdy>\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)'
    r'|(?P<iso>\b\d{4}-\d{2}-\d{2}\b)'
    r'|(?P<us>\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b)'
    r')',
    _re.I,
)
_MONTHS = {
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
    'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
    'august': 8, 'aug': 8, 'september': 9, 'sept': 9, 'sep': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12,
}


def _parse_syllabus_date(raw, default_year=None):
    raw = (raw or '').strip()
    default_year = default_year or apptime.today_local().year
    try:
        if _re.match(r'\d{4}-\d{2}-\d{2}$', raw):
            return _date.fromisoformat(raw)
        m = _re.match(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$', raw)
        if m:
            mo, d, y = int(m.group(1)), int(m.group(2)), m.group(3)
            y = int(y) if y else default_year
            if y < 100:
                y += 2000
            return _date(y, mo, d)
        m = _re.match(r'([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?', raw)
        if m:
            mon = _MONTHS.get(m.group(1).lower())
            d = int(m.group(2))
            y = int(m.group(3)) if m.group(3) else default_year
            if mon:
                return _date(y, mon, d)
    except ValueError:
        return None
    return None


def extract_syllabus_items(text):
    """Find dated exam/quiz/assignment lines. Returns [{name, date, line}]."""
    items, seen = [], set()
    year = apptime.today_local().year
    for line in (text or '').splitlines():
        line = line.strip()
        if not line or not _SYLLABUS_KIND.search(line):
            continue
        dm = _SYLLABUS_DATE.search(line)
        if not dm:
            continue
        raw = next(g for g in dm.groups() if g)
        dt = _parse_syllabus_date(raw, year)
        if not dt:
            continue
        name = _SYLLABUS_DATE.sub('', line)
        name = _re.sub(r'\s{2,}', ' ', name).strip(' -\t:,.')
        if len(name) < 3:
            name = line[:80]
        key = (name.lower(), dt.isoformat())
        if key in seen:
            continue
        seen.add(key)
        items.append({'name': name[:255], 'date': dt.isoformat(), 'line': line[:200]})
    return items[:40]


def _read_upload_text(f):
    filename = (f.filename or '').lower()
    data = f.read()
    if filename.endswith('.txt') or (f.mimetype or '').startswith('text/'):
        return data.decode('utf-8', errors='replace')
    if filename.endswith('.pdf') or (f.mimetype or '') == 'application/pdf':
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(data))
            return '\n'.join((p.extract_text() or '') for p in reader.pages)
        except Exception:
            raise RuntimeError('Could not read that PDF. Try a .txt syllabus.')
    raise RuntimeError('Please upload a PDF or .txt file.')


@user_courses_bp.route('/courses/<int:course_id>/syllabus', methods=['GET', 'POST'])
@login_required
def syllabus_import(course_id):
    uid = session['user_id']
    course = _owned_course(course_id, uid)
    if not course:
        flash('Class not found.', 'warning')
        return redirect(url_for('user_courses_bp.add_courses'))
    items = session.get('syllabus_preview')
    if request.method == 'POST':
        action = (request.form.get('action') or 'upload').strip()
        if action == 'upload':
            f = request.files.get('syllabus')
            if not f or not f.filename:
                flash('Choose a PDF or .txt syllabus.', 'warning')
                return redirect(url_for('user_courses_bp.syllabus_import', course_id=course_id))
            try:
                text = _read_upload_text(f)
            except RuntimeError as e:
                flash(str(e), 'danger')
                return redirect(url_for('user_courses_bp.syllabus_import', course_id=course_id))
            found = extract_syllabus_items(text)
            if not found:
                flash('No dated exams, quizzes, or assignments found in that file.', 'warning')
                return redirect(url_for('user_courses_bp.syllabus_import', course_id=course_id))
            session['syllabus_preview'] = {'course_id': course_id, 'items': found}
            return redirect(url_for('user_courses_bp.syllabus_import', course_id=course_id))
        if action == 'commit':
            preview = session.get('syllabus_preview') or {}
            if preview.get('course_id') != course_id:
                flash('Upload the syllabus again.', 'warning')
                return redirect(url_for('user_courses_bp.syllabus_import', course_id=course_id))
            n = 0
            for idx in request.form.getlist('pick'):
                try:
                    it = preview['items'][int(idx)]
                except (IndexError, ValueError, KeyError, TypeError):
                    continue
                due = f"{it['date']} 23:59:00"
                query('INSERT INTO coursedeadlines (course_id, deadline_name, deadline_date) VALUES (%s, %s, %s)',
                      (course_id, it['name'], due), commit=True)
                n += 1
            session.pop('syllabus_preview', None)
            flash(f'Added {n} deadline{"s" if n != 1 else ""} from the syllabus.', 'success' if n else 'info')
            return redirect(url_for('user_courses_bp.add_courses'))
    preview_items = None
    if items and items.get('course_id') == course_id:
        preview_items = items.get('items')
    return render_template('syllabus_import.html', course=course, items=preview_items)
