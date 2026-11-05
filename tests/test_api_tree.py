"""Tests for GET /api/tree (contract v0.5). Run: PRODY_DB=sqlite python3 -m pytest tests/test_api_tree.py"""
import os
import sys
import tempfile
from datetime import date, datetime, timedelta

_TMP = tempfile.mkdtemp(prefix='prody_api_tree_')
os.environ.setdefault('PRODY_DB', 'sqlite')
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(_TMP, 'prody_test.sqlite3'))  # fresh temp DB, never prody_dev
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

import app as prody_app  # noqa: E402  (init_db() runs migrations on the temp DB)
import api_tree  # noqa: E402
from helpers import query  # noqa: E402

TODAY = date(2026, 10, 23)
SEM_START, SEM_END = date(2026, 8, 24), date(2026, 12, 14)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api_tree, '_today', lambda: TODAY)
    prody_app.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return prody_app.app.test_client()


_n = [0]


def make_user(semester=True):
    _n[0] += 1
    uid = query('INSERT INTO users (username, email, password_hash, created_at) VALUES (%s, %s, %s, %s)',
                (f'u{_n[0]}', f'u{_n[0]}@t.test', 'x', datetime(2026, 8, 20)), commit=True)
    query('INSERT INTO userprofiles (user_id, semester_start, semester_end) VALUES (%s, %s, %s)',
          (uid, SEM_START if semester else None, SEM_END if semester else None), commit=True)
    return uid


def course(uid, slot, name='C'):
    return query('INSERT INTO usercourses (id, course_name, course_code, color, branch_slot) VALUES (%s, %s, %s, %s, %s)',
                 (uid, name, 'X 1', '#CFDCC6', slot), commit=True)


def deadline(cid, due, done=False, completed_at=None, grade_id=None, name='D'):
    return query('INSERT INTO coursedeadlines (course_id, deadline_name, deadline_date, is_completed, completed_at, grade_id) '
                 'VALUES (%s, %s, %s, %s, %s, %s)', (cid, name, datetime.combine(due, datetime.min.time()),
                                                     1 if done else 0, completed_at, grade_id), commit=True)


def task(uid, cid, done=False, completed_at=None):
    return query('INSERT INTO todolist (user_id, task_name, is_completed, course_id, completed_at) VALUES (%s, %s, %s, %s, %s)',
                 (uid, 'T', 1 if done else 0, cid, completed_at), commit=True)


def get(client, uid):
    with client.session_transaction() as s:
        s['user_id'] = uid
    r = client.get('/api/tree')
    assert r.status_code == 200, r.data[:300]
    return r.get_json()


# ---------------------------------------------------------------- auth
def test_auth_required(client):
    r = client.get('/api/tree')
    assert r.status_code == 401
    assert r.is_json and r.get_json()['error'] == 'unauthorized'
    assert 'Location' not in r.headers


def test_auth_401_no_flash(client):
    client.get('/api/tree')
    with client.session_transaction() as s:
        assert not s.get('_flashes')


# ---------------------------------------------------------------- pure rules
@pytest.mark.parametrize('p,d,exp', [(0, 0, 0.15), (1, 1, 1.0), (0.5, 0.5, 0.575), (0.52, 0.25, 0.15 + 0.85 * 0.385)])
def test_branch_length_formula(p, d, exp):
    assert api_tree.branch_length(p, d) == pytest.approx(exp, abs=1e-4)


@pytest.mark.parametrize('length,chain', [
    (0.15, ['base', 'mid1', 'tip_m1']), (0.2499, ['base', 'mid1', 'tip_m1']),
    (0.25, ['base', 'mid1', 'mid2', 'tip_m2']), (0.5, ['base', 'mid1', 'mid2', 'mid3', 'tip']),
    (0.75, ['base', 'mid1', 'mid_loop', 'mid2', 'mid3', 'tip']),
    (0.875, ['base', 'mid1', 'mid_loop', 'mid_loop', 'mid2', 'mid3', 'tip']),
    (1.0, ['base', 'mid1', 'mid_loop', 'mid_loop', 'mid_loop', 'mid2', 'mid3', 'tip'])])
