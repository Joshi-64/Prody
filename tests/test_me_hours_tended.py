"""Me page (clay Design 4dc31fa): Buds growing / Tasks harvested / Zen time / Points; First focus medal (not streak)."""
import os, tempfile
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from _jobs_helpers import client_for, make_user, query  # noqa: E402


def test_me_shows_zen_time_buds_and_no_streak():
    u = make_user()
    for m in (50, 40):  # 90 focus minutes -> 1.5h Zen time
        query('INSERT INTO studysessions (user_id, label, minutes, started_at, completed) VALUES (%s,%s,%s,CURRENT_TIMESTAMP,1)',
              (u, 'Focus', m), commit=True)
    query('INSERT INTO todolist (user_id, task_name, is_completed) VALUES (%s,%s,0)', (u, 'Open bud'), commit=True)
    html = client_for(u).get('/profile', follow_redirects=True).get_data(as_text=True)
    assert '<b>1.5h</b><span>Zen time</span>' in html
    assert 'Buds growing' in html and 'Tasks harvested' in html and 'Points' in html
    assert 'Day streak' not in html and 'day streak' not in html.split('Garden medals')[0]
    assert '7-day streak' not in html and 'badge_streak_7' not in html
    assert 'First focus' in html
