import apptime
import os
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from calendar_routes import calendar_bp  # adds calendar functionality
from user_courses import user_courses_bp  # adds course upload functionality
from tasks import tasks_bp
from study import study_bp  # focus timer, analytics, achievements
from grades import grades_bp
from buddy import buddy_bp  # AI study buddy chat
from profiles import profile_bp  # profiles + points store
from friends import friends_bp  # friends + online status
from dm import dm_bp  # friend DMs
from forums import forums_bp  # discussion boards
from admin_mod import admin_mod_bp  # admin login + course verify
from db import DB_BACKEND, IntegrityError, get_db_connection, init_db
from helpers import admin_required, as_dt, login_required, fill_display_colours, query, rate_limit_hit, rate_limit_reset, user_sessions, user_stats

app = Flask(__name__)
# Session secret key: fixed PRODY_SECRET_KEY from env. Never generate a per-instance random key
# (that breaks CSRF across Vercel cold starts). Local/dev may use the hardcoded fallback.
app.config['MAX_CONTENT_LENGTH'] = 3 * 1024 * 1024  # avatar uploads
# Static assets are cache-busted with ?v=N in templates, so let browsers keep them for a year.
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000
# Compress HTML/CSS/JS/JSON/SVG responses (gzip or brotli, by Accept-Encoding).
app.config['COMPRESS_MIMETYPES'] = ['text/html', 'text/css', 'text/javascript', 'application/javascript',
                                    'application/json', 'image/svg+xml', 'text/plain', 'text/xml']
app.config['COMPRESS_ALGORITHM'] = ['br', 'gzip']
app.config['COMPRESS_MIN_SIZE'] = 500
_DEV_SECRET = 'prody_dev_secret_key_2026'
_sk = (os.environ.get('PRODY_SECRET_KEY') or '').strip()
# --- Session hardening (Bark). HttpOnly + SameSite always; Secure on hosted HTTPS
# (Render sets RENDER / Vercel sets VERCEL, or force with PRODY_SECURE_COOKIES=1).
_HOSTED = bool(os.environ.get('RENDER') or os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV')) or os.environ.get('PRODY_SECURE_COOKIES', '0').lower() in ('1', 'true', 'yes')
if _HOSTED:
    if not _sk or _sk == _DEV_SECRET or len(_sk) < 32:
        raise RuntimeError(
            'PRODY_SECRET_KEY must be a fixed secret of at least 32 characters when hosted; '
            'refusing a missing, short, or per-instance key.')
    app.secret_key = _sk
else:
    app.secret_key = _sk or _DEV_SECRET
if _HOSTED:  # Render runs one proxy hop in front of us; trust exactly that one X-Forwarded-For entry
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=_HOSTED,
    PERMANENT_SESSION_LIFETIME=timedelta(days=int(os.environ.get('PRODY_SESSION_DAYS', 14))),
    SESSION_REFRESH_EACH_REQUEST=True,
    WTF_CSRF_TIME_LIMIT=None,  # token lives as long as the session, avoids mid-semester form expiry
)

# Links separate core functionality code to main app script
for bp in (calendar_bp, user_courses_bp, tasks_bp, study_bp, grades_bp, buddy_bp, profile_bp, friends_bp, dm_bp, forums_bp, admin_mod_bp):
    app.register_blueprint(bp)
from api_tree import api_tree_bp; app.register_blueprint(api_tree_bp)  # GET /api/tree (contract v0.5)
from rooms import rooms_bp; app.register_blueprint(rooms_bp)  # video study rooms + shared whiteboard

# --- CSRF protection (Flask-WTF). Token is auto-injected into every POST form,
# exposed as <meta name="csrf-token">, and added to same-origin fetch() calls.
from flask_wtf.csrf import CSRFProtect, CSRFError, generate_csrf
csrf = CSRFProtect(app)


@app.errorhandler(CSRFError)
def _csrf_error(e):
    """Never show raw CSRF text. Auth forms redirect to styled sign-in; JSON/fetch get soft JSON;
    other HTML posts get a short 400 (not e.description)."""
    from flask import jsonify
    wants = (
        'application/json' in (request.headers.get('Accept') or '')
        or request.headers.get('X-Requested-With') == 'fetch'
        or request.is_json
        or (request.content_type or '').startswith('application/json')
    )
    if wants:
        return jsonify(ok=False, error='csrf', message="That didn't send, try again"), 400
    if request.path in ('/login', '/register') or request.path.startswith('/admin/login'):
        flash('Your sign-in form expired, please try again.', 'warning')
        if request.path.startswith('/admin'):
            return redirect(url_for('admin_mod_bp.admin_login'))
        return redirect(url_for('login'))
    return "That didn't send, try again.", 400
