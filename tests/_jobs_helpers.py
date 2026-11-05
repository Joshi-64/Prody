"""Shared fixtures for grade-picker / slot tests. DB chosen by PRODY_DB env (sqlite copy or MySQL copy)."""
import os, sys, uuid
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module  # noqa: E402  (runs init_db on the configured copy)
from helpers import query  # noqa: E402

app = app_module.app
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False  # route logic under test, not CSRF


def make_user():
    tag = uuid.uuid4().hex[:10]
    return query('INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)',
                 ('t_' + tag, tag + '@test.invalid', 'x'), commit=True)


def make_course(uid, name, slot):
    return query('INSERT INTO usercourses (id, course_name, subject, branch_slot) VALUES (%s, %s, %s, %s)',
                 (uid, name, 'Other', slot), commit=True)


def make_deadline(cid, name='Midterm'):
    return query('INSERT INTO coursedeadlines (course_id, deadline_name, deadline_date) VALUES (%s, %s, %s)',
                 (cid, name, datetime.now() + timedelta(days=10)), commit=True)


def client_for(uid):
    c = app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid
    return c
