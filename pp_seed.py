"""Preview-only idempotent seed: pp_admin / pp_student, maxed out. Passwords from PP_ADMIN_PW / PP_STUDENT_PW."""
import os, random
from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from helpers import query

COURSES = [('Software Engineering', 'CSC 4350', 'Computer Science'), ('Database Systems', 'CSC 4710', 'Computer Science'),
           ('Linear Algebra', 'MATH 3435', 'Mathematics'), ('Intro to Psychology', 'PSYC 1101', 'Psychology'),
           ('Technical Writing', 'ENGL 3130', 'English')]


def _q(sql, args=()):
    return query(sql, args, commit=True)


def _fill(uid, display, bio, rnd):
    now = datetime.now().replace(second=0, microsecond=0)
    today = datetime(now.year, now.month, now.day)
    try:
        from helpers import COURSE_COLORS
    except Exception:
        COURSE_COLORS = [None] * 8
    cids = [_q('INSERT INTO usercourses (id, course_name, course_code, subject, color, branch_slot) VALUES (%s,%s,%s,%s,%s,%s)',
               (uid, n, c, s, COURSE_COLORS[i % len(COURSE_COLORS)], i)) for i, (n, c, s) in enumerate(COURSES)]
    labels = ['Lecture notes review', 'Problem set', 'Project work', 'Flashcards', 'Practice exam', 'Focus session']
    for d in range(200):  # 200-day streak: every badge, max plant stage, big coin balance
        for k in range(3):
            _q('INSERT INTO studysessions (user_id, course_id, label, minutes, started_at) VALUES (%s,%s,%s,%s,%s)',
               (uid, cids[(d + k) % 5], rnd.choice(labels), rnd.choice([25, 50, 90, 120, 200]),
                today - timedelta(days=d) + timedelta(hours=9 + k * 4)))
    tasks = [('Push login page fixes', 0, True), ('Write unit tests for calendar', 1, False), ('Normalize schema to 3NF', 1, True),
             ('ER diagram homework', 1, True), ('Practice eigenvalue problems', 2, False), ('Problem set 7', 2, True),
             ('Read chapter 9', 3, False), ('Chapter quiz review', 3, True), ('Draft memo outline', 4, True),
             ('Peer review essay', 4, False), ('Update sprint board', 0, True), ('Email TA about lab grade', None, True),
             ('Buy graph paper', None, False), ('Submit lab 3', 1, True), ('Office hours prep', 2, True), ('Flashcards ch. 7', 3, True), ('Fix CSS bug', 0, True)]
    for i, (n, ci, done) in enumerate(tasks):
        _q('INSERT INTO todolist (user_id, task_name, due_date, is_completed, course_id, progress, category) VALUES (%s,%s,%s,%s,%s,%s,%s)',
           (uid, n, date.today() + timedelta(days=i - 4), done, cids[ci] if ci is not None else None, 100 if done else 0, 'task'))
    for n, ci, p in [('Recursion', 0, 80), ('SQL joins', 1, 100), ('Eigenvectors', 2, 45), ('Classical conditioning', 3, 90), ('APA style', 4, 60)]:
        _q('INSERT INTO todolist (user_id, task_name, is_completed, course_id, progress, category) VALUES (%s,%s,%s,%s,%s,%s)',
           (uid, n, p >= 100, cids[ci], p, 'concept'))
    dl = [(0, 'Sprint 3 demo', -12), (0, 'Sprint 4 demo', 2), (0, 'Final project report', 30), (1, 'Homework 4', -8),
          (1, 'Midterm exam', 6), (2, 'Problem set 6', -5), (2, 'Quiz 4', 9), (3, 'Chapter 8 quiz', -3), (3, 'Research summary', 14),
          (4, 'Memo draft', -10), (4, 'Proposal', 11)]
    for ci, n, day in dl:
        when = today + timedelta(days=day, hours=23, minutes=59)
        _q('INSERT INTO coursedeadlines (course_id, deadline_name, deadline_date, is_completed) VALUES (%s,%s,%s,%s)',
           (cids[ci], n, when, day < 0 or day == 2))
        _q('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, is_ai_recommended) VALUES (%s,%s,%s,%s,%s)',
           (uid, n, when - timedelta(hours=1), 30, False))
    for wk in range(-3, 4):
        for dow, (n, hr) in {0: ('CSC 4350 Lecture', 11), 1: ('MATH 3435 Lecture', 9), 2: ('PSYC 1101 Lecture', 13),
                             3: ('CSC 4710 Lecture', 14), 4: ('ENGL 3130 Seminar', 10)}.items():
            _q('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, is_ai_recommended) VALUES (%s,%s,%s,%s,%s)',
               (uid, n, today - timedelta(days=today.weekday()) + timedelta(weeks=wk, days=dow, hours=hr), 75, False))
    for n, day, st in [('Study: Database Systems', -1, 'confirmed'), ('Study: Linear Algebra', 1, 'is_pending'), ('Study: Writing', 3, 'is_pending')]:
        _q('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, is_ai_recommended, flag_status) VALUES (%s,%s,%s,%s,%s,%s)',
           (uid, n, today + timedelta(days=day, hours=19), 90, True, st))
    for i, (n, cat, s, w) in enumerate([('Sprint 1', 'Project', 96, 10), ('Midterm', 'Exam', 93, 20), ('Homework 1', 'Assignment', 100, 5),
                                        ('Quiz 1', 'Quiz', 91, 10), ('Exam 1', 'Exam', 95, 25), ('Problem sets', 'Assignment', 98, 15),
                                        ('Chapter quizzes', 'Quiz', 97, 20), ('Essay 1', 'Assignment', 94, 15), ('Sprint 2', 'Project', 99, 10),
                                        ('Lab practical', 'Exam', 92, 20)]):
        _q('INSERT INTO grades (user_id, course_id, item_name, category, score, weight) VALUES (%s,%s,%s,%s,%s,%s)',
           (uid, cids[i % 5], n, cat, s, w))
    for k, (r, c) in enumerate([('user', 'Can you help me plan for my Database Systems midterm?'),
                                ('assistant', 'Sure! Let\'s split it into three 50-minute blocks: normalization, SQL joins, and transactions.'),
                                ('user', 'What should I focus on tonight?'),
                                ('assistant', 'Start with Sprint 4 demo prep, then a 25-minute review of eigenvectors.')]):
        _q('INSERT INTO chatmessages (user_id, role, content, created_at) VALUES (%s,%s,%s,%s)', (uid, r, c, now - timedelta(minutes=40 - k)))
    from profiles import CATALOG
    owned = list(CATALOG)
    for i, k in enumerate(owned):
        _q('INSERT INTO userinventory (user_id, item_key, price_paid, purchased_at) VALUES (%s,%s,%s,%s)', (uid, k, 0, now - timedelta(days=60 - i % 60)))
    pick = lambda t, d='': next((k for k, v in CATALOG.items() if v[0] == t and v[2] > 0), d)
    _q('INSERT INTO userprofiles (user_id, display_name, bio, pronouns, university, major, class_year, theme_key, frame_key, name_key, '
       'pinned_badges, pot_key, acc_keys, scene_key, plant_name, show_on_leaderboard) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
       (uid, display, bio, '', 'Georgia State University', 'Computer Science', '2027', pick('theme', 'theme_sky'), pick('frame'),
        pick('name'), 'streak7,twenty_hours,planner', 'pot_kintsugi' if 'pot_kintsugi' in CATALOG else pick('pot'),
        'acc_hat,acc_lights', pick('scene'), 'Oakley', 1))
    for d in range(60):
        _q('INSERT INTO plantcare (user_id, cared_on) VALUES (%s,%s)', (uid, date.today() - timedelta(days=d)))
    moods = ['great', 'good', 'okay', 'rough']
    for d in range(1, 15):
        _q('INSERT INTO journalentries (user_id, entry_date, mood, body, updated_at) VALUES (%s,%s,%s,%s,%s)',
           (uid, date.today() - timedelta(days=d), moods[d % 4], f'Day {d}: solid focus blocks, finished my task list.', now - timedelta(days=d)))
    try:
        from plant import plant_state, record_milestones
        record_milestones(uid, plant_state(uid))
    except Exception as e:
        print('pp_seed milestones:', e)


