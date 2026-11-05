from pathlib import Path
"""PR #1 garden fixes: idempotent harvest, classless tasks reach the garden, scene follows the equipped tree, pine equips."""
import json, os, re, shutil, subprocess
from datetime import datetime, timedelta

import pytest

from _jobs_helpers import app, client_for, make_course, make_user, query

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _csrf(csrf_off):
    yield


def _task(uid, cid=None, done=0, due=None):
    return query('INSERT INTO todolist (user_id, task_name, is_completed, course_id, due_date) VALUES (%s, %s, %s, %s, %s)',
                 (uid, 'Essay', done, cid, due or datetime.now() + timedelta(days=5)), commit=True)


def _row(tid):
    return query('SELECT is_completed, completed_at FROM todolist WHERE task_id = %s', (tid,), one=True)


def test_harvest_twice_stays_done():
    uid = make_user(); tid = _task(uid); c = client_for(uid)
    r1 = c.post(f'/tasks/done/{tid}'); assert r1.status_code == 200 and r1.get_json()['changed'] is True
    first = _row(tid)['completed_at']
    r2 = c.post(f'/tasks/done/{tid}'); assert r2.status_code == 200 and r2.get_json()['changed'] is False
    row = _row(tid)
    assert row['is_completed'] and row['completed_at'] == first


def test_toggle_still_unmarks():
    uid = make_user(); tid = _task(uid); c = client_for(uid)
    c.post(f'/tasks/done/{tid}')
    c.post(f'/tasks/complete/{tid}')
    assert not _row(tid)['is_completed']


def test_harvest_other_users_task_404():
    owner = make_user(); tid = _task(owner)
    r = client_for(make_user()).post(f'/tasks/done/{tid}')
    assert r.status_code == 404 and not _row(tid)['is_completed']


def test_harvest_requires_csrf():
    app.config['WTF_CSRF_ENABLED'] = True
    uid = make_user(); tid = _task(uid)
    assert client_for(uid).post(f'/tasks/done/{tid}').status_code == 400
    assert not _row(tid)['is_completed']


def test_harvest_requires_login():
    uid = make_user(); tid = _task(uid)
    app.test_client().post(f'/tasks/done/{tid}')
    assert not _row(tid)['is_completed']


def test_garden_js_harvest_uses_set_done():
    js = open(os.path.join(ROOT, 'static/ui/js/garden.js')).read()
    assert "'/tasks/done/'" in js and "'/tasks/complete/'" not in js


def test_api_tree_sends_trunk_buds_and_species():
    uid = make_user(); tid = _task(uid, cid=None)
    t = client_for(uid).get('/api/tree').get_json()
    assert any(b['task_id'] == tid for b in t['trunk_buds'])
    assert t['species'] == 'default'


def test_pine_equips_and_scene_species():
    uid = make_user(); c = client_for(uid)
    query('INSERT INTO userinventory (user_id, item_key, price_paid, purchased_at) VALUES (%s, %s, %s, %s)',
          (uid, 'species_pine', 600, datetime.now()), commit=True)
    r = c.post('/store/equip/species_pine'); assert r.status_code in (200, 302)
    assert c.get('/api/tree').get_json()['species'] == 'pine'


def test_harvest_undo_cycle_explicit_state():
    """Harvest x2, Undo x2, Harvest again: state always matches the last request, never toggles."""
    uid = make_user(); tid = _task(uid); c = client_for(uid)
    for done, expect in ((True, 1), (True, 1), (False, 0), (False, 0), (True, 1)):
        r = c.post(f'/tasks/done/{tid}', json={'done': done})
        assert r.status_code == 200 and r.get_json()['done'] is done
        row = _row(tid)
        assert bool(row['is_completed']) == bool(expect)
        assert (row['completed_at'] is None) == (not expect)


