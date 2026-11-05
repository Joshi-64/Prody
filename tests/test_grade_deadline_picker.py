from _jobs_helpers import client_for, make_course, make_deadline, make_user, query


def post(c, cid, did, name='Quiz'):
    return c.post('/grades', data={'course_id': cid, 'item_name': name, 'category': 'Quiz',
                                   'score': '90', 'weight': '10', 'deadline_id': did})


def grades_of(uid):
    return query('SELECT * FROM grades WHERE user_id = %s', (uid,))


def test_link_saved_by_id():
    u = make_user(); c1 = make_course(u, 'A', 0); d = make_deadline(c1, 'Totally different name')
    post(client_for(u), c1, d)
    g = grades_of(u); assert len(g) == 1
    assert query('SELECT grade_id FROM coursedeadlines WHERE deadline_id=%s', (d,), one=True)['grade_id'] == g[0]['grade_id']


def test_empty_choice_no_link():
    u = make_user(); c1 = make_course(u, 'A', 0); d = make_deadline(c1, 'Quiz')  # same name: must NOT auto-link
    post(client_for(u), c1, '')
    assert len(grades_of(u)) == 1
    assert query('SELECT grade_id FROM coursedeadlines WHERE deadline_id=%s', (d,), one=True)['grade_id'] is None


def test_other_users_deadline_rejected():
    u = make_user(); other = make_user()
    c1 = make_course(u, 'A', 0); oc = make_course(other, 'A', 0); od = make_deadline(oc)
    post(client_for(u), c1, od)
    assert grades_of(u) == []
    assert query('SELECT grade_id FROM coursedeadlines WHERE deadline_id=%s', (od,), one=True)['grade_id'] is None


def test_other_users_deadline_with_other_users_course_rejected():
    u = make_user(); other = make_user()
    make_course(u, 'A', 0); oc = make_course(other, 'A', 0); od = make_deadline(oc)
    post(client_for(u), oc, od)
    assert grades_of(u) == [] and grades_of(other) == []
    assert query('SELECT grade_id FROM coursedeadlines WHERE deadline_id=%s', (od,), one=True)['grade_id'] is None


def test_same_user_other_class_rejected():
    u = make_user(); c1 = make_course(u, 'A', 0); c2 = make_course(u, 'B', 1); d2 = make_deadline(c2)
    post(client_for(u), c1, d2)
    assert grades_of(u) == []
    assert query('SELECT grade_id FROM coursedeadlines WHERE deadline_id=%s', (d2,), one=True)['grade_id'] is None


def test_garbage_and_already_linked_rejected():
    u = make_user(); c1 = make_course(u, 'A', 0); d = make_deadline(c1)
    cl = client_for(u)
    post(cl, c1, 'abc'); assert grades_of(u) == []
    post(cl, c1, d); first = grades_of(u)[0]['grade_id']
    post(cl, c1, d, 'Second')
    assert len(grades_of(u)) == 1
    assert query('SELECT grade_id FROM coursedeadlines WHERE deadline_id=%s', (d,), one=True)['grade_id'] == first


def test_picker_lists_only_open_deadlines_and_delete_unlinks():
    u = make_user(); other = make_user(); c1 = make_course(u, 'A', 0); d = make_deadline(c1, 'MyDL')
    make_deadline(make_course(other, 'X', 0), 'OtherUserDL')
    cl = client_for(u)
    html = cl.get('/grades').get_data(as_text=True)
    assert 'MyDL' in html and 'OtherUserDL' not in html and 'Which deadline is this for?' in html
    post(cl, c1, d); gid = grades_of(u)[0]['grade_id']
    assert 'MyDL' not in cl.get('/grades').get_data(as_text=True).split('g-deadline')[1].split('</select>')[0]
    cl.post(f'/grades/delete/{gid}')
    assert query('SELECT grade_id FROM coursedeadlines WHERE deadline_id=%s', (d,), one=True)['grade_id'] is None