_FORM_RE = re.compile(r'(<form\b(?:"[^"]*"|\'[^\']*\'|[^>"\'])*>)', re.I)
_CSRF_JS = ("<script>(function(){var t=document.querySelector('meta[name=csrf-token]').content,f=window.fetch;"
            "window.fetch=function(u,o){o=o||{};var m=(o.method||'GET').toUpperCase();"
            "if(m!=='GET'&&m!=='HEAD'){var h=new Headers(o.headers||{});if(!h.has('X-CSRFToken'))h.set('X-CSRFToken',t);o.headers=h;}"
            "return f.call(this,u,o)}})();</script>")


try:  # registered BEFORE inject_csrf: after_request hooks run in reverse, so compression runs last
    from flask_compress import Compress
    Compress(app)
except ImportError:
    pass


@app.after_request
def inject_csrf(resp):
    # Inject on 2xx AND 4xx re-renders (401 bad password, 429 rate limit, 400 form errors):
    # skipping >=300 left the re-rendered login form without csrf_token, so the retry 400'd.
    if (resp.mimetype != 'text/html' or resp.direct_passthrough or 300 <= resp.status_code < 400
            or resp.headers.get('Content-Encoding')):
        return resp
    html = resp.get_data(as_text=True)
    if '<form' not in html and '</head>' not in html:
        return resp
    tok = generate_csrf()
    html = _FORM_RE.sub(lambda m: m.group(1) + (f'<input type="hidden" name="csrf_token" value="{tok}">' if re.search(r'\bmethod=["\']?post', m.group(1), re.I) else ''), html)
    if '</head>' in html and 'name="csrf-token"' not in html:
        html = html.replace('</head>', f'<meta name="csrf-token" content="{tok}">{_CSRF_JS}</head>', 1)
    resp.set_data(html)
    return resp


PREFETCH_OK = re.compile(r'^/(dashboard|tasks|calendar|achievements|friends|store|u/[A-Za-z0-9_.-]+)/?$')  # nav-perf: read-only pages shell.js may warm


@app.after_request
def static_cache_headers(resp):
    if request.path.startswith('/static/') and resp.status_code in (200, 304):
        if assets.valid_version(request.path[len('/static/'):], request.args.get('v')):
            resp.cache_control.public = True
            resp.cache_control.max_age = 31536000
            resp.cache_control.immutable = True
        else:
            # Unversioned / stale-hash URLs must revalidate, or a deploy could serve stale assets.
            resp.headers['Cache-Control'] = 'no-cache'
        # Static files never depend on the session: drop Vary: Cookie / Set-Cookie so
        # a rotated session cookie doesn't defeat the browser cache (iPhone repeat loads).
        if resp.vary:
            keep = [h for h in resp.vary if h.lower() != 'cookie']
            resp.vary.clear()
            resp.vary.update(keep)
        resp.headers.pop('Set-Cookie', None)
        try:
            session.accessed = False  # stop save_session re-adding Vary: Cookie
        except Exception:
            pass
    elif not request.path.startswith('/static/') and 'Cache-Control' not in resp.headers:
        # Auth forms must never be cached (iPhone Safari bfcache kept a stale CSRF token).
        if request.path in ('/login', '/register') or request.path.startswith('/admin/login'):
            resp.headers['Cache-Control'] = 'no-store'
        elif (request.method == 'GET' and resp.status_code == 200 and request.headers.get('X-Prody-Prefetch') == '1' and PREFETCH_OK.match(request.path)
                and resp.mimetype == 'text/html'):
            # nav-perf: shell.js warms the next page with fetch() (WebKit has no rel=prefetch). A short private
            # max-age lets the tap that follows reuse that response from the browser cache; never shared.
            resp.headers['Cache-Control'] = 'private, max-age=10'
        else:
            resp.headers['Cache-Control'] = 'no-cache'
    return resp


import assets  # content-hashed /static URLs (after static_cache_headers so it runs before it)
assets.register(app)

import plant  # Prody the plant: growth state + SVG renderer
plant.register(app)

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


@app.context_processor
def inject_globals():
    return {'today': apptime.today_local(), 'db_backend': DB_BACKEND}


from profiles import class_dot_colour
@app.template_filter('class_dot')
def _class_dot(stored):
    return class_dot_colour(stored)


