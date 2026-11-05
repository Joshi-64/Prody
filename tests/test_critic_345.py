"""Critic items 3-5: first task needs class + due date; Calendar 'Add a deadline' opens To-Do sheet; empty Calendar state."""
from datetime import datetime, timedelta

import pytest

from _jobs_helpers import client_for, make_course, make_user, query


pytestmark = pytest.mark.usefixtures('csrf_off')  # every test here posts forms without a token


def tasks_of(uid):
    return query('SELECT * FROM todolist WHERE user_id = %s', (uid,))


# --- item 3 ---
def test_no_classes_prompts_first_class_and_blocks_task():
    u = make_user(); c = client_for(u)
    html = c.get('/tasks').get_data(as_text=True)
    assert 'Add your first class' in html and 'id="ctCls"' not in html
    c.post('/tasks', data={'task_name': 'Lab', 'category': 'task', 'due_date': '2030-01-01'})
    assert tasks_of(u) == []


def test_task_requires_class_and_due_date():
    u = make_user(); cid = make_course(u, 'Bio', 0); c = client_for(u)
    c.post('/tasks', data={'task_name': 'A', 'category': 'task', 'due_date': '2030-01-01'})
    assert tasks_of(u) == []  # class still required
    r = c.post('/tasks', data={'task_name': 'B', 'category': 'task', 'course_id': cid}, follow_redirects=True)
    assert 'Add a due date?' in r.get_data(as_text=True)
    c.post('/tasks', data={'task_name': 'C', 'category': 'task', 'course_id': cid, 'due_date': 'garbage'})
    c.post('/tasks', data={'task_name': 'D', 'category': 'task', 'course_id': cid, 'due_date': '2030-01-01'})
    got = {t['task_name']: t['due_date'] for t in tasks_of(u)}
    assert set(got) == {'B', 'C', 'D'} and got['B'] is None and got['C'] is None and str(got['D'])[:10] == '2030-01-01'


def test_other_users_class_rejected():
    u = make_user(); o = make_user(); make_course(u, 'Mine', 0); oc = make_course(o, 'Theirs', 0)
    client_for(u).post('/tasks', data={'task_name': 'X', 'category': 'task', 'course_id': oc, 'due_date': '2030-01-01'})
    assert tasks_of(u) == []


def test_concept_needs_no_class_or_due():
    u = make_user(); c = client_for(u)
    c.post('/tasks', data={'task_name': 'Recursion', 'category': 'concept'})
    assert len(tasks_of(u)) == 1


def test_picker_defaults_to_last_used_class_and_due_required():
    u = make_user(); a = make_course(u, 'Alpha', 0); b = make_course(u, 'Beta', 1); c = client_for(u)
    c.post('/tasks', data={'task_name': 'T1', 'category': 'task', 'course_id': b, 'due_date': '2030-01-01'})
    html = c.get('/tasks').get_data(as_text=True)
    assert f'<option value="{b}" selected>' in html and f'<option value="{a}">' in html
    assert 'name="due_date" value="">' in html


# --- item 4 ---
def test_calendar_add_deadline_links_to_todo_sheet_with_due():
    u = make_user(); html = client_for(u).get('/calendar').get_data(as_text=True)
    import apptime
    today = apptime.today_local().isoformat()
    assert f'/tasks?add=1&amp;due={today}' in html and 'add_courses' not in html.split('Add a deadline')[0][-300:]


def test_todo_sheet_opens_prefilled():
    u = make_user(); make_course(u, 'Alpha', 0)
    html = client_for(u).get('/tasks?add=1&due=2030-02-03').get_data(as_text=True)
    assert 'value="2030-02-03">' in html and 'ctAdd(\'task\', "2030-02-03")' in html
    bad = client_for(u).get('/tasks?add=1&due=<x>').get_data(as_text=True)
    assert '<x>' not in bad and 'name="due_date" value="">' in bad


# --- item 5 ---
def test_empty_calendar_single_empty_state():
    u = make_user(); html = client_for(u).get('/calendar').get_data(as_text=True)
    assert 'id="ctCalEmpty"' in html
    # owner (clay round): the month grid shows alongside the empty message, not instead of it
    assert 'id="ppWeek"' not in html and 'id="calendar"' in html and 'Suggest study blocks' not in html
    assert html.count('data-add-deadline href') == 1 and 'aria-label="New event"' not in html


def test_calendar_with_events_shows_planner():
    u = make_user()
    query('INSERT INTO calendarevents (user_id, event_name, event_date, duration_minutes) VALUES (%s, %s, %s, %s)',
          (u, 'Dinner', datetime.now() + timedelta(days=1), 60), commit=True)
    html = client_for(u).get('/calendar').get_data(as_text=True)
    assert 'id="ctCalEmpty"' not in html and 'id="ppWeek"' in html and 'id="calendar"' in html
