"""libSQL HTTP client batches DML into one BEGIN…COMMIT pipeline."""
import db as dbmod


def test_libsql_commit_wraps_buffered_writes_in_begin_commit(monkeypatch):
    monkeypatch.setattr(dbmod, 'TURSO_DATABASE_URL', 'libsql://example.turso.io')
    monkeypatch.setattr(dbmod, 'TURSO_AUTH_TOKEN', 'tok')
    seen = []

    def fake_pipeline(self, requests):
        seen.append(requests)
        # BEGIN + N stmts + COMMIT + close
        out = [{'type': 'ok', 'response': {'result': {}}}]
        for i, req in enumerate(requests):
            if req.get('type') == 'execute' and (req.get('stmt') or {}).get('sql') not in ('BEGIN', 'COMMIT', 'ROLLBACK'):
                out.append({'type': 'ok', 'response': {'result': {'affected_row_count': 1, 'last_insert_rowid': '9'}}})
            elif req.get('type') == 'close':
                out.append({'type': 'ok'})
            else:
                out.append({'type': 'ok', 'response': {'result': {}}})
        # align length
        return [{'type': 'ok', 'response': {'result': {'last_insert_rowid': '9' if i == 1 else None}}} for i in range(len(requests))]

    monkeypatch.setattr(dbmod._LibsqlConnection, '_pipeline', fake_pipeline)
    conn = dbmod._LibsqlConnection()
    cur = conn.cursor()
    cur.execute('INSERT INTO t (a) VALUES (%s)', (1,))
    cur.execute('INSERT INTO t (a) VALUES (%s)', (2,))
    assert seen == []  # buffered, not sent yet
    conn.commit()
    assert len(seen) == 1
    reqs = seen[0]
    assert reqs[0]['stmt']['sql'] == 'BEGIN'
    assert reqs[-2]['stmt']['sql'] == 'COMMIT'
    assert reqs[-1]['type'] == 'close'
    assert sum(1 for r in reqs if r.get('type') == 'execute' and r['stmt']['sql'].startswith('INSERT')) == 2


def test_libsql_rollback_discards_buffer(monkeypatch):
    monkeypatch.setattr(dbmod, 'TURSO_DATABASE_URL', 'libsql://example.turso.io')
    monkeypatch.setattr(dbmod, 'TURSO_AUTH_TOKEN', 'tok')
    seen = []
    monkeypatch.setattr(dbmod._LibsqlConnection, '_pipeline', lambda self, requests: seen.append(requests) or [])
    conn = dbmod._LibsqlConnection()
    cur = conn.cursor()
    cur.execute('DELETE FROM t WHERE id=%s', (1,))
    conn.rollback()
    conn.commit()
    assert seen == []


def test_locked_user_txn_libsql_does_not_use_for_update(monkeypatch):
    monkeypatch.setattr(dbmod, 'DB_BACKEND', 'libsql')
    monkeypatch.setattr(dbmod, 'TURSO_DATABASE_URL', 'libsql://example.turso.io')
    monkeypatch.setattr(dbmod, 'TURSO_AUTH_TOKEN', 'tok')

    seen_sql = []

    class FakeConn(dbmod._LibsqlConnection):
        def __init__(self):
            self._base = 'https://example.turso.io'
            self._token = 'tok'
            self._buf = []
            self._lastrowid = None
            self.started = False

        def start_transaction(self):
            self.started = True

        def _pipeline(self, requests):
            for req in requests:
                if req.get('type') == 'execute':
                    seen_sql.append((req.get('stmt') or {}).get('sql', ''))
            return [{'type': 'ok', 'response': {'result': {'cols': [{'name': 'id'}], 'rows': [[{'type': 'integer', 'value': '1'}]]}}}]

    monkeypatch.setattr(dbmod, 'get_db_connection', FakeConn)
    conn, cur = dbmod.locked_user_txn(1)
    assert conn.started is True
    assert any('SELECT id FROM users' in s for s in seen_sql)
    assert not any('FOR UPDATE' in s.upper() for s in seen_sql)