def test_chain_by_length(length, chain):
    assert api_tree.chain_for(length) == chain


@pytest.mark.parametrize('idx,stage,scale,boost,clumps,art', [
    (0, 1, 1.0, False, 3, 0.6), (1, 1, 1.1, True, 5, 0.6), (2, 2, 1.0, False, 5, 0.8),
    (3, 2, 1.1, True, 7, 0.8), (4, 3, 1.0, False, 7, 1.0), (5, 3, 1.1, True, 8, 1.0)])
def test_stage_mapping(idx, stage, scale, boost, clumps, art):
    assert api_tree.stage_info(idx) == {'stage': stage, 'stage_scale': scale, 'stage_boost': boost,
                                        'canopy_clumps': clumps, 'art_scale': art}


def test_root_depth():
    assert api_tree.root_depth(-3, 50) == 0.0
    assert api_tree.root_depth(0, 50) == 0.0
    assert api_tree.root_depth(25, 50) == 0.5
    assert api_tree.root_depth(80, 50) == 1.0
    assert api_tree.root_depth(5, 0) == 1.0


# ---------------------------------------------------------------- endpoint
def test_cap_8_and_overflow(client):
    uid = make_user()
    for s in [3, 0, 7, 1, 2, 4, 5, 6]:
        course(uid, s, f'S{s}')
    course(uid, None, 'Extra')
    j = get(client, uid)
    assert [b['slot'] for b in j['branches']] == list(range(8))
    assert [b['kit']['slot'] for b in j['branches']] == list(range(1, 9))
    assert [b['side'] for b in j['branches'][:2]] == ['left', 'right']
    assert [o['name'] for o in j['overflow']] == ['Extra']
    assert j['kit_version'] == 'oak-kit-3'


def test_branch_length_and_chain_end_to_end(client):
    uid = make_user()
    cid = course(uid, 0)
    task(uid, cid, done=True); task(uid, cid); deadline(cid, TODAY + timedelta(days=5), done=True)
    deadline(cid, TODAY + timedelta(days=9))
    j = get(client, uid)
    prog = j['semester']['progress']
    assert prog == pytest.approx((TODAY - SEM_START).days / (SEM_END - SEM_START).days, abs=1e-3)
    b = j['branches'][0]
    assert b['length'] == pytest.approx(0.15 + 0.85 * (0.5 * prog + 0.25), abs=1e-3)
    assert b['kit']['chain'] == api_tree.chain_for(b['length']) and b['kit']['bend'] == 'ap0'


def test_bloom_fill_order_and_flowers_more(client):
    uid = make_user()
    cid = course(uid, 0)  # nothing open -> done_ratio 1 -> length >= 0.75 -> chain with loops
    t_new = task(uid, cid, True, datetime(2026, 10, 20, 9))
    t_old = task(uid, cid, True, datetime(2026, 9, 1, 9))
    nulls = [task(uid, cid, True, None) for _ in range(50)]
    j = get(client, uid)
    b = j['branches'][0]
    chain = b['kit']['chain']
    cap = 6 * (len(chain) - 1)
    assert len(b['flowers']) == cap and b['flowers_more'] == 52 - cap and b['flower_count'] == 52
    ids = [f['id'] for f in b['flowers']]
    assert ids[:3] == [f'task:{t_old}', f'task:{t_new}', f'task:{nulls[0]}']  # dated oldest first, then NULLs by id
    assert [f['bloom'] for f in b['flowers'][:8]] == [{'seg': 1, 'i': i} for i in range(6)] + [{'seg': 2, 'i': 0}, {'seg': 2, 'i': 1}]
    assert b['flowers'][-1]['bloom'] == {'seg': len(chain) - 1, 'i': 5}
    assert b['flowers'][0]['done_at'] == '2026-09-01' and b['flowers'][0]['piece'] == 'flower_task'