@app.template_filter('nice_dt')
def nice_dt(v, fmt='%b %d, %I:%M %p'):
    d = as_dt(v)
    return d.strftime(fmt).replace(' 0', ' ') if d else ''


@app.template_filter('nice_stamp')
def nice_stamp(v, fmt='%b %d, %I:%M %p'):
    """Server-written timestamps (naive UTC) shown in ET. User-entered times use nice_dt."""
    d = as_dt(v)
    return nice_dt(apptime.to_local(d), fmt) if d else ''


@app.template_filter('rel_day')
def rel_day(v):
    d = as_dt(v)
    if not d:
        return ''
    delta = (d.date() - apptime.today_local()).days
    if delta == 0:
        return 'Today'
    if delta == 1:
        return 'Tomorrow'
    if delta < 0:
        return f'{-delta}d overdue'
    return f'in {delta} days'


@app.template_filter('hm')
def hm(minutes):
    minutes = int(minutes or 0)
    return f'{minutes // 60}h {minutes % 60:02d}m' if minutes >= 60 else f'{minutes}m'


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))  # landing.html parked per Leader


@app.route('/register', methods=['GET', 'POST'])
def register():
    errors, form = {}, {}
    if request.method == 'POST':
        form = {k: request.form.get(k, '').strip() for k in ('username', 'email')}
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', password)
        if not form['username'] or len(form['username']) < 3:
            errors['username'] = 'Username must be at least 3 characters.'
        elif len(form['username']) > 50:
            errors['username'] = 'Username must be 50 characters or fewer.'
        if not EMAIL_RE.match(form['email']):
            errors['email'] = 'Please enter a valid email address.'
        if len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters.'
        elif password != confirm:
            errors['confirm'] = 'Passwords do not match.'
        if not errors:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            try:
                # Role is always 'student' on self sign-up; admins are promoted from the admin console.
                cursor.execute(
                    'INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s, %s, %s, %s, %s)',
                    (form['username'], form['email'].lower(), generate_password_hash(password), 'student',
                     apptime.now_utc_naive()))
                conn.commit()
                flash('Account created successfully. Please log in.', 'success')
                return redirect(url_for('login'))
            except IntegrityError:
                flash('That username or email is already registered.', 'danger')
            finally:
                cursor.close()
                conn.close()
        else:
            flash('Please fix the highlighted fields.', 'warning')
    return render_template('register.html', errors=errors, form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ident = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        ip = request.remote_addr or 'unknown'  # real client IP via ProxyFix when hosted; never raw X-Forwarded-For
        keys = (f'login:ip:{ip}', f'login:user:{ident.lower()}')
        if any(rate_limit_hit(k, limit=lim, window=900, peek=True) for k, lim in zip(keys, (20, 5))):
            flash('Too many login attempts. Please wait 15 minutes and try again.', 'danger')
            return render_template('login.html', ident=ident), 429
        user = query('SELECT * FROM users WHERE username = %s OR email = %s', (ident, ident.lower()), one=True)
        # Verify user exists and password hash matches
        if user and check_password_hash(user['password_hash'], password):
            rate_limit_reset(keys[1])
            session.clear()  # rotate: drop any pre-login session data (and its CSRF token)
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f"Welcome back, {user['username']}!", 'success')
            return redirect(url_for('dashboard'))
        for k, lim in zip(keys, (20, 5)):
            rate_limit_hit(k, limit=lim, window=900)
        flash('Wrong username or password', 'danger')
        return render_template('login.html', ident=ident), 401
    return render_template('login.html')


def home_first_name(uid):
    """Home headline name: first word of the profile display name; never the raw login handle."""
    from profiles import get_profile
    name = ((get_profile(uid) or {}).get('display_name') or '').strip()
    return name.split()[0][:40] if name else ''


APP_TZ = apptime.APP_TZ


def _local_now():
    """Wall clock in the app's zone (server runs UTC), tz-aware; goes through apptime.now_local."""
    return apptime.now_local().replace(tzinfo=APP_TZ)