def test_undo_past_due_shows_overdue_again():
    uid = make_user(); tid = _task(uid, due=datetime.now() - timedelta(days=3)); c = client_for(uid)
    c.post(f'/tasks/done/{tid}', json={'done': True}); c.post(f'/tasks/done/{tid}', json={'done': False})
    t = c.get('/api/tree').get_json()
    assert any(b['task_id'] == tid for b in t['trunk_buds'])
    assert _row(tid)['is_completed'] in (0, False)


def test_set_done_rejects_garbage():
    uid = make_user(); tid = _task(uid)
    assert client_for(uid).post(f'/tasks/done/{tid}', json={'done': 'maybe'}).status_code == 400


def _norm(payload):
    js = open(os.path.join(ROOT, 'static/ui/js/garden.js')).read()
    body = js[js.index('  var DUE_SOON_DAYS'):js.index('  function summaryLine(')]
    stubs = "var localStorage={getItem:function(){return null}},location={search:''},document={},ASSETS='';\n"
    prog = stubs + body + '\nprocess.stdout.write(JSON.stringify(normalize(' + json.dumps(payload) + ')));'
    return json.loads(subprocess.run(['node', '-e', prog], capture_output=True, text=True, check=True).stdout)


def _bud(i, due):
    return {'task_id': i, 'title': f't{i}', 'due': due, 'species': 'default'}


needs_node = pytest.mark.skipif(not shutil.which('node'), reason='node not installed')


@needs_node
def test_normalize_trunk_branch_counts_and_equipped_species():
    out = _norm({'today': '2026-11-04', 'species': 'pine',
                 'branches': [{'course_id': 1, 'name': 'Bio', 'slot': 0, 'buds': [_bud(9, '2026-11-20')], 'flowers': []}],
                 'roots': [], 'trunk_buds': [_bud(7, '2026-11-03')],
                 'trunk_flowers': [{'task_id': 8, 'title': 'Old', 'done_at': '2026-11-02'}]})
    assert out['scene'] == 'pine'                 # equipped tree, not the first task's 'default' species
    trunk = [b for b in out['branches'] if b['course_id'] == 'none'][0]
    assert trunk['name'] == 'No class' and trunk['care'] is True
    assert sorted(i['ref'] for i in trunk['items']) == [7, 8]
    assert out['counts']['overdue'] == 1 and out['counts']['done'] == 1


@needs_node
def test_branch_with_six_tasks_shows_all():
    buds = [_bud(i, f'2026-11-{10 + i:02d}') for i in range(6)]
    b = _norm({'today': '2026-11-04', 'branches': [{'course_id': 1, 'name': 'A', 'slot': 0, 'buds': buds, 'flowers': []}], 'roots': []})['branches'][0]
    assert len(b['shown']) == 6 and b['more'] == 0


@needs_node
def test_branch_with_many_caps_at_six_in_order():
    buds = [_bud(i, f'2026-11-{20 - i:02d}') for i in range(8)] + [_bud(50, '2026-11-01')]   # 50 is overdue
    flowers = [{'kind': 'task', 'status': 'done', 'task_id': 60, 'title': 'old done', 'done_at': '2026-11-01'},
               {'kind': 'task', 'status': 'done', 'task_id': 61, 'title': 'new done', 'done_at': '2026-11-03'},
               {'kind': 'task', 'status': 'done', 'task_id': 62, 'title': 'stale', 'done_at': '2026-10-20'}]
    b = _norm({'today': '2026-11-04', 'branches': [{'course_id': 1, 'name': 'A', 'slot': 0, 'buds': buds, 'flowers': flowers}], 'roots': []})['branches'][0]
    refs = [i['ref'] for i in b['shown']]
    assert len(refs) == 6
    assert refs[0] == 50                          # overdue first
    assert refs[1:5] == [7, 6, 5, 4]              # then soonest due
    assert refs[5] == 61                          # one spot kept for the newest finished
    assert 62 not in [i['ref'] for i in b['items']]   # finished > 7 days ago dropped
    assert b['more'] == len(b['items']) - 6 == 5