def test_roots_order_overdue_sockets_and_more(client):
    uid = make_user()
    cid = course(uid, 0)
    gid = query('INSERT INTO grades (user_id, course_id, item_name, score, weight) VALUES (%s, %s, %s, %s, %s)',
                (uid, cid, 'Unrelated name', 90, 25), commit=True)
    over = deadline(cid, TODAY - timedelta(days=2), grade_id=gid)
    future = [deadline(cid, TODAY + timedelta(days=k)) for k in range(1, 14)]  # 13 future
    deadline(cid, TODAY + timedelta(days=3), done=True)  # done: not a root
    j = get(client, uid)
    roots = j['roots']
    assert len(roots) == 12 and len(j['roots_more']) == 2
    assert roots[0]['deadline_id'] == over and roots[0]['overdue'] and roots[0]['depth'] == 0.0
    assert roots[0]['weight'] == 25.0 and roots[1]['weight'] is None  # linked by id only
    assert [r['days_left'] for r in roots] == [-2] + list(range(1, 12))
    assert [r['kit']['socket'] for r in roots] == [2, 3, 1, 4] * 3
    assert [r['kit']['angle'] for r in roots] == ['ap0'] * 4 + ['am12'] * 4 + ['ap12'] * 4
    dte = (SEM_END - TODAY).days
    assert roots[1]['depth'] == pytest.approx(1 / dte, abs=1e-3)
    assert roots[1]['kit']['scale'] == pytest.approx(0.35 + 0.65 * roots[1]['depth'], abs=1e-3)
    assert roots[0]['kit']['scale'] == 0.35
    assert all('kit' not in r for r in j['roots_more'])
    from collections import Counter
    assert max(Counter(r['kit']['socket'] for r in roots).values()) == 3


def test_stage_fields_and_park_present(client):
    uid = make_user(semester=False)  # fallback semester bounds
    course(uid, 0)
    j = get(client, uid)
    si = api_tree.stage_info(j['tree']['stage_idx'])
    for k, v in si.items():
        assert j[k] == v
    assert set(j['park']) >= {'layers', 'under_tree', 'visitor_slots', 'friends', 'owned_items', 'sky', 'sky_night'}
    assert j['semester']['start'] < j['semester']['end']


# ---------------------------------------------------------------- flower fixes (stopped sessions, undated, kind floor)
def sess(uid, cid, minutes, completed=0, started=datetime(2026, 10, 1, 9)):
    return query('INSERT INTO studysessions (user_id, course_id, label, minutes, started_at, completed) '
                 'VALUES (%s, %s, %s, %s, %s, %s)', (uid, cid, 'S', minutes, started, completed), commit=True)


def test_stopped_session_blooms_at_5_min(client):
    uid = make_user()
    cid = course(uid, 0)
    s5, s4, sfull = sess(uid, cid, 5), sess(uid, cid, 4), sess(uid, cid, 2, completed=1)
    ids = {f['id'] for f in get(client, uid)['branches'][0]['flowers']}
    assert f'focus:{s5}' in ids and f'focus:{sfull}' in ids and f'focus:{s4}' not in ids


def test_classless_session_on_longest_branch(client):
    uid = make_user()
    short = course(uid, 0, 'Short')
    deadline(short, TODAY + timedelta(days=5))  # open -> shorter branch
    long_ = course(uid, 1, 'Long')
    task(uid, long_, True, datetime(2026, 10, 1))
    s = sess(uid, None, 30)
    br = {b['course_id']: b for b in get(client, uid)['branches']}
    assert br[long_]['length'] > br[short]['length']
    assert f'focus:{s}' in {f['id'] for f in br[long_]['flowers']}
    assert f'focus:{s}' not in {f['id'] for f in br[short]['flowers']}


