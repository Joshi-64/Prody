"""Owner preview feedback 2026-10-23: no old tree flash, prefetch + caching, atomic theme swap, icons + planner output."""
import glob, os, re
from datetime import datetime, timedelta

from _jobs_helpers import client_for, make_course, make_deadline, make_user, query
import calendar_routes as cr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return open(os.path.join(ROOT, p), encoding='utf-8').read()


# 1 — stale roots tree gone from the dashboard
def test_dashboard_has_only_current_tree():
    # garden home (clay scene) replaced the kit tree: one live tree, none of the retired roots / kit views
    html = client_for(make_user()).get('/dashboard').get_data(as_text=True)
    assert 'data-garden' in html and 'roots-slot' not in html and 'data-roots-src' not in html
    assert '/static/ui/js/roots.js' not in html and 'branch_kit.js' not in html and '/static/ui/js/tree_kit.js' not in html
    assert re.search(r'data-garden(?![^>]*\bhidden\b)', html)


def test_oak_pixel_kit_removed_from_tree():
    # Leader drop: clay garden Home replaced the oak pixel kit stack.
    assert not os.path.exists(os.path.join(ROOT, 'static', 'ui', 'js', 'tree_kit.js'))
    assert not os.path.exists(os.path.join(ROOT, 'static', 'img', 'oak_kit'))
    assert not os.path.exists(os.path.join(ROOT, 'static', 'trees', 'oak'))


# 2 — prefetch + caching
def test_prefetch_rules_and_hover_prefetch():
    html = client_for(make_user()).get('/dashboard').get_data(as_text=True)
    assert 'speculationrules' not in html  # r3: cost WebKit ~25-30ms/page, never fired headless
    js = read('static/ui/js/shell.js')
    assert "relList.supports('prefetch')" in js and 'var OK=/^\\/(dashboard|tasks|calendar' in js  # nav-perf: allowlist, not denylist
    assert "'touchstart'" in js and "'pointerenter'" in js and "rel='prefetch'" in js


def test_spot_art_urls_are_versioned_and_immutable():
    u = make_user(); c = client_for(u)
    html = c.get('/calendar').get_data(as_text=True) + c.get('/tasks').get_data(as_text=True)
    for src in re.findall(r'src="(/static/ui/icons/[^"]+)"', html):
        assert '?v=' in src, src
        r = c.get(src)
        assert 'immutable' in r.headers.get('Cache-Control', ''), src
    assert re.search(r'sprig_\{n\}\.svg"', read('plant.py')) is None


# 3 — atomic theme switch
def test_theme_switch_is_atomic():
    css = read('static/ui/css/app.css'); base = read('templates/base.html'); js = read('static/ui/js/app.js')
    body = re.search(r'\nbody\{[^}]*\}', css).group(0)
    assert 'transition' not in body
    assert ':root.theme-switching *' in css and 'transition:none!important' in css
    head = base.split('</head>')[0]
    assert 'prodySetTheme' in head and "localStorage.getItem('prody-theme')" in head
    assert head.index('prody-theme') < head.index('ui/css/app.css')  # applied before first paint
    assert 'prodySetTheme(' in js and 'root.dataset.theme=n' not in js


# 4 — icons + planner output
def _subset():
    return set(re.search(r'icon_names=([a-z_0-9,]+)', read('static/ui/css/fonts.css')).group(1).split(','))


def test_every_literal_material_icon_is_in_font_subset():
    names = _subset(); miss = set()
    files = glob.glob(os.path.join(ROOT, 'templates', '**', '*.html'), recursive=True) + glob.glob(os.path.join(ROOT, 'static/ui/js/*.js'))
    for f in files:
        for m in re.finditer(r'class=["\']?[^"\'>]*\bms\b[^"\'>]*["\']?[^>]*>\s*([a-z_0-9]+)\s*<', open(f, encoding='utf-8').read()):
            if m.group(1) not in names:
                miss.add((m.group(1), os.path.basename(f)))
    assert not miss, miss
    subs = re.findall(r'icon_names=([a-z_0-9,]+)', read('static/ui/css/fonts.css'))  # perf_r1: self-hosted subset
    assert len(subs) == 1 and subs[0].split(',') == sorted(subs[0].split(','))


