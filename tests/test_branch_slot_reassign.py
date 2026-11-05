from _jobs_helpers import client_for, make_course, make_deadline, make_user, query


def slot(cid):
    r = query('SELECT branch_slot FROM usercourses WHERE course_id=%s', (cid,), one=True)
    return r and r['branch_slot']


def test_freed_slot_goes_to_earliest_overflow():
    u = make_user(); other = make_user()
    cs = [make_course(u, f'C{i}', i) for i in range(8)]
    o1 = make_course(u, 'O1', None); o2 = make_course(u, 'O2', None)
    oo = make_course(other, 'OtherOverflow', None)
    make_deadline(cs[3])
    client_for(u).post(f'/courses/{cs[3]}/delete')
    assert slot(cs[3]) is None and query('SELECT 1 FROM usercourses WHERE course_id=%s', (cs[3],)) == []
    assert slot(o1) == 3 and slot(o2) is None and slot(oo) is None


def test_delete_overflow_class_changes_nothing():
    u = make_user()
    cs = [make_course(u, f'C{i}', i) for i in range(8)]
    o1 = make_course(u, 'O1', None); o2 = make_course(u, 'O2', None)
    client_for(u).post(f'/courses/{o1}/delete')
    assert slot(o2) is None and [slot(c) for c in cs] == list(range(8))


def test_no_overflow_slot_just_freed():
    u = make_user(); a = make_course(u, 'A', 0); b = make_course(u, 'B', 1)
    client_for(u).post(f'/courses/{a}/delete')
    assert slot(b) == 1


def test_cannot_delete_other_users_class():
    u = make_user(); other = make_user(); oc = make_course(other, 'X', 0)
    client_for(u).post(f'/courses/{oc}/delete')
    assert slot(oc) == 0