def test_undated_deadline_sorts_by_due_date(client):
    uid = make_user()
    cid = course(uid, 0)
    t = task(uid, cid, True, datetime(2026, 10, 10))
    d = deadline(cid, date(2026, 9, 5), done=True, completed_at=None)
    ids = [f['id'] for f in get(client, uid)['branches'][0]['flowers']]
    assert ids.index(f'deadline:{d}') < ids.index(f'task:{t}')


def test_every_kind_gets_a_bloom(client):
    uid = make_user()
    cid = course(uid, 0)
    for _ in range(60):
        task(uid, cid, True, datetime(2026, 9, 1))
    d = deadline(cid, date(2026, 10, 20), done=True, completed_at=datetime(2026, 10, 20))
    s = sess(uid, cid, 25, completed=1, started=datetime(2026, 10, 21))
    b = get(client, uid)['branches'][0]
    kinds = {f['kind'] for f in b['flowers']}
    assert {'task', 'deadline', 'focus'} <= kinds
    assert b['flower_count'] == 62 and len(b['flowers']) + b['flowers_more'] == 62
    ids = [f['id'] for f in b['flowers']]
    assert f'deadline:{d}' in ids and f'focus:{s}' in ids


# ---------------------------------------------------------------- NULL branch_slot fill (read time)
def test_all_null_slots_fill_lowest_in_creation_order(client):
    uid = make_user()
    cids = [course(uid, None, f'C{i}') for i in range(10)]
    j = get(client, uid)
    assert [(b['course_id'], b['slot']) for b in j['branches']] == [(c, i) for i, c in enumerate(cids[:8])]
    assert [o['course_id'] for o in j['overflow']] == cids[8:]
    assert query('SELECT COUNT(*) AS n FROM usercourses WHERE id = %s AND branch_slot IS NULL', (uid,), one=True)['n'] == 2  # 8 saved, overflow stays NULL


def test_null_slots_keep_existing_slots(client):
    uid = make_user()
    a = course(uid, None, 'A')
    b = course(uid, 0, 'B')
    c = course(uid, 2, 'C')
    d = course(uid, None, 'D')
    slots = {x['course_id']: x['slot'] for x in get(client, uid)['branches']}
    assert slots == {b: 0, c: 2, a: 1, d: 3}


# ---------------------------------------------------------------- saved slots + session fallback
def test_null_slot_saved_then_new_class_no_swap(client):
    import user_courses
    uid = make_user()
    old = course(uid, None, 'Old')
    before = {b['course_id']: b['slot'] for b in get(client, uid)['branches']}
    assert before == {old: 0}
    assert query('SELECT branch_slot FROM usercourses WHERE course_id = %s', (old,), one=True)['branch_slot'] == 0
    new = user_courses.add_course(uid, ('course_name', 'course_code', 'color'), ('New', 'N 1', '#CFDCC6'))
    after = {b['course_id']: b['slot'] for b in get(client, uid)['branches']}
    assert after == {old: 0, new: 1}


def test_new_class_before_any_read_does_not_steal_null_slot(client):
    import user_courses
    uid = make_user()
    old = course(uid, None, 'Old')
    new = user_courses.add_course(uid, ('course_name', 'course_code', 'color'), ('New', 'N 1', '#CFDCC6'))
    assert {b['course_id']: b['slot'] for b in get(client, uid)['branches']} == {old: 0, new: 1}


def test_fill_is_idempotent(client):
    import user_courses
    uid = make_user()
    for i in range(3):
        course(uid, None, f'C{i}')
    assert user_courses.save_null_slots(uid) == 3
    assert user_courses.save_null_slots(uid) == 0


def test_overflow_or_deleted_class_session_goes_to_longest(client):
    uid = make_user()
    cids = [course(uid, i, f'C{i}') for i in range(8)]
    task(uid, cids[3], True, datetime(2026, 10, 1))  # C3 longest
    for c in cids:
        if c != cids[3]:
            deadline(c, TODAY + timedelta(days=5))
    extra = course(uid, None, 'Extra')  # 9th -> overflow
    s_over = sess(uid, extra, 30)
    s_gone = sess(uid, 999999, 30)  # deleted class
    br = {b['course_id']: b for b in get(client, uid)['branches']}
    ids = {f['id'] for f in br[cids[3]]['flowers']}
    assert f'focus:{s_over}' in ids and f'focus:{s_gone}' in ids


