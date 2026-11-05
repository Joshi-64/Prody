"""Discussion boards: Global, University, Course tabs. Threads + replies. Admin hide/pin/delete."""
import apptime
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from fn_flags import DEMO_LABEL
from helpers import admin_required, login_required, query

forums_bp = Blueprint('forums_bp', __name__)
SCOPES = ('global', 'university', 'course')
MAX_TITLE, MAX_BODY = 200, 4000
# Match profiles.decorate header avatar hues (peach / sage / sand).
AV_PALETTE = ['#E7DCC6', '#CFDCC6', '#EFD3C3']  # last is peach


def av_color(name):
    return AV_PALETTE[sum(ord(c) for c in (name or '')) % len(AV_PALETTE)]


def author_chip(username):
    """Avatar chip for board authors: initial on peach-matching header circle."""
    uname = (username or '').strip() or '?'
    return {
        'username': uname,
        'initial': uname[0].upper(),
        'av': av_color(uname),
    }


def _profile_uni(uid):
    row = query('SELECT university FROM userprofiles WHERE user_id = %s', (uid,), one=True)
    return ((row or {}).get('university') or '').strip()


def _user_courses(uid):
    return query('SELECT course_id, course_name, course_code, COALESCE(verified, 0) AS verified '
                 'FROM usercourses WHERE id = %s ORDER BY course_name', (uid,))


def _thread_or_404(tid, allow_hidden=False):
    t = query('SELECT t.*, u.username AS author_name FROM forum_threads t JOIN users u ON u.id = t.author_id '
              'WHERE t.id = %s', (tid,), one=True)
    if not t:
        abort(404)
    if t.get('hidden') and session.get('role') != 'admin' and not allow_hidden:
        abort(404)
    return t


@forums_bp.route('/boards')
@login_required
def index():
    uid = session['user_id']
    tab = (request.args.get('tab') or 'global').lower()
    if tab not in SCOPES:
        tab = 'global'
    courses = _user_courses(uid)
    uni = _profile_uni(uid)
    course_id = request.args.get('course_id', type=int)
    params = []
    where = 't.scope = %s'
    params.append(tab)
    if session.get('role') != 'admin':
        where += ' AND COALESCE(t.hidden, 0) = 0'
    if tab == 'university':
        where += ' AND t.university = %s'
        params.append(uni or '__none__')
    elif tab == 'course':
        if course_id and any(c['course_id'] == course_id for c in courses):
            where += ' AND t.course_id = %s'
            params.append(course_id)
        else:
            course_id = courses[0]['course_id'] if courses else None
            if course_id:
                where += ' AND t.course_id = %s'
                params.append(course_id)
            else:
                where += ' AND 1 = 0'
    threads = query(
        f'SELECT t.*, u.username AS author_name, '
        f'(SELECT COUNT(*) FROM forum_replies r WHERE r.thread_id = t.id) AS reply_n '
        f'FROM forum_threads t JOIN users u ON u.id = t.author_id WHERE {where} '
        f'ORDER BY COALESCE(t.pinned, 0) DESC, t.id DESC LIMIT 50', tuple(params))
    for th in threads:
        th['author'] = author_chip(th.get('author_name'))
    return render_template('forums.html', tab=tab, threads=threads, courses=courses,
                           course_id=course_id, university=uni, demo_label=DEMO_LABEL,
                           is_admin=session.get('role') == 'admin')


@forums_bp.route('/boards/new', methods=['POST'])
@login_required
def create():
    uid = session['user_id']
    scope = (request.form.get('scope') or 'global').lower()
    if scope not in SCOPES:
        flash('Unknown board.', 'warning')
        return redirect(url_for('forums_bp.index'))
    title = (request.form.get('title') or '').strip()[:MAX_TITLE]
    body = (request.form.get('body') or '').strip()[:MAX_BODY]
    if not title or not body:
        flash('Title and post are required.', 'warning')
        return redirect(url_for('forums_bp.index', tab=scope))
    course_id, uni = None, ''
    if scope == 'university':
        uni = _profile_uni(uid)
        if not uni:
            flash('Add your university on your profile to post here.', 'warning')
            return redirect(url_for('forums_bp.index', tab=scope))
    elif scope == 'course':
        try:
            course_id = int(request.form.get('course_id') or 0)
        except ValueError:
            course_id = 0
        if not any(c['course_id'] == course_id for c in _user_courses(uid)):
            flash('Pick one of your classes.', 'warning')
            return redirect(url_for('forums_bp.index', tab=scope))
    tid = query(
        'INSERT INTO forum_threads (scope, course_id, university, author_id, title, body, created_at, pinned, hidden) '
        'VALUES (%s,%s,%s,%s,%s,%s,%s,0,0)',
        (scope, course_id, uni, uid, title, body, apptime.now_utc_naive()), commit=True)
    return redirect(url_for('forums_bp.thread', thread_id=tid))


