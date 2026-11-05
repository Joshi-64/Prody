"""Database access for Prody.

MySQL 8 is the default (class requirement). For quick local development you can
set PRODY_DB=sqlite to use a file-based SQLite database instead; all queries go
through a thin adapter that accepts the same %s placeholders and
cursor(dictionary=True) calls as mysql-connector.
"""
import logging
import os
import sqlite3
from decimal import Decimal
from datetime import date, datetime

DB_CONFIG = {
    'host': os.environ.get('PRODY_DB_HOST', 'localhost'),
    'user': os.environ.get('PRODY_DB_USER', 'root'),
    'password': os.environ.get('PRODY_DB_PASSWORD', 'YOUR_PASSWORD_HERE'),  # Enter your MySQL password
    'database': os.environ.get('PRODY_DB_NAME', 'prody_dev'),
    'time_zone': '+00:00',  # CURRENT_TIMESTAMP defaults store UTC, matching apptime
}
def apply_port_ssl_env(config, env=None):
    """Optional, for hosted MySQL such as TiDB Serverless (port 4000, TLS only). Unset = unchanged behaviour.

    Raises FileNotFoundError naming the path if PRODY_DB_SSL_CA points at a missing file.
    """
    env = os.environ if env is None else env
    if env.get('PRODY_DB_PORT'):
        config['port'] = int(env['PRODY_DB_PORT'])
    ca = env.get('PRODY_DB_SSL_CA')
    if ca:
        if not os.path.isfile(ca):
            raise FileNotFoundError(f"PRODY_DB_SSL_CA points at a missing file: {ca}")
        config['ssl_ca'] = ca
        config['ssl_verify_cert'] = True
        config['ssl_verify_identity'] = True
    return config


apply_port_ssl_env(DB_CONFIG)

SQLITE_PATH = os.environ.get(
    'PRODY_SQLITE_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prody_dev.sqlite3'))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TURSO_DATABASE_URL = (os.environ.get('TURSO_DATABASE_URL') or '').strip()
TURSO_AUTH_TOKEN = (os.environ.get('TURSO_AUTH_TOKEN') or '').strip()


def _turso_http_base(url):
    """libsql://host -> https://host; leave https:// as-is."""
    u = url.rstrip('/')
    if u.startswith('libsql://'):
        u = 'https://' + u[len('libsql://'):]
    return u


def _turso_opt_in():
    """True only when Turso is explicitly opted in for non-production.

    Preview/local must set PRODY_USE_TURSO=1 (true/yes/on). Production
    (VERCEL_ENV=production) never selects Turso even if the flag or TURSO_*
    leak in — TiDB/MySQL stays the default path.
    """
    flag = (os.environ.get('PRODY_USE_TURSO') or '').strip().lower()
    if flag not in ('1', 'true', 'yes', 'on'):
        return False
    vercel_env = (os.environ.get('VERCEL_ENV') or '').strip().lower()
    if vercel_env == 'production':
        return False
    return True


def _pick_backend():
    """Choose DB backend.

    - PRODY_DB=sqlite → SQLite (explicit only; used by the test suite / local).
    - Turso/libSQL only when PRODY_USE_TURSO is opted in AND VERCEL_ENV is not
      production. Then both TURSO_DATABASE_URL and TURSO_AUTH_TOKEN are required;
      incomplete opted-in config raises (no silent SQLite fallback). TURSO_*
      present without the opt-in flag are ignored — production stays mysql/TiDB.
      No startup reachability ping; connection/query failures raise to the caller.
    - Else → PRODY_DB or mysql (TiDB/MySQL production path).
    """
    explicit = (os.environ.get('PRODY_DB') or '').strip().lower()
    if explicit == 'sqlite':
        return 'sqlite'

    url = (TURSO_DATABASE_URL or os.environ.get('TURSO_DATABASE_URL') or '').strip()
    token = (TURSO_AUTH_TOKEN or os.environ.get('TURSO_AUTH_TOKEN') or '').strip()
    any_turso = bool(url or token) or any(
        k.startswith('TURSO_') and (os.environ.get(k) or '').strip() for k in os.environ
    )

    if _turso_opt_in():
        if not any_turso and not (url or token):
            raise RuntimeError(
                'PRODY_USE_TURSO is set but no TURSO_* config was found. '
                'Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN, or unset PRODY_USE_TURSO.'
            )
        if not url or not token:
            raise RuntimeError(
                'Turso is opted in (PRODY_USE_TURSO) but misconfigured: set both '
                'TURSO_DATABASE_URL and TURSO_AUTH_TOKEN. Refusing silent SQLite fallback '
                '(set PRODY_DB=sqlite to use SQLite explicitly).'
            )
        return 'libsql'

    # TURSO_* may be present accidentally in production — ignore; never touch libsql.
    return explicit or 'mysql'


