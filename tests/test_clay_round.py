"""Clay round owner notes: no Video Study Rooms anywhere, Zen flower stills + pick, shared nap art, Oak label, chat daily cap."""
import os, tempfile
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from unittest import mock  # noqa: E402
from _jobs_helpers import client_for, make_user, query  # noqa: E402

GONE = ('video study', 'fivehive')  # acad-r1: "Study rooms" More-hub placeholder is intentional
NAP = 'ui/icons/nap_A_potted_drowsy_bud.png'


def _html(c, path):
    return c.get(path, follow_redirects=True).get_data(as_text=True)


def test_video_study_rooms_absent_everywhere():
    c = client_for(make_user())
    for path in ('/dashboard', '/tasks', '/calendar', '/zen', '/profile', '/store', '/buddy'):
        low = _html(c, path).lower()
        assert not any(g in low for g in GONE), path
        # real FiveHive/calls UI must stay gone; Study rooms is the live rooms list, not FiveHive
        assert 'fivehive' not in low
    assert c.get('/coming-soon/calls').status_code == 404
    rooms = c.get('/rooms').get_data(as_text=True).lower()
    assert 'fivehive' not in rooms
    assert 'study' in rooms or 'room' in rooms


def test_zen_growth_frames_and_pick():
    html = _html(client_for(make_user()), '/zen')
    assert 'js/zenGrowth.js' in html and 'zen/tulip/tulip_0001.webp' in html   # yellow tulip is the default
    assert 'data-fl="tulip">Yellow tulip</button>' in html
    assert 'data-fl="camellia">Pink rose</button>' in html
    assert 'data-fl="peony"' not in html and 'Pink peony' not in html
    assert '03_bloom_yellow_tulip' not in html and '04_bud_pink_rose' not in html
    assert "f==='peony'" in html and "normalize(" in html  # old peony migrates to camellia
    here = os.path.dirname(__file__)
    for fl in ('tulip', 'camellia'):
        d = os.path.join(here, '..', 'static', 'zen', fl)
        assert len([f for f in os.listdir(d) if f.endswith('.webp')]) == 220
    assert not os.path.exists(os.path.join(here, '..', 'static', 'zen', 'peony'))


def test_todo_all_done_uses_nap_art():
    u = make_user()
    query('INSERT INTO todolist (user_id, task_name, is_completed) VALUES (%s,%s,1)', (u, 'done one'), commit=True)
    html = _html(client_for(u), '/tasks')
    assert 'All done' in html and NAP in html and 'empty_sleeping_bud' not in html


def test_chat_resting_uses_nap_art():
    u = make_user()
    c = client_for(u)
    query("INSERT INTO chatmessages (user_id, role, content, created_at) VALUES (%s,'user','hi',CURRENT_TIMESTAMP)", (u,), commit=True)
    with mock.patch('buddy.ai_available', return_value=False):
        html = _html(c, '/buddy')
    assert 'Resting' in html and NAP in html and 'empty_sleeping_bud' not in html


def test_me_plant_card_says_oak():
    html = _html(client_for(make_user()), '/profile')
    assert 'Classic tree' not in html and 'Oak' in html and 'data-me-scene' in html


def test_chat_daily_cap_blocks_ai_call(monkeypatch):
    monkeypatch.setenv('PRODY_AI_DAILY_CAP', '2')
    u = make_user()
    c = client_for(u)
    with mock.patch('buddy.ai_chat', return_value='hello') as ai, mock.patch('buddy.ai_available', return_value=True):
        for _ in range(3):
            c.post('/buddy', data={'message': 'explain osmosis'})
    assert ai.call_count == 2
    n = query("SELECT COUNT(*) AS n FROM chatmessages WHERE user_id=%s AND role='user'", (u,), one=True)['n']
    assert n == 2


def test_auth_pages_have_no_drawer_pull_tab():
    """Fix 7: login/signup must not render the sidebar/drawer pull handle at all."""
    from app import app
    with app.test_client() as c:
        for path in ('/login', '/register'):
            html = c.get(path).get_data(as_text=True)
            assert 'logged-out' in html, path
            assert 'auth-frame' in html, path
            assert 'side-pull' not in html and 'drawer-pull' not in html and 'data-side-pull' not in html, path
            assert 'drawer-tab' not in html and 'side-peek' not in html, path
            assert 'js/shell.js' not in html, path
            assert 'class="side-pull"' not in html and "class='side-pull'" not in html


def test_zen_has_no_stage_pngs_or_streak_ui_and_hides_drawer():
    html = _html(client_for(make_user()), '/zen')
    assert 'zen_stage_' not in html and 'zFlower' not in html and 'class="zen-hero"' not in html
    assert 'Day streak' not in html and 'day streak' not in html
    assert 'Pink peony' not in html and 'Pink rose' in html and 'Yellow tulip' in html
    assert 'is-zen' in html
    assert 'zGrowImgB' in html and 'zfl-back' in html  # cross-fade pair
    assert 'js/zenGrowth.js' in html