@forums_bp.route('/boards/<int:thread_id>')
@login_required
def thread(thread_id):
    t = _thread_or_404(thread_id)
    if t['scope'] == 'course' and t.get('course_id'):
        mine = {c['course_id'] for c in _user_courses(session['user_id'])}
        if t['course_id'] not in mine and session.get('role') != 'admin' and t['author_id'] != session['user_id']:
            flash('That course board is for students in the class.', 'warning')
            return redirect(url_for('forums_bp.index', tab='course')), 403
    replies = query(
        'SELECT r.*, u.username AS author_name FROM forum_replies r JOIN users u ON u.id = r.author_id '
        'WHERE r.thread_id = %s ORDER BY r.id ASC', (thread_id,))
    for r in replies:
        r['author'] = author_chip(r.get('author_name'))
    t['author'] = author_chip(t.get('author_name'))
    course = None
    if t.get('course_id'):
        course = query('SELECT course_id, course_name, course_code, COALESCE(verified, 0) AS verified '
                       'FROM usercourses WHERE course_id = %s', (t['course_id'],), one=True)
    return render_template('forum_thread.html', thread=t, replies=replies, course=course,
                           demo_label=DEMO_LABEL, is_admin=session.get('role') == 'admin')


@forums_bp.route('/boards/<int:thread_id>/reply', methods=['POST'])
@login_required
def reply(thread_id):
    _thread_or_404(thread_id)
    body = (request.form.get('body') or '').strip()[:MAX_BODY]
    if not body:
        flash('Write a reply first.', 'warning')
        return redirect(url_for('forums_bp.thread', thread_id=thread_id))
    query('INSERT INTO forum_replies (thread_id, author_id, body, created_at) VALUES (%s,%s,%s,%s)',
          (thread_id, session['user_id'], body, apptime.now_utc_naive()), commit=True)
    return redirect(url_for('forums_bp.thread', thread_id=thread_id))


@forums_bp.route('/admin/boards/thread/<int:thread_id>/delete', methods=['POST'])
@admin_required
def admin_delete_thread(thread_id):
    query('DELETE FROM forum_replies WHERE thread_id = %s', (thread_id,), commit=True)
    query('DELETE FROM forum_threads WHERE id = %s', (thread_id,), commit=True)
    flash('Thread deleted.', 'info')
    return redirect(url_for('forums_bp.index'))


@forums_bp.route('/admin/boards/thread/<int:thread_id>/hide', methods=['POST'])
@admin_required
def admin_hide_thread(thread_id):
    t = _thread_or_404(thread_id, allow_hidden=True)
    flag = 0 if t.get('hidden') else 1
    query('UPDATE forum_threads SET hidden = %s WHERE id = %s', (flag, thread_id), commit=True)
    flash('Post hidden.' if flag else 'Post unhidden.', 'info')
    return redirect(url_for('forums_bp.thread', thread_id=thread_id) if not flag else url_for('forums_bp.index'))


@forums_bp.route('/admin/boards/thread/<int:thread_id>/pin', methods=['POST'])
@admin_required
def admin_pin_thread(thread_id):
    t = _thread_or_404(thread_id, allow_hidden=True)
    flag = 0 if t.get('pinned') else 1
    query('UPDATE forum_threads SET pinned = %s WHERE id = %s', (flag, thread_id), commit=True)
    flash('Post pinned.' if flag else 'Pin removed.', 'success')
    return redirect(url_for('forums_bp.thread', thread_id=thread_id))


@forums_bp.route('/admin/boards/reply/<int:reply_id>/delete', methods=['POST'])
@admin_required
def admin_delete_reply(reply_id):
    row = query('SELECT thread_id FROM forum_replies WHERE id = %s', (reply_id,), one=True)
    query('DELETE FROM forum_replies WHERE id = %s', (reply_id,), commit=True)
    flash('Reply deleted.', 'info')
    if row:
        return redirect(url_for('forums_bp.thread', thread_id=row['thread_id']))
    return redirect(url_for('forums_bp.index'))