DB_BACKEND = _pick_backend()

if DB_BACKEND in ('sqlite', 'libsql'):
    IntegrityError = sqlite3.IntegrityError
else:
    import mysql.connector
    IntegrityError = mysql.connector.IntegrityError


def _as_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- SQLite adapter
def _parse_dt(b):
    s = b.decode()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return s


sqlite3.register_converter('DATETIME', _parse_dt)
sqlite3.register_converter('TIMESTAMP', _parse_dt)
sqlite3.register_converter('DATE', lambda b: _parse_dt(b).date() if isinstance(_parse_dt(b), datetime) else b.decode())
sqlite3.register_adapter(datetime, lambda d: d.strftime('%Y-%m-%d %H:%M:%S'))
sqlite3.register_adapter(date, lambda d: d.isoformat())


class _SqliteCursor:
    def __init__(self, conn, dictionary):
        self._cur = conn.cursor()
        self._dict = dictionary

    def execute(self, sql, params=()):
        self._cur.execute(sql.replace('%s', '?'), tuple(params or ()))
        return self

    def _row(self, r):
        if r is None:
            return None
        return dict(r) if self._dict else tuple(r)

    def fetchone(self):
        return self._row(self._cur.fetchone())

    def fetchall(self):
        return [self._row(r) for r in self._cur.fetchall()]

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        self._cur.close()