def test_ghost_session_gets_401(client):
    with client.session_transaction() as s:
        s['user_id'] = 987654321  # no such user
    r = client.get('/api/tree')
    assert r.status_code == 401 and r.get_json() == {'error': 'unauthorized', 'login': '/login'}
    with client.session_transaction() as s:
        assert 'user_id' not in s


def test_tap_sheet_fields(client):
    uid = make_user()
    cid = course(uid, 0, 'Bio')
    tid = task(uid, cid, done=True, completed_at=datetime(2026, 10, 2, 9))
    did = deadline(cid, TODAY + timedelta(days=10), name='Essay')
    sess(uid, cid, 25, completed=1)
    sess(uid, cid, 7, completed=0)
    data = get(client, uid)
    b = data['branches'][0]
    assert b['class_id'] == cid == b['course_id']
    assert b['class_url'].endswith(f'#course-{cid}')
    fl = {f['kind']: f for f in b['flowers']}
    assert fl['task']['task_id'] == tid and fl['task']['title'] == 'T' and fl['task']['status'] == 'done'
    assert {f['status'] for f in b['flowers'] if f['kind'] == 'focus'} == {'completed', 'stopped_early'}
    assert all(f['task_id'] is None for f in b['flowers'] if f['kind'] == 'focus')
    r = next(r for r in data['roots'] if r['deadline_id'] == did)
    assert r['due_date'] == r['due'] == (TODAY + timedelta(days=10)).isoformat() and r['days_left'] == 10


def test_tap_fields_isolated_between_users(client):
    a, b = make_user(), make_user()
    ca, cb = course(a, 0, 'A'), course(b, 0, 'B')
    ta, tb = task(a, ca, done=True), task(b, cb, done=True)
    deadline(ca, TODAY + timedelta(days=3)); deadline(cb, TODAY + timedelta(days=3))
    for me, other_c, other_t in ((a, cb, tb), (b, ca, ta)):
        d = get(client, me)
        assert other_c not in {br['class_id'] for br in d['branches']}
        assert other_t not in {f['task_id'] for br in d['branches'] for f in br['flowers']}
        assert other_c not in {r['course_id'] for r in d['roots']}


@pytest.mark.parametrize('key,exp', [(None, 'default'), ('species_classic', 'default'), ('species_default', 'default'),
                                     ('species_cherry', 'cherry_blossom'), ('species_maple', 'maple'),
                                     ('species_olive', 'olive'), ('species_bogus', 'default')])
def test_flower_species(client, key, exp):
    uid = make_user()
    query('UPDATE userprofiles SET species_key = %s WHERE user_id = %s', (key, uid), commit=True)
    cid = course(uid, 0)
    task(uid, cid, done=True, completed_at=datetime(2026, 10, 2, 9))
    task(uid, cid)
    b = get(client, uid)['branches'][0]
    assert {f['species'] for f in b['flowers'] + b['buds']} == {exp}


def test_open_tasks_are_buds(client):
    uid = make_user()
    cid = course(uid, 0)
    done = task(uid, cid, done=True, completed_at=datetime(2026, 10, 2, 9))
    t1 = query('INSERT INTO todolist (user_id, task_name, is_completed, course_id, due_date) VALUES (%s, %s, 0, %s, %s)',
               (uid, 'Read ch 4', cid, TODAY + timedelta(days=3)), commit=True)
    t2 = task(uid, cid)  # no due date
    b = get(client, uid)['branches'][0]
    buds = {x['task_id']: x for x in b['buds']}
    assert set(buds) == {t1, t2} and done not in buds
    assert buds[t1] == {'id': f'task:{t1}', 'kind': 'task', 'task_id': t1, 'title': 'Read ch 4', 'status': 'pending',
                        'species': 'default', 'due': (TODAY + timedelta(days=3)).isoformat()}
    assert buds[t2]['due'] is None
    assert all(f['status'] != 'pending' for f in b['flowers'])


