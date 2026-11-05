"""Grade tracker with weighted averages (Use Case: Grade Calculator)."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import get_db_connection
from helpers import _clear_stats_cache, ai_available, ai_chat, login_required, query

grades_bp = Blueprint('grades_bp', __name__)

LETTERS = [(93, 'A'), (90, 'A-'), (87, 'B+'), (83, 'B'), (80, 'B-'), (77, 'C+'), (73, 'C'), (70, 'C-'), (60, 'D'), (0, 'F')]


def letter(avg):
    return next(l for cut, l in LETTERS if avg >= cut) if avg is not None else '—'


@grades_bp.route('/grades', methods=['GET', 'POST'])
@login_required
def grades():
    uid = session['user_id']
    courses = query('SELECT * FROM usercourses WHERE id = %s ORDER BY course_name', (uid,))
    if request.method == 'POST':
        course_id = request.form.get('course_id')
        name = (request.form.get('item_name') or '').strip()
        category = (request.form.get('category') or 'Assignment').strip()[:100]
        if not courses:
            flash("It looks like you haven't added any classes yet. Add one in My Classes first.", 'warning')
            return redirect(url_for('grades_bp.grades'))
        if not name:
            flash("It looks like you haven't added any assignments yet. Enter an assignment name first.", 'warning')
            return redirect(url_for('grades_bp.grades'))
        try:
            score = float(request.form.get('score', ''))
            weight = float(request.form.get('weight', ''))
            if not (0 <= score <= 100 and 0 < weight <= 100):
                raise ValueError
        except ValueError:
            flash('invalid input, please put in a percentage.', 'danger')
            return redirect(url_for('grades_bp.grades'))
        if not any(str(c['course_id']) == str(course_id) for c in courses):
            flash('Please choose one of your classes.', 'warning')
            return redirect(url_for('grades_bp.grades'))
        # Optional "Which deadline is this for?" link, by id only (no name matching).
        # The link lives on coursedeadlines.grade_id; one deadline links at most one grade,
        # so only that user's, that class's, still-unlinked deadlines are accepted.
        deadline_id = (request.form.get('deadline_id') or '').strip()
        if deadline_id:
            if not deadline_id.isdigit():
                flash('Please choose one of the deadlines for that class.', 'warning')
                return redirect(url_for('grades_bp.grades'))
            ok = query('SELECT d.deadline_id FROM coursedeadlines d JOIN usercourses c ON c.course_id = d.course_id '
                       'WHERE d.deadline_id = %s AND d.course_id = %s AND c.id = %s AND d.grade_id IS NULL',
                       (int(deadline_id), course_id, uid), one=True)
            if not ok:
                flash('That deadline is not in this class or already has a grade.', 'warning')
                return redirect(url_for('grades_bp.grades'))
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute('INSERT INTO grades (user_id, course_id, item_name, category, score, weight) VALUES (%s, %s, %s, %s, %s, %s)',
                        (uid, course_id, name[:255], category, score, weight))
            gid = cur.lastrowid
            if deadline_id:
                cur.execute('UPDATE coursedeadlines SET grade_id = %s WHERE deadline_id = %s AND course_id = %s AND grade_id IS NULL',
                            (gid, int(deadline_id), course_id))
                if cur.rowcount != 1:  # linked by someone else in between
                    conn.rollback()
                    flash('That deadline already has a grade.', 'warning')
                    return redirect(url_for('grades_bp.grades'))
            conn.commit()
            _clear_stats_cache()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
        flash(f'Saved {name}: {score:g}%', 'success')
        return redirect(url_for('grades_bp.grades'))

    rows = query('SELECT * FROM grades WHERE user_id = %s ORDER BY grade_id', (uid,))
    summary, wsum, gpa_n = [], 0, 0
    for c in courses:
        items = [r for r in rows if r['course_id'] == c['course_id']]
        tw = sum(float(i['weight']) for i in items)
        avg = round(sum(float(i['score']) * float(i['weight']) for i in items) / tw, 1) if tw else None
        summary.append({'course': c, 'rows': items, 'avg': avg, 'letter': letter(avg), 'weight_used': round(tw, 1)})
        if avg is not None:
            wsum += avg
            gpa_n += 1
    overall = round(wsum / gpa_n, 1) if gpa_n else None
    open_deadlines = query('SELECT d.deadline_id, d.course_id, d.deadline_name, d.deadline_date FROM coursedeadlines d '
                           'JOIN usercourses c ON c.course_id = d.course_id WHERE c.id = %s AND d.grade_id IS NULL '
                           'ORDER BY d.deadline_date', (uid,))
    analysis = session.pop('grade_analysis', None)
    return render_template('grades.html', summary=summary, courses=courses, overall=overall, overall_letter=letter(overall),
                           open_deadlines=open_deadlines, analysis=analysis)


@grades_bp.route('/grades/delete/<int:grade_id>', methods=['POST'])
@login_required
def delete_grade(grade_id):
    if query('SELECT grade_id FROM grades WHERE grade_id = %s AND user_id = %s', (grade_id, session['user_id']), one=True):
        query('UPDATE coursedeadlines SET grade_id = NULL WHERE grade_id = %s', (grade_id,), commit=True)
    query('DELETE FROM grades WHERE grade_id = %s AND user_id = %s', (grade_id, session['user_id']), commit=True)
    flash('Grade removed.', 'info')
    return redirect(url_for('grades_bp.grades'))


def _course_averages(uid):
    courses = query('SELECT * FROM usercourses WHERE id = %s ORDER BY course_name', (uid,))
    rows = query('SELECT * FROM grades WHERE user_id = %s', (uid,))
    out = []
    for c in courses:
        items = [r for r in rows if r['course_id'] == c['course_id']]
        tw = sum(float(i['weight']) for i in items)
        avg = round(sum(float(i['score']) * float(i['weight']) for i in items) / tw, 1) if tw else None
        out.append({'name': c['course_name'], 'avg': avg, 'letter': letter(avg), 'n': len(items)})
    return out


def _fallback_analysis(avgs):
    scored = [a for a in avgs if a['avg'] is not None]
    if not scored:
        return ("No grades logged yet. Add a few scores with their syllabus weights, then ask again — "
                "I'll point out the classes that need the most attention.")
    scored.sort(key=lambda a: a['avg'])
    low = scored[:2]
    bits = [f"{a['name']} is at {a['avg']}% ({a['letter']})" for a in low]
    focus = ', '.join(a['name'] for a in low)
    return ("Here's a quick read without AI: " + '; '.join(bits) +
            f". Focus study time on {focus} first — review concepts there and log any missing weighted items.")


@grades_bp.route('/grades/analyze', methods=['POST'])
@login_required
def analyze_grades():
    uid = session['user_id']
    avgs = _course_averages(uid)
    lines = [f"{a['name']}: {a['avg']}% ({a['letter']})" if a['avg'] is not None else f"{a['name']}: no scores yet"
             for a in avgs]
    text = None
    if ai_available() and any(a['avg'] is not None for a in avgs):
        try:
            text = ai_chat([
                {'role': 'system', 'content': (
                    'You are Prody, a concise study coach. Given weighted course averages, write 3-5 short '
                    'sentences: overall picture, weakest classes, and concrete study areas to prioritize. '
                    'No markdown headers, no bullet spam — warm prose.')},
                {'role': 'user', 'content': 'My current averages:\n' + '\n'.join(lines)},
            ], timeout=30)
        except Exception:
            text = None
    if not text:
        text = _fallback_analysis(avgs)
    session['grade_analysis'] = text
    return redirect(url_for('grades_bp.grades') + '#grade-analysis')