class _SqliteConnection:
    def __init__(self):
        self._conn = sqlite3.connect(SQLITE_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute('PRAGMA foreign_keys = ON')

    def cursor(self, dictionary=False):
        return _SqliteCursor(self._conn, dictionary)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


class _PooledConnection:
    """Wraps a MySQL connection so close() rolls back an open transaction before it returns to the
    pool (pool_reset_session=False keeps checkouts cheap, so nothing else would clear it)."""
    def __init__(self, conn):
        self._raw = conn

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def close(self):
        try:
            if self._raw.in_transaction:
                self._raw.rollback()
        except Exception as e:
            # Rollback failed: the session may still hold an open transaction and row locks, so never hand
            # it back as-is. Drop the socket (the server then rolls back and frees the locks), then return the
            # slot. mysql.connector's pool.get_connection() sees is_connected() is False and reconnect()s, so
            # the next checkout is a fresh session and the pool keeps its size.
            logging.getLogger(__name__).warning('db: rollback on close failed (%s); discarding connection', type(e).__name__)
            self._discard()
        finally:
            try:
                self._raw.close()
            except Exception as e:  # a disconnected plain connection can complain on close; it is gone either way
                logging.getLogger(__name__).warning('db: close after discard failed (%s)', type(e).__name__)

    def _discard(self):
        inner = getattr(self._raw, '_cnx', None) or self._raw  # PooledMySQLConnection wraps the real one in _cnx
        try:
            inner.disconnect()
        except Exception:
            try:
                inner.shutdown()  # hard socket close, no COM_QUIT
            except Exception:
                pass


_POOL = None


def _mysql_pool():
    # Opening a MySQL connection costs ~10-14ms and pages run 15-40 queries, each on its own
    # connection; a pool reuses them (close() hands the connection back to the pool).
    global _POOL
    if _POOL is None:
        from mysql.connector import pooling
        _POOL = pooling.MySQLConnectionPool(pool_name='prody', pool_size=int(os.environ.get('PRODY_DB_POOL', 16)),
                                            pool_reset_session=False, **DB_CONFIG)
    return _POOL


def locked_user_txn(uid):
    """Open a connection with a write transaction that holds the user's lock until commit/rollback.
    SQLite: BEGIN IMMEDIATE (one writer at a time).
    libSQL/Turso: buffer DML into one Hrana pipeline wrapped in BEGIN…COMMIT (HTTP has no
    interactive lock; SELECT FOR UPDATE is skipped).
    MySQL/TiDB: SELECT ... FOR UPDATE on the user's row."""
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    if DB_BACKEND == 'sqlite':
        conn._conn.isolation_level = None
        conn._conn.execute('PRAGMA busy_timeout = 10000')
        conn._conn.execute('BEGIN IMMEDIATE')
    elif DB_BACKEND == 'libsql':
        conn.start_transaction()
        cur.execute('SELECT id FROM users WHERE id = %s', (uid,))
        cur.fetchall()
    else:
        conn.start_transaction()
        cur.execute('SELECT id FROM users WHERE id = %s FOR UPDATE', (uid,))
        cur.fetchall()
    return conn, cur



# ---------------------------------------------------------------- Turso / libSQL (HTTP pipeline via requests)
def _turso_arg(v):
    """Encode a Python value for Turso HTTP /v2/pipeline args.
    Floats (and Decimal) must be JSON numbers — Turso rejects stringified f64
    ("invalid type: string \"12.5\", expected f64"). Integers stay stringified.
    """
    if v is None:
        return {'type': 'null'}
    if isinstance(v, bool):
        return {'type': 'integer', 'value': '1' if v else '0'}
    if isinstance(v, int) and not isinstance(v, bool):
        return {'type': 'integer', 'value': str(v)}
    if isinstance(v, float):
        return {'type': 'float', 'value': float(v)}
    if isinstance(v, Decimal):
        return {'type': 'float', 'value': float(v)}
    if isinstance(v, (datetime, date)):
        return {'type': 'text', 'value': v.strftime('%Y-%m-%d %H:%M:%S') if isinstance(v, datetime) else v.isoformat()}
    return {'type': 'text', 'value': str(v)}


def _turso_decode(cell):
    """Turso HTTP returns typed cells with stringified values; coerce to Python types."""
    if cell is None or cell.get('type') == 'null' or 'value' not in cell and cell.get('type') == 'null':
        return None
    typ = (cell.get('type') or '').lower()
    val = cell.get('value')
    if typ in ('null',) or val is None and typ != 'text':
        return None
    if typ in ('integer', 'int'):
        try:
            return int(val)
        except (TypeError, ValueError):
            return val
    if typ in ('float', 'real', 'numeric'):
        try:
            return float(val)
        except (TypeError, ValueError):
            return val
    if typ == 'blob':
        return val
    # text / default
    return val


class _LibsqlCursor:
    """Minimal mysql-style cursor over Turso HTTP. SQL keeps %s placeholders (converted to ?).

    Writes are buffered on the connection until commit() so multi-step DML can share one
    Hrana pipeline wrapped in BEGIN…COMMIT. Reads run immediately (flushing any pending
    writes first so DDL/DML is visible to later PRAGMA/SELECT).
    """
    def __init__(self, conn, dictionary):
        self._conn = conn
        self._dict = dictionary
        self._rows = []
        self._i = 0
        self._own_lastrowid = None
        self.rowcount = -1
        self._cols = []

    @property
    def lastrowid(self):
        if self._own_lastrowid is not None:
            return self._own_lastrowid
        return getattr(self._conn, '_lastrowid', None)

    @lastrowid.setter
    def lastrowid(self, v):
        self._own_lastrowid = v

    @staticmethod
    def _is_read(sql):
        u = sql.lstrip().upper()
        return u.startswith('SELECT') or u.startswith('PRAGMA') or u.startswith('EXPLAIN')

    def execute(self, sql, params=()):
        q = sql.replace('%s', '?')
        args = tuple(params or ())
        if self._is_read(q):
            if self._conn._buf:
                self._conn._flush(commit=True)
            return self._execute_immediate(q, args)
        self._conn._buf.append((q, args))
        self._rows = []
        self._i = 0
        self._cols = []
        self.rowcount = -1
        self.lastrowid = None
        return self

    def _execute_immediate(self, q, args):
        results = self._conn._pipeline([
            {
                'type': 'execute',
                'stmt': {'sql': q, 'args': [_turso_arg(p) for p in args]},
            },
            {'type': 'close'},
        ])
        return self._apply_result(results[0])

    def _apply_result(self, entry):
        if not entry or entry.get('type') == 'error':
            err = (entry.get('error') if entry else None) or entry
            msg = str(err)
            if 'UNIQUE' in msg.upper() or 'CONSTRAINT' in msg.upper():
                raise IntegrityError(msg)
            raise RuntimeError(f'Turso execute failed: {err}')
        res = entry.get('response', {}).get('result', {})
        cols = [c.get('name') for c in (res.get('cols') or [])]
        self._cols = cols
        rows = []
        for row in res.get('rows') or []:
            vals = [_turso_decode(cell) for cell in row]
            rows.append(dict(zip(cols, vals)) if self._dict else tuple(vals))
        self._rows = rows
        self._i = 0
        try:
            self.rowcount = int(res.get('affected_row_count') if res.get('affected_row_count') is not None else len(rows))
        except (TypeError, ValueError):
            self.rowcount = len(rows)
        lid = res.get('last_insert_rowid')
        if lid is not None:
            try:
                self.lastrowid = int(lid)
            except (TypeError, ValueError):
                self.lastrowid = lid
        return self

    def fetchone(self):
        if self._i >= len(self._rows):
            return None
        r = self._rows[self._i]
        self._i += 1
        return r

    def fetchall(self):
        out = self._rows[self._i:]
        self._i = len(self._rows)
        return out

    def close(self):
        pass


class _LibsqlConnection:
    """Turso HTTP connection. DML is buffered and committed as one BEGIN…COMMIT pipeline."""

    def __init__(self):
        self._base = _turso_http_base(TURSO_DATABASE_URL)
        self._token = TURSO_AUTH_TOKEN
        self._buf = []  # list[(sql, params)] pending DML/DDL
        self._lastrowid = None

    def cursor(self, dictionary=False):
        return _LibsqlCursor(self, dictionary)

    def start_transaction(self):
        """Begin an explicit write batch (locked_user_txn). Pending buffer is flushed first."""
        if self._buf:
            self._flush(commit=True)

    def commit(self):
        lid = self._flush(commit=True)
        if lid is not None:
            self._lastrowid = lid

    def rollback(self):
        self._buf = []

    def close(self):
        self._buf = []

    def _pipeline(self, requests):
        import requests as req
        try:
            r = req.post(
                f'{self._base}/v2/pipeline',
                headers={'Authorization': f'Bearer {self._token}', 'Content-Type': 'application/json'},
                json={'requests': requests},
                timeout=45,
            )
            r.raise_for_status()
        except Exception as e:
            raise RuntimeError(
                'Turso/libSQL request failed (%s). Check TURSO_DATABASE_URL / TURSO_AUTH_TOKEN; '
                'SQLite is only used when PRODY_DB=sqlite is set explicitly.' % (type(e).__name__,)
            ) from e
        data = r.json()
        return data.get('results') or []

    def _flush(self, commit=True):
        stmts = self._buf
        self._buf = []
        if not stmts:
            return None
        end = 'COMMIT' if commit else 'ROLLBACK'
        requests = [{'type': 'execute', 'stmt': {'sql': 'BEGIN'}}]
        for sql, params in stmts:
            requests.append({
                'type': 'execute',
                'stmt': {'sql': sql, 'args': [_turso_arg(p) for p in params]},
            })
        requests.append({'type': 'execute', 'stmt': {'sql': end}})
        requests.append({'type': 'close'})
        results = self._pipeline(requests)
        # results[0]=BEGIN, results[1:-2]=stmts, results[-2]=COMMIT/ROLLBACK, results[-1]=close
        last_lid = None
        for i, entry in enumerate(results):
            if entry.get('type') == 'error':
                err = entry.get('error') or entry
                msg = str(err)
                if 'UNIQUE' in msg.upper() or 'CONSTRAINT' in msg.upper():
                    raise IntegrityError(msg)
                raise RuntimeError(f'Turso execute failed: {err}')
            if 0 < i < len(results) - 2:
                res = entry.get('response', {}).get('result', {}) or {}
                lid = res.get('last_insert_rowid')
                if lid is not None:
                    try:
                        last_lid = int(lid)
                    except (TypeError, ValueError):
                        last_lid = lid
        return last_lid


def get_db_connection():
    if DB_BACKEND == 'libsql':
        return _LibsqlConnection()
    if DB_BACKEND == 'sqlite':
        return _SqliteConnection()
    try:
        return _PooledConnection(_mysql_pool().get_connection())
    except mysql.connector.errors.PoolError:  # pool exhausted: fall back to a plain connection
        return _PooledConnection(mysql.connector.connect(**DB_CONFIG))


# ---------------------------------------------------------------- schema
def _columns(cursor, table_name):
    if DB_BACKEND in ('sqlite', 'libsql'):
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row[1] for row in cursor.fetchall()}
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    return {row[0] for row in cursor.fetchall()}