def test_classless_tasks_on_trunk(client):
    uid = make_user()
    cid = course(uid, 0)
    open_t = query('INSERT INTO todolist (user_id, task_name, is_completed, course_id, due_date) VALUES (%s, %s, 0, NULL, %s)',
                   (uid, 'Loose', TODAY + timedelta(days=5)), commit=True)
    done_t = task(uid, None, done=True, completed_at=datetime(2026, 10, 3, 9))
    task(uid, cid)
    d = get(client, uid)
    assert d['trunk_buds'] == [{'id': f'task:{open_t}', 'kind': 'task', 'task_id': open_t, 'title': 'Loose',
                                'status': 'pending', 'species': 'default', 'due': (TODAY + timedelta(days=5)).isoformat()}]
    assert [(f['task_id'], f['status'], f['done_at']) for f in d['trunk_flowers']] == [(done_t, 'done', '2026-10-03')]
    on_branches = {x['task_id'] for b in d['branches'] for x in b['flowers'] + b['buds']}
    assert open_t not in on_branches and done_t not in on_branches


def _t(done=False, due=None, completed_at=None):
    return {'is_completed': 1 if done else 0, 'due_date': due, 'completed_at': completed_at}


D = lambda n: datetime.combine(TODAY + timedelta(days=n), datetime.min.time())  # noqa: E731
MON = datetime(2026, 10, 19, 8)  # week of TODAY (Fri 2026-10-23) starts Monday 10-19


@pytest.mark.parametrize('todos,exp', [
    ([], 'steady'),
    ([_t(due=D(-1)), _t(due=D(0)), _t(due=D(2))], 'tired'),                    # overdue + today + 48h edge
    ([_t(due=D(1)), _t(due=D(2)), _t(due=D(3))], 'steady'),                     # only 2 within 48h
    ([_t(due=D(1)), _t(due=D(1)), _t(due=D(2)), _t(done=True, completed_at=MON)], 'tired'),  # tired beats thriving
    ([_t(due=D(-5)), _t(due=D(-4)), _t(due=D(-3))], 'tired'),
    ([_t(done=True, due=D(-1)), _t(done=True, due=D(-1)), _t(done=True, due=D(0), completed_at=MON)], 'thriving'),  # done ones don't count
    ([_t(done=True, completed_at=MON)], 'thriving'),                             # Monday boundary
    ([_t(done=True, completed_at=MON - timedelta(hours=9))], 'steady'),          # Sunday before: last week
    ([_t(done=True, completed_at=datetime(2026, 10, 23, 23, 59))], 'thriving'),  # today
    ([_t(done=True, completed_at=MON), _t(due=D(-1))], 'steady'),               # one overdue blocks thriving
    ([_t(done=True, completed_at=MON), _t(due=D(0))], 'thriving'),              # due today is not overdue
    ([_t(done=True, completed_at=MON), _t(), _t(), _t()], 'thriving'),          # no due date never counts
])
def test_tree_mood_rules(todos, exp):
    from api_tree import tree_mood
    assert tree_mood(todos, TODAY) == exp


def test_mood_in_feed(client):
    uid = make_user()
    cid = course(uid, 0)
    assert get(client, uid)['mood'] == 'steady'
    task(uid, cid, done=True, completed_at=datetime(2026, 10, 21, 10))
    assert get(client, uid)['mood'] == 'thriving'
    for n in (-1, 1, 2):
        query('INSERT INTO todolist (user_id, task_name, is_completed, course_id, due_date) VALUES (%s, %s, 0, NULL, %s)',
              (uid, 'x', TODAY + timedelta(days=n)), commit=True)
    assert get(client, uid)['mood'] == 'tired'


