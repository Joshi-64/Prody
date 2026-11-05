"""Static cache header tests (Sap)."""
import os, sys, tempfile
_TMP = tempfile.mkdtemp(prefix='prody_cache_')
os.environ.setdefault('PRODY_DB', 'sqlite')
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(_TMP, 'cache.sqlite3'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as prody_app  # noqa: E402

ASSET = '/static/css/app.css'


def client():
    prody_app.app.config.update(TESTING=True)
    return prody_app.app.test_client()


def test_versioned_static_is_immutable_for_a_year():
    import assets  # perf_r1: only the current content hash earns the long cache
    r = client().get(ASSET + '?v=' + assets.file_hash('css/app.css'))
    assert r.status_code == 200
    cc = r.headers['Cache-Control']
    assert 'max-age=31536000' in cc and 'immutable' in cc and 'public' in cc
    assert 'cookie' not in r.headers.get('Vary', '').lower()
    assert 'Set-Cookie' not in r.headers


def test_unversioned_static_is_no_cache():
    r = client().get(ASSET)
    assert r.status_code == 200
    cc = r.headers['Cache-Control']
    assert cc == 'no-cache'
    assert 'immutable' not in cc and '31536000' not in cc


def test_page_never_gets_year_cache():
    r = client().get('/login')
    cc = r.headers.get('Cache-Control', '')
    assert '31536000' not in cc and 'immutable' not in cc
    assert cc == 'no-store'


def test_stale_or_hand_version_is_no_cache():
    assert client().get(ASSET + '?v=6.1.15').headers['Cache-Control'] == 'no-cache'