# Columns added after Sprint 3. Applied to existing databases so nobody has to drop tables.
_NEW_COLUMNS = [
    ('users', 'created_at', 'DATETIME NULL'),
    ('users', 'last_seen_at', 'DATETIME NULL'),  # friends: online = seen in last 5 min
    ('studyrooms', 'friends_can_join', 'BOOLEAN NOT NULL DEFAULT 1'),  # friends discover/join without invite
    ('usercourses', 'subject', "VARCHAR(100) DEFAULT ''"),
    ('usercourses', 'color', "VARCHAR(20) DEFAULT '#CFDCC6'"),
    ('calendarevents', 'flag_status', 'VARCHAR(20) NULL'),
    ('calendarevents', 'duration_minutes', 'INT DEFAULT 60'),
    ('calendarevents', 'source_deadline_id', 'INT NULL'),  # deadline mirror rows; manual events stay NULL
    ('coursedeadlines', 'is_completed', 'BOOLEAN DEFAULT FALSE'),
    ('todolist', 'course_id', 'INT NULL'),
    ('todolist', 'progress', 'INT DEFAULT 0'),
    ('todolist', 'category', "VARCHAR(20) DEFAULT 'task'"),
    ('userprofiles', 'pot_key', "VARCHAR(50) DEFAULT 'pot_basket'"),
    ('userprofiles', 'acc_keys', "VARCHAR(200) DEFAULT ''"),
    ('userprofiles', 'scene_key', "VARCHAR(50) DEFAULT ''"),
    ('userprofiles', 'plant_name', "VARCHAR(40) DEFAULT 'Prody'"),
    ('userprofiles', 'plant_stage_seen', 'INT DEFAULT 0'),
    ('userprofiles', 'soil_key', "VARCHAR(50) DEFAULT ''"),
    ('userprofiles', 'sky_key', "VARCHAR(50) DEFAULT 'sky_clear_day'"),
    ('userprofiles', 'flower_key', "VARCHAR(50) DEFAULT ''"),
    ('userprofiles', 'leaves_key', "VARCHAR(50) DEFAULT ''"),
    ('userprofiles', 'decor_keys', "VARCHAR(200) DEFAULT ''"),
    ('studysessions', 'completed', 'BOOLEAN NOT NULL DEFAULT 0'),  # timer ran to 0 -> a flower on that course's branch
    ('userprofiles', 'species_key', "VARCHAR(50) DEFAULT 'species_classic'"),  # plant species slot
    ('friendships', 'user_lo', 'INT NULL'),  # LEAST(requester, addressee): direction-free pair key
    ('friendships', 'user_hi', 'INT NULL'),
    ('userprofiles', 'show_on_leaderboard', 'BOOLEAN NOT NULL DEFAULT 0'),  # opt-in, off by default
    # tree migrations (docs/migrations_plan.md)
    ('todolist', 'completed_at', 'DATETIME NULL'),
    ('coursedeadlines', 'completed_at', 'DATETIME NULL'),
    ('userprofiles', 'semester_start', 'DATE NULL'),  # NULL -> plant.py 16-week fallback
    ('userprofiles', 'semester_end', 'DATE NULL'),
    ('usercourses', 'branch_slot', 'INT NULL'),  # 0..7, unique per owner; NULL = overflow
    ('coursedeadlines', 'grade_id', 'INT NULL'),  # -> grades.grade_id (weight); name kept
    ('usercourses', 'verified', 'BOOLEAN NOT NULL DEFAULT 0'),  # admin-verified class badge
    ('forum_threads', 'pinned', 'BOOLEAN NOT NULL DEFAULT 0'),
    ('forum_threads', 'hidden', 'BOOLEAN NOT NULL DEFAULT 0'),
]