# ---- round 2: one of the 6 spots is kept for the newest bloom (finished <= 7 days ago)
def _fl(i, done_at):
    return {'kind': 'task', 'status': 'done', 'task_id': i, 'title': f'f{i}', 'done_at': done_at}


@needs_node
def test_six_open_plus_bloom_keeps_bloom_spot():
    buds = [_bud(i, f'2026-11-{10 + i:02d}') for i in range(6)]
    b = _norm({'today': '2026-11-04', 'roots': [],
               'branches': [{'course_id': 1, 'name': 'A', 'slot': 0, 'buds': buds, 'flowers': [_fl(50, '2026-11-03')]}]})['branches'][0]
    assert len(b['shown']) == 6 and b['more'] == 1
    assert [i['ref'] for i in b['shown'] if i['done']] == [50]
    assert [i['ref'] for i in b['shown'] if not i['done']] == [0, 1, 2, 3, 4]   # soonest due five


@needs_node
def test_twelve_open_two_blooms_only_newest_bloom():
    buds = [_bud(i, f'2026-11-{10 + i:02d}') for i in range(10)] + [_bud(20, '2026-11-01'), _bud(21, '2026-11-02')]
    fl = [_fl(50, '2026-11-01'), _fl(51, '2026-11-03')]
    b = _norm({'today': '2026-11-04', 'roots': [],
               'branches': [{'course_id': 1, 'name': 'A', 'slot': 0, 'buds': buds, 'flowers': fl}]})['branches'][0]
    assert len(b['shown']) == 6 and b['more'] == 8
    assert [i['ref'] for i in b['shown'] if i['done']] == [51]
    assert [i['ref'] for i in b['shown'] if not i['done']][:2] == [20, 21]   # overdue first


@needs_node
def test_bloom_older_than_7_days_gets_no_spot():
    buds = [_bud(i, f'2026-11-{10 + i:02d}') for i in range(6)]
    b = _norm({'today': '2026-11-04', 'roots': [],
               'branches': [{'course_id': 1, 'name': 'A', 'slot': 0, 'buds': buds, 'flowers': [_fl(50, '2026-10-27')]}]})['branches'][0]
    assert len(b['shown']) == 6 and not any(i['done'] for i in b['shown']) and b['more'] == 0


@needs_node
def test_no_class_branch_keeps_bloom_spot():
    buds = [_bud(i, f'2026-11-{10 + i:02d}') for i in range(6)]
    out = _norm({'today': '2026-11-04', 'roots': [], 'branches': [], 'trunk_buds': buds,
                 'trunk_flowers': [{'task_id': 50, 'title': 'x', 'done_at': '2026-11-02'}, {'task_id': 51, 'title': 'y', 'done_at': '2026-11-04'}]})
    t = [b for b in out['branches'] if b['course_id'] == 'none'][0]
    assert len(t['shown']) == 6 and t['more'] == 2
    assert [i['ref'] for i in t['shown'] if i['done']] == [51]


def test_heavy_user_feed_keeps_newest_bloom():
    """Many finished tasks on one class: trimming to the cap must drop the oldest, never the newest bloom."""
    uid = make_user(); cid = make_course(uid, 'Bio', 0); now = datetime.now()
    ids = []
    for i in range(80):
        ids.append(query('INSERT INTO todolist (user_id, task_name, is_completed, completed_at, course_id, due_date) '
                         'VALUES (%s, %s, 1, %s, %s, %s)', (uid, f'old{i}', now - timedelta(days=60 - i * 0.5), cid, now), commit=True))
    newest = query('INSERT INTO todolist (user_id, task_name, is_completed, completed_at, course_id, due_date) '
                   'VALUES (%s, %s, 1, %s, %s, %s)', (uid, 'newest', now - timedelta(hours=1), cid, now), commit=True)
    t = client_for(uid).get('/api/tree').get_json()
    br = [b for b in t['branches'] if b['course_id'] == cid][0]
    got = [f['task_id'] for f in br['flowers'] if f['kind'] == 'task']
    assert newest in got and ids[0] not in got
    assert len(got) < 81                                  # the feed really was trimmed
    out = _norm(dict(t, today=now.strftime('%Y-%m-%d'))) if shutil.which('node') else None
    if out:
        b = [x for x in out['branches'] if x['course_id'] == cid][0]
        assert [i['ref'] for i in b['shown'] if i['done']][:1] == [newest]


