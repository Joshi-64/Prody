"""Critic-3 rule on the Ctrl/Cmd+K /quick-add path."""
from _jobs_helpers import client_for, make_user, query


def course(uid, name, code, slot=0):
    return query('INSERT INTO usercourses (id, course_name, course_code, subject, branch_slot) VALUES (%s,%s,%s,%s,%s)',
                 (uid, name, code, 'Other', slot), commit=True)


def qa(c, text, **kw):
    return c.post('/quick-add', json=dict(text=text, **kw))


def todos(uid):
    return query('SELECT * FROM todolist WHERE user_id = %s', (uid,))


def test_no_class_blocked():
    u = make_user(); r = qa(client_for(u), 'Read ch 4 due fri')
    assert r.status_code == 400 and 'first class' in r.get_json()['error'] and todos(u) == []


def test_missing_due_saves_with_nudge():
    u = make_user(); course(u, 'Bio', 'BIO1'); d = qa(client_for(u), 'Read ch 4 #BIO1').get_json()
    assert d['ok'] and d['nudge'] == 'Add a due date?'
    t = todos(u); assert len(t) == 1 and t[0]['due_date'] is None


def test_quickadd_js_shows_error_inline_and_cache_bumped():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(root, 'static/ui/js/quickadd.js')).read()
    assert 'qa-err' in js and 'err.textContent=d.error' in js
    assert 'quickadd.js?v=2' in open(os.path.join(root, 'templates/base.html')).read()


def test_unknown_or_foreign_class_blocked():
    u = make_user(); o = make_user(); course(u, 'Bio', 'BIO1'); oc = course(o, 'Art', 'ART9')
    c = client_for(u)
    assert qa(c, 'X due fri #ART9').status_code == 400
    assert qa(c, 'X due fri', course_id=oc).status_code == 400
    assert qa(c, 'X', course_id=oc, due_date='2030-01-01').status_code == 400
    assert todos(u) == []


def test_bad_due_date_field_blocked():
    u = make_user(); cid = course(u, 'Bio', 'BIO1')
    assert qa(client_for(u), 'X', course_id=cid, due_date='nope').status_code == 400 and todos(u) == []


def test_valid_and_defaults_to_last_used_class():
    u = make_user(); a = course(u, 'Alpha', 'A1', 0); b = course(u, 'Beta', 'B2', 1); c = client_for(u)
    assert qa(c, 'Two classes no tag due fri').status_code == 400  # ambiguous, nothing last-used yet
    assert qa(c, 'First due fri #B2').get_json()['ok']
    assert qa(c, 'Second due tomorrow').get_json()['ok']
    rows = sorted(todos(u), key=lambda t: t['task_id'])
    assert [t['course_id'] for t in rows] == [b, b] and all(t['due_date'] for t in rows)
    assert qa(c, 'Third', course_id=a, due_date='2030-01-01').get_json()['ok']