def _align_existing_columns(cursor):
    """Add columns that CREATE TABLE IF NOT EXISTS cannot add to an existing table."""
    if DB_BACKEND not in ('sqlite', 'libsql'):
        course_columns = _columns(cursor, "usercourses")
        if "id" not in course_columns:
            cursor.execute("ALTER TABLE usercourses ADD COLUMN id INT NULL")
            if "user_id" in course_columns:
                cursor.execute("UPDATE usercourses SET id = user_id WHERE id IS NULL")
            cursor.execute("ALTER TABLE usercourses MODIFY COLUMN id INT NOT NULL")
            cursor.execute(
                "ALTER TABLE usercourses ADD CONSTRAINT fk_usercourses_id "
                "FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE")
        cursor.execute("ALTER TABLE usercourses MODIFY COLUMN user_id INT NULL")
    for table, col, ddl in _NEW_COLUMNS:
        if col not in _columns(cursor, table):
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    # r11: no boot-time colour rewrite. NULL/empty colours are filled for display only
    # (helpers.fill_display_colours); persisting them is opt-in via scripts/migrate_null_class_colours.py.


# Per-user lookup indexes (every page filters by user_id). Safe to re-run on both backends.
_INDEXES = [
    ('ix_sessions_user_started', 'studysessions', 'user_id, started_at'),
    ('ix_todo_user_done', 'todolist', 'user_id, is_completed'),
    ('ix_events_user_start', 'calendarevents', 'user_id, event_date'),
    ('ix_grades_user', 'grades', 'user_id'),
    ('ix_inventory_user', 'userinventory', 'user_id'),
    ('ix_deadlines_course', 'coursedeadlines', 'course_id'),
    ('ix_chat_user', 'chatmessages', 'user_id'),
    ('ix_journal_user', 'journalentries', 'user_id'),
    ('ix_friend_addressee', 'friendships', 'addressee_id, status'),
    ('ix_deadlines_course_done', 'coursedeadlines', 'course_id, is_completed'),
    ('ix_deadlines_grade', 'coursedeadlines', 'grade_id'),
    ('ix_dm_pair_time', 'dm_messages', 'sender_id, recipient_id, id'),
    ('ix_dm_inbox', 'dm_messages', 'recipient_id, id'),
    ('ix_forum_scope', 'forum_threads', 'scope, created_at'),
    ('ix_forum_replies_thread', 'forum_replies', 'thread_id, id'),
    ('ix_strokes_room', 'studyroom_strokes', 'room_id, stroke_id'),
]


