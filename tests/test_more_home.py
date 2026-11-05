"""Home garden must expose a tappable More control when topnav is hidden."""
import app as prody_app
from helpers import query


def _client(name='more_home_u'):
    if not query('SELECT id FROM users WHERE username=%s', (name,), one=True):
        query("INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)",
              (name, name + '@example.com', 'x', 'student'), commit=True)
    uid = query('SELECT id FROM users WHERE username=%s', (name,), one=True)['id']
    c = prody_app.app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid
        s['username'] = name
    return c


def test_dashboard_has_garden_more_opener():
    html = _client().get('/dashboard').get_data(as_text=True)
    assert 'data-more-open' in html
    assert 'class="g-more"' in html
    assert 'id="moreSheet"' in html
    assert 'id="moreOpen"' in html


def test_tasks_still_has_topnav_more():
    html = _client('more_tasks_u').get('/tasks').get_data(as_text=True)
    assert 'id="moreOpen"' in html