def run():
    pws = {'pp_admin': os.environ.get('PP_ADMIN_PW', ''), 'pp_student': os.environ.get('PP_STUDENT_PW', '')}
    if not all(pws.values()):
        return
    rnd = random.Random(42)
    ids = {}
    for u, role, disp, bio in [('pp_admin', 'admin', 'Project Pro Admin', 'Keeping the hive running.'),
                               ('pp_student', 'student', 'Pro Student', 'CS junior. Cold brew, lo-fi and 25-minute sprints.')]:
        r = query('SELECT id, password_hash FROM users WHERE username = %s', (u,))
        if r:
            ids[u] = r[0]['id']
            if not check_password_hash(r[0]['password_hash'] or '', pws[u]):
                _q('UPDATE users SET password_hash = %s WHERE id = %s', (generate_password_hash(pws[u]), ids[u]))
            continue
        uid = _q('INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,%s)',
                 (u, f'{u}@projectpro.app', generate_password_hash(pws[u]), role, datetime.now() - timedelta(days=210)))
        ids[u] = uid
        _fill(uid, disp, bio, rnd)
    a, s = ids['pp_admin'], ids['pp_student']
    if not query('SELECT 1 AS x FROM friendships WHERE user_lo = %s AND user_hi = %s', (min(a, s), max(a, s))):
        _q("INSERT INTO friendships (requester_id, addressee_id, user_lo, user_hi, status, created_at, accepted_at) "
           "VALUES (%s,%s,%s,%s,'accepted',%s,%s)", (s, a, min(a, s), max(a, s), datetime.now() - timedelta(days=30), datetime.now() - timedelta(days=29)))

if __name__ == '__main__':
    run()
