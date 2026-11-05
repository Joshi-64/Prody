"""Study Buddy AI chat. Uses an OpenAI-compatible API when PRODY_AI_KEY / OPENAI_API_KEY is set."""
import os
import apptime
from flask import Blueprint, current_app, flash, make_response, redirect, render_template, request, session, url_for
from itsdangerous import BadSignature, URLSafeSerializer

from helpers import ai_available, ai_chat, login_required, query  # all chat R/W goes through query -> Turso/SQLite

buddy_bp = Blueprint('buddy_bp', __name__)

# Spec: when no AI key is configured the buddy must say it is unavailable. Prody says it in its own voice.
UNAVAILABLE = ("Study Buddy AI is unavailable right now. Prody is resting its leaves, so please try again later.")
PERSONA = ("You are Prody, the student's study buddy inside the Prody app. You are also their houseplant: you grow when "
           "they study and droop a little when they don't. Let that show only lightly (an occasional, natural plant "
           "reference at most; no puns in every line, no emoji). First and foremost you are a clear, warm, concise "
           "tutor: explain step by step, check understanding with a quick question when useful, suggest a focus "
           "session when they seem stuck, and refuse harmful or dishonest requests (like writing graded work for "
           "them). ")
DAILY_CAP_MSG = ("That's a lot of great questions for one day. Prody needs to rest its leaves now, so chat opens again "
                 "tomorrow. A focus session still helps your plant grow in the meantime.")
BLOCKED_WORDS = ('how to make a bomb', 'kill someone', 'porn', 'nsfw', 'cheat on the exam for me')
CAP_COOKIE = 'prody_ai_day'


def daily_cap():
    try:
        return int(os.environ.get('PRODY_AI_DAILY_CAP', 40))
    except ValueError:
        return 40


def _cap_ser():
    return URLSafeSerializer(current_app.secret_key, salt='prody-ai-day')


def _today_utc():
    return apptime.now_utc_naive().date().isoformat()


def messages_today(uid):
    """Per-user daily AI count from a signed cookie (shared across Vercel instances; no DB index)."""
    raw = request.cookies.get(CAP_COOKIE)
    if not raw:
        return 0
    try:
        data = _cap_ser().loads(raw)
    except BadSignature:
        return 0
    if data.get('d') != _today_utc() or int(data.get('u') or -1) != int(uid):
        return 0
    return max(0, int(data.get('n') or 0))


def _set_cap_cookie(resp, uid, n):
    payload = _cap_ser().dumps({'u': int(uid), 'd': _today_utc(), 'n': int(n)})
    resp.set_cookie(CAP_COOKIE, payload, httponly=True, samesite='Lax', max_age=60 * 60 * 48)
    return resp


def _context(uid):
    courses = [c['course_name'] for c in query('SELECT course_name FROM usercourses WHERE id = %s', (uid,))]
    tasks = [t['task_name'] for t in query('SELECT task_name FROM todolist WHERE user_id = %s AND is_completed = 0', (uid,))][:10]
    return f"Student's courses: {courses}. Open tasks/concepts: {tasks}."


def _wants_json():
    acc = (request.headers.get('Accept') or '')
    return 'application/json' in acc or request.headers.get('X-Requested-With') == 'fetch'


@buddy_bp.route('/buddy', methods=['GET', 'POST'])
@login_required
def chat():
    from flask import jsonify
    uid = session['user_id']
    if request.method == 'POST':
        text = (request.form.get('message') or '').strip()[:2000]
        if not text:
            if _wants_json():
                return jsonify(ok=False, error='empty', message="That didn't send, try again"), 400
            return redirect(url_for('buddy_bp.chat'))
        if any(w in text.lower() for w in BLOCKED_WORDS):
            if _wants_json():
                return jsonify(ok=False, error='blocked', message="Prody can't help with explicit, illegal, or harmful requests."), 400
            flash("Prody can't help with explicit, illegal, or harmful requests.", 'warning')
            return redirect(url_for('buddy_bp.chat'))
        used = messages_today(uid)
        if used >= daily_cap():
            if _wants_json():
                return jsonify(ok=False, error='capped', message=DAILY_CAP_MSG), 429
            flash(DAILY_CAP_MSG, 'info')
            return redirect(url_for('buddy_bp.chat'))
        history = query('SELECT role, content FROM chatmessages WHERE user_id = %s ORDER BY message_id DESC LIMIT 10', (uid,))
        from plant import plant_state
        st = plant_state(uid)
        msgs = [{'role': 'system', 'content': PERSONA + f"Your current form: {st['stage']} stage, feeling {st['mood']}, "
                 f"{st['hours']} hours of study so far. " + _context(uid)}]
        msgs += [{'role': h['role'], 'content': h['content']} for h in reversed(history)]
        msgs.append({'role': 'user', 'content': text})
        try:
            reply = ai_chat(msgs, timeout=30)
        except Exception:
            if _wants_json():
                return jsonify(ok=False, error='unavailable', message=UNAVAILABLE), 503
            flash(UNAVAILABLE, 'danger')
            return render_template('buddy.html', messages=_messages(uid), draft=text, ai_ready=ai_available(), resting=True)
        now = apptime.now_utc_naive()
        query('INSERT INTO chatmessages (user_id, role, content, created_at) VALUES (%s, %s, %s, %s)',
              (uid, 'user', text, now), commit=True)
        query('INSERT INTO chatmessages (user_id, role, content, created_at) VALUES (%s, %s, %s, %s)',
              (uid, 'assistant', reply, now), commit=True)
        if _wants_json():
            resp = make_response(jsonify(ok=True, reply=reply))
            return _set_cap_cookie(resp, uid, used + 1)
        resp = make_response(redirect(url_for('buddy_bp.chat')))
        return _set_cap_cookie(resp, uid, used + 1)
    return render_template('buddy.html', messages=_messages(uid), draft='', ai_ready=ai_available(),
                           capped=messages_today(uid) >= daily_cap())


def _messages(uid):
    return query('SELECT * FROM chatmessages WHERE user_id = %s ORDER BY message_id', (uid,))


@buddy_bp.route('/buddy/clear', methods=['POST'])
@login_required
def clear():
    query('DELETE FROM chatmessages WHERE user_id = %s', (session['user_id'],), commit=True)
    flash('Conversation cleared. Fresh soil.', 'info')
    return redirect(url_for('buddy_bp.chat'))
