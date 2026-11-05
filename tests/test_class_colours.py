"""r8/r9: class colours - blank-on-create gets the next palette colour, explicit colours are kept, blank rows display
a palette colour by order without any DB write, and the one-off migration only touches NULL/empty rows."""
from _jobs_helpers import client_for, make_user, query
from db import get_db_connection
from helpers import COURSE_COLORS, fill_display_colours, null_colour_map
from profiles import class_dot_colour
from user_courses import _insert_course


def colours(uid):
    return [r['color'] for r in query('SELECT color FROM usercourses WHERE id=%s ORDER BY course_id', (uid,))]


def raw_course(uid, name, color):
    return query('INSERT INTO usercourses (id, course_name, subject, color) VALUES (%s, %s, %s, %s)',
                 (uid, name, 'Other', color), commit=True)


def test_insert_without_colour_gets_distinct_palette_colours():
    u = make_user()
    c = get_db_connection(); cur = c.cursor(dictionary=True)
    for i in range(5):
        _insert_course(cur, u, ('course_name', 'subject'), (f'C{i}', 'Other'))  # no colour, one transaction
    c.commit()
    assert colours(u) == COURSE_COLORS[:5]
    assert len({class_dot_colour(x) for x in colours(u)}) == 5


def test_explicit_colour_never_overridden_even_default():
    u = make_user()
    c = get_db_connection(); cur = c.cursor(dictionary=True)
    _insert_course(cur, u, ('course_name', 'color'), ('A', '#CFDCC6'))
    _insert_course(cur, u, ('course_name', 'color'), ('B', '#CFDCC6'))
    c.commit()
    assert colours(u) == ['#CFDCC6', '#CFDCC6']


def test_blank_colours_display_by_order_without_writing():
    u = make_user()
    a = raw_course(u, 'A', '#CFDCC6'); b = raw_course(u, 'B', None); d = raw_course(u, 'D', '')
    assert null_colour_map(u) == {b: COURSE_COLORS[1], d: COURSE_COLORS[2]}
    rows = fill_display_colours([{'course_id': b, 'color': None}, {'course_id': a, 'color': '#CFDCC6'}], u)
    assert [r['color'] for r in rows] == [COURSE_COLORS[1], '#CFDCC6']
    assert colours(u) == ['#CFDCC6', None, '']  # display only
    r = client_for(u).get('/roots/data')
    assert r.status_code in (200, 302)
    assert colours(u) == ['#CFDCC6', None, '']


def test_migration_dry_run_then_apply_only_blank_rows():
    import importlib.util, os
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'migrate_null_class_colours.py')
    spec = importlib.util.spec_from_file_location('mig', p); mig = importlib.util.module_from_spec(spec); spec.loader.exec_module(mig)
    u = make_user()
    raw_course(u, 'A', '#CFDCC6'); raw_course(u, 'B', '#CFDCC6'); raw_course(u, 'C', None)
    mig.main(apply=False)
    assert colours(u) == ['#CFDCC6', '#CFDCC6', None]
    mig.main(apply=True)
    assert colours(u) == ['#CFDCC6', '#CFDCC6', COURSE_COLORS[1]]


def test_api_tree_no_colour_class_matches_its_chip():
    """r10: a no-colour class gets the SAME order-based fallback (helper, course_id order) on /api/tree as on its chip."""
    u = make_user()
    a = raw_course(u, 'A', '#EADCC2'); b = raw_course(u, 'B', None); d = raw_course(u, 'D', '')
    c = client_for(u)
    tree = c.get('/api/tree').get_json()
    chips = {x['course_id']: x for x in c.get('/roots/data').get_json()['branches']}
    want = null_colour_map(u)
    assert want == {b: COURSE_COLORS[0], d: COURSE_COLORS[2]}
    tb = {x.get('course_id', x.get('id')): x for x in tree['branches']}
    for cid in (b, d):
        assert tb[cid]['color'] == chips[cid]['color'] == want[cid]
        assert tb[cid]['dot'] == chips[cid]['dot'] == class_dot_colour(want[cid])
    assert colours(u) == ['#EADCC2', None, '']  # display only, no DB write


def test_init_db_leaves_class_colours_unchanged():
    """r11: init_db() must not rewrite class colours at boot (NULL, '' and custom stay as stored)."""
    from db import init_db
    u = make_user()
    raw_course(u, 'N', None); raw_course(u, 'E', ''); raw_course(u, 'C', '#123456')
    init_db(); init_db()
    assert colours(u) == [None, '', '#123456']
