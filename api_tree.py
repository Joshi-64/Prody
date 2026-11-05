"""GET /api/tree: read-only JSON feed for the oak tree (docs/api_tree_contract.md, v0.5, oak-kit-3)."""
import apptime
import math
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, session, url_for

from helpers import as_dt, login_required, query

api_tree_bp = Blueprint('api_tree_bp', __name__)

KIT_VERSION = 'oak-kit-3'
MAX_BRANCHES = 8
BLOOMS_PER_PIECE = 6
ROOT_SOCKETS = [2, 3, 1, 4]          # inner, then outer, alternating sides
ROOT_ANGLES = ['ap0', 'am12', 'ap12']  # one pass per angle
MAX_ROOTS = len(ROOT_SOCKETS) * len(ROOT_ANGLES)  # 12, 3 per socket
CLUMPS = {0: 3, 1: 5, 2: 5, 3: 7, 4: 7, 5: 8}
ART_SCALE = {1: 0.6, 2: 0.8, 3: 1.0}
KIND_ORDER = {'task': 0, 'deadline': 1, 'focus': 2}


def _today():
    return apptime.today_local()


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _d(v):
    dt = as_dt(v)
    return dt.date() if dt else None


# ------------------------------------------------------------ pure rules (unit-tested)
def branch_length(progress, done_ratio):
    return round(0.15 + 0.85 * clamp(0.5 * progress + 0.5 * done_ratio), 4)


def chain_for(length):
    if length < 0.25:
        return ['base', 'mid1', 'tip_m1']
    if length < 0.5:
        return ['base', 'mid1', 'mid2', 'tip_m2']
    if length < 0.75:
        return ['base', 'mid1', 'mid2', 'mid3', 'tip']
    loops = min(3, 1 + int(math.floor((length - 0.75) / 0.125 + 1e-9)))
    return ['base', 'mid1'] + ['mid_loop'] * loops + ['mid2', 'mid3', 'tip']


def stage_info(stage_idx):
    idx = int(clamp(stage_idx or 0, 0, 5))
    art = idx // 2 + 1
    boost = idx % 2 == 1
    return {'stage': art, 'stage_scale': 1.1 if boost else 1.0, 'stage_boost': boost,
            'canopy_clumps': CLUMPS[idx], 'art_scale': ART_SCALE[art]}


def dated_task_roots(todos, known_course_ids, today):
    """Shared root rule (/api/tree and /roots/data): every open todo with a due date on a known class is a root,
    alongside open course deadlines. Task roots use deadline_id = -task_id so ids never collide."""
    out = []
    for t in todos:
        due = _d(t.get('due_date')) if t.get('due_date') else None
        if t.get('is_completed') or not due or t.get('course_id') not in known_course_ids:
            continue
        out.append({'deadline_id': -int(t['task_id']), 'task_id': t['task_id'], 'course_id': t['course_id'], 'name': t['task_name'],
                    'due': due.isoformat(), 'days_left': (due - today).days, 'kind': 'task', 'actions': {}})
    return out



def root_depth(days_left, days_to_end):
    if days_left < 0:
        return 0.0
    if days_to_end <= 0:
        return 1.0
    return round(clamp(days_left / days_to_end), 3)


MIN_BLOOM_MINUTES = 5


