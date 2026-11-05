"""db.py optional PRODY_DB_PORT / PRODY_DB_SSL_CA. Uses monkeypatch only (no module reload), no network."""
import pytest
import db


@pytest.fixture
def cfg(monkeypatch):
    config = {'host': 'localhost', 'user': 'u', 'password': 'p', 'database': 'd'}
    monkeypatch.setattr(db, 'DB_CONFIG', config)
    for k in ('PRODY_DB_PORT', 'PRODY_DB_SSL_CA'):
        monkeypatch.delenv(k, raising=False)
    return config


def test_port_and_ssl_ca_read_from_env(cfg, monkeypatch, tmp_path):
    ca = tmp_path / 'ca.pem'
    ca.write_text('x')
    monkeypatch.setenv('PRODY_DB_PORT', '4000')
    monkeypatch.setenv('PRODY_DB_SSL_CA', str(ca))
    db.apply_port_ssl_env(db.DB_CONFIG)
    assert db.DB_CONFIG['port'] == 4000
    assert db.DB_CONFIG['ssl_ca'] == str(ca)
    assert db.DB_CONFIG['ssl_verify_cert'] is True
    assert db.DB_CONFIG['ssl_verify_identity'] is True


def test_missing_ca_file_raises_with_path(cfg, monkeypatch, tmp_path):
    missing = tmp_path / 'nope' / 'ca.pem'
    monkeypatch.setenv('PRODY_DB_SSL_CA', str(missing))
    with pytest.raises(FileNotFoundError, match=str(missing)):
        db.apply_port_ssl_env(db.DB_CONFIG)
    assert 'ssl_ca' not in db.DB_CONFIG


def test_unset_leaves_config_unchanged(cfg):
    before = dict(cfg)
    db.apply_port_ssl_env(db.DB_CONFIG)
    assert db.DB_CONFIG == before


def test_sqlite_still_works_when_unset(cfg, monkeypatch, tmp_path):
    monkeypatch.setattr(db, 'DB_BACKEND', 'sqlite')
    monkeypatch.setattr(db, 'SQLITE_PATH', str(tmp_path / 't.db'))
    con = db.get_db_connection()
    cur = con.cursor()
    cur.execute('CREATE TABLE t (x INT)')
    cur.execute('INSERT INTO t VALUES (1)')
    cur.execute('SELECT x FROM t')
    row = cur.fetchone()
    assert (row['x'] if isinstance(row, dict) else row[0]) == 1
    con.close()