@app.route('/dashboard')
@login_required
def dashboard():
    uid = session['user_id']
    start = apptime.day_start()
    events = query('SELECT * FROM calendarevents WHERE user_id = %s AND event_date >= %s AND event_date < %s '
                   "AND (flag_status IS NULL OR flag_status <> 'is_pending') ORDER BY event_date",
                   (uid, start, start + timedelta(days=1)))
    deadlines = query('SELECT d.*, c.course_name, c.color FROM coursedeadlines d JOIN usercourses c '
                      'ON c.course_id = d.course_id WHERE c.id = %s AND d.deadline_date >= %s '
                      'ORDER BY d.deadline_date LIMIT 6', (uid, start))
    fill_display_colours(deadlines, uid)
    from helpers import user_sessions, user_todos
    tasks = [dict(t) for t in user_todos(uid)]  # copies: fill_display_colours mutates, the cached rows feed stats/plant
    fill_display_colours(tasks, uid)
    total = len(tasks)
    done = sum(1 for t in tasks if t['is_completed'])
    stats = user_stats(uid)
    week = []
    wk_start, wk_end = apptime.week_bounds_utc(7)
    _ws, _we = as_dt(wk_start), as_dt(wk_end)
    sessions = [s for s in user_sessions(uid) if as_dt(s['started_at']) and _ws <= as_dt(s['started_at']) < _we]
    for i in range(6, -1, -1):
        d = (start - timedelta(days=i)).date()
        week.append({'label': d.strftime('%a'),
                     'minutes': sum(int(s['minutes']) for s in sessions if apptime.local_date(as_dt(s['started_at'])) == d)})
    first_name = home_first_name(uid)
    local = _local_now()
    greeting = 'Good morning' if local.hour < 12 else 'Good afternoon' if local.hour < 18 else 'Good evening'
    return render_template('dashboard.html', greeting=greeting, today=local.date(), first_name=first_name, username=session.get('username'), role=session.get('role'),
                           events=events, deadlines=deadlines, open_tasks=[t for t in tasks if not t['is_completed'] and t.get('category') != 'concept'][:5],
                           task_total=total, task_done=done, stats=stats, week=week, st=_plant(uid))


def _plant(uid):
    st = plant.plant_state(uid)
    plant.record_milestones(uid, st)
    return st


@app.route('/more')
@login_required
def more_hub():
    """Header grid hub: every page the tab bar hides."""
    return render_template('more.html', is_admin=session.get('role') == 'admin')





@app.route('/admin')
@admin_required
def admin():
    users = query('SELECT id, username, email, role, created_at FROM users ORDER BY id DESC')
    counts = {
        'users': len(users),
        'students': sum(1 for u in users if u['role'] == 'student'),
        'events': query('SELECT COUNT(*) AS n FROM calendarevents', one=True)['n'],
        'sessions': query('SELECT COUNT(*) AS n FROM studysessions', one=True)['n'],
    }
    return render_template('admin.html', users=users, counts=counts)


@app.route('/admin/role/<int:user_id>', methods=['POST'])
@admin_required
def admin_set_role(user_id):
    role = request.form.get('role')
    if role not in ('student', 'admin'):
        flash('Invalid role.', 'danger')
    elif user_id == session['user_id']:
        flash("You can't change your own role.", 'warning')
    else:
        query('UPDATE users SET role = %s WHERE id = %s', (role, user_id), commit=True)
        flash('Role updated.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    if user_id == session['user_id']:
        flash("You can't delete your own account here.", 'warning')
    else:
        from account_data import delete_user_data
        delete_user_data(user_id)
        flash('User deleted.', 'success')
    return redirect(url_for('admin'))


@app.route('/logout', methods=['POST'])  # CSRF-checked POST only
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.errorhandler(404)
def not_found(_e):
    return render_template('error.html', code=404, message="We couldn't find that page."), 404


@app.errorhandler(413)
def too_large(_e):
    flash('That file is too large. Avatars must be 2 MB or smaller.', 'danger')
    return redirect(url_for('profile_bp.edit_profile'))


@app.errorhandler(500)
def server_error(_e):
    return render_template('error.html', code=500,
                           message='We ran into an unexpected error, please try again later.'), 500


try:
    init_db()
    print(f'Database schema initialized successfully ({DB_BACKEND}).')
    try:
        from profiles import migrate_removed_flowers
        print('Flower palette migration (profiles cleared, rows refunded, coins): %s' % (migrate_removed_flowers(),))
    except Exception as e:
        print(f'Flower palette migration failed: {e}')
except Exception as e:  # keep the app bootable so the error page can explain
    print(f'Database schema initialization failed: {e}')

if __name__ == '__main__':
    _debug = os.environ.get('FLASK_DEBUG', '0').lower() in ('1', 'true', 'yes')
    app.run(debug=_debug, use_reloader=_debug, port=int(os.environ.get('PORT', 5000)))
