"""Store: Design trees-only confirm overlay; coming-soon show real scenes + cream veil."""
from _jobs_helpers import client_for, make_user, query


def test_store_has_plant_confirm_overlay():
    uid = make_user()
    c = client_for(uid)
    html = c.get('/store').get_data(as_text=True)
    assert 'Plant ' in html and 'storeConfirm' in html
    assert 'Not now' in html and 'Buy for' in html
    assert 'Your tree' in html and 'Trees' in html
    for gone in ('Change pot', 'Flower', 'Get more', 'shop-preview', 'park_birds', 'Name style'):
        assert gone not in html, gone


def test_buy_without_points_still_refused_server_side():
    uid = make_user()
    c = client_for(uid)
    r = c.post('/store/buy/species_cherry_blossom', headers={'Accept': 'application/json'})
    assert r.status_code in (400, 403, 302)
    assert not query('SELECT 1 FROM userinventory WHERE user_id=%s AND item_key=%s', (uid, 'species_cherry_blossom'), one=True)


def test_buy_button_disabled_while_inflight_in_markup():
    html = client_for(make_user()).get('/store').get_data(as_text=True)
    assert 'yes.disabled=true' in html or "yes.disabled = true" in html.replace(' ', '')


def test_coming_soon_real_scenes_veil_no_locked():
    html = client_for(make_user()).get('/store').get_data(as_text=True)
    for name in ('Maple', 'Olive', 'Willow', 'Palm'):
        assert name in html
    assert html.count('Coming soon') >= 4
    assert 'Locked' not in html
    for slug in ('maple', 'olive', 'willow', 'palm'):
        assert f'{slug}-scene.webp' in html
    assert 'rgba(251,246,239,.28)' in html
    # buy API still rejects
    c = client_for(make_user())
    r = c.post('/store/buy/species_maple', headers={'Accept': 'application/json'})
    assert r.status_code == 403