def _ensure_indexes(cursor):
    for name, table, cols in _INDEXES:
        try:
            have = _columns(cursor, table)
        except Exception:
            continue
        if not all(c.strip() in have for c in cols.split(',')):
            continue
        if DB_BACKEND in ('sqlite', 'libsql'):
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})")
        else:
            cursor.execute("SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() "
                           "AND table_name = %s AND index_name = %s", (table, name))
            if _as_int((cursor.fetchone() or [0])[0]) == 0:
                cursor.execute(f"CREATE INDEX {name} ON {table} ({cols})")


DEFAULT_SKY = 'sky_clear_day'
LAST_MIGRATION = {}


def _migrate_default_sky(cursor):
    """Clear day is the free default sky: move everyone on the old cream/day default (or none) onto it."""
    ph = '?' if DB_BACKEND in ('sqlite', 'libsql') else '%s'
    if DB_BACKEND not in ('sqlite', 'libsql'):
        cursor.execute(f"ALTER TABLE userprofiles ALTER COLUMN sky_key SET DEFAULT '{DEFAULT_SKY}'")
    cursor.execute(f"UPDATE userprofiles SET sky_key = {ph} WHERE sky_key IS NULL OR sky_key = '' OR sky_key = 'sky_day'",
                   (DEFAULT_SKY,))
    LAST_MIGRATION['default_sky'] = cursor.rowcount


