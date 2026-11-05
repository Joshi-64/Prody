"""Owner call: no Care button; a finished focus session waters the plant once a day."""
from _jobs_helpers import client_for, make_user, query


def log(c, completed=True, minutes=25):
    return c.post('/study/log', json=dict(minutes=minutes, completed=completed)).get_json()


def cares(uid):
    return query('SELECT * FROM plantcare WHERE user_id = %s', (uid,))


def test_finished_session_waters_once_per_day():
    u = make_user(); c = client_for(u)
    assert log(c)['watered'] is True and len(cares(u)) == 1
    assert log(c)['watered'] is False and len(cares(u)) == 1


def test_unfinished_session_does_not_water():
    u = make_user(); c = client_for(u)
    assert log(c, completed=False)['watered'] is False and cares(u) == []


def test_dashboard_has_no_care_button():
    u = make_user(); html = client_for(u).get('/dashboard').get_data(as_text=True)
    assert 'careBtn' not in html and 'prodyCare' not in html


def test_toast_text_in_timer_pages():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for f in ('study.html', 'zen.html'):
        assert 'Session done, your tree got tended.' in open(os.path.join(root, 'templates', f)).read()


def test_local_day_two_evening_sessions_et(monkeypatch):
    monkeypatch.setenv('PRODY_ADD_PLANTCARE_UTC', '1')
    import profiles
    from datetime import datetime
    u = make_user(); c = client_for(u)
    et = -240  # EDT, minutes east of UTC
    monkeypatch.setattr(profiles, '_utcnow', lambda: datetime(2026, 10, 23, 23, 30))  # 7:30 PM ET
    assert c.post('/study/log', json=dict(minutes=25, completed=True, tz_offset=et)).get_json()['watered'] is True
    monkeypatch.setattr(profiles, '_utcnow', lambda: datetime(2026, 10, 24, 0, 30))   # 8:30 PM ET, next UTC day
    assert c.post('/study/log', json=dict(minutes=25, completed=True, tz_offset=et)).get_json()['watered'] is False
    assert [str(r['cared_on'])[:10] for r in cares(u)] == ['2026-10-23']


def test_offset_rules():
    from profiles import local_day
    from datetime import datetime
    import apptime
    server = apptime.today_local().isoformat()  # bad offsets fall back to the ET day
    for bad in (7, 330.5, -780, 900, 'x', None):
        assert local_day(bad) == server
    for good in (330, 345, -720, 840):
        assert len(local_day(good)) == 10


def test_changing_offset_cannot_water_twice(monkeypatch):
    monkeypatch.setenv('PRODY_ADD_PLANTCARE_UTC', '1')
    import profiles
    from datetime import datetime
    u = make_user(); c = client_for(u)
    monkeypatch.setattr(profiles, '_utcnow', lambda: datetime(2026, 10, 23, 12, 0))
    assert c.post('/study/log', json=dict(minutes=25, completed=True, tz_offset=840)).get_json()['watered'] is True   # local Oct 24
    assert c.post('/study/log', json=dict(minutes=25, completed=True, tz_offset=-720)).get_json()['watered'] is False  # local Oct 23


def _at(monkeypatch, dt):
    import profiles
    monkeypatch.setattr(profiles, '_utcnow', lambda: dt)


def test_minus12_then_plus14_waters_once(monkeypatch):
    monkeypatch.setenv('PRODY_ADD_PLANTCARE_UTC', '1')
    from datetime import datetime
    u = make_user(); c = client_for(u)
    _at(monkeypatch, datetime(2026, 10, 23, 12, 0))  # local Oct 23 at -12h, Oct 24 at +14h
    assert log_tz(c, -720) is True
    assert log_tz(c, 840) is False
    assert len(cares(u)) == 1


def log_tz(c, off):
    return c.post('/study/log', json=dict(minutes=25, completed=True, tz_offset=off)).get_json()['watered']


def test_72h_sweep_any_offsets_never_two_within_20h(monkeypatch):
    monkeypatch.setenv('PRODY_ADD_PLANTCARE_UTC', '1')
    from datetime import datetime, timedelta
    u = make_user(); c = client_for(u)
    start = datetime(2026, 10, 23, 0, 0); offs = [-720, 840, 0, -240, 330, 345]
    hits = []
    for h in range(72):
        now = start + timedelta(hours=h); _at(monkeypatch, now)
        for off in offs:  # try every offset every hour
            if log_tz(c, off):
                hits.append(now)
    assert hits and all(b - a >= timedelta(hours=20) for a, b in zip(hits, hits[1:]))
    assert len(hits) <= 4  # 72h / 20h gap


def test_flag_off_no_utc_table_and_offset_ignored(monkeypatch):
    import profiles
    from datetime import datetime
    monkeypatch.delenv('PRODY_ADD_PLANTCARE_UTC', raising=False)
    monkeypatch.setattr(profiles, '_UTC_TABLE_READY', False)
    u = make_user(); c = client_for(u)
    _at(monkeypatch, datetime(2026, 10, 23, 12, 0))
    assert log_tz(c, -720) is True and log_tz(c, 840) is False
    assert [str(r['cared_on'])[:10] for r in cares(u)] == ['2026-10-23']  # ET day


def test_flag_off_730_and_830_pm_et_water_once(monkeypatch):
    from datetime import datetime
    monkeypatch.delenv('PRODY_ADD_PLANTCARE_UTC', raising=False)
    u = make_user(); c = client_for(u)
    _at(monkeypatch, datetime(2026, 10, 23, 23, 30))  # 7:30 PM ET
    assert log_tz(c, None) is True
    _at(monkeypatch, datetime(2026, 10, 24, 0, 30))   # 8:30 PM ET (next UTC day)
    assert log_tz(c, None) is False
    _at(monkeypatch, datetime(2026, 10, 24, 14, 0))   # 10 AM ET next day
    assert log_tz(c, None) is True
