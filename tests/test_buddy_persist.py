"""Buddy chat history/send/clear must go through helpers.query (Turso/SQLite), not a side store."""
import os, tempfile, inspect
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'buddy_persist.sqlite3'))
from unittest import mock
import buddy
from helpers import query
from _jobs_helpers import client_for, make_user


def test_buddy_io_uses_helpers_query_only():
    src = inspect.getsource(buddy)
    assert 'sqlite3' not in src and 'localStorage' not in src
    assert "query('SELECT" in src and "query('INSERT INTO chatmessages" in src
    assert "query('DELETE FROM chatmessages" in src


def test_buddy_send_clear_roundtrip(monkeypatch, csrf_off):
    uid = make_user()
    monkeypatch.setattr(buddy, 'ai_available', lambda: True)
    monkeypatch.setattr(buddy, 'ai_chat', lambda msgs, timeout=30: 'ok leaf')
    c = client_for(uid)
    assert c.post('/buddy', data={'message': 'explain mitosis'}).status_code in (200, 302)
    rows = query('SELECT role, content FROM chatmessages WHERE user_id=%s ORDER BY message_id', (uid,))
    assert any(r['role'] == 'user' and 'mitosis' in r['content'] for r in rows)
    assert any(r['role'] == 'assistant' for r in rows)
    assert c.post('/buddy/clear').status_code in (200, 302)
    assert not query('SELECT message_id FROM chatmessages WHERE user_id=%s', (uid,))