def test_undo_toast_sits_above_branches_overlay():
    css = open(os.path.join(ROOT, 'static/ui/css/garden.css')).read()
    toast = re.search(r'\.g-toast\{([^}]*)\}', css).group(1)
    br = re.search(r'\.g-branches\{([^}]*)\}', css).group(1)
    assert 'position:fixed' in toast
    z = lambda s: int(re.search(r'z-index:(\d+)', s).group(1))
    assert z(toast) > 80 and z(toast) > z(br)
    js = open(os.path.join(ROOT, 'static/ui/js/garden.js')).read()
    assert 'document.body.appendChild(toastEl)' in js   # out of the scene's stacking context


def test_harvest_and_undo_update_limb_label_immediately():
    js = open(os.path.join(ROOT, 'static/ui/js/garden.js')).read()
    assert 'function markItem(it, done)' in js
    h = js[js.index('function harvest(it)'):js.index('var toastEl')]
    u = js[js.index('function undo(it)'):js.index('function harvest(it)')]
    assert 'markItem(it, true)' in h and 'markItem(it, false)' in u
    m = js[js.index('function markItem'):js.index('function undo(it)')]
    assert "setAttribute('aria-label'" in m and 'WORDS[it.state]' in m and 'data-gid' in m
    assert js.count('n.dataset.gid = it.id') == 2   # garden element + limb node both tagged
    html = open(os.path.join(ROOT, 'templates/dashboard.html')).read()
    assert 'garden.js?v=8' in html


def test_branches_cutscene_has_no_one_time_seen_flag():
    """Item 9: garden cutscene must play every tree tap — no sessionStorage seen flag."""
    js = Path('static/ui/js/garden.js').read_text()
    assert 'prody-branches-cut' not in js
    assert 'cutSeen' not in js and 'markCut' not in js
    assert "sessionStorage.setItem('prody-branches-cut'" not in js
    # reverse ~70% of forward camera (720)
    assert '720 * 0.7' in js
    # skip both directions
    assert 'cutSkip' in js and 'finishFinite' in js
    # reduced-motion: quick fade both ways (~180ms)
    assert 'duration: 180' in js
    # popstate closes (browser/phone back) and open uses pushState once
    assert "addEventListener('popstate'" in js
    assert 'history.pushState' in js
    # rapid taps guarded
    assert 'busy || !view.hidden' in js


def test_roots_grow_in_has_no_one_time_seen_flag():
    """Item 9: roots grow-in plays every mount — no prody_roots_grown sessionStorage."""
    js = Path('static/ui/js/roots.js').read_text()
    assert 'prody_roots_grown' not in js
    assert 'var SEEN' not in js
    # reduced-motion still gets a fade intro
    assert "intro = (reduce && reduce.matches) ? 'fade' : 'grow'" in js


def test_tree_scene_has_coo_60s_idle_loop():
    """Item 10: Nov-4 COO idle (60s loop + boosted sway) ported into garden tree-scene."""
    js = Path('static/garden/tree-scene.js').read_text()
    assert 'LOOP = 60' in js and 'driftL' in js and 'GUSTS' in js
    assert 'uMotion*w*6.0' in js  # boosted sway
    # app hooks kept
    assert 'api.sleep' in js and "ART_V" in js