def place_flowers(flowers, chain):
    """Keep the newest (cap) finished items, drawn oldest first; undated ones use their fallback date (deadline_date / started_at), still-undated last.
    Every kind present gets at least one bloom point; the rest fill 6 per non-base piece."""
    def key(f):
        t = f.get('_t') or f.get('_f')
        return (t is None, t or datetime.min, KIND_ORDER.get(f['kind'], 9), f['_n'])
    # pick newest first so trimming drops the OLDEST finished work and the newest bloom always survives;
    # the placed ones are re-sorted oldest first for drawing below
    def newest(f):
        t = f.get('_t') or f.get('_f')
        return (t is None, -(t.timestamp()) if t else 0, KIND_ORDER.get(f['kind'], 9), f['_n'])
    ordered = sorted(flowers, key=newest)
    cap = BLOOMS_PER_PIECE * (len(chain) - 1)
    placed, rest = ordered[:cap], ordered[cap:]
    for kind in sorted({f['kind'] for f in ordered}, key=lambda k: KIND_ORDER.get(k, 9)):
        if cap <= 0 or any(f['kind'] == kind for f in placed):
            continue
        counts = {}
        for f in placed:
            counts[f['kind']] = counts.get(f['kind'], 0) + 1
        victim = next((f for f in reversed(placed) if counts[f['kind']] > 1), None)
        if victim is None:
            continue
        newcomer = next(f for f in rest if f['kind'] == kind)
        placed.remove(victim); rest.remove(newcomer)
        placed.append(newcomer); rest.append(victim)
    placed.sort(key=key)
    for n, f in enumerate(placed):
        f['bloom'] = {'seg': 1 + n // BLOOMS_PER_PIECE, 'i': n % BLOOMS_PER_PIECE}
        f['pos'] = round((1 + n // BLOOMS_PER_PIECE) / (len(chain) - 1), 3)
    return placed, len(rest)


def assign_roots(roots):
    """Overdue first, then days_left asc; first 12 get a kit piece, rest -> roots_more."""
    ordered = sorted(roots, key=lambda r: (not r['overdue'], r['days_left'], r['deadline_id']))
    drawn = ordered[:MAX_ROOTS]
    for i, r in enumerate(drawn):
        r['kit'] = {'socket': ROOT_SOCKETS[i % 4], 'angle': ROOT_ANGLES[i // 4],
                    'scale': round(0.35 + 0.65 * r['depth'], 3)}
    return drawn, ordered[MAX_ROOTS:]


# ------------------------------------------------------------ data
_COLS = {}


def _columns(table):
    """Cached per process (schema only changes at boot via init_db); failures aren't cached."""
    if table in _COLS:
        return _COLS[table]
    got = _columns_uncached(table)
    if got:
        _COLS[table] = got
    return got


def _columns_uncached(table):
    try:
        from db import _columns as cols, get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            return cols(cur, table)
        finally:
            cur.close()
            conn.close()
    except Exception:
        return set()


def _semester(uid, today, dls):
    """Stored userprofiles.semester_start/end, else the plant.py fallback (sign-up / first deadline - 7d -> last deadline, or +16 weeks)."""
    start = end = None
    try:
        from plant import semester_bounds
        start, end = semester_bounds(uid)
    except Exception:
        pass
    start, end = _d(start), _d(end)
    if not (start and end and end > start):
        u = query('SELECT created_at FROM users WHERE id = %s', (uid,), one=True) or {}
        dates = [as_dt(d['deadline_date']) for d in dls if as_dt(d['deadline_date'])]
        s = as_dt(u.get('created_at')) or datetime.combine(today, datetime.min.time())
        if dates:
            s = min(s, min(dates) - timedelta(days=7))
        e = max(dates) if dates else s + timedelta(weeks=16)
        if e <= s + timedelta(days=14):
            e = s + timedelta(weeks=16)
        start, end = start or s.date(), end if (end and end > (start or s.date())) else e.date()
    progress = clamp((today - start).days / max(1, (end - start).days))
    return start, end, round(progress, 3)


SPECIES_OUT = {'species_cherry': 'cherry_blossom', 'species_cherry_blossom': 'cherry_blossom',
               'species_maple': 'maple', 'species_olive': 'olive',
               'species_pine': 'pine'}


def tree_species(key):
    """userprofiles.species_key -> flower species; anything else (classic/default/unknown/NULL) -> 'default'."""
    return SPECIES_OUT.get(key or '', 'default')


TIRED_MIN = 3          # open tasks overdue or due within 48h
DUE_SOON_DAYS = 2      # date-only due dates: due <= today + 2 days counts as "within 48h"


def tree_mood(todos, today, dls=()):
    """tired: >= 3 open tasks overdue or due within 48h; thriving: none overdue and >= 1 task completed this
    week (Monday..today); else steady. Tasks without a due date never count as overdue / due soon.
    Open class deadlines (exams/assignments) count exactly like open tasks for tired and for blocking thriving."""
    open_due = [as_dt(t.get('due_date')).date() for t in todos if not t['is_completed'] and as_dt(t.get('due_date'))]
    open_due += [as_dt(d.get('deadline_date')).date() for d in dls
                 if not d['is_completed'] and as_dt(d.get('deadline_date'))]
    if sum(1 for d in open_due if d <= today + timedelta(days=DUE_SOON_DAYS)) >= TIRED_MIN:
        return 'tired'
    week_start = today - timedelta(days=today.weekday())
    done_week = any(t['is_completed'] and as_dt(t.get('completed_at')) and
                    week_start <= as_dt(t['completed_at']).date() <= today for t in todos)
    if not any(d < today for d in open_due) and done_week:
        return 'thriving'
    return 'steady'


def _bud(t, species):
    due = as_dt(t.get('due_date'))
    return {'id': f"task:{t['task_id']}", 'kind': 'task', 'task_id': t['task_id'], 'title': t['task_name'],
            'status': 'pending', 'species': species, 'due': due.date().isoformat() if due else None}


def build_tree(uid, today=None):
    today = today or _today()
    from profiles import _deepen, get_profile, owned_keys, park_scene, sky_key_of, DEFAULT_SKY, DEFAULT_SKY_NIGHT, PARK_ITEMS
    import plant

    has_slot = 'branch_slot' in _columns('usercourses')
    has_gid = 'grade_id' in _columns('coursedeadlines')
    has_tdone = 'completed_at' in _columns('todolist')
    has_ddone = 'completed_at' in _columns('coursedeadlines')
    has_tdue = 'due_date' in _columns('todolist')
    prof = get_profile(uid) or {}
    species = tree_species(prof.get('species_key'))

    if has_slot:  # save slots for NULL-slot classes (same order as init_db / read-time fill below)
        from user_courses import save_null_slots
        save_null_slots(uid)
    courses = query('SELECT course_id, course_name, course_code, color%s FROM usercourses WHERE id = %%s ORDER BY course_id'
                    % (', branch_slot' if has_slot else ''), (uid,)) or []
    __import__('helpers').fill_display_colours(courses, uid)  # r10: NULL/empty colours use the same order-based display fill as every other page (no DB write)
    ids = [c['course_id'] for c in courses]
    dls = []
    if ids:
        ph = ','.join(['%s'] * len(ids))
        dls = query(f"SELECT deadline_id, course_id, deadline_name, deadline_date, is_completed"
                    f"{', completed_at' if has_ddone else ''}{', grade_id' if has_gid else ''} "
                    f"FROM coursedeadlines WHERE course_id IN ({ph})", tuple(ids)) or []
    todos = query(f"SELECT task_id, course_id, task_name, is_completed{', completed_at' if has_tdone else ''}{', due_date' if has_tdue else ''} "
                  "FROM todolist WHERE user_id = %s", (uid,)) or []
    sess = query('SELECT session_id, course_id, label, minutes, started_at, completed FROM studysessions WHERE user_id = %s',
                 (uid,)) or []
    weights = {}
    if has_gid:  # weight only via the grade linked by id; no name matching
        weights = {g['grade_id']: float(g['weight']) for g in
                   (query('SELECT grade_id, weight FROM grades WHERE user_id = %s', (uid,)) or [])}

    sem_start, sem_end, progress = _semester(uid, today, dls)
    st = plant.plant_state(uid, today)
    sinfo = stage_info(st['stage_idx'])

    # ---- branches: stored slot 0..7 first; NULL / duplicate / extra -> overflow
    drawn, overflow, used = [], [], set()
    for c in sorted(courses, key=lambda c: (c.get('branch_slot') is None, c.get('branch_slot') or 0, c['course_id'])):
        s = c.get('branch_slot')
        if s is not None and 0 <= int(s) < MAX_BRANCHES and int(s) not in used:
            used.add(int(s)); c['_slot'] = int(s); drawn.append(c)
        else:
            overflow.append(c)
    # NULL slot (pre-migration / direct DB rows): lowest free slot, oldest class first. Read-time only, no writes.
    for c in sorted([c for c in overflow if c.get('branch_slot') is None], key=lambda c: c['course_id']):
        free = next((i for i in range(MAX_BRANCHES) if i not in used), None)
        if free is None:
            break
        used.add(free); c['_slot'] = free; drawn.append(c); overflow.remove(c)
    if not has_slot:  # pre-migration: query order
        drawn, overflow = courses[:MAX_BRANCHES], courses[MAX_BRANCHES:]
        for i, c in enumerate(drawn):
            c['_slot'] = i
    drawn.sort(key=lambda c: c['_slot'])

    # sessions whose class is in overflow or deleted count as classless -> longest branch
    drawn_ids = {c['course_id'] for c in drawn}
    for s in sess:
        s['_cid'] = s['course_id'] if s['course_id'] in drawn_ids else None

    mins = {}
    for s in sess:
        mins[s['course_id']] = mins.get(s['course_id'], 0) + int(s['minutes'] or 0)

    def _len(c):
        c_all = [x for x in todos + dls if x['course_id'] == c['course_id']]
        return branch_length(progress, sum(1 for x in c_all if x['is_completed']) / len(c_all) if c_all else 0.0)
    # classless sessions bloom on the longest drawn branch (ties: lowest slot)
    longest = max(drawn, key=lambda c: (_len(c), -c['_slot']))['course_id'] if drawn else None

    branches = []
    for n, c in enumerate(drawn):
        cid = c['course_id']
        c_t = [t for t in todos if t['course_id'] == cid]
        c_d = [d for d in dls if d['course_id'] == cid]
        total = len(c_t) + len(c_d)
        done = sum(1 for x in c_t + c_d if x['is_completed'])
        length = branch_length(progress, done / total if total else 0.0)
        chain = chain_for(length)
        fl = []
        for t in c_t:
            if t['is_completed']:
                fl.append({'id': f"task:{t['task_id']}", 'kind': 'task', 'label': t['task_name'],
                           'task_id': t['task_id'], 'title': t['task_name'], 'status': 'done',
                           '_t': as_dt(t.get('completed_at')), '_n': t['task_id']})
        for d in c_d:
            if d['is_completed']:
                fl.append({'id': f"deadline:{d['deadline_id']}", 'kind': 'deadline', 'label': d['deadline_name'],
                           'task_id': None, 'deadline_id': d['deadline_id'], 'title': d['deadline_name'], 'status': 'done',
                           '_t': as_dt(d.get('completed_at')), '_f': as_dt(d.get('deadline_date')),
                           '_n': d['deadline_id']})
        for s in sess:
            # full timer, or stopped early after >= MIN_BLOOM_MINUTES
            if (s['_cid'] or longest) == cid and (s.get('completed') or int(s['minutes'] or 0) >= MIN_BLOOM_MINUTES):
                t0 = as_dt(s['started_at'])
                fl.append({'id': f"focus:{s['session_id']}", 'kind': 'focus', 'label': s.get('label') or 'Focus session',
                           'task_id': None, 'session_id': s['session_id'], 'title': s.get('label') or 'Focus session',
                           'status': 'completed' if s.get('completed') else 'stopped_early',
                           '_t': t0 + timedelta(minutes=int(s['minutes'] or 0)) if t0 else None, '_f': t0,
                           '_n': s['session_id']})
        for f in fl:
            f['species'] = species
        buds = [_bud(t, species) for t in c_t if not t['is_completed']]
        total_fl = len(fl)
        placed, more = place_flowers(fl, chain)
        for f in placed:
            f['done_at'] = apptime.local_date(f['_t']).isoformat() if f['_t'] else None
            f['piece'] = 'flower_' + f['kind']
            f.pop('_f', None); del f['_t'], f['_n']
        slot = c['_slot']
        branches.append({
            'course_id': cid, 'class_id': cid,
            'class_url': url_for('user_courses_bp.add_courses') + f'#course-{cid}', 'name': c['course_name'], 'code': c.get('course_code') or '', 'color': c['color'],
            'dot': _deepen(c['color']), 'slot': slot, 'side': 'left' if slot % 2 == 0 else 'right',
            'length': length, 'minutes': mins.get(cid, 0), 'leaves': mins.get(cid, 0) // 60,
            'flower_count': total_fl, 'flowers': placed, 'flowers_more': more, 'buds': buds,
            'kit': {'slot': slot + 1, 'bend': 'ap0', 'chain': chain,
                    'clump': f'canopy_clump_{slot + 1}' if n < sinfo['canopy_clumps'] else None},
        })

    # ---- roots: all open deadlines
    days_to_end = (sem_end - today).days
    roots = []
    for d in dls:
        if d['is_completed']:
            continue
        due = _d(d['deadline_date'])
        if due is None:  # no/unparseable date: can't place a root, and (None - today) would 500
            continue
        left = (due - today).days
        win = min(due, today) - timedelta(days=14)
        studied = sum(int(s['minutes'] or 0) for s in sess
                      if s['course_id'] == d['course_id'] and _d(s['started_at']) and win <= apptime.local_date(as_dt(s['started_at'])) <= today)
        roots.append({'deadline_id': d['deadline_id'], 'course_id': d['course_id'], 'name': d['deadline_name'],
                      'due': due.isoformat(), 'due_date': due.isoformat(), 'days_left': left, 'depth': root_depth(left, days_to_end),
                      'overdue': left < 0, 'weight': weights.get(d.get('grade_id')),
                      'studied_minutes': studied, 'dashed': studied == 0,
                      'actions': {'done_url': url_for('user_courses_bp.api_deadline_done', deadline_id=d['deadline_id']),
                                  'edit_url': url_for('user_courses_bp.api_deadline_edit', deadline_id=d['deadline_id'])}})
    # v5: an open, dated class task is a deadline too -> adding one adds a root badge (shared with /roots/data)
    for r in dated_task_roots(todos, {c['course_id'] for c in courses}, today):
        r.update({'due_date': r['due'], 'depth': root_depth(r['days_left'], days_to_end), 'overdue': r['days_left'] < 0,
                  'weight': None, 'studied_minutes': 0, 'dashed': True})
        roots.append(r)
    roots, roots_more = assign_roots(roots)
    # classless tasks (course_id NULL or a class that no longer exists) sit on the trunk
    known = {c['course_id'] for c in courses}
    loose = [t for t in todos if t['course_id'] not in known]
    trunk_buds = [_bud(t, species) for t in loose if not t['is_completed']]
    trunk_flowers = sorted(
        ({'id': f"task:{t['task_id']}", 'kind': 'task', 'label': t['task_name'], 'task_id': t['task_id'],
          'title': t['task_name'], 'status': 'done', 'species': species, 'piece': 'flower_task',
          'done_at': apptime.local_date(as_dt(t['completed_at'])).isoformat() if as_dt(t.get('completed_at')) else None}
         for t in loose if t['is_completed']),
        key=lambda f: (f['done_at'] is None, f['done_at'] or '', f['task_id']))

    # ---- park
    owned = owned_keys(uid)
    park = park_scene(prof, st['stage_idx'], owned, owner_id=uid, show_friends=True)
    sky = sky_key_of(prof)
    park = {'layers': park['layers'], 'under_tree': park['under_tree'], 'visitor_slots': park['visitor_slots'],
            'friends': park['friends'], 'owned_items': [k for k in owned if k in PARK_ITEMS],
            'sky': sky, 'sky_night': DEFAULT_SKY_NIGHT if sky == DEFAULT_SKY else sky}

    return {
        'version': 1, 'kit_version': KIT_VERSION, 'today': today.isoformat(),
        'semester': {'start': sem_start.isoformat(), 'end': sem_end.isoformat(), 'progress': progress},
        'tree': {'stage_idx': st['stage_idx'], 'stage': st['stage'], 'growth': st['growth']},
        **sinfo,
        'branches': branches,
        'overflow': [{'course_id': c['course_id'], 'name': c['course_name'], 'code': c.get('course_code') or '',
                      'color': c['color']} for c in overflow],
        'species': species,
        'roots': roots, 'roots_more': roots_more, 'mood': tree_mood(todos, today, dls), 'trunk_buds': trunk_buds, 'trunk_flowers': trunk_flowers, 'park': park,
    }


@api_tree_bp.route('/api/tree')
def api_tree():
    uid = session.get('user_id')
    if not uid or not query('SELECT id FROM users WHERE id = %s', (uid,), one=True):
        session.clear()  # stale session (deleted user / other DB): same 401 as logged out
        return jsonify({'error': 'unauthorized', 'login': url_for('login')}), 401
    return jsonify(build_tree(session['user_id']))
