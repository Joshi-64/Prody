"""Store buy: locked ('coming soon') and unknown trees are refused with 403. Run: pytest tests/test_store_locked.py -q"""
import os, sys, tempfile
_TMP = tempfile.mkdtemp(prefix='prody_store_')
os.environ.setdefault('PRODY_DB', 'sqlite')
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(_TMP, 'store.sqlite3'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest  # noqa: E402
import app as prody_app  # noqa: E402
import profiles  # noqa: E402
from helpers import query, user_stats as real_stats  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    prody_app.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    if not query('SELECT id FROM users WHERE username = %s', ('store_user',), one=True):
        query("INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)",
              ('store_user', 's@example.com', 'x', 'student'), commit=True)
    uid = query('SELECT id FROM users WHERE username = %s', ('store_user',), one=True)['id']
    query('DELETE FROM userinventory WHERE user_id = %s', (uid,), commit=True)
    monkeypatch.setattr(profiles, 'user_stats', lambda u: dict(real_stats(u), points=10000 - sum(
        r['price_paid'] for r in query('SELECT price_paid FROM userinventory WHERE user_id = %s', (u,)))))
    import helpers  # the merged buy() reads earned points under a row lock via helpers._user_stats
    real_inner = helpers._user_stats
    monkeypatch.setattr(helpers, '_user_stats', lambda u: dict(real_inner(u), earned_points=10000))
    c = prody_app.app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = uid
    yield c, uid
    # config (incl. WTF_CSRF_ENABLED) restored by conftest._restore_app_config


def inv(uid):
    return {r['item_key'] for r in query('SELECT item_key FROM userinventory WHERE user_id = %s', (uid,))}


def test_locked_tree_403_no_charge(client):
    c, uid = client
    before = profiles.user_stats(uid)['points']
    r = c.post('/store/buy/species_maple')
    assert r.status_code == 403 and r.get_json()['error'] == 'coming_soon'
    assert profiles.user_stats(uid)['points'] == before and 'species_maple' not in inv(uid)


def test_unknown_tree_403(client):
    c, uid = client
    r = c.post('/store/buy/species_nope')
    assert r.status_code == 403 and r.get_json()['error'] == 'unknown_item' and not inv(uid)


def test_available_tree_buys(client):
    c, uid = client
    r = c.post('/store/buy/species_cherry_blossom')
    assert r.status_code == 302 and 'species_cherry_blossom' in inv(uid)
    assert profiles.user_stats(uid)['points'] == 10000 - profiles.CATALOG['species_cherry_blossom'][2]


def test_coming_soon_flag():
    assert profiles.item('species_olive')['coming_soon'] and not profiles.item('species_cherry_blossom')['coming_soon']
    assert not profiles.item(profiles.DEFAULT_SPECIES)['coming_soon']


@pytest.mark.parametrize('key', ['species_oak_gold', 'species_willow', 'species_cherry_x'])
def test_new_species_keys_locked_by_default(client, monkeypatch, key):
    c, uid = client
    monkeypatch.setitem(profiles.CATALOG, key, ('species', 'New', 100, 'common', ''))
    assert key not in profiles.LAUNCH_TREES and profiles.item(key)['coming_soon']
    r = c.post('/store/buy/' + key)
    assert r.status_code == 403 and r.get_json()['error'] == 'coming_soon' and key not in inv(uid)


def test_third_tree_is_single_constant():
    assert profiles.THIRD_TREE in profiles.LAUNCH_TREES and not profiles.item(profiles.THIRD_TREE)['coming_soon']
