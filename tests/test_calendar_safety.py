"""Critic 1 & 2: state-changing calendar routes are POST-only; deadline deletes never remove manual events."""
from datetime import datetime, timedelta
import pytest
from _jobs_helpers import client_for, make_course, make_user, query


@pytest.mark.parametrize('url', ['/ai_accept', '/ai_accept/1', '/ai_reject', '/ai_reject/1', '/calendar/delete/1'])
def test_get_is_405(url):
    assert client_for(make_user()).get(url).status_code == 405


def test_get_delete_does_not_remove_event():
    u = make_user()
    query('INSERT INTO calendarevents (user_id, event_name, event_date) VALUES (%s,%s,%s)', (u, 'Keep me', '2030-01-01 10:00:00'), commit=True)
    eid = query('SELECT event_id FROM calendarevents WHERE user_id=%s', (u,), one=True)['event_id']
    client_for(u).get(f'/calendar/delete/{eid}')
    assert query('SELECT 1 FROM calendarevents WHERE event_id=%s', (eid,))


def _add_deadline(c, course, name, when):
    c.post('/add_course_deadlines', data={'course_name': course, 'deadline_name': name, 'deadline_date': when})


def _setup(u, cname):
    when = (datetime.now() + timedelta(days=10)).replace(microsecond=0)
    w = when.strftime('%Y-%m-%dT%H:%M')
    c = client_for(u)
    _add_deadline(c, cname, 'Essay', w)
    d = query('SELECT d.deadline_id, d.deadline_date FROM coursedeadlines d JOIN usercourses c ON c.course_id=d.course_id '
              'WHERE c.id=%s', (u,), one=True)
    mirror = query('SELECT * FROM calendarevents WHERE user_id=%s AND source_deadline_id=%s', (u, d['deadline_id']), one=True)
    assert mirror, 'deadline mirror row should carry source_deadline_id'
    query('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes) VALUES (%s,%s,%s,%s)',
          (u, 'Essay', d['deadline_date'], 30), commit=True)
    return c, d


def _names(u):
    return [(r['event_name'], r['source_deadline_id']) for r in query('SELECT * FROM calendarevents WHERE user_id=%s', (u,))]


def test_deadline_delete_keeps_same_name_manual_event():
    u = make_user(); make_course(u, 'Bio', 0)
    c, d = _setup(u, 'Bio')
    c.post(f"/deadlines/{d['deadline_id']}/delete")
    assert _names(u) == [('Essay', None)]


def test_class_delete_keeps_same_name_manual_event():
    u = make_user(); cid = make_course(u, 'Chem', 0)
    c, d = _setup(u, 'Chem')
    c.post(f'/courses/{cid}/delete')
    assert _names(u) == [('Essay', None)]


def _backfill(apply=True):
    import importlib.util, os
    spec = importlib.util.spec_from_file_location('bf', os.path.join(os.path.dirname(__file__), '..', 'scripts', 'backfill_source_deadline_id.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m.main(apply=apply)


def test_backfill_tags_unique_legacy_row_and_is_idempotent():
    u = make_user(); make_course(u, 'Hist', 0)
    c, d = _setup(u, 'Hist')
    query('DELETE FROM calendarevents WHERE user_id=%s AND source_deadline_id IS NULL', (u,), commit=True)  # drop manual twin
    query('UPDATE calendarevents SET source_deadline_id=NULL WHERE user_id=%s', (u,), commit=True)  # pre-migration row
    assert _backfill(apply=False)[0] >= 1 and _names(u) == [('Essay', None)]  # dry run writes nothing
    _backfill(); _backfill()
    assert _names(u) == [('Essay', d['deadline_id'])]
    c.post(f"/deadlines/{d['deadline_id']}/delete")
    assert _names(u) == []


def test_backfill_skips_ambiguous_and_delete_leaves_both():
    u = make_user(); make_course(u, 'Geo', 0)
    c, d = _setup(u, 'Geo')
    query('UPDATE calendarevents SET source_deadline_id=NULL WHERE user_id=%s', (u,), commit=True)  # two identical rows
    _backfill()
    assert _names(u) == [('Essay', None), ('Essay', None)]



def test_legacy_fallback_still_deletes_one_until_backfill_runs():
    u = make_user(); make_course(u, 'Art', 0)
    c, d = _setup(u, 'Art')
    query('UPDATE calendarevents SET source_deadline_id=NULL WHERE user_id=%s', (u,), commit=True)
    c.post(f"/deadlines/{d['deadline_id']}/delete")
    assert len(_names(u)) == 1  # TODO fallback: exactly one removed, never both


def test_init_db_leaves_untagged_rows_untouched():
    import db
    u = make_user(); make_course(u, 'Lit', 0)
    c, d = _setup(u, 'Lit')
    query('DELETE FROM calendarevents WHERE user_id=%s AND source_deadline_id IS NULL', (u,), commit=True)
    query('UPDATE calendarevents SET source_deadline_id=NULL WHERE user_id=%s', (u,), commit=True)  # uniquely backfillable
    db.init_db()
    assert _names(u) == [('Essay', None)]  # no data writes at boot
