"""db._PooledConnection: close() rolls back an open transaction before the connection returns to the pool."""
import db


class FakeRaw:
    """Stands in for a pooled MySQL connection sharing one 'server' state with the pool."""
    def __init__(self, pool, calls):
        self.pool, self.calls, self.in_transaction, self.pending = pool, calls, False, []

    def start_transaction(self):
        self.in_transaction = True

    def write(self, v):
        self.in_transaction = True
        self.pending.append(v)

    def commit(self):
        self.calls.append('commit'); self.pool.committed += self.pending; self.pending = []; self.in_transaction = False

    def rollback(self):
        self.calls.append('rollback'); self.pending = []; self.in_transaction = False

    def cursor(self, dictionary=False):
        return ('cursor', dictionary)

    def close(self):
        self.calls.append('close'); self.pool.free.append(self)


class FakePool:
    def __init__(self):
        self.calls, self.committed = [], []
        self.free = [FakeRaw(self, self.calls)]

    def get_connection(self):
        return self.free.pop()


def _use_pool(monkeypatch):
    pool = FakePool()
    monkeypatch.setattr(db, 'DB_BACKEND', 'mysql')
    monkeypatch.setattr(db, '_mysql_pool', lambda: pool)
    return pool


def test_direct_open_uncommitted_write_is_clean_on_next_checkout(monkeypatch):
    pool = _use_pool(monkeypatch)
    conn = db.get_db_connection()
    conn.start_transaction()
    conn.write('row')
    conn.close()
    nxt = db.get_db_connection()
    assert nxt.in_transaction is False
    assert nxt.pending == [] and pool.committed == []
    assert nxt.cursor(dictionary=True) == ('cursor', True)  # passthrough


def test_close_without_transaction_skips_rollback(monkeypatch):
    pool = _use_pool(monkeypatch)
    conn = db.get_db_connection()
    conn.close()
    assert pool.calls == ['close']


def test_close_with_transaction_rolls_back_first(monkeypatch):
    pool = _use_pool(monkeypatch)
    conn = db.get_db_connection()
    conn.start_transaction()
    conn.close()
    assert pool.calls == ['rollback', 'close']


def test_commit_then_close_keeps_write(monkeypatch):
    pool = _use_pool(monkeypatch)
    conn = db.get_db_connection()
    conn.write('row'); conn.commit(); conn.close()
    assert pool.committed == ['row'] and pool.calls == ['commit', 'close']


class FakeCnx:
    """Real-connector shape: the session behind a PooledMySQLConnection (`_cnx`)."""
    n = 0

    def __init__(self, fail_rollback=False):
        FakeCnx.n += 1
        self.session, self.connected, self.fail_rollback = FakeCnx.n, True, fail_rollback
        self.in_transaction, self.locks = False, []

    def is_connected(self):
        return self.connected

    def disconnect(self):
        self.connected, self.in_transaction, self.locks = False, False, []  # server drops the session

    def reconnect(self):
        FakeCnx.n += 1
        self.session, self.connected, self.fail_rollback = FakeCnx.n, True, False

    def rollback(self):
        if self.fail_rollback:
            raise RuntimeError('2013 lost connection during rollback')
        self.in_transaction, self.locks = False, []


class FakePooled:
    """Mirrors mysql.connector PooledMySQLConnection: close() always queues `_cnx` back."""
    def __init__(self, pool, cnx):
        self._pool, self._cnx = pool, cnx

    def __getattr__(self, name):
        return getattr(self._cnx, name)

    def close(self):
        self._pool.queue.append(self._cnx); self._cnx = None


class FakeMySQLPool:
    """Mirrors MySQLConnectionPool.get_connection(): reconnect() a queued cnx that is not connected."""
    def __init__(self, cnx):
        self.queue = [cnx]

    def get_connection(self):
        cnx = self.queue.pop()
        if not cnx.is_connected():
            cnx.reconnect()
        return FakePooled(self, cnx)


def test_rollback_failure_discards_connection_next_checkout_fresh(monkeypatch, caplog):
    cnx = FakeCnx(fail_rollback=True)
    pool = FakeMySQLPool(cnx)
    monkeypatch.setattr(db, 'DB_BACKEND', 'mysql')
    monkeypatch.setattr(db, '_mysql_pool', lambda: pool)
    conn = db.get_db_connection()
    old_session = cnx.session
    cnx.in_transaction, cnx.locks = True, ['userinventory row 7']
    conn.close()  # must not raise
    assert 'discarding connection' in caplog.text
    queued = pool.queue[0]
    assert queued.connected is False and queued.in_transaction is False and queued.locks == []  # not returned dirty
    nxt = db.get_db_connection()
    assert nxt.session != old_session and nxt.is_connected()  # fresh session from reconnect()
    assert nxt.in_transaction is False and nxt.locks == []
    nxt.close()
    assert len(pool.queue) == 1  # pool keeps its size


def test_rollback_failure_on_plain_fallback_connection_does_not_raise(monkeypatch):
    cnx = FakeCnx(fail_rollback=True)
    cnx.in_transaction = True
    cnx.close = lambda: None
    wrapped = db._PooledConnection(cnx)
    wrapped.close()
    assert cnx.connected is False
