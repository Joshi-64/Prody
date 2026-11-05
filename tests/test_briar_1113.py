import re
"""Briar 11-13: class-coloured deadline cards, accessible urgency chips, delete moved into the row sheet."""
import os
from datetime import date, datetime, timedelta

import apptime  # app clock (America/New_York), not the server's
from _jobs_helpers import client_for, make_user, query
from profiles import class_dot_colour

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLOR = '#A8C8E8'


def course(uid):
    return query('INSERT INTO usercourses (id, course_name, subject, branch_slot, color) VALUES (%s,%s,%s,%s,%s)',
                 (uid, 'Bio', 'Other', 0, COLOR), commit=True)


def deadline(cid, days, name='Lab'):
    return query('INSERT INTO coursedeadlines (course_id, deadline_name, deadline_date) VALUES (%s,%s,%s)',
                 (cid, name, apptime.now_local().replace(hour=23, minute=0) + timedelta(days=days)), commit=True)


def task(uid, cid, days, name='T'):
    return query('INSERT INTO todolist (user_id, task_name, due_date, course_id, category, progress) VALUES (%s,%s,%s,%s,%s,0)',
                 (uid, name, (apptime.today_local() + timedelta(days=days)).isoformat(), cid, 'task'), commit=True)


def test_11_rail_and_dot_use_class_colour():
    u = make_user(); cid = course(u); deadline(cid, 0); deadline(cid, 20, 'Far')
    html = client_for(u).get('/calendar').get_data(as_text=True)
    dot = class_dot_colour(COLOR)
    assert html.count(f'class="ct-rail" aria-hidden="true" style="background:{dot}"') == 2
    assert 'u-urgent' not in html
    css = open(os.path.join(ROOT, 'static/ui/css/caltodo.css')).read()
    assert '.ct-dcard.u-urgent .ct-rail' not in css and re.search(r'caltodo\.css\?v=[0-9a-f]{10}', html)  # perf_r1: content-hashed URL


def test_12_chips_tint_plus_label():
    u = make_user(); cid = course(u); deadline(cid, 0); deadline(cid, 1, 'B'); deadline(cid, 9, 'C')
    html = client_for(u).get('/calendar').get_data(as_text=True)
    assert 'class="ct-chip u-soon"><span class="ms" aria-hidden="true">schedule</span>Today' in html
    assert 'schedule</span>Tomorrow' in html and 'class="ct-chip u-later"><span class="ms" aria-hidden="true">event</span>9 days' in html


def test_12_overdue_chip_on_todo():
    u = make_user(); cid = course(u); task(u, cid, -3, 'Late'); task(u, cid, 1, 'Soon'); task(u, cid, 30, 'Later')
    html = client_for(u).get('/tasks').get_data(as_text=True)
    assert 'class="ct-chip u-over"><span class="ms" aria-hidden="true">error</span>Overdue · 3d' in html
    assert 'u-soon' in html and 'u-later' in html


def test_13_no_row_trash_delete_in_sheet_post_only():
    u = make_user(); cid = course(u); tid = task(u, cid, 2, 'Essay')
    c = client_for(u); html = c.get('/tasks').get_data(as_text=True)
    assert 'ct-del' not in html and 'aria-label="Delete Essay"' not in html
    assert f'data-del="/tasks/delete/{tid}"' in html and 'id="ctRowDel"' in html
    assert '<form method="POST" id="ctRowDel"' in html
    assert c.get(f'/tasks/delete/{tid}').status_code == 405
    assert query('SELECT 1 FROM todolist WHERE task_id=%s', (tid,))
    c.post(f'/tasks/delete/{tid}')
    assert not query('SELECT 1 FROM todolist WHERE task_id=%s', (tid,))
