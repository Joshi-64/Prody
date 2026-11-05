"""db._pick_backend: preview Turso opt-in vs production TiDB vs explicit SQLite."""
import pytest
import requests
import db as dbmod


@pytest.fixture(autouse=True)
def _clean_backend_env(monkeypatch):
    """Isolate picker from suite/shell TURSO_*, PRODY_DB, PRODY_USE_TURSO, VERCEL_ENV."""
    monkeypatch.delenv('PRODY_DB', raising=False)
    monkeypatch.delenv('PRODY_USE_TURSO', raising=False)
    monkeypatch.delenv('VERCEL_ENV', raising=False)
    for k in list(__import__('os').environ):
        if k.startswith('TURSO_'):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(dbmod, 'TURSO_DATABASE_URL', '')
    monkeypatch.setattr(dbmod, 'TURSO_AUTH_TOKEN', '')
    yield


def test_turso_without_opt_in_ignored_stays_mysql(monkeypatch):
    """Production-like: TURSO_* present but no PRODY_USE_TURSO → mysql, never libsql."""
    monkeypatch.setattr(dbmod, 'TURSO_DATABASE_URL', 'libsql://example.turso.io')
    monkeypatch.setattr(dbmod, 'TURSO_AUTH_TOKEN', 'fake-token')
    monkeypatch.setenv('TURSO_DATABASE_URL', 'libsql://example.turso.io')
    monkeypatch.setenv('TURSO_AUTH_TOKEN', 'fake-token')
    assert dbmod._pick_backend() == 'mysql'
    assert dbmod._pick_backend() != 'libsql'


def test_production_vercel_env_never_selects_turso_even_with_flag(monkeypatch):
    """VERCEL_ENV=production + PRODY_USE_TURSO + TURSO_* → still mysql (preview-only)."""
    monkeypatch.setenv('VERCEL_ENV', 'production')
    monkeypatch.setenv('PRODY_USE_TURSO', '1')
    monkeypatch.setattr(dbmod, 'TURSO_DATABASE_URL', 'libsql://example.turso.io')
    monkeypatch.setattr(dbmod, 'TURSO_AUTH_TOKEN', 'fake-token')
    assert dbmod._pick_backend() == 'mysql'
    assert dbmod._pick_backend() != 'libsql'


def test_opt_in_preview_incomplete_turso_raises(monkeypatch):
    """Opted-in preview with incomplete TURSO_* → clear error (no silent SQLite)."""
    monkeypatch.setenv('PRODY_USE_TURSO', '1')
    monkeypatch.setenv('VERCEL_ENV', 'preview')
    monkeypatch.setattr(dbmod, 'TURSO_DATABASE_URL', 'libsql://example-unreachable.turso.io')
    monkeypatch.setattr(dbmod, 'TURSO_AUTH_TOKEN', '')  # incomplete
    with pytest.raises(RuntimeError, match='Turso'):
        dbmod._pick_backend()


def test_opt_in_preview_complete_selects_libsql(monkeypatch):
    """Legitimate preview: PRODY_USE_TURSO + complete TURSO_* → libsql (no ping)."""
    monkeypatch.setenv('PRODY_USE_TURSO', '1')
    monkeypatch.setenv('VERCEL_ENV', 'preview')
    monkeypatch.setattr(dbmod, 'TURSO_DATABASE_URL', 'libsql://example-unreachable.turso.io')
    monkeypatch.setattr(dbmod, 'TURSO_AUTH_TOKEN', 'fake-token-not-real')
    assert dbmod._pick_backend() == 'libsql'


def test_opt_in_without_vercel_env_allows_libsql_for_local(monkeypatch):
    """Local/dev with opt-in and no VERCEL_ENV → libsql (flag is enough)."""
    monkeypatch.setenv('PRODY_USE_TURSO', 'true')
    monkeypatch.setattr(dbmod, 'TURSO_DATABASE_URL', 'libsql://example.turso.io')
    monkeypatch.setattr(dbmod, 'TURSO_AUTH_TOKEN', 'tok')
    assert dbmod._pick_backend() == 'libsql'


def test_opt_in_query_failure_raises_clear_error(monkeypatch):
    """When opted-in Turso HTTP fails, surface RuntimeError — never soft-fall back."""
    monkeypatch.setenv('PRODY_USE_TURSO', '1')
    monkeypatch.setenv('VERCEL_ENV', 'preview')
    monkeypatch.setattr(dbmod, 'TURSO_DATABASE_URL', 'libsql://example-unreachable.turso.io')
    monkeypatch.setattr(dbmod, 'TURSO_AUTH_TOKEN', 'fake-token-not-real')
    assert dbmod._pick_backend() == 'libsql'

    class _FakeResp:
        status_code = 503
        def raise_for_status(self):
            raise requests.HTTPError('503')
        def json(self):
            return {}

    monkeypatch.setattr(requests, 'post', lambda *a, **k: _FakeResp())
    conn = dbmod._LibsqlConnection()
    cur = conn.cursor()
    with pytest.raises(RuntimeError, match='Turso/libSQL'):
        cur.execute('SELECT 1')


def test_prody_db_sqlite_selects_sqlite_even_with_opt_in(monkeypatch):
    monkeypatch.setenv('PRODY_DB', 'sqlite')
    monkeypatch.setenv('PRODY_USE_TURSO', '1')
    monkeypatch.setattr(dbmod, 'TURSO_DATABASE_URL', 'libsql://demo.turso.io')
    monkeypatch.setattr(dbmod, 'TURSO_AUTH_TOKEN', 'tok')
    assert dbmod._pick_backend() == 'sqlite'


def test_no_turso_default_path_unchanged(monkeypatch):
    """No TURSO_* / no opt-in → existing default (mysql) when PRODY_DB unset."""
    assert dbmod._pick_backend() == 'mysql'
    monkeypatch.setenv('PRODY_DB', 'mysql')
    assert dbmod._pick_backend() == 'mysql'


def test_opt_in_without_any_turso_vars_raises(monkeypatch):
    monkeypatch.setenv('PRODY_USE_TURSO', '1')
    with pytest.raises(RuntimeError, match='PRODY_USE_TURSO'):
        dbmod._pick_backend()