def test_plan_button_uses_inline_svg():
    u = make_user(); make_deadline(make_course(u, 'Bio', 0))
    html = client_for(u).get('/calendar').get_data(as_text=True)
    assert 'hourglass_top' not in html and 'ico-svg' in html


def test_planner_empty_state_without_deadlines():
    u = make_user()
    query('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, is_ai_recommended, flag_status) '
          'VALUES (%s,%s,%s,%s,%s,%s)', (u, 'Gym', datetime.now() + timedelta(days=1), 60, False, 'confirmed'), commit=True)
    html = client_for(u).get('/calendar').get_data(as_text=True)
    assert 'data-plan-empty' in html and 'Nothing to plan yet' in html


def test_pending_blocks_grouped_by_class_with_time_ranges():
    u = make_user(); cid = make_course(u, 'Chem 210', 0); make_deadline(cid, 'Lab report')
    when = (datetime.now() + timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)
    query('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes, is_ai_recommended, flag_status) '
          'VALUES (%s,%s,%s,%s,%s,%s)', (u, 'Study: Chem 210 – Lab report', when, 90, True, 'is_pending'), commit=True)
    html = client_for(u).get('/calendar').get_data(as_text=True)
    assert 'plan-group' in html and '<span class="plan-count">1</span>' in html
    assert '6:00–7:30 PM' in html and 'Study block · 90 min' in html and 'Lab report' in html
    assert 'data-plan-empty' not in html


def test_time_range_and_title_helpers():
    d = datetime(2026, 10, 27, 11, 0)
    assert cr._time_range(d, 90) == '11:00 AM–12:30 PM'
    assert cr._time_range(d.replace(hour=18), 90) == '6:00–7:30 PM'
    assert cr._split_study_title('Study: CS 101 – Midterm') == ('CS 101', 'Midterm')
    assert cr._split_study_title('Gym') == ('', 'Gym')


# r2 — skeleton placeholder + prefetch exclusions for GET routes that write
def test_tree_placeholder_is_skeleton_with_reserved_height():
    # 0px shift: the stage is fixed full-screen and paints the still artwork before WebGL is ready
    html = client_for(make_user()).get('/dashboard').get_data(as_text=True)
    assert 'class="g-stage"' in html
    css = read('static/ui/css/garden.css')
    assert '.garden{position:fixed;inset:0' in css
    # perf: the fallback JPG is no longer a CSS placeholder; TreeScene loads it only when WebGL/scene loading fails
    assert "fallback.jpg'" not in css and "fallback.jpg)" not in css
    assert 'prefers-reduced-motion:reduce' in css


def test_prefetch_skips_writing_get_routes():
    js = read('static/ui/js/shell.js'); base = read('templates/base.html')
    ok = js.split('var OK=')[1].split(',K=')[0]  # nav-perf: allowlist of read-only pages only
    assert 'ai_' not in ok and 'automatic_add' not in ok and 'logout' not in ok
    assert 'speculationrules' not in base


# r3 — 0px placeholder shift, single tree-data fetch, no roots.css on the dashboard
def test_dashboard_r3_assets():
    html = client_for(make_user()).get('/dashboard').get_data(as_text=True)
    assert 'roots.css' not in html and 'rel="preload"' not in html   # WebKit fetched as=fetch preloads twice
    assert html.count("fetch('/api/tree'") == 1                       # one tree-data fetch, started while parsing
    js = read('static/ui/js/garden.js')
    assert 'window.__gardenP' in js


# r3b — writing calendar routes are POST-only
def test_writing_calendar_routes_reject_get():
    c = client_for(make_user())
    for url in ('/calendar/ai_reccomended_schedule', '/calendar/automatic_add'):
        assert c.get(url).status_code == 405
    tpl = read('templates/calendar.html')
    assert tpl.count('method="POST"') >= 2
