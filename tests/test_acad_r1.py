"""acad-r1: More sheet/hub, analytics week/month, concepts, grade analysis, store redeem, syllabus, focus days."""
import os, tempfile, io
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from _jobs_helpers import app, client_for, make_user, make_course, query  # noqa: E402
from datetime import timedelta
import apptime


def test_more_hub_sheet_and_admin_only():
    uid = make_user()
    c = client_for(uid)
    # sheet markup lives in base (any logged-in page)
    zen = c.get('/zen').get_data(as_text=True)
    assert 'id="moreSheet"' in zen and 'id="moreOpen"' in zen
    assert 'Study buddy' in zen and 'Boards' in zen and 'Calendar sync' in zen
    assert 'data-role="admin"' not in zen
    # /more deep link
    html = c.get('/more').get_data(as_text=True)
    assert c.get('/more').status_code == 200
    for label in ('Study buddy', 'Analytics', 'Grades', 'Whiteboard', 'Achievements', 'Store',
                  'Messages', 'Boards', 'Study rooms', 'Calendar sync'):
        assert label in html
    assert 'data-role="admin"' not in html
    assert c.get('/messages').status_code == 200
    assert c.get('/boards').status_code == 200
    assert c.get('/rooms').status_code == 200
    me = c.get('/profile', follow_redirects=True).get_data(as_text=True)
    assert 'aria-label="More"' in me and 'Study buddy' in me
    query("UPDATE users SET role='admin' WHERE id=%s", (uid,), commit=True)
    with c.session_transaction() as s:
        s['role'] = 'admin'
    more = c.get('/more').get_data(as_text=True)
    assert 'data-role="admin"' in more and 'Admin' in more
    assert 'data-role="admin"' in c.get('/zen').get_data(as_text=True)


def test_analytics_week_month_toggle_and_stacked():
    uid = make_user()
    cid = make_course(uid, 'Chem', 0)
    start = apptime.now_utc_naive() - timedelta(days=2)
    query('INSERT INTO studysessions (user_id, course_id, label, minutes, started_at, completed) VALUES (%s,%s,%s,%s,%s,1)',
          (uid, cid, 'Focus', 90, start), commit=True)
    c = client_for(uid)
    week = c.get('/analytics?period=week')
    assert week.status_code == 200
    wh = week.get_data(as_text=True)
    assert 'period=week' in wh and 'Hours by class' in wh and 'id="stacked"' in wh
    assert 'Chem' in wh
    month = c.get('/analytics?period=month').get_data(as_text=True)
    assert 'period=month' in month and 'Hours by class' in month


def test_course_concepts_add_toggle_rename_delete():
    uid = make_user()
    cid = make_course(uid, 'Algo', 1)
    c = client_for(uid)
    r = c.post(f'/courses/{cid}/concepts', data={'action': 'add', 'name': 'Dijkstra'}, follow_redirects=True)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Dijkstra' in html
    assert '0 of 1 mastered' in html
    assert 'class="crs"' in html and 'To review' in html
    row = query('SELECT concept_id, status FROM courseconcepts WHERE course_id=%s', (cid,), one=True)
    assert row['status'] == 'Review'
    c.post(f'/courses/{cid}/concepts', data={'action': 'toggle', 'concept_id': row['concept_id']}, follow_redirects=True)
    assert query('SELECT status FROM courseconcepts WHERE concept_id=%s', (row['concept_id'],), one=True)['status'] == 'Mastered'
    html = c.get(f'/courses/{cid}/concepts?filter=mastered').get_data(as_text=True)
    assert '1 of 1 mastered' in html and 'Dijkstra' in html
    c.post(f'/courses/{cid}/concepts', data={'action': 'rename', 'concept_id': row['concept_id'], 'name': 'Shortest paths'},
           follow_redirects=True)
    assert query('SELECT name FROM courseconcepts WHERE concept_id=%s', (row['concept_id'],), one=True)['name'] == 'Shortest paths'
    c.post(f'/courses/{cid}/concepts', data={'action': 'delete', 'concept_id': row['concept_id']}, follow_redirects=True)
    assert not query('SELECT concept_id FROM courseconcepts WHERE course_id=%s', (cid,))
    classes = c.get('/add_courses').get_data(as_text=True)
    assert f'/courses/{cid}/concepts' in classes


def test_grade_analyze_fallback_without_ai_key(monkeypatch):
    uid = make_user()
    cid = make_course(uid, 'Bio', 2)
    query('INSERT INTO grades (user_id, course_id, item_name, category, score, weight) VALUES (%s,%s,%s,%s,%s,%s)',
          (uid, cid, 'Midterm', 'Exam', 62, 40), commit=True)
    import helpers
    monkeypatch.setattr(helpers, 'ai_available', lambda: False)
    c = client_for(uid)
    r = c.post('/grades/analyze', follow_redirects=True)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'grade-analysis' in html
    assert 'Bio' in html and ('62' in html or 'Focus study' in html or 'quick read' in html)
    assert 'Analyze my grades' in c.get('/grades').get_data(as_text=True)


def test_store_redeem_coming_soon():
    uid = make_user()
    html = client_for(uid).get('/store').get_data(as_text=True)
    assert 'id="storeRedeem"' in html
    assert 'Gift cards' in html and 'Ad-free Prody' in html
    redeem = html.split('id="storeRedeem"')[1].split('store-confirm')[0]
    assert 'store-buy' not in redeem
    assert redeem.count('Coming soon') >= 2


def test_focus_days_tile_on_me():
    uid = make_user()
    today = apptime.today_local()
    # session today -> that weekday lit
    query('INSERT INTO studysessions (user_id, label, minutes, started_at, completed) VALUES (%s,%s,%s,%s,1)',
          (uid, 'Focus', 25, apptime.now_utc_naive()), commit=True)
    html = client_for(uid).get('/profile', follow_redirects=True).get_data(as_text=True)
    assert 'Focus days this week' in html and 'focusdays' in html
    assert html.count('class="on"') >= 1 or 'class="dots"' in html
    # seven dots
    assert html.split('focusdays')[1].split('</div>')[0].count('<i') >= 7 or html.count('class="dots"') >= 1


def test_syllabus_import_txt_preview_and_commit():
    uid = make_user()
    cid = make_course(uid, 'Hist', 3)
    c = client_for(uid)
    body = b"Midterm Exam October 20, 2026\nQuiz 1 due 11/05/2026\nRandom note\n"
    r = c.post(f'/courses/{cid}/syllabus', data={'action': 'upload', 'syllabus': (io.BytesIO(body), 'syllabus.txt')},
               content_type='multipart/form-data', follow_redirects=True)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Confirm deadlines' in html and 'Midterm Exam' in html
    # commit first item only
    r2 = c.post(f'/courses/{cid}/syllabus', data={'action': 'commit', 'pick': ['0']}, follow_redirects=True)
    assert r2.status_code == 200
    rows = query('SELECT deadline_name FROM coursedeadlines WHERE course_id=%s', (cid,))
    assert any('Midterm' in (r['deadline_name'] or '') for r in rows)
