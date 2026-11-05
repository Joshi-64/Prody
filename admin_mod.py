"""Separate admin login + course verification tools."""
import apptime
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from helpers import admin_required, login_required, query, rate_limit_hit, rate_limit_reset

admin_mod_bp = Blueprint('admin_mod_bp', __name__)


@admin_mod_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin-only login. Students with a valid password are rejected."""
    if session.get('user_id') and session.get('role') == 'admin':
        return redirect(url_for('admin'))
    if request.method == 'POST':
        ident = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        ip = request.remote_addr or 'unknown'
        keys = (f'adminlogin:ip:{ip}', f'adminlogin:user:{ident.lower()}')
        if any(rate_limit_hit(k, limit=lim, window=900, peek=True) for k, lim in zip(keys, (20, 5))):
            flash('Too many login attempts. Please wait 15 minutes and try again.', 'danger')
            return render_template('admin_login.html', ident=ident), 429
        user = query('SELECT * FROM users WHERE username = %s OR email = %s', (ident, ident.lower()), one=True)
        if user and check_password_hash(user['password_hash'], password):
            if user.get('role') != 'admin':
                for k, lim in zip(keys, (20, 5)):
                    rate_limit_hit(k, limit=lim, window=900)
                flash('Admin access only. This account is not an administrator.', 'danger')
                return render_template('admin_login.html', ident=ident), 403
            rate_limit_reset(keys[1])
            session.clear()
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f"Welcome, admin {user['username']}.", 'success')
            return redirect(url_for('admin'))
        for k, lim in zip(keys, (20, 5)):
            rate_limit_hit(k, limit=lim, window=900)
        flash('Wrong username or password', 'danger')
        return render_template('admin_login.html', ident=ident), 401
    return render_template('admin_login.html')


@admin_mod_bp.route('/admin/courses')
@admin_required
def courses():
    rows = query(
        'SELECT c.course_id, c.course_name, c.course_code, c.subject, COALESCE(c.verified, 0) AS verified, '
        'u.username, u.id AS owner_id FROM usercourses c JOIN users u ON u.id = c.id '
        'ORDER BY c.course_id DESC LIMIT 200')
    return render_template('admin_courses.html', courses=rows)


@admin_mod_bp.route('/admin/courses/<int:course_id>/verify', methods=['POST'])
@admin_required
def verify_course(course_id):
    action = (request.form.get('action') or 'verify').lower()
    flag = 0 if action == 'unverify' else 1
    row = query('SELECT course_id FROM usercourses WHERE course_id = %s', (course_id,), one=True)
    if not row:
        flash('Course not found.', 'warning')
        return redirect(url_for('admin_mod_bp.courses'))
    query('UPDATE usercourses SET verified = %s WHERE course_id = %s', (flag, course_id), commit=True)
    flash('Course verified.' if flag else 'Verification removed.', 'success')
    return redirect(url_for('admin_mod_bp.courses'))
