"""Seed demo accounts with realistic sample data.

    python seed_demo.py            # uses the configured DB (MySQL by default)
    PRODY_DB=sqlite python seed_demo.py

Creates (or resets) demo_student / Student123! and demo_admin / Admin123!.
"""
import random
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

from db import init_db
from user_courses import add_course
from helpers import COURSE_COLORS, query


def main():
    random.seed(7)
    init_db()
    now = datetime.now().replace(second=0, microsecond=0)
    today = datetime(now.year, now.month, now.day)


    def wipe(uid):
        from db import DB_BACKEND
        if DB_BACKEND == 'libsql':
            raise RuntimeError('refusing wipe on shared Turso/libSQL backend')
        for d in query('SELECT course_id FROM usercourses WHERE id = %s', (uid,)):
            query('DELETE FROM coursedeadlines WHERE course_id = %s', (d['course_id'],), commit=True)


    def user(username, email, pw, role):
        """Create or (on sqlite/mysql) reset a demo user. On libsql/Turso never wipe — return existing id."""
        from db import DB_BACKEND
        existing = query('SELECT id FROM users WHERE username = %s OR email = %s', (username, email), one=True)
        if existing:
            if DB_BACKEND == 'libsql':
                return existing['id']  # shared DB: keep existing demo user, never wipe
            wipe(existing['id'])
            query('DELETE FROM users WHERE username = %s OR email = %s', (username, email), commit=True)
        return query('INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,%s)',
                     (username, email, generate_password_hash(pw), role, now - timedelta(days=40)), commit=True)


    from db import DB_BACKEND as _SEED_BACKEND
    _had_student = bool(query('SELECT id FROM users WHERE username = %s', ('demo_student',), one=True))
    admin = user('demo_admin', 'admin@prody.app', 'Admin123!', 'admin')
    sid = user('demo_student', 'jordan@student.gsu.edu', 'Student123!', 'student')
    _SKIP_FILL = (_SEED_BACKEND == 'libsql' and _had_student)
    if _SKIP_FILL:
        print('seed_demo: demo users already on Turso; skipping refill (no wipe)')

    if not _SKIP_FILL:
        courses = [('Software Engineering', 'CSC 4350', 'Computer Science'), ('Database Systems', 'CSC 4710', 'Computer Science'),

                   ('Linear Algebra', 'MATH 3435', 'Mathematics'), ('Intro to Psychology', 'PSYC 1101', 'Psychology')]

        cids = []

        for i, (n, code, subj) in enumerate(courses):

            cids.append(add_course(sid, ('course_name', 'course_code', 'subject', 'color'), (n, code, subj, COURSE_COLORS[i])))



        deadlines = [(0, 'Sprint 4 demo', 1, 14), (0, 'Final project report', 12, 23), (1, 'ER diagram homework', 3, 23),

                     (1, 'Midterm exam', 6, 10), (2, 'Problem set 7', 2, 17), (2, 'Quiz 4', 8, 9), (3, 'Chapter 9 reading quiz', 4, 12),

                     (0, 'Peer evaluation', -3, 23)]

        for ci, name, day, hour in deadlines:

            when = today + timedelta(days=day, hours=hour)

            query('INSERT INTO coursedeadlines (course_id, deadline_name, deadline_date, is_completed) VALUES (%s,%s,%s,%s)',

                  (cids[ci], name, when, day < 0), commit=True)

            query('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, is_ai_recommended) VALUES (%s,%s,%s,%s,%s)',

                  (sid, name, when, 30, False), commit=True)



        # weekly class meetings + personal events for this month

        for wk in range(-3, 4):

            for dow, (name, hr) in {0: ('CSC 4350 Lecture', 11), 2: ('CSC 4350 Lecture', 11), 1: ('MATH 3435 Lecture', 9),

                                    3: ('CSC 4710 Lecture', 14), 4: ('Team stand-up', 16)}.items():

                d = today - timedelta(days=today.weekday()) + timedelta(weeks=wk, days=dow, hours=hr)

                query('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, is_ai_recommended) VALUES (%s,%s,%s,%s,%s)',

                      (sid, name, d, 75, False), commit=True)

        for name, day, hr in [('Gym with Sam', 0, 18), ('Career fair', 5, 10), ('Shift at library', 2, 13)]:

            query('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, is_ai_recommended) VALUES (%s,%s,%s,%s,%s)',

                  (sid, name, today + timedelta(days=day, hours=hr), 90, False), commit=True)

        # AI study blocks: one kept, two pending review

        for name, day, hr, status in [('Study: Database Systems – Midterm exam', -1, 19, 'confirmed'),

                                      ('Study: Linear Algebra – Problem set 7', 1, 19, 'is_pending'),

                                      ('Study: Database Systems – Midterm exam', 4, 18, 'is_pending')]:

            query('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, is_ai_recommended, flag_status) '

                  'VALUES (%s,%s,%s,%s,%s,%s)', (sid, name, today + timedelta(days=day, hours=hr), 90, True, status), commit=True)



        tasks = [('Push login page fixes', 0, 'task', 0, True), ('Write unit tests for calendar', 1, 'task', 0, False),

                 ('Email TA about lab grade', None, 'task', None, True), ('Read chapter 9', 3, 'task', 3, False),

                 ('Normalize schema to 3NF', 2, 'task', 1, True), ('Buy graph paper', None, 'task', None, True),

                 ('Practice eigenvalue problems', 2, 'task', 2, False), ('Update sprint board', -1, 'task', 0, False),

                 ('Recursion', None, 'concept', 0, 80), ('SQL joins', None, 'concept', 1, 65), ('Eigenvectors', None, 'concept', 2, 35),

                 ('Classical conditioning', None, 'concept', 3, 90), ('Design patterns', None, 'concept', 0, 50)]

        for name, due, cat, ci, state in tasks:

            prog = state if cat == 'concept' else (100 if state else 0)

            done = (state is True) if cat == 'task' else prog >= 100

            query('INSERT INTO todolist (user_id, task_name, due_date, is_completed, course_id, progress, category) VALUES (%s,%s,%s,%s,%s,%s,%s)',

                  (sid, name, (date.today() + timedelta(days=due)) if due is not None else None, done,

                   cids[ci] if ci is not None else None, prog, cat), commit=True)



        labels = ['Lecture notes review', 'Problem set', 'Project work', 'Flashcards', 'Practice exam']

        for back in range(0, 75):

            if back > 9 and random.random() < 0.35:

                continue

            for _ in range(random.randint(1, 3)):

                hr = random.choice([9, 10, 14, 15, 19, 20, 20, 21])

                mins = random.choice([25, 25, 25, 50, 50, 40])

                query('INSERT INTO studysessions (user_id, course_id, label, minutes, started_at) VALUES (%s,%s,%s,%s,%s)',

                      (sid, random.choice(cids), random.choice(labels), mins,

                       today - timedelta(days=back) + timedelta(hours=hr, minutes=random.randint(0, 40))), commit=True)



        grades = [(0, 'Sprint 1', 'Project', 94, 10), (0, 'Sprint 2', 'Project', 88, 10), (0, 'Midterm', 'Exam', 91, 20),

                  (1, 'Homework 1', 'Assignment', 100, 5), (1, 'Homework 2', 'Assignment', 85, 5), (1, 'Quiz 1', 'Quiz', 78, 10),

                  (2, 'Exam 1', 'Exam', 82, 25), (2, 'Problem set avg', 'Assignment', 90, 15), (3, 'Chapter quizzes', 'Quiz', 96, 20)]

        for ci, n, cat, s, w in grades:

            query('INSERT INTO grades (user_id, course_id, item_name, category, score, weight) VALUES (%s,%s,%s,%s,%s,%s)',

                  (sid, cids[ci], n, cat, s, w), commit=True)







        def profile(uid, name, bio, pronouns, major, year, theme, frame, namefx, pins, owned, paid=True,

                    pot='pot_terracotta', accs='', scene='', plant_name='Prody'):

            from profiles import CATALOG

            query('DELETE FROM userprofiles WHERE user_id = %s', (uid,), commit=True)

            query('INSERT INTO userprofiles (user_id, display_name, bio, pronouns, university, major, class_year, theme_key, '

                  'frame_key, name_key, pinned_badges, pot_key, acc_keys, scene_key, plant_name) '

                  'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',

                  (uid, name, bio, pronouns, 'Georgia State University', major, year, theme, frame, namefx, pins,

                   pot, accs, scene, plant_name), commit=True)

            for i, k in enumerate(dict.fromkeys(owned)):

                if CATALOG[k][2] == 0:

                    continue

                query('INSERT INTO userinventory (user_id, item_key, price_paid, purchased_at) VALUES (%s,%s,%s,%s)',

                      (uid, k, CATALOG[k][2] if paid else 0, now - timedelta(days=20 - i)), commit=True)





        profile(sid, 'Jordan Rivera', 'CS junior. Cold brew, lo-fi and 25-minute sprints.', 'they/them',

                'Computer Science', '2027', 'theme_peach', 'frame_mint', 'name_serif', 'streak7,twenty_hours,planner',

                ['theme_peach', 'frame_mint', 'name_serif', 'pot_wave', 'acc_hat', 'acc_sticker', 'scene_window'],

                pot='pot_wave', accs='acc_hat,acc_sticker', scene='scene_window', plant_name='Basil')

        profile(admin, 'Prody Admin', 'Keeping the hive running.', '', 'Staff', '', 'theme_ocean', 'frame_white', 'name_blue', '',

                ['theme_ocean', 'frame_white', 'name_blue'], paid=False)



        # classmates at different growth stages, for the leaderboard / profiles / admin list

        # name: (display, bio, pronouns, major, year, banner, frame, name fx, sessions, days idle, pot, accs, scene, plant)

        mates = {'maya_t': ('Maya Thompson', 'Bio major, future vet. Flashcards are my love language.', 'she/her', 'Biology', '2026',

                            'theme_holo', 'frame_rainbow', 'name_shimmer', 70, 0, 'pot_kintsugi', 'acc_lights,acc_butterfly',

                            'scene_greenhouse', 'Fern Gully'),

                 'dev_patel': ('Dev Patel', 'Math + coffee. Ask me about eigenvectors.', 'he/him', 'Mathematics', '2028',

                               'theme_galaxy', 'frame_flame', 'name_glow', 34, 1, 'pot_forest', 'acc_glasses', 'scene_desk', 'Euler'),

                 'chris.l': ('Chris Lee', 'Psych student trying to out-study my own procrastination.', '', 'Psychology', '2027',

                             'theme_mint', 'frame_mint', '', 9, 6, 'pot_terracotta', 'acc_scarf', '', 'Sprout'),

                 'ana_k': ('Ana Kim', 'First week on Prody. Be nice to my seed.', 'she/her', 'Economics', '2029',

                           'theme_sky', '', '', 2, 0, 'pot_speckle', '', '', 'Pip')}

        for name, (disp, bio, pr, major, yr, th, fr, nm, n, idle, pot, accs, scene, pname) in mates.items():

            uid = user(name, f'{name.replace(".", "")}@student.gsu.edu', 'Classmate123!', 'student')

            owned = [k for k in [th, fr, nm, pot, scene] + accs.split(',') if k]

            profile(uid, disp, bio, pr, major, yr, th, fr, nm, 'twenty_hours,five_hours,first_focus', owned, paid=False,

                    pot=pot, accs=accs, scene=scene, plant_name=pname)

            for back in range(n):

                query('INSERT INTO studysessions (user_id, label, minutes, started_at) VALUES (%s,%s,%s,%s)',

                      (uid, 'Focus session', random.choice([25, 50, 50]) if n > 2 else 25,

                       today - timedelta(days=idle + back // 2, hours=-15)), commit=True)



        # Maya is near the end of her course load, so her plant can reach the last stage

        maya = query("SELECT id FROM users WHERE username = 'maya_t'", one=True)['id']

        query('UPDATE users SET created_at = %s WHERE id = %s', (now - timedelta(days=105), maya), commit=True)

        for i, (n, code) in enumerate([('Genetics', 'BIOL 3800'), ('Organic Chemistry', 'CHEM 2400'), ('Animal Physiology', 'BIOL 4110')]):

            cid = add_course(maya, ('course_name', 'course_code', 'subject', 'color'), (n, code, 'Biology', COURSE_COLORS[i]))

            for k, day in enumerate((-80, -50, -20, 6)):

                query('INSERT INTO coursedeadlines (course_id, deadline_name, deadline_date, is_completed) VALUES (%s,%s,%s,%s)',

                      (cid, f'Unit {k + 1} exam', today + timedelta(days=day, hours=10), day < 0), commit=True)



        # record the growth milestones each plant has already reached

        from helpers import as_dt  # noqa: E402

        from plant import STAGES, growth_for, plant_state, stage_for  # noqa: E402



        for row in query("SELECT id, created_at FROM users WHERE role = 'student'"):

            uid = row['id']

            query('DELETE FROM plantmilestones WHERE user_id = %s', (uid,), commit=True)

            final = plant_state(uid)

            start = as_dt(row['created_at'])

            seen, hours = 0, 0.0

            for sess in query('SELECT minutes, started_at FROM studysessions WHERE user_id = %s ORDER BY started_at', (uid,)):

                when = as_dt(sess['started_at'])

                hours += int(sess['minutes']) / 60

                frac = max(0.0, min(1.0, (when - start) / (now - start))) if now > start else 1

                idx = stage_for(growth_for(hours, final['progress'] * frac))[0]

                for k in range(seen + 1, idx + 1):

                    query('INSERT INTO plantmilestones (user_id, stage, hours_at, reached_at) VALUES (%s,%s,%s,%s)',

                          (uid, STAGES[k][0], round(hours, 1), when), commit=True)

                seen = max(seen, idx)

        print('Seeded demo_student / Student123! and demo_admin / Admin123!')



        # Maxed-out tester accounts (prody_admin / prody_student)

        import seed_testers  # noqa: E402
        seed_testers.main()
    else:
        print("seed_demo: ready (shared Turso)")


if __name__ == '__main__':
    main()