def _migrate_friend_pairs(cursor):
    """Fill user_lo/user_hi, merge any A->B + B->A duplicates into one accepted row, add UNIQUE(user_lo, user_hi)."""
    ph = '?' if DB_BACKEND in ('sqlite', 'libsql') else '%s'
    cursor.execute("UPDATE friendships SET user_lo = CASE WHEN requester_id < addressee_id THEN requester_id ELSE addressee_id END, "
                   "user_hi = CASE WHEN requester_id < addressee_id THEN addressee_id ELSE requester_id END "
                   "WHERE user_lo IS NULL OR user_hi IS NULL")
    cursor.execute("SELECT user_lo, user_hi, MIN(id) FROM friendships GROUP BY user_lo, user_hi HAVING COUNT(*) > 1")
    for lo, hi, keep in cursor.fetchall():  # mutual requests both pending/accepted = friends
        cursor.execute(f"DELETE FROM friendships WHERE user_lo = {ph} AND user_hi = {ph} AND id <> {ph}", (lo, hi, keep))
        cursor.execute(f"UPDATE friendships SET status = 'accepted', accepted_at = COALESCE(accepted_at, CURRENT_TIMESTAMP) WHERE id = {ph}", (keep,))
    if DB_BACKEND in ('sqlite', 'libsql'):
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_friend_lohi ON friendships (user_lo, user_hi)")
    else:
        cursor.execute("SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() "
                       "AND table_name = 'friendships' AND index_name = 'uq_friend_lohi'")
        if _as_int((cursor.fetchone() or [0])[0]) == 0:
            cursor.execute("CREATE UNIQUE INDEX uq_friend_lohi ON friendships (user_lo, user_hi)")
    if DB_BACKEND in ('sqlite', 'libsql'):
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_frlog_user_time ON friend_request_log (user_id, created_at)")


def _has_unique(cursor, table, cols):
    want = sorted(cols)
    if DB_BACKEND in ('sqlite', 'libsql'):
        cursor.execute(f"PRAGMA index_list({table})")
        for row in cursor.fetchall():
            if row[2]:  # unique
                cursor.execute(f"PRAGMA index_info({row[1]})")
                if sorted(r[2] for r in cursor.fetchall()) == want:
                    return True
        return False
    cursor.execute("SELECT index_name, GROUP_CONCAT(column_name ORDER BY column_name) FROM information_schema.statistics "
                   "WHERE table_schema = DATABASE() AND table_name = %s AND non_unique = 0 GROUP BY index_name", (table,))
    return any(r[1] == ','.join(want) for r in cursor.fetchall())


