"""Create (or reset) two maxed-out tester accounts for trying the Store and customizing.
    PRODY_DB=sqlite python seed_testers.py
prody_admin and prody_student (local testing only). Passwords come from the environment:
    PRODY_ADMIN_PASSWORD and PRODY_STUDENT_PASSWORD (e.g. `set -a; source .secrets/test_accounts.env; set +a`)."""
import os
import sys
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from db import init_db
from user_courses import add_course
from helpers import query, user_stats

def main():
    init_db()
    now = datetime.now().replace(second=0, microsecond=0)
    out = []
    _pw = {k: os.environ.get(k, '') for k in ('PRODY_ADMIN_PASSWORD', 'PRODY_STUDENT_PASSWORD')}
    if not all(_pw.values()):
        sys.exit('Set PRODY_ADMIN_PASSWORD and PRODY_STUDENT_PASSWORD (see .secrets/test_accounts.env).')
    for username, email, role, pw in [('prody_admin', 'prody_admin@prody.app', 'admin', _pw['PRODY_ADMIN_PASSWORD']),
                                      ('prody_student', 'prody_student@prody.app', 'student', _pw['PRODY_STUDENT_PASSWORD'])]:
        from db import DB_BACKEND
        existing = query('SELECT id FROM users WHERE username = %s OR email = %s', (username, email), one=True)
        if existing and DB_BACKEND == 'libsql':
            out.append((username, 'kept-on-turso')); continue  # never wipe shared Turso
        if existing:
            query('DELETE FROM users WHERE username = %s OR email = %s', (username, email), commit=True)
        uid = query('INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,%s)',
                    (username, email, generate_password_hash(pw), role, now - timedelta(days=120)), commit=True)
        cids = [add_course(uid, ('course_name', 'course_code', 'subject'), (n, c, sub)) for n, c, sub in
                [('Software Engineering', 'CSC 4350', 'Computer Science'), ('Database Systems', 'CSC 4710', 'Computer Science'),
                 ('Linear Algebra', 'MATH 3435', 'Mathematics'), ('Intro to Psychology', 'PSYC 1101', 'Psychology')]]
        cid = cids[0]
        for d in range(200):  # 200-day streak, 10h a day: every badge, max plant stage, huge coin balance
            query('INSERT INTO studysessions (user_id, course_id, label, minutes, started_at) VALUES (%s,%s,%s,%s,%s)',
                  (uid, cids[d % 4], 'Focus session', 600, now - timedelta(days=d, hours=2)), commit=True)
        for i in range(12):
            query('INSERT INTO todolist (user_id, task_name, is_completed, progress, course_id) VALUES (%s,%s,1,100,%s)',
                  (uid, f'Test task {i+1}', cids[i % 4]), commit=True)
            query('INSERT INTO grades (user_id, course_id, item_name, score, weight) VALUES (%s,%s,%s,%s,%s)',
                  (uid, cids[i % 4], f'Assignment {i // 4 + 1}', 98 + i % 3, 10), commit=True)
        for name, ci, days in [('Sprint demo', 0, 3), ('Lab 5 report', 1, 6), ('Problem set 7', 2, 9),
                               ('Chapter 6 quiz', 3, 13), ('Midterm project', 0, 20), ('Final exam', 2, 45)]:
            query('INSERT INTO coursedeadlines (course_id, deadline_name, deadline_date, is_completed) VALUES (%s,%s,%s,0)',
                  (cids[ci], name, (now + timedelta(days=days)).replace(hour=23, minute=59)), commit=True)
        query("INSERT INTO calendarevents (user_id, event_name, event_date, is_ai_recommended, flag_status) "
              "VALUES (%s,'AI study block',%s,1,'confirmed')", (uid, now - timedelta(days=1)), commit=True)
        s = user_stats(uid)
        out.append(f'{role}: {username}  ({s["points"]} coins, level {s["level"]}, {s["earned_count"]} badges)')
    print('\n'.join(out))
    from plant import plant_state, record_milestones  # noqa: E402
    for u in query("SELECT id FROM users WHERE username IN ('prody_admin', 'prody_student')"):
        record_milestones(u['id'], plant_state(u['id']))


if __name__ == '__main__':
    main()
