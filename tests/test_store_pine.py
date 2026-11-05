"""Pine store item (launch tree) + coming-soon cards render without a Buy form. Run: pytest tests/test_store_pine.py -q"""
import os, re, sys, tempfile
_TMP = tempfile.mkdtemp(prefix='prody_pine_')
os.environ.setdefault('PRODY_DB', 'sqlite')
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(_TMP, 'store.sqlite3'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest  # noqa: E402
import app as prody_app  # noqa: E402
import profiles  # noqa: E402
import api_tree  # noqa: E402
from helpers import query, user_stats as real_stats  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    prody_app.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    if not query('SELECT id FROM users WHERE username = %s', ('pine_user',), one=True):
        query("INSERT INTO users (username, email, password_hash, role, created_at) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)",
              ('pine_user', 'w@example.com', 'x', 'student'), commit=True)
    uid = query('SELECT id FROM users WHERE username = %s', ('pine_user',), one=True)['id']
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


def test_pine_in_catalog_not_coming_soon():
    it = profiles.item('species_pine')
    assert it and it['type'] == 'species' and not it['coming_soon']
    assert it['price'] == profiles.CATALOG['species_cherry_blossom'][2]
    assert api_tree.tree_species('species_pine') == 'pine'


def test_pine_buy_granted(client):
    c, uid = client
    r = c.post('/store/buy/species_pine')
    assert r.status_code == 302 and 'species_pine' in inv(uid)
    assert profiles.user_stats(uid)['points'] == 10000 - profiles.CATALOG['species_pine'][2]


def _store_html(c):
    pages = [c.get('/store').get_data(as_text=True)]
    for g in profiles.STORE_GROUPS:
        pages.append(c.get('/store?tab=' + g).get_data(as_text=True))
    return '\n'.join(pages)


def test_store_coming_soon_cards(client):
    c, _ = client
    html = _store_html(c)
    for key in ('species_maple', 'species_olive', 'species_willow', 'species_palm'):
        assert profiles.item(key)['coming_soon']
        assert 'data-item="%s"' % key in html
        assert 'Coming soon' in html
        assert 'data-tree="%s"' % key not in html  # no buy button for soon
    assert 'data-tree="species_pine"' in html


def test_willow_now_blocked_403(client):
    c, uid = client
    r = c.post('/store/buy/species_willow')
    assert r.status_code == 403 and 'species_willow' not in inv(uid)
    assert 'species_willow' not in profiles.LAUNCH_TREES and 'species_pine' in profiles.LAUNCH_TREES


# ---- round 2: one plain list, no tabs, no rarity tiers; 403 lock unchanged
def test_store_is_one_plain_list_no_tiers(client):
    c, _ = client
    html = c.get('/store').get_data(as_text=True)
    for gone in ('shop-tabs', 'role="tablist"', 'shop-rarity', 'tier-', 'rarity r-', 'store_tabs.js', 'pvRarity', 'shop-preview'):
        assert gone not in html, gone
    assert 'shop-grid shop-list' in html
    assert c.get('/store?tab=garden&rarity=epic').status_code == 200   # old links still load


def test_store_order_launch_trees_then_coming_soon(client):
    c, _ = client
    html = c.get('/store').get_data(as_text=True)
    keys = re.findall(r'class="[^"]*shop-card[^"]*"[^>]*data-item="([^"]+)"', html)
    if not keys:
        keys = re.findall(r'data-item="(species_[^"]+)"', html)
    assert keys[:3] == ['species_default', 'species_cherry_blossom', 'species_pine']
    assert all(profiles.CATALOG[k][0] == 'species' for k in keys)  # trees only
    assert all(profiles.item(k)['coming_soon'] for k in keys[3:]) and len(keys) >= 7


@pytest.mark.parametrize('key', ['species_willow', 'species_maple', 'species_olive', 'nope_item'])
def test_locked_or_unknown_buy_403_no_charge(client, key):
    c, uid = client
    r = c.post('/store/buy/' + key)
    assert r.status_code == 403 and inv(uid) == set()
