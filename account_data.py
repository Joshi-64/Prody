"""Account wipe: remove a user and every row keyed to them in one transaction."""
from db import DB_BACKEND, get_db_connection
from helpers import _clear_stats_cache, _release

# Order matters: dependents before parents. Studyrooms have no ON DELETE CASCADE to users.
_ACCOUNT_TABLES = [
    ('studyroom_strokes',
     'user_id = %s OR room_id IN (SELECT room_id FROM studyrooms WHERE owner_id = %s)'),
    ('studyroom_members',
     'user_id = %s OR room_id IN (SELECT room_id FROM studyrooms WHERE owner_id = %s)'),
    ('studyrooms', 'owner_id = %s'),
    ('forum_replies', 'author_id = %s'),
    ('forum_threads', 'author_id = %s'),
    ('dm_messages', 'sender_id = %s OR recipient_id = %s'),
    ('courseconcepts', 'course_id IN (SELECT course_id FROM usercourses WHERE id = %s OR user_id = %s)'),
    ('coursedeadlines', 'course_id IN (SELECT course_id FROM usercourses WHERE id = %s OR user_id = %s)'),
    ('grades', 'user_id = %s'),
    ('todolist', 'user_id = %s'),
    ('calendarevents', 'user_id = %s'),
    ('studysessions', 'user_id = %s'),
    ('chatmessages', 'user_id = %s'),
    ('userinventory', 'user_id = %s'),
    ('plantmilestones', 'user_id = %s'),
    ('plantcare', 'user_id = %s'),
    ('plantcare_utc', 'user_id = %s'),
    ('journalentries', 'user_id = %s'),
    ('friend_request_log', 'user_id = %s'),
    ('friendships', 'requester_id = %s OR addressee_id = %s'),
    ('userprofiles', 'user_id = %s'),
    ('usercourses', 'id = %s OR user_id = %s'),
    ('users', 'id = %s'),
]
_OPTIONAL_TABLES = {
    'plantcare_utc', 'forum_replies', 'forum_threads', 'dm_messages', 'courseconcepts',
    'chatmessages',
}


def _existing_tables(cur):
    names = {t for t, _ in _ACCOUNT_TABLES}
    if DB_BACKEND in ('sqlite', 'libsql'):
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        rows = cur.fetchall() or []
        have = set()
        for r in rows:
            have.add(r['name'] if isinstance(r, dict) else r[0])
        return names & have
    cur.execute(
        "SELECT table_name AS name FROM information_schema.tables WHERE table_schema = DATABASE()")
    rows = cur.fetchall() or []
    have = set()
    for r in rows:
        have.add(r['name'] if isinstance(r, dict) else r[0])
    return names & have


def delete_user_data(uid):
    """Remove the user and every row keyed to them in one transaction; rolls back on any error."""
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        present = _existing_tables(cur)
        if hasattr(conn, 'start_transaction'):
            try:
                conn.start_transaction()
            except Exception:
                pass
        for table, where in _ACCOUNT_TABLES:
            if table in _OPTIONAL_TABLES and table not in present:
                continue
            if table not in present and table in _OPTIONAL_TABLES:
                continue
            params = (uid,) * where.count('%s')
            cur.execute(f'DELETE FROM {table} WHERE {where}', params)
        conn.commit()
        _clear_stats_cache()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        cur.close()
        _release(conn)
