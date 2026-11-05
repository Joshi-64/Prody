"""Fail the suite if any tracked file still has a merge conflict marker."""
import os
import subprocess

MARKERS = ('<<<<<<<', '>>>>>>>')
# A line that is exactly ======= is a conflict separator (ignore longer ==== rules in markdown/CSS).


def test_no_conflict_markers_in_tracked_files():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = subprocess.check_output(['git', '-C', root, 'ls-files', '-z'])
    paths = [p.decode() for p in out.split(b'\0') if p]
    bad = []
    for rel in paths:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        try:
            text = open(path, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            s = line.lstrip()
            if s.startswith('<<<<<<<') or s.startswith('>>>>>>>') or line == '=======':
                bad.append(f'{rel}:{i}:{line[:80]}')
    assert not bad, 'conflict markers still present:\n' + '\n'.join(bad[:40])


def test_schema_sqlite_parses_into_fresh_db(tmp_path):
    import sqlite3
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sql = open(os.path.join(root, 'schema_sqlite.sql'), encoding='utf-8').read()
    assert '<<<<<<<' not in sql and '>>>>>>>' not in sql
    db = tmp_path / 'schema_check.sqlite3'
    conn = sqlite3.connect(db)
    try:
        conn.executescript(sql)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    for need in ('studyrooms', 'studyroom_members', 'studyroom_strokes',
                 'dm_messages', 'forum_threads', 'forum_replies', 'courseconcepts', 'users'):
        assert need in tables, need
