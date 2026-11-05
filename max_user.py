"""Max out an existing account: python max_user.py USERNAME"""
import sys
from datetime import datetime, timedelta
from db import init_db
from user_courses import add_course
from helpers import query, user_stats
init_db()
now = datetime.now().replace(second=0, microsecond=0)
uname = sys.argv[1]
r = query('SELECT id FROM users WHERE username = %s', (uname,))
if not r: sys.exit('no such user')
uid = r[0]['id']
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
print(f'{uname}: {s["points"]} coins, level {s["level"]}, {s["earned_count"]} badges')
from plant import plant_state, record_milestones
record_milestones(uid, plant_state(uid))