def _d(done=False, due=None):
    return {'is_completed': 1 if done else 0, 'deadline_date': due}


@pytest.mark.parametrize('todos,dls,exp', [
    ([], [_d(due=D(-1)), _d(due=D(0)), _d(due=D(2))], 'tired'),                     # deadlines alone
    ([_t(due=D(1))], [_d(due=D(-2)), _d(due=D(2))], 'tired'),                       # mixed tasks + deadlines
    ([], [_d(due=D(1)), _d(due=D(2)), _d(due=D(3))], 'steady'),                     # 3rd is past 48h
    ([_t(done=True, completed_at=MON)], [_d(due=D(-1))], 'steady'),                 # overdue deadline blocks thriving
    ([_t(done=True, completed_at=MON)], [_d(due=D(0))], 'thriving'),                # due today isn't overdue
    ([_t(done=True, completed_at=MON)], [_d(done=True, due=D(-1))] * 3, 'thriving'),  # finished deadlines ignored
    ([_t(done=True, completed_at=MON)], [_d(), _d(), _d()], 'thriving'),            # undated never count
])
def test_tree_mood_deadlines(todos, dls, exp):
    from api_tree import tree_mood
    assert tree_mood(todos, TODAY, dls) == exp


def test_mood_feed_counts_deadlines(client):
    uid = make_user()
    cid = course(uid, 0)
    task(uid, cid, done=True, completed_at=datetime(2026, 10, 21, 10))
    deadline(cid, TODAY - timedelta(days=1))
    assert get(client, uid)['mood'] == 'steady'
    deadline(cid, TODAY + timedelta(days=1)); deadline(cid, TODAY + timedelta(days=2))
    assert get(client, uid)['mood'] == 'tired'


def test_open_dated_class_tasks_are_roots(client):
    uid = make_user()
    cid = course(uid, 0)
    deadline(cid, TODAY + timedelta(days=9), name='Exam')
    def t(name, due, done=False, c=cid):
        return query('INSERT INTO todolist (user_id, task_name, due_date, is_completed, course_id) VALUES (%s, %s, %s, %s, %s)',
                     (uid, name, due, done, c), commit=True)
    open_id = t('Open dated', (TODAY + timedelta(days=4)).isoformat())
    t('Done dated', (TODAY + timedelta(days=5)).isoformat(), done=True)
    t('Undated', None)
    t('Classless dated', (TODAY + timedelta(days=6)).isoformat(), c=None)
    roots = get(client, uid)['roots']
    names = [r['name'] for r in roots]
    assert names == ['Open dated', 'Exam']
    r = roots[0]
    assert r['task_id'] == open_id and r['kind'] == 'task' and r['course_id'] == cid and r['days_left'] == 4


def test_api_tree_and_roots_data_share_root_set(client):
    uid = make_user()
    cid = course(uid, 0)
    deadline(cid, TODAY + timedelta(days=9), name='Exam')
    query('INSERT INTO todolist (user_id, task_name, due_date, is_completed, course_id) VALUES (%s, %s, %s, %s, %s)',
          (uid, 'Open dated', (TODAY + timedelta(days=4)).isoformat(), False, cid), commit=True)
    query('INSERT INTO todolist (user_id, task_name, due_date, is_completed, course_id) VALUES (%s, %s, %s, %s, %s)',
          (uid, 'Done dated', (TODAY + timedelta(days=5)).isoformat(), True, cid), commit=True)
    j = get(client, uid)
    tree = {(r['deadline_id'], r['name']) for r in j['roots'] + (j.get('roots_more') or [])}
    r = client.get('/roots/data')
    assert r.status_code == 200, r.data[:300]
    rd = {(x['deadline_id'], x['name']) for x in r.get_json()['roots']}
    assert tree == rd and {n for _, n in tree} == {'Exam', 'Open dated'}
