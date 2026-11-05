from _jobs_helpers import client_for, make_user, query


def _uname(u):
    return query('SELECT username FROM users WHERE id=%s', (u,), one=True)['username']


def test_home_never_shows_raw_handle():
    u = make_user()
    html = client_for(u).get('/dashboard').get_data(as_text=True)
    assert 'Hi there, your semester is growing.' in html
    assert f'Hi {_uname(u)}' not in html


def test_home_uses_display_first_name():
    u = make_user()
    client_for(u).get('/dashboard')  # ensures a profile row exists
    query('UPDATE userprofiles SET display_name=%s WHERE user_id=%s', ('Maya Lopez', u), commit=True)
    html = client_for(u).get('/dashboard').get_data(as_text=True)
    assert 'Hi Maya, your semester is growing.' in html
