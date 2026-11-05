import apptime
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from helpers import as_dt, login_required, fill_display_colours, query

tasks_bp = Blueprint('tasks_bp', __name__)


@tasks_bp.route('/tasks', methods=['GET', 'POST'])
@login_required
def manage_tasks():
    user_id = session['user_id']
    if request.method == 'POST':
        task_name = (request.form.get('task_name') or '').strip()
        due_date = request.form.get('due_date') or None
        category = 'concept' if request.form.get('category') == 'concept' else 'task'
        course_id = request.form.get('course_id') or None
        owned = {str(c['course_id']) for c in query('SELECT course_id FROM usercourses WHERE id = %s', (user_id,))}
        if course_id is not None and str(course_id) not in owned:
            course_id = None
        if due_date:  # critic-3: only a real YYYY-MM-DD date counts
            try:
                due_date = datetime.strptime(due_date, '%Y-%m-%d').date().isoformat()
            except ValueError:
                due_date = None
        if not task_name:
            flash('Please enter a task or concept.', 'warning')
        elif len(task_name) > 255:
            flash('Task names must be 255 characters or fewer.', 'warning')
        elif category == 'task' and not owned:
            flash('Add your first class before adding a task.', 'warning')
        elif category == 'task' and not course_id:
            flash('Pick a class for this task.', 'warning')
        else:
            query('INSERT INTO todolist (user_id, task_name, due_date, category, course_id, progress) '
                  'VALUES (%s, %s, %s, %s, %s, %s)', (user_id, task_name, due_date, category, course_id, 0), commit=True)
            flash('Task added successfully!' if category == 'task' else 'Concept added to your tracker!', 'success')
            if category == 'task' and not due_date:
                flash('Add a due date? It helps Prody plan around it.', 'info')
        return redirect(url_for('tasks_bp.manage_tasks'))

    tasks = query('SELECT t.*, c.course_name, c.color FROM todolist t LEFT JOIN usercourses c ON c.course_id = t.course_id '
                  'WHERE t.user_id = %s ORDER BY t.is_completed ASC, t.due_date IS NULL, t.due_date ASC', (user_id,))
    fill_display_colours(tasks, user_id)
    today = apptime.today_local()
    for t in tasks:  # caltodo v1: days until due, for grouped sections
        d = as_dt(t.get('due_date'))
        t['due_days'] = (d.date() - today).days if d else None
    courses = query('SELECT course_id, course_name FROM usercourses WHERE id = %s ORDER BY course_name', (user_id,))
    last = query('SELECT course_id FROM todolist WHERE user_id = %s AND course_id IS NOT NULL '
                 'ORDER BY task_id DESC LIMIT 1', (user_id,), one=True)
    ids = {c['course_id'] for c in courses}
    last_course_id = last['course_id'] if last and last['course_id'] in ids else None
    prefill_due = request.args.get('due') or ''
    try:
        prefill_due = datetime.strptime(prefill_due, '%Y-%m-%d').date().isoformat() if prefill_due else ''
    except ValueError:
        prefill_due = ''
    todo = [t for t in tasks if t['category'] != 'concept']
    concepts = [t for t in tasks if t['category'] == 'concept']
    done = sum(1 for t in todo if t['is_completed'])
    return render_template('tasks.html', tasks=todo, concepts=concepts, courses=courses,
                           last_course_id=last_course_id, prefill_due=prefill_due,
                           open_add=bool(request.args.get('add')), done=done, pct=int(100 * done / len(todo)) if todo else 0)


@tasks_bp.route('/tasks/complete/<int:task_id>', methods=['POST'])
@login_required
def complete_task(task_id):
    t = query('SELECT is_completed FROM todolist WHERE task_id = %s AND user_id = %s', (task_id, session['user_id']), one=True)
    if t:
        new = not t['is_completed']
        query('UPDATE todolist SET is_completed = %s, progress = %s, completed_at = %s WHERE task_id = %s',
              (new, 100 if new else 0, apptime.now_utc_naive() if new else None, task_id), commit=True)
        if new:
            flash('Nice work! +10 points', 'success')
    return redirect(url_for('tasks_bp.manage_tasks'))


@tasks_bp.route('/tasks/done/<int:task_id>', methods=['POST'])
@login_required
def set_task_done(task_id):
    """Harvest / Undo with an explicit state: {"done": true|false} (JSON or form, default true). Never toggles,
    so repeats are safe. Done keeps the first completed_at; not-done clears it (the client then shows it as
    coming up, or overdue if past due). The old toggle stays on /tasks/complete for the To-Do page."""
    from flask import jsonify
    data = request.get_json(silent=True) or request.form
    raw = data.get('done', True)
    if isinstance(raw, bool):
        done = raw
    elif str(raw).strip().lower() in ('1', 'true', 'yes'):
        done = True
    elif str(raw).strip().lower() in ('0', 'false', 'no'):
        done = False
    else:
        return jsonify(ok=False, error='bad_done'), 400
    uid = session['user_id']
    t = query('SELECT is_completed FROM todolist WHERE task_id = %s AND user_id = %s', (task_id, uid), one=True)
    if not t:
        return jsonify(ok=False, error='not_found'), 404
    was = bool(t['is_completed'])
    if done and not was:
        query('UPDATE todolist SET is_completed = %s, progress = 100, completed_at = %s WHERE task_id = %s AND user_id = %s',
              (True, apptime.now_utc_naive(), task_id, uid), commit=True)
    elif not done and was:
        query('UPDATE todolist SET is_completed = %s, progress = 0, completed_at = NULL WHERE task_id = %s AND user_id = %s',
              (False, task_id, uid), commit=True)
    return jsonify(ok=True, done=done, changed=done != was)


@tasks_bp.route('/tasks/progress/<int:task_id>', methods=['POST'])
@login_required
def set_progress(task_id):
    try:
        p = int(request.form.get('progress', 0))
    except ValueError:
        p = -1
    if not 0 <= p <= 100:
        flash('Progress must be between 0 and 100.', 'warning')
    else:
        # completed_at: keep the first completion time if already done; clear it when un-done
        query('UPDATE todolist SET progress = %s, is_completed = %s, '
              'completed_at = CASE WHEN %s THEN COALESCE(completed_at, %s) ELSE NULL END '
              'WHERE task_id = %s AND user_id = %s',
              (p, p == 100, p == 100, apptime.now_utc_naive(), task_id, session['user_id']), commit=True)
    return redirect(url_for('tasks_bp.manage_tasks') + '#concepts')


@tasks_bp.route('/tasks/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    query('DELETE FROM todolist WHERE task_id = %s AND user_id = %s', (task_id, session['user_id']), commit=True)
    flash('Task deleted.', 'info')
    return redirect(url_for('tasks_bp.manage_tasks'))