def _migrate_inventory_unique(cursor):
    """Opt-in only (PRODY_ADD_INVENTORY_INDEX=1, off by default): add UNIQUE (user_id, item_key) on userinventory.
    Existing duplicates are counted and the index skipped; rows are never deleted (that would refund points).
    For live MySQL use migrations/2026-10-23_inventory_unique.sql after the owner's yes."""
    if os.environ.get('PRODY_ADD_INVENTORY_INDEX') != '1':
        LAST_MIGRATION['inventory_unique'] = 'off (PRODY_ADD_INVENTORY_INDEX unset)'
        return
    if _has_unique(cursor, 'userinventory', ['user_id', 'item_key']):
        LAST_MIGRATION['inventory_unique'] = 'present'
        return
    cursor.execute("SELECT COUNT(*) FROM (SELECT user_id, item_key FROM userinventory GROUP BY user_id, item_key HAVING COUNT(*) > 1) d")
    dups = _as_int((cursor.fetchone() or [0])[0])
    if dups:
        LAST_MIGRATION['inventory_unique'] = f'skipped: {dups} duplicate (user, item) pairs'
        import logging
        logging.getLogger(__name__).warning('userinventory has %s duplicate (user_id, item_key) pairs; unique index not added', dups)
        return
    cursor.execute("CREATE UNIQUE INDEX uq_inventory_user_item ON userinventory (user_id, item_key)")
    LAST_MIGRATION['inventory_unique'] = 'added'


def _index_exists(cursor, table, name):
    if DB_BACKEND in ('sqlite', 'libsql'):
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND name = ?", (name,))
    else:
        cursor.execute("SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() "
                       "AND table_name = %s AND index_name = %s", (table, name))
    row = cursor.fetchone()
    return bool(row) and int(row[0]) > 0


def _migrate_tree(cursor):
    """Tree data gaps (docs/api_tree_contract.md). Idempotent: only fills NULLs, never overwrites."""
    ph = '?' if DB_BACKEND in ('sqlite', 'libsql') else '%s'
    # 1. completed_at: NOT backfilled (no real completion time exists); old rows stay NULL, routes set it from now on
    # 3. branch_slot: fill free slots 0..7 per owner in course_id order (plant.py order); rest stay NULL
    cursor.execute("SELECT course_id, id, branch_slot FROM usercourses ORDER BY id, course_id")
    rows = cursor.fetchall()
    used, n = {}, 0
    for cid, owner, slot in rows:
        if slot is not None:
            used.setdefault(owner, set()).add(slot)
    for cid, owner, slot in rows:
        if slot is None:
            free = [i for i in range(8) if i not in used.setdefault(owner, set())]
            if free:
                used[owner].add(free[0])
                cursor.execute(f"UPDATE usercourses SET branch_slot = {ph} WHERE course_id = {ph}", (free[0], cid))
                n += 1
    LAST_MIGRATION['branch_slot'] = n
    if not _index_exists(cursor, 'usercourses', 'uq_course_branch_slot'):
        cursor.execute("CREATE UNIQUE INDEX uq_course_branch_slot ON usercourses (id, branch_slot)")
    # 4. grade_id: NOT backfilled (name matching dropped); links are set only by id via the grade picker
    LAST_MIGRATION['deadline_grade_id'] = 0


def _statements(path):
    with open(path) as f:
        text = '\n'.join(l for l in f.read().splitlines() if not l.strip().startswith('--'))
    return [s.strip() for s in text.split(';') if s.strip()]


def init_db():
    """Create missing tables from schema.sql (or schema_sqlite.sql) and migrate old ones."""
    conn = get_db_connection()
    cursor = conn.cursor()
    schema = 'schema_sqlite.sql' if DB_BACKEND in ('sqlite', 'libsql') else 'schema.sql'
    try:
        deferred = []  # SQLite CREATE INDEX lines may name columns that only _align_existing_columns adds
        for stmt in _statements(os.path.join(BASE_DIR, schema)):
            up = stmt.upper()
            if up.startswith('CREATE DATABASE') or up.startswith('USE '):
                continue
            if up.startswith('CREATE INDEX') or up.startswith('CREATE UNIQUE INDEX'):
                deferred.append(stmt)
                continue
            cursor.execute(stmt)
        _align_existing_columns(cursor)
        for stmt in deferred:
            cursor.execute(stmt)
        _ensure_indexes(cursor)
        _migrate_default_sky(cursor)
        _migrate_friend_pairs(cursor)
        _migrate_inventory_unique(cursor)
        _migrate_tree(cursor)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
