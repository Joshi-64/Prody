import apptime
import re
"""Profiles, decorations and the points Store."""
import os
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from helpers import BADGES, as_dt, login_required, fill_display_colours, query, user_stats

profile_bp = Blueprint('profile_bp', __name__)

RARITY = {'common': ('Common', 1), 'rare': ('Rare', 2), 'epic': ('Epic', 3), 'legendary': ('Legendary', 4)}

# key: (type, name, price, rarity, css value)
CATALOG = {
    # --- for your Prody plant
    'pot_terracotta': ('pot', 'Classic Terracotta', 0, 'common', 'pot_terracotta'),
    'pot_cream':      ('pot', 'Banded Ceramic', 250, 'common', 'pot_cream'),
    'pot_speckle':    ('pot', 'Speckled Stoneware', 300, 'common', 'pot_speckle'),
    'pot_basket':     ('pot', 'Woven Basket', 0, 'common', 'pot_basket'),
    'pot_wave':       ('pot', 'Painted Waves', 500, 'rare', 'pot_wave'),
    'pot_sage':       ('pot', 'Sage Drip Glaze', 800, 'epic', 'pot_sage'),
    'pot_forest':     ('pot', 'Forest Glaze', 900, 'epic', 'pot_forest'),
    'pot_kintsugi':   ('pot', 'Kintsugi', 2000, 'legendary', 'pot_kintsugi'),
    'acc_sticker':    ('acc', 'Watering Can Sticker', 120, 'common', 'acc_sticker'),
    'acc_glasses':    ('acc', 'Reading Glasses', 200, 'common', 'acc_glasses'),
    'acc_scarf':      ('acc', 'Knit Scarf', 400, 'rare', 'acc_scarf'),
    'acc_hat':        ('acc', 'Tiny Sun Hat', 500, 'rare', 'acc_hat'),
    'acc_butterfly':  ('acc', 'Butterfly Friend', 900, 'epic', 'acc_butterfly'),
    'acc_lights':     ('acc', 'Fairy Lights', 1500, 'legendary', 'acc_lights'),
    'scene_desk':     ('scene', 'Study Desk', 300, 'common', 'scene_desk'),
    'scene_window':   ('scene', 'Sunny Windowsill', 600, 'rare', 'scene_window'),
    'scene_greenhouse': ('scene', 'Greenhouse', 1400, 'epic', 'scene_greenhouse'),
    # --- profile decorations (keys kept from v2 so existing equips still work)
    'theme_sky':     ('theme', 'Meadow', 0, 'common', 'pat-solid-pink'),
    'theme_mint':    ('theme', 'Sage', 150, 'common', 'pat-solid-blue'),
    'theme_peach':   ('theme', 'Garden Gingham', 150, 'common', 'pat-checker'),
    'theme_sunset':  ('theme', 'Pinstripe', 400, 'rare', 'pat-stripes'),
    'theme_ocean':   ('theme', 'Seed Dots', 400, 'rare', 'pat-dots'),
    'theme_waves':   ('theme', 'Golden Hour', 600, 'rare', 'pat-waves'),
    'theme_aurora':  ('theme', 'Slow Rain', 900, 'epic', 'anim-stripes'),
    'theme_galaxy':  ('theme', 'Drifting Seeds', 900, 'epic', 'anim-dots'),
    'theme_holo':    ('theme', 'Falling Leaves', 2000, 'legendary', 'anim-sprinkle'),
    'frame_white':   ('frame', 'Sand Ring', 100, 'common', 'frame-butter'),
    'frame_mint':    ('frame', 'Forest Ring', 200, 'common', 'frame-red'),
    'frame_gold':    ('frame', 'Seed Ring', 600, 'rare', 'frame-dots'),
    'frame_rainbow': ('frame', 'Gingham Ring', 1200, 'epic', 'frame-checker'),
    'frame_flame':   ('frame', 'Sunburst', 2200, 'legendary', 'frame-spin'),
    'name_blue':     ('name', 'Forest Ink', 120, 'common', 'name-red'),
    'name_sunset':   ('name', 'Highlighter', 500, 'rare', 'name-highlight'),
    'name_serif':    ('name', 'Serif', 700, 'rare', 'name-serif'),
    'name_glow':     ('name', 'Soft Shadow', 1000, 'epic', 'name-shadow'),
    'name_shimmer':  ('name', 'Golden Bloom', 1800, 'legendary', 'name-squiggle'),
}
# --- Earned park (Profile banner only). Ownership is the gate: never equipped, never in decor_keys or roots data.
PARK_ITEMS = {
    'park_trees':      ('park', 'Park Trees', 350, 'common', 'trees'),
    'park_path':       ('park', 'Garden Path', 300, 'common', 'path'),
    'park_flowerbeds': ('park', 'Flower Beds', 500, 'rare', 'flowerbeds'),
    'park_lamp':       ('park', 'Park Lamp', 600, 'rare', 'lamp'),
    'park_bench':      ('park', 'Park Bench', 800, 'epic', 'bench'),
    'park_birds':      ('park', 'Songbirds', 1200, 'epic', 'birds'),
}
CATALOG.update(PARK_ITEMS)
TYPE_LABEL = {'pot': 'Pots', 'acc': 'Accessories', 'scene': 'Scenes', 'theme': 'Banners', 'frame': 'Avatar frames',
              'name': 'Name styles', 'park': 'Park'}
SLOT = {'pot': 'pot_key', 'acc': 'acc_keys', 'scene': 'scene_key', 'theme': 'theme_key', 'frame': 'frame_key', 'name': 'name_key'}
FREE = {'theme_sky', 'pot_terracotta', 'pot_basket', 'species_default', 'sky_clear_day', 'sky_clear_night'}  # classic tree: everyone owns it  # woven basket is the new-user default pot
# Clay-plant era items: nothing draws them any more, so they are off sale. Owned copies stay in inventory.
RETIRED_TYPES = {'acc', 'scene'}

# --- Garden shop (Roots map). Item ids and colours come from 3d design 1's shop/items.json.
GARDEN_TYPES = {'soil': ('Soils', 'soil_key'), 'sky': ('Skies', 'sky_key'), 'flower': ('Flower palettes', 'flower_key'),
                'leaves': ('Leaf seasons', 'leaves_key'), 'decor': ('Garden décor', 'decor_keys'),
                'species': ('Plant', 'species_key')}
DEFAULT_SPECIES = 'species_default'
# Placeholder species until 3d design 1 ships type "species" rows in shop/items.json (those replace these).
SPECIES_PLACEHOLDER = [
    {'id': 'species_classic', 'name': 'Classic tree', 'price': 0, 'rarity': 'common', 'default': True,
     'colors': {'leaf': '#5E8C4A', 'flower': '#F08A6C', 'bark': '#7A5A3C', 'leaf_shape': 'round',
                'blooms': True, 'bloom': '#F08A6C', 'petals': 5}},
    {'id': 'species_cherry', 'name': 'Cherry blossom', 'price': 600, 'rarity': 'rare',
     'colors': {'leaf': '#7FA65A', 'flower': '#F6B8C8', 'bark': '#5B3A33', 'leaf_shape': 'ellipse',
                'blooms': True, 'bloom': '#F6B8C8', 'petals': 5}},
    {'id': 'species_maple', 'name': 'Maple', 'price': 900, 'rarity': 'epic',
     'colors': {'leaf': '#C8553D', 'flower': '#F2B632', 'bark': '#6B4A2F', 'leaf_shape': 'maple', 'blooms': False}},
    {'id': 'species_olive', 'name': 'Olive', 'price': 900, 'rarity': 'epic',
     'colors': {'leaf': '#8A9A6B', 'flower': '#FFFDF7', 'bark': '#8C7B65', 'leaf_shape': 'narrow', 'blooms': False}},
]
MAX_DECOR = 4
GARDEN_META = {}
POT_META = {}


def _load_garden():
    import json
    base = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(base, 'static', 'shop', 'items.json'),
                 '/workspace/prody_assets/roots_style/shop/items.json'):
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        rows = data.get('items', data) if isinstance(data, dict) else data
        if isinstance(rows, dict):
            rows = [dict(v, id=k) for k, v in rows.items()]
        for r in rows or []:
            key = r.get('id') or r.get('key')
            t = r.get('type') or (key or '').split('_')[0]
            t = {'flowers': 'flower', 'pots': 'pot'}.get(t, t)
            if key and t == 'pot':
                POT_META[key] = r  # art + colours only; pot prices/names stay in CATALOG
            if not key or t not in GARDEN_TYPES:
                continue
            rar = r.get('rarity', 'common') if r.get('rarity') in RARITY else 'common'
            CATALOG[key] = (t, r.get('name') or key.replace('_', ' ').title(), int(r.get('price', 300)), rar, key)
            GARDEN_META[key] = r
        return path
    return None


_load_garden()
if not any(m.get('type') == 'species' for m in GARDEN_META.values()):
    for _r in SPECIES_PLACEHOLDER:
        _r = dict(_r, id=_r['id'].replace('species_classic', DEFAULT_SPECIES))
        CATALOG[_r['id']] = ('species', _r['name'], _r['price'], _r['rarity'], _r['id'])
        GARDEN_META[_r['id']] = dict(_r, type='species', placeholder=True)


# --- Default sky: Clear day (light) / Clear night (dark). Placeholders until 3d design 1's items.json has them.
DEFAULT_SKY, DEFAULT_SKY_NIGHT = 'sky_clear_day', 'sky_clear_night'
_SKY_PLACEHOLDER = {
    DEFAULT_SKY: {'name': 'Clear day', 'colors': {'stops': [{'offset': 0.0, 'color': '#BFDDF2'}, {'offset': 1.0, 'color': '#F4F8F2'}]}},
    DEFAULT_SKY_NIGHT: {'name': 'Clear night', 'colors': {'stops': [{'offset': 0.0, 'color': '#16223A'}, {'offset': 1.0, 'color': '#2E3C55'}]}},
}
for _k, _r in _SKY_PLACEHOLDER.items():
    if _k not in GARDEN_META:
        CATALOG[_k] = ('sky', _r['name'], 0, 'common', _k)
        GARDEN_META[_k] = dict(_r, id=_k, type='sky', price=0, rarity='common', placeholder=True)
    else:
        CATALOG[_k] = (CATALOG[_k][0], CATALOG[_k][1], 0, CATALOG[_k][3], CATALOG[_k][4])  # always free
# Kept in CATALOG/GARDEN_META so old equips and links still resolve, but not listed in the Store.
STORE_HIDDEN = {'sky_day', DEFAULT_SKY_NIGHT}

# --- Store v3: three tabs. Every listed type maps to exactly one group.
STORE_GROUPS = {'tree': ('Tree', ('species', 'pot')),
                'garden': ('Garden', ('sky', 'soil', 'leaves', 'decor', 'park')),
                'profile': ('Profile', ('theme', 'frame', 'name'))}
GROUP_OF = {t: g for g, (_l, ts) in STORE_GROUPS.items() for t in ts}
# Flower palettes are redundant now that blooms come from the chosen tree species: off sale and migrated away.
REMOVED_FLOWERS = sorted(k for k, v in CATALOG.items() if v[0] == 'flower')
RETIRED_TYPES = set(RETIRED_TYPES) | {'flower'}


def migrate_removed_flowers():
    """Idempotent: unequip flower palettes and refund them. The Store balance is earned - SUM(price_paid),
    so deleting the inventory row refunds exactly what was paid. Returns (profiles_cleared, rows_refunded, coins)."""
    if not REMOVED_FLOWERS:
        return 0, 0, 0
    ph = ','.join(['%s'] * len(REMOVED_FLOWERS))
    keys = tuple(REMOVED_FLOWERS)
    n_prof = query(f'SELECT COUNT(*) AS n FROM userprofiles WHERE flower_key IN ({ph})', keys, one=True)['n']
    inv = query(f'SELECT COUNT(*) AS n, COALESCE(SUM(price_paid), 0) AS c FROM userinventory WHERE item_key IN ({ph})', keys, one=True)
    if n_prof:
        query(f"UPDATE userprofiles SET flower_key = '' WHERE flower_key IN ({ph})", keys, commit=True)
    if inv['n']:
        query(f'DELETE FROM userinventory WHERE item_key IN ({ph})', keys, commit=True)
    return int(n_prof), int(inv['n']), int(inv['c'])


def sky_key_of(prof):
    k = (prof or {}).get('sky_key') or ''
    return DEFAULT_SKY if k in ('', 'sky_day') or k not in GARDEN_META else k


SPECIES_ALIAS = {'species_cherry': 'species_cherry_blossom', 'species_classic': DEFAULT_SPECIES}


def species_json(key):
    """Species block for /roots/data, in a fixed key order for roots.js: id, leaf_color, flower_color, bark_color,
    leaf_shape, blooms, bloom_color, then every other field from the item's colors (leafDensity, leaf, flower, bark...)."""
    key = SPECIES_ALIAS.get(key, key)
    key = key if (key in GARDEN_META and GARDEN_META[key].get('type') == 'species') else DEFAULT_SPECIES
    c = (GARDEN_META.get(key) or {}).get('colors') or {}
    pick = lambda n, d: c.get(n + '_color') or (c.get(n) if isinstance(c.get(n), str) else None) or d
    blooms = bool(c.get('blooms', True))
    out = {'id': key, 'leaf_color': pick('leaf', '#2F6B3A'), 'flower_color': pick('flower', '#F08A6C'),
           'bark_color': pick('bark', '#6B4A2F'), 'leaf_shape': c.get('leaf_shape') or 'round',
           'blooms': blooms, 'bloom_color': (c.get('bloom_color') or pick('flower', '#F08A6C')) if blooms else None}
    for k, v in c.items():
        if k not in out and k != 'id' and not k.endswith('_color'):
            out[k] = v
    return out


for _t, (_label, _col) in GARDEN_TYPES.items():
    TYPE_LABEL[_t] = _label
    SLOT[_t] = _col
for _t in RETIRED_TYPES:
    TYPE_LABEL.pop(_t, None)
MAX_ACCS = 3
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'avatars')
MAX_AVATAR = 2 * 1024 * 1024
AVATAR_SIZE = 512
MAGIC = {b'\x89PNG\r\n\x1a\n': 'png', b'\xff\xd8\xff': 'jpg', b'GIF87a': 'gif', b'GIF89a': 'gif'}


# Launch list (server-side): exact store keys that can be bought; every other species is 'coming soon'.
# THIRD_TREE is the one place to swap the third launch tree (e.g. 'species_maple' or 'species_pine').
THIRD_TREE = 'species_pine'
LAUNCH_TREES = frozenset({DEFAULT_SPECIES, 'species_cherry_blossom', THIRD_TREE})  # species_default is the classic oak


LAUNCH_ORDER = (DEFAULT_SPECIES, 'species_cherry_blossom', THIRD_TREE)

# Trees-only Store (Design 4dc31fa/7e8292d): scene thumbs; coming-soon use real scenes + cream veil.
TREE_LABEL = {
    DEFAULT_SPECIES: 'Oak',
    'species_cherry_blossom': 'Cherry',
    'species_pine': 'Pine',
    'species_maple': 'Maple',
    'species_olive': 'Olive',
    'species_willow': 'Willow',
    'species_palm': 'Palm',
}
TREE_SCENE = {
    DEFAULT_SPECIES: 'garden/scenes/tree-scene.webp',
    'species_cherry_blossom': 'garden/scenes/cherry-scene.webp',
    'species_pine': 'garden/scenes/pine-scene.webp',
    'species_maple': 'garden/scenes/maple-scene.webp',
    'species_olive': 'garden/scenes/olive-scene.webp',
    'species_willow': 'garden/scenes/willow-scene.webp',
    'species_palm': 'garden/scenes/palm-scene.webp',
}
COMING_SOON_EXTRA = (
    ('species_willow', 'Willow', 600),
    ('species_palm', 'Palm', 600),
)
for _k, _n, _pr in COMING_SOON_EXTRA:
    if _k not in CATALOG:
        CATALOG[_k] = ('species', _n, _pr, 'rare', _k)
        GARDEN_META[_k] = {'id': _k, 'type': 'species', 'name': _n, 'price': _pr, 'rarity': 'rare',
                           'colors': {'leaf': '#9AA090', 'bark': '#6B5A4A', 'leaf_shape': 'ellipse', 'blooms': False},
                           'placeholder': True}
# Maple/Olive may already be in items.json; keep them as coming soon (not in LAUNCH_TREES).



def store_order(i):
    """Store list order: oak, cherry, pine; then coming-soon trees; then the other types in their old group order, cheapest first."""
    if i['type'] == 'species':
        return (0, LAUNCH_ORDER.index(i['key']), 0, '') if i['key'] in LAUNCH_ORDER else (1, 0, i['price'], i['name'])
    types = [t for _g, (_l, ts) in STORE_GROUPS.items() for t in ts]
    return (2, types.index(i['type']), i['price'], i['name'])


def coming_soon(key):
    if key not in CATALOG or CATALOG[key][0] != 'species':
        return False
    return key not in LAUNCH_TREES


def item(key):
    if key not in CATALOG:
        return None
    t, n, p, r, css = CATALOG[key]
    label = TREE_LABEL.get(key, n)
    if key == 'species_cherry_blossom':
        label = 'Cherry'
    sil = key.replace('species_', '') if coming_soon(key) else ''
    if sil == 'cherry_blossom':
        sil = 'cherry'
    return {'key': key, 'type': t, 'name': label, 'price': p, 'rarity': r, 'rarity_label': RARITY[r][0], 'css': css,
            'coming_soon': coming_soon(key), 'scene': TREE_SCENE.get(key), 'sil': sil,
            'catalog_name': n}


def get_profile(user_id):
    p = query('SELECT * FROM userprofiles WHERE user_id = %s', (user_id,), one=True)
    if not p:
        query("INSERT INTO userprofiles (user_id, pot_key) VALUES (%s, 'pot_basket')", (user_id,), commit=True)
        p = query('SELECT * FROM userprofiles WHERE user_id = %s', (user_id,), one=True)
    return p


def owned_keys(user_id):
    return {r['item_key'] for r in query('SELECT item_key FROM userinventory WHERE user_id = %s', (user_id,))} | FREE


def decorate(user):
    """Return a dict the templates use to draw an avatar / name / banner for any user row."""
    p = get_profile(user['id'])
    theme = item(p.get('theme_key') or 'theme_sky') or item('theme_sky')
    frame = item(p.get('frame_key') or '')
    name = item(p.get('name_key') or '')
    display = p.get('display_name') or user['username']
    initials = ''.join(w[0] for w in display.replace('_', ' ').replace('.', ' ').split()[:2]).upper() or '?'
    return {'username': user['username'], 'display': display, 'initials': initials, 'profile': p,
            'avatar': url_for('static', filename=p['avatar_path']) if p.get('avatar_path') else None,
            'banner': theme['css'], 'banner_anim': True,
            'frame': frame['css'] if frame else '', 'name_cls': name['css'] if name else '',
            'hue': sum(map(ord, user['username'])) % 360,
            'av': ['#E7DCC6', '#CFDCC6', '#EFD3C3'][sum(map(ord, user['username'])) % 3]}


@profile_bp.app_context_processor
def inject_me():
    out = {'decorate': decorate, 'plant_card': lambda uid: plant_card(get_profile(uid)), 'celebrate': session.pop('celebrate', False)}
    if 'user_id' in session:
        u = query('SELECT id, username FROM users WHERE id = %s', (session['user_id'],), one=True)
        if u:
            out['me'] = decorate(u)
            out['me_points'] = user_stats(u['id'])['points']
    return out


TREE_BARE_HOURS = 5  # Me page shows tree_small_bare below this many study hours (Leader to confirm)


def real_milestones(user_id, st):
    """Stage history replayed from study sessions: the hours and date each stage threshold was first crossed.
    Uses today's semester progress, so it matches the plant the user sees now."""
    from plant import STAGES, growth_for
    from helpers import as_dt
    prog = float(st.get('progress') or 0)
    rows = sorted((r for r in query('SELECT minutes, started_at FROM studysessions WHERE user_id = %s', (user_id,))
                   if as_dt(r['started_at'])), key=lambda r: as_dt(r['started_at']))
    out, cum, i = [], 0.0, 1
    for r in rows:
        cum += int(r['minutes']) / 60.0
        while i < len(STAGES) and i <= st.get('stage_idx', 0) and growth_for(cum, prog) >= STAGES[i][1]:
            out.append({'stage': STAGES[i][0], 'hours_at': cum, 'reached_at': as_dt(r['started_at'])})
            i += 1
    # One row per real date: if one session crossed several stages, keep the highest stage for that day.
    by_day = {}
    for m in out:
        by_day[apptime.local_date(m['reached_at'])] = m
    return sorted(by_day.values(), key=lambda m: m['reached_at'])


def focus_days_this_week(uid):
    """Seven bools Mon..Sun for the current local week: True if any study session that day."""
    today = apptime.today_local()
    monday = today - timedelta(days=today.weekday())  # Mon=0
    start_utc = apptime.day_bounds_utc(monday)[0]
    end_utc = apptime.day_bounds_utc(monday + timedelta(days=6))[1]
    rows = query('SELECT started_at FROM studysessions WHERE user_id = %s AND started_at >= %s AND started_at < %s',
                 (uid, start_utc, end_utc))
    days = set()
    for r in rows:
        d = apptime.local_date(as_dt(r['started_at']))
        if d:
            days.add(d)
    return [monday + timedelta(days=i) in days for i in range(7)]


def profile_garden(prof):
    """Banner decorations for the Me page: equipped sky gradient, soil strip and décor, from the shop metadata."""
    def meta(key, fallback):
        return GARDEN_META.get(key) or GARDEN_META.get(fallback) or {}
    sky = meta(sky_key_of(prof), DEFAULT_SKY)
    soil = meta(prof.get('soil_key'), 'soil_loam')
    stops = (sky.get('colors') or {}).get('stops') or [{'offset': 0, 'color': '#FBF6EC'}, {'offset': 1, 'color': '#FBF6EC'}]
    sc = soil.get('colors') or {}
    decor = []
    for k in [k for k in (prof.get('decor_keys') or '').split(',') if k][:MAX_DECOR]:
        m = GARDEN_META.get(k)
        if m and m.get('svg'):
            decor.append({'key': k, 'name': m.get('name', k), 'svg': m['svg']})
    return {'sky': ', '.join(f"{s['color']} {round(float(s['offset']) * 100)}%" for s in stops),
            'sky_name': sky.get('name', 'Cream day'), 'soil_name': soil.get('name', 'Loam'),
            'banner': {'sky_sunset': 'orchard', 'sky_night': 'dusk', 'sky_rain': 'greenhouse'}.get(prof.get('sky_key'), 'meadow'),
            'soil': sc.get('fill', '#C49A72'), 'horizon': sc.get('horizon', '#6B4A2F'), 'decor': decor}


@profile_bp.route('/profile/leaderboard', methods=['POST'])
@login_required
def leaderboard_optin():
    uid = session['user_id']
    get_profile(uid)
    on = 1 if request.form.get('show') in ('1', 'on', 'true') else 0
    query('UPDATE userprofiles SET show_on_leaderboard = %s WHERE user_id = %s', (on, uid), commit=True)
    flash('You are on the leaderboard now.' if on else 'You are off the leaderboard. Only you can see your rank.', 'success')
    return redirect(request.referrer or url_for('profile_bp.my_profile'))


@profile_bp.route('/u/<username>')
@login_required
def public_profile(username):
    u = query('SELECT id, username, role, created_at FROM users WHERE username = %s', (username,), one=True)
    if not u:
        abort(404)
    d = decorate(u)
    stats = user_stats(u['id'])
    pinned = [b for b in stats['badges'] if b['key'] in (d['profile'].get('pinned_badges') or '').split(',') and b['earned']]
    courses = fill_display_colours(query('SELECT course_id, course_name, color FROM usercourses WHERE id = %s ORDER BY course_name', (u['id'],)), u['id'])
    from plant import plant_state, milestones
    st = plant_state(u['id'])
    has_course = query('SELECT COUNT(*) AS n FROM usercourses WHERE id = %s', (u['id'],), one=True)['n'] > 0
    done = query('SELECT COUNT(*) AS n FROM coursedeadlines d JOIN usercourses c ON c.course_id = d.course_id '
                 'WHERE c.id = %s AND d.is_completed = 1', (u['id'],), one=True)['n']
    wk = query('SELECT SUM(CASE WHEN d.is_completed = 1 THEN 1 ELSE 0 END) AS met, COUNT(*) AS n FROM coursedeadlines d '
               'JOIN usercourses c ON c.course_id = d.course_id WHERE c.id = %s AND d.deadline_date >= %s AND d.deadline_date < %s',
               (u['id'], apptime.now_utc_naive() - timedelta(days=7), apptime.now_utc_naive()), one=True)
    # Design Item 14: First focus (= ≥1 Zen/study session), First bloom, 10 harvests, Zen 5h, Full canopy.
    # helpers.streak7 / seeds untouched — just not shown on Me.
    zen_sessions = query('SELECT COUNT(*) AS n FROM studysessions WHERE user_id = %s AND COALESCE(completed,1) = 1', (u['id'],), one=True)['n']
    tasks_done = stats.get('tasks_done') or 0
    total_min = stats.get('total_minutes') or 0
    # Medal keys stay stable; img maps to existing static/ui/icons/badge_*.svg (light+dark).
    medals = [
        ('first_focus', 'badge_first_seed', 'First focus', 'Completed a Zen session', zen_sessions >= 1),
        ('first_bloom', 'badge_first_bloom', 'First bloom', 'Finished a deadline', done > 0),
        ('harvests_10', 'badge_all_deadlines_week', '10 harvests', 'Finished 10 tasks', tasks_done >= 10),
        ('zen_5h', 'badge_focus_10h', 'Zen 5h', 'Five hours of Zen', total_min >= 300),
        ('full_canopy', 'badge_full_tree', 'Full canopy', 'Tree fully grown', not st.get('next_stage')),
    ]
    medals = [dict(key=k, img=img, name=n, desc=ds, earned=e) for k, img, n, ds, e in medals]
    buds_growing = query('SELECT COUNT(*) AS n FROM todolist WHERE user_id = %s AND is_completed = 0', (u['id'],), one=True)['n']
    from friends import relation
    from rooms import active_room_for
    is_me = u['id'] == session['user_id']
    friend_rel, friend_row = relation(session['user_id'], u['id'])
    active_room = active_room_for(u['id'])
    # Profile chip Join only when viewer is friends with host and room allows friends_can_join
    room_joinable = bool(
        active_room and friend_rel == 'friends' and int(active_room.get('friends_can_join') or 0)
        and not is_me)
    return render_template('profile.html', friend_rel=friend_rel, friend_row=friend_row, tree_bare=(st.get('hours') or 0) < TREE_BARE_HOURS, medals=medals, u=u, d=d, stats=stats, pinned=pinned, courses=courses,
                           st=st, milestones=real_milestones(u['id'], st),
                           is_me=is_me, garden=profile_garden(d['profile']),
                           card=plant_card(d['profile']),
                           park=park_scene(d['profile'], st.get('stage_idx', 0), owned_keys(u['id']), owner_id=u['id'], show_friends=is_me),
                           buds_growing=buds_growing, focus_days=focus_days_this_week(u['id']),
                           active_room=active_room, room_joinable=room_joinable)


@profile_bp.route('/profile')
@login_required
def my_profile():
    # session may hold only user_id (no 'username'), e.g. older/partial sessions: read the handle from the DB
    uname = session.get('username')
    if not uname:
        row = query('SELECT username FROM users WHERE id = %s', (session.get('user_id'),), one=True)
        if not row:
            session.clear()
            return redirect(url_for('login'))
        uname = session['username'] = row['username']
    return redirect(url_for('profile_bp.public_profile', username=uname))


@profile_bp.route('/profile/plant-preview')
@login_required
def plant_preview():
    """Live preview for edit-profile: the user's plant with unsaved pot, scene and accessory picks."""
    from plant import plant_state, render_plant
    st = dict(plant_state(session['user_id']))
    st['pot'] = request.args.get('pot') or 'pot_terracotta'
    st['scene'] = request.args.get('scene', '')
    st['accs'] = [a for a in request.args.get('accs', '').split(',') if a][:3]
    try:
        return str(render_plant(st))
    except Exception:
        abort(400)


def _save_avatar(f):
    data = f.read(MAX_AVATAR + 1)
    if len(data) > MAX_AVATAR:
        return None, 'Avatar must be 2 MB or smaller.'
    ext = next((e for sig, e in MAGIC.items() if data.startswith(sig)), None)
    if not ext and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        ext = 'webp'
    if not ext:
        return None, 'Avatar must be a PNG, JPG, GIF or WebP image.'
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    try:  # center-crop to a square and shrink to AVATAR_SIZE so pages stay light
        from io import BytesIO
        from PIL import Image, ImageOps
        img = ImageOps.exif_transpose(Image.open(BytesIO(data)))
        img = ImageOps.fit(img.convert('RGBA'), (AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
        name = f'{session["user_id"]}_{uuid.uuid4().hex[:10]}.webp'
        img.save(os.path.join(UPLOAD_DIR, name), 'WEBP', quality=88, method=6)
    except ImportError:  # Pillow missing: keep the original file
        name = f'{session["user_id"]}_{uuid.uuid4().hex[:10]}.{ext}'
        with open(os.path.join(UPLOAD_DIR, name), 'wb') as out:
            out.write(data)
    except Exception:
        return None, "That image couldn't be read. Try a different file."
    return f'uploads/avatars/{name}', None


def _set_slot(uid, it, p, toggle=False):
    """Equip an owned item. Accessories stack (up to MAX_ACCS); other slots hold one item."""
    col = SLOT[it['type']]
    if it['type'] in ('acc', 'decor'):
        cap = MAX_ACCS if it['type'] == 'acc' else MAX_DECOR
        cur = [a for a in (p.get(col) or '').split(',') if a]
        if it['key'] in cur:
            if not toggle:
                return True
            cur.remove(it['key'])
            on = False
        else:
            cur = (cur + [it['key']])[-cap:]
            on = True
        query(f'UPDATE userprofiles SET {col} = %s WHERE user_id = %s', (','.join(cur), uid), commit=True)
        return on
    if it['type'] == 'sky' and toggle and sky_key_of(p) == it['key']:
        it = item(DEFAULT_SKY)  # taking a sky off puts Clear day back rather than leaving no sky
        toggle = False
    removable = it['type'] in ('frame', 'name', 'scene', 'soil', 'flower', 'leaves')
    new = '' if (toggle and removable and p.get(col) == it['key']) else it['key']
    query(f'UPDATE userprofiles SET {col} = %s WHERE user_id = %s', (new, uid), commit=True)
    return bool(new)


def equipped_keys(p):
    return {p.get('theme_key'), p.get('frame_key'), p.get('name_key'), p.get('pot_key') or 'pot_terracotta',
            p.get('scene_key'), p.get('soil_key'), sky_key_of(p), p.get('flower_key'), p.get('leaves_key'),
            p.get('species_key') or DEFAULT_SPECIES} \
        | {a for a in (p.get('acc_keys') or '').split(',') if a} | {d for d in (p.get('decor_keys') or '').split(',') if d}


@profile_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    uid = session['user_id']
    p = get_profile(uid)
    owned = owned_keys(uid)
    stats = user_stats(uid)
    if request.method == 'POST':
        f = {k: (request.form.get(k) or '').strip() for k in
             ('display_name', 'bio', 'pronouns', 'university', 'major', 'class_year', 'plant_name')}
        limits = {'display_name': 80, 'bio': 300, 'pronouns': 40, 'university': 120, 'major': 120, 'class_year': 10,
                  'plant_name': 40}
        for k, n in limits.items():
            if len(f[k]) > n:
                flash(f"{k.replace('_', ' ').capitalize()} must be {n} characters or fewer.", 'warning')
                return redirect(url_for('profile_bp.edit_profile'))
        if f['class_year'] and not (f['class_year'].isdigit() and 2000 <= int(f['class_year']) <= 2040):
            flash('Class year should look like 2028.', 'warning')
            return redirect(url_for('profile_bp.edit_profile'))
        avatar = p.get('avatar_path') or ''
        up = request.files.get('avatar')
        if up and up.filename:
            path, err = _save_avatar(up)
            if err:
                flash(err, 'danger')
                return redirect(url_for('profile_bp.edit_profile'))
            avatar = path
        if request.form.get('remove_avatar'):
            avatar = ''
        slots = {}
        for t, col in SLOT.items():
            # Trimmed edit form (Item 12) only posts avatar/display/plant_name — keep cosmetics as-is.
            if col not in request.form:
                slots[col] = p.get(col) or ''
                continue
            if t == 'acc':
                keys = [k for k in request.form.getlist('acc_keys') if k in owned and CATALOG.get(k, ('',))[0] == 'acc']
                slots[col] = ','.join(keys[:MAX_ACCS])
                continue
            key = request.form.get(col) or ''
            slots[col] = key if (key == '' or (key in owned and CATALOG.get(key, ('',))[0] == t)) else (p.get(col) or '')
        slots['theme_key'] = slots['theme_key'] or 'theme_sky'
        slots['pot_key'] = slots['pot_key'] or 'pot_terracotta'
        earned = {b['key'] for b in stats['badges'] if b['earned']}
        if 'pinned' in request.form:
            pins = [k for k in request.form.getlist('pinned') if k in earned][:3]
        else:
            pins = [k for k in (p.get('pinned_badges') or '').split(',') if k][:3]
        query('UPDATE userprofiles SET display_name=%s, bio=%s, pronouns=%s, university=%s, major=%s, class_year=%s, '
              'avatar_path=%s, theme_key=%s, frame_key=%s, name_key=%s, pot_key=%s, acc_keys=%s, scene_key=%s, '
              'plant_name=%s, pinned_badges=%s WHERE user_id=%s',
              (f['display_name'], f['bio'], f['pronouns'], f['university'], f['major'], f['class_year'], avatar,
               slots['theme_key'], slots['frame_key'], slots['name_key'], slots['pot_key'], slots['acc_keys'],
               slots['scene_key'], f['plant_name'] or p.get('plant_name') or 'Prody', ','.join(pins), uid), commit=True)
        flash('Profile saved.', 'success')
        return redirect(url_for('profile_bp.public_profile', username=session['username']))
    inv = {t: [item(k) for k in CATALOG if k in owned and CATALOG[k][0] == t] for t in SLOT}
    return render_template('profile_edit.html', p=p, inv=inv, stats=stats, labels=TYPE_LABEL,
                           accs=(p.get('acc_keys') or '').split(','), pinned=(p.get('pinned_badges') or '').split(','))


def _static_exists(rel):
    return bool(rel) and os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', rel))


def _with_art(it):
    """Garden items: the shop thumb from items.json if the file is there, else colour data for an inline SVG swatch."""
    if it['type'] == 'park':
        lt, dk = (f"ui/park/{str(it['css']).replace('_','-')}-{v}.svg" for v in ('light', 'dark'))
        it['thumb'] = lt if _static_exists(lt) else None
        it['thumb_dark'] = dk if _static_exists(dk) else None
        return it
    m = GARDEN_META.get(it['key'])
    if m:
        it['thumb'] = m.get('thumb') if _static_exists(m.get('thumb')) else None
        if not it['thumb']:
            c = dict(m.get('colors') or {})
            for n in ('leaf', 'flower', 'bark'):
                c.setdefault(n, c.get(n + '_color'))
            it['swatch'] = c
    return it


def plant_card(prof):
    """Static composite for the 'My plant' card: equipped sky, species tree and pot, from shop art and colours."""
    def meta(k, d):
        return GARDEN_META.get(k) or GARDEN_META.get(d) or {}
    pk = prof.get('pot_key') or 'pot_basket'
    pot = dict(POT_META.get(pk) or POT_META.get('pot_basket') or {}, name=(item(pk) or {}).get('name', 'Woven Basket'))
    sky = meta(sky_key_of(prof), DEFAULT_SKY)
    stops = (sky.get('colors') or {}).get('stops') or [{'offset': 0, 'color': '#FBF6EC'}]
    fl = meta(prof.get('flower_key'), 'flower_coral').get('colors') or {}
    sp = species_json(prof.get('species_key'))
    rar = (item(pk) or {}).get('rarity', 'common')
    return {'sky': ', '.join(f"{s['color']} {round(float(s['offset']) * 100)}%" for s in stops),
            'pot_svg': pot.get('svg') if _static_exists(pot.get('svg')) else None, 'pot_name': pot.get('name', 'Pot'),
            'pot_color': (pot.get('colors') or {}).get('body', '#C46A43'),
            'flower': fl.get('petal', sp['flower_color']), 'species': sp,
            # the default species is the Home oak (same scene art); it reads "Oak", not "Classic tree"
            'species_name': 'Oak' if sp['id'] == DEFAULT_SPECIES else (GARDEN_META.get(sp['id']) or {}).get('name', 'Oak'), 'tier': rar,
            # banner tree (park scene): tile-free shop thumbs for the equipped species + pot, light/dark
            'species_key': sp['id'], 'pot_key': pk,
            'banner_tree': _banner_thumbs(sp['id'], 'species_default'), 'banner_pot': _banner_thumbs(pk, 'pot_basket')}


# Plant STAGES (plant.py): 0 Seed, 1 Sprout, 2 Sapling, 3 Leafy(=art "Young"), 4 Bloom(=art "Mature"), 5 Flourishing(=art "Bloom")
PARK_ORDER = ['base', 'tree_base', 'trees', 'path', 'flowerbeds', 'lamp', 'bench', 'v_reader_bench', 'v_reader_walk_phone',
              'v_jogger_path', 'v_jogger_grass', 'v_dog', 'v_kids', 'birds']
PARK_STAGE = {'sapling': 2, 'young': 3, 'mature': 4, 'bloom': 5}


def park_layers(prof, stage_idx, owned):
    """Ordered Profile-banner park layers [{key, light, dark}] from owned park items + tree growth stage.
    v_under_tree is not full-canvas; it is returned separately by park_scene()."""
    have = {CATALOG[k][4] for k in owned if k in PARK_ITEMS}
    on = {'base'} | have
    if (stage_idx or 0) >= PARK_STAGE['young']:  # Design: tree_base from Leafy (stage 3); Coder's ground layer below
        on.add('tree_base')
    s = stage_idx or 0
    if s >= PARK_STAGE['sapling']:
        if 'bench' in have:
            on |= {'v_reader_bench'}
            on.discard('bench')  # the reader file draws its own bench
        elif 'path' in have:
            on.add('v_reader_walk_phone')
    if s >= PARK_STAGE['young']:
        if 'path' in have:
            on.add('v_jogger_path')
        elif 'v_reader_walk_phone' not in on:
            on.add('v_jogger_grass')
    if s >= PARK_STAGE['mature']:  # Leader: dog joins at stage 4 with or without the path
        on.add('v_dog')
        if 'bench' in have and 'path' in have:  # Leader: walker + dog also for bench owners from stage 4
            on.add('v_reader_walk_phone')
    if s >= PARK_STAGE['bloom']:
        on.add('v_kids')
    walk_open = 'v_reader_walk_phone' in on and 'v_reader_bench' in on  # Design: open-grass walker brings own dog
    if walk_open:
        on.discard('v_dog')
    def _f(k):
        n = 'v_reader_walk_phone_open' if (walk_open and k == 'v_reader_walk_phone') else k
        return {'key': k, 'light': f"ui/park/{str(n).replace('_','-')}-light.svg", 'dark': f"ui/park/{str(n).replace('_','-')}-dark.svg"}
    return [_f(k) for k in PARK_ORDER if k in on]


def park_scene(prof, stage_idx, owned, owner_id=None, show_friends=False):
    under = None
    if (stage_idx or 0) >= PARK_STAGE['mature']:
        under = {'key': 'v_under_tree', 'light': 'ui/park/v-under-tree-canvas-light.svg',
                 'dark': 'ui/park/v-under-tree-canvas-dark.svg'}
    layers = park_layers(prof, stage_idx, owned)
    if under:
        layers.append(under)  # full-canvas layer: roots.js rewrites .fp-banner-tree, so he lives in .fp-park
    slots = [L['key'] for L in layers if L['key'].startswith('v_') and L['key'] not in ('v_dog', 'v_under_tree')]  # scenery, not friend spots;  # PARK_ORDER, v_under_tree last
    friends = []
    if owner_id and show_friends:  # privacy: only the owner sees who is online
        from friends import online_friends_for_park
        friends = online_friends_for_park(owner_id, len(slots))
    if 'v_reader_bench' in slots and slots.index('v_reader_bench') >= len(friends):
        # nobody on the bench: show the bought bench itself instead of an empty spot
        i = slots.index('v_reader_bench'); slots.pop(i)
        layers = [({'key': 'bench', 'light': 'ui/park/bench-light.svg', 'dark': 'ui/park/bench-dark.svg'}
                   if L['key'] == 'v_reader_bench' else L) for L in layers]
    return {'layers': layers, 'under_tree': under, 'friends': friends, 'visitor_slots': slots}


def _banner_thumbs(key, fallback):
    k = key if _static_exists(f'shop/thumbs/{key}.svg') else fallback
    dark = f'shop/thumbs/{k}_dark.svg'
    return {'light': f'shop/thumbs/{k}.svg', 'dark': dark if _static_exists(dark) else f'shop/thumbs/{k}.svg'}


@profile_bp.route('/store')
@login_required
def store():
    from plant import plant_state
    uid = session['user_id']
    owned = owned_keys(uid)
    p = get_profile(uid)
    # Design 4dc31fa: trees-only lineup (no leaf/flower/pot/decor). Launch then coming soon.
    listed = [_with_art(item(k)) for k in CATALOG if CATALOG[k][0] == 'species']
    items = sorted(listed, key=store_order)
    bought = item(session.pop('just_bought', None) or '')
    if bought:
        bought['colors'] = list(((GARDEN_META.get(bought['key']) or {}).get('colors') or {}).values())[:3]
        bought['type_label'] = TYPE_LABEL.get(bought['type'], '')
    eq = equipped_keys(p)
    sel_key = p.get('species_key') or DEFAULT_SPECIES
    if sel_key not in owned and DEFAULT_SPECIES in owned:
        sel_key = DEFAULT_SPECIES
    selected = item(sel_key) or item(DEFAULT_SPECIES)
    return render_template('store.html', items=items, owned=owned, equipped=eq, bought=bought,
                           stats=user_stats(uid), st=plant_state(uid), selected=selected)


@profile_bp.route('/store/buy/<key>', methods=['POST'])
@login_required
def buy(key):
    uid = session['user_id']
    it = item(key)
    if not it or it['type'] in RETIRED_TYPES:
        return jsonify(ok=False, error='unknown_item', message='That item is not in the store.'), 403
    if it.get('coming_soon'):
        return jsonify(ok=False, error='coming_soon', message=f"{it['name']} is coming soon."), 403
    from db import IntegrityError, locked_user_txn
    from helpers import _clear_stats_cache, _user_stats
    earned = _user_stats(uid)['earned_points']  # earned only grows; what's spent is re-read under the lock
    conn, cur = locked_user_txn(uid)
    msg = None
    try:
        cur.execute('SELECT item_key, price_paid FROM userinventory WHERE user_id = %s', (uid,))
        rows = cur.fetchall()
        balance = earned - sum(int(r['price_paid'] or 0) for r in rows)
        if key in owned_keys(uid) or any(r['item_key'] == key for r in rows):
            msg = ('You already own that one.', 'info')
        elif balance < it['price']:
            msg = (f"Not enough points yet. A few more focus sessions and {it['name']} is yours.", 'warning')
        else:
            cur.execute('INSERT INTO userinventory (user_id, item_key, price_paid, purchased_at) VALUES (%s, %s, %s, %s)',
                        (uid, key, it['price'], apptime.now_utc_naive()))
        conn.commit()
    except IntegrityError:  # unique (user_id, item_key): someone else's request saved it first; nothing charged
        conn.rollback()
        msg = ('You already own that one.', 'info')
    finally:
        cur.close()
        try:
            conn.rollback()  # no-op after commit; on any error (even BaseException) releases the lock before close
        except Exception:
            pass
        conn.close()
    _clear_stats_cache()
    wants = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'fetch'
    if msg:
        if wants:
            return jsonify(ok=False, error='buy_failed', message=msg[0]), 400
        flash(*msg)
    else:
        session['celebrate'] = True
        session['just_bought'] = key
        if wants:
            bal = user_stats(uid)['points']
            return jsonify(ok=True, key=key, name=it['name'], price=it['price'], points=bal)
    return redirect(url_for('profile_bp.store', tab=GROUP_OF.get(it['type'], 'tree')))


@profile_bp.route('/store/equip/<key>', methods=['POST'])
@login_required
def equip(key):
    uid = session['user_id']
    it = item(key)
    if not it or key not in owned_keys(uid) or it['type'] in RETIRED_TYPES or it['type'] == 'park':
        abort(404)
    on = _set_slot(uid, it, get_profile(uid), toggle=True)
    flash(f"{'Equipped' if on else 'Took off'} {it['name']}.", 'success')
    return redirect(url_for('profile_bp.store', tab=GROUP_OF.get(it['type'], 'tree')))


# Zen Mode and Whiteboard live on this blueprint; these exact paths win over app.py's /coming-soon/<feature>.
@profile_bp.route('/coming-soon/zen')
@login_required
def zen():
    from plant import plant_state
    return render_template('zen.html', st=plant_state(session['user_id']))


@profile_bp.route('/whiteboard')
@login_required
def whiteboard():
    return render_template('whiteboard.html')


@profile_bp.route('/coming-soon/whiteboard')
def whiteboard_legacy():
    return redirect(url_for('profile_bp.whiteboard'), code=302)


_CARE_TABLE_READY = False


def _care_table():
    # Run once per process: query(..., commit=True) also clears the per-request stats cache,
    # which made the dashboard recompute user_stats 3x on every load.
    global _CARE_TABLE_READY
    if _CARE_TABLE_READY:
        return
    _CARE_TABLE_READY = True
    query('CREATE TABLE IF NOT EXISTS plantcare (user_id INT NOT NULL, cared_on DATE NOT NULL, PRIMARY KEY (user_id, cared_on))', (), commit=True)


_UTC_TABLE_READY = False


def _utc_gap_on():
    """PRODY_ADD_PLANTCARE_UTC=1 (off by default): keep the last watering's UTC time and require a 20h gap.
    Live MySQL needs migrations/2026-10-23_plantcare_utc.sql first (owner's yes)."""
    import os
    return os.environ.get('PRODY_ADD_PLANTCARE_UTC') == '1'


def last_cared(uid):
    """Date the user last watered their plant, or None. Kept out of study stats on purpose."""
    from flask import g, has_request_context
    cache = g.setdefault('_last_cared', {}) if has_request_context() else {}
    if uid in cache:  # the dashboard asks 3x per render
        return cache[uid]
    _care_table()
    r = query('SELECT MAX(cared_on) AS d FROM plantcare WHERE user_id = %s', (uid,), one=True)
    cache[uid] = str(r['d'])[:10] if r and r.get('d') else None
    return cache[uid]


def _utcnow():
    from datetime import timezone
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _app_day():
    from datetime import timezone
    from zoneinfo import ZoneInfo
    return _utcnow().replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')


def local_day(offset_min=None):
    """The user's calendar day. offset_min = minutes east of UTC from the client; only 15-minute steps in -12h..+14h count,
    anything else falls back to the server's day."""
    try:
        f = float(offset_min)
        off = int(f) if f.is_integer() else None
    except (TypeError, ValueError, OverflowError):
        off = None
    if off is None or off % 15 or not -720 <= off <= 840:
        return apptime.today_local().isoformat()
    return (_utcnow() + timedelta(minutes=off)).strftime('%Y-%m-%d')


MIN_CARE_GAP = timedelta(hours=20)


def water_today(uid, offset_min=None):
    """Water the plant once per day. With PRODY_ADD_PLANTCARE_UTC=1 both must hold: the local date is later than the last watering's,
    and at least 20 hours of real (UTC) time have passed, so swapping offsets can't buy a second watering. Flag off: America/New_York day, client offset ignored, no schema change.
    Returns True only if this call did the watering."""
    from flask import g, has_request_context
    global _UTC_TABLE_READY
    gap = _utc_gap_on()
    if gap and not _UTC_TABLE_READY:
        query('CREATE TABLE IF NOT EXISTS plantcare_utc (user_id INT NOT NULL PRIMARY KEY, last_at DATETIME NOT NULL)', (), commit=True)
        _UTC_TABLE_READY = True
    day = local_day(offset_min) if gap else _app_day()  # flag off: America/New_York day, client offset ignored
    last = last_cared(uid)
    if last and day <= last:
        return False
    now = _utcnow()
    r = query('SELECT last_at FROM plantcare_utc WHERE user_id = %s', (uid,), one=True) if gap else None
    last_at = r and r.get('last_at')
    if isinstance(last_at, str):
        last_at = datetime.strptime(last_at[:19], '%Y-%m-%d %H:%M:%S')
    if last_at and now - last_at < MIN_CARE_GAP:
        return False
    query('INSERT INTO plantcare (user_id, cared_on) VALUES (%s, %s)', (uid, day), commit=True)
    if gap and last_at:
        query('UPDATE plantcare_utc SET last_at = %s WHERE user_id = %s', (now, uid), commit=True)
    elif gap:
        query('INSERT INTO plantcare_utc (user_id, last_at) VALUES (%s, %s)', (uid, now), commit=True)
    if has_request_context():
        g.pop('_last_cared', None)
    return True


@profile_bp.route('/plant/care', methods=['POST'])
@login_required
def plant_care():
    """Once a day: water the plant. Its own action, not a study session, so hours, streaks and charts stay honest."""
    from flask import jsonify
    uid = session['user_id']
    if not water_today(uid):
        return jsonify(ok=False, error='Already watered today. Come back tomorrow.')
    return jsonify(ok=True, cared_on=last_cared(uid))


def pending_achievements():
    """Badges and stage-ups earned since this browser session last saw them. First call just records the baseline."""
    if 'user_id' not in session:
        return []
    from plant import plant_state
    uid = session['user_id']
    stats = user_stats(uid)
    earned = {b['key']: b for b in stats['badges'] if b['earned']}
    st = plant_state(uid)
    seen, seen_stage = session.get('seen_badges'), session.get('seen_stage')
    session['seen_badges'], session['seen_stage'] = list(earned), st['stage_idx']
    if seen is None:
        return []
    out = [{'icon': b['icon'], 'title': b['name'], 'sub': b['desc']} for k, b in earned.items() if k not in seen]
    if seen_stage is not None and st['stage_idx'] > seen_stage:
        out.append({'icon': 'potted_plant', 'title': f"{st['name']} is now {st['stage']}", 'sub': st.get('blurb', '')})
    return out


@profile_bp.app_context_processor
def _xp_globals():
    return {'pending_achievements': pending_achievements, 'last_cared': last_cared, 'today_str': apptime.today_local().isoformat()}


MOODS = ('great', 'good', 'okay', 'rough')


def _journal_table():
    query('CREATE TABLE IF NOT EXISTS journalentries (user_id INT NOT NULL, entry_date DATE NOT NULL, mood VARCHAR(10), '
          'body TEXT, updated_at DATETIME, PRIMARY KEY (user_id, entry_date))', (), commit=True)


@profile_bp.route('/journal', methods=['GET', 'POST'])
@login_required
def journal():
    """One short entry per day: what you studied, how it went. Today's minutes are pulled in from real sessions."""
    uid, today = session['user_id'], apptime.today_local().isoformat()
    _journal_table()
    if request.method == 'POST':
        body = (request.form.get('body') or '').strip()[:4000]
        mood = request.form.get('mood') if request.form.get('mood') in MOODS else None
        exists = query('SELECT 1 AS x FROM journalentries WHERE user_id = %s AND entry_date = %s', (uid, today), one=True)
        if not (body or mood):
            query('DELETE FROM journalentries WHERE user_id = %s AND entry_date = %s', (uid, today), commit=True)
        elif exists:  # update in place so a failed write never loses the old entry
            query('UPDATE journalentries SET mood = %s, body = %s, updated_at = %s WHERE user_id = %s AND entry_date = %s',
                  (mood, body, apptime.now_utc_naive(), uid, today), commit=True)
        else:
            query('INSERT INTO journalentries (user_id, entry_date, mood, body, updated_at) VALUES (%s,%s,%s,%s,%s)',
                  (uid, today, mood, body, apptime.now_utc_naive()), commit=True)
        flash('Saved today\'s entry.', 'success')
        return redirect(url_for('profile_bp.journal'))
    entries = query('SELECT entry_date, mood, body FROM journalentries WHERE user_id = %s ORDER BY entry_date DESC LIMIT 60', (uid,))
    mins = {}
    for s in query('SELECT minutes, started_at FROM studysessions WHERE user_id = %s', (uid,)):
        d = str(apptime.local_date(as_dt(s['started_at'])))[:10]
        mins[d] = mins.get(d, 0) + int(s['minutes'])
    past = [dict(e, entry_date=str(e['entry_date'])[:10]) for e in entries]
    cur = next((e for e in past if e['entry_date'] == today), None)
    return render_template('journal.html', today=today, cur=cur, past=[e for e in past if e['entry_date'] != today],
                           mins=mins, moods=MOODS)


def parse_quick(text, today=None):
    """'Read ch 4 due fri #CSC4710' -> name, due date, course code hint. Dates: today, tomorrow/tmr, weekday, 'in N days', M/D, YYYY-MM-DD.
    'due/by/on <date>' and ISO dates are read anywhere; a bare date only at the end. The date is removed from the title."""
    import re
    from datetime import date, timedelta
    today = today or apptime.today_local()
    t, due, course = ' '.join(text.split()), None, None
    m = re.search(r'#(\S+)', t)
    if m:
        course, t = m.group(1), ' '.join((t[:m.start()] + t[m.end():]).split())
    days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    expr = (r'(today|tonight|tomorrow|tmr|tmrw|in (\d{1,4}) days?|(mon|tue|wed|thu|fri|sat|sun)'
            r'(?:day|s|sday|nesday|rsday|urday|r|rs|n|nes)?|(\d{1,2})/(\d{1,2}))')

    def to_date(m):
        w = m.group(1).lower()
        if w in ('today', 'tonight'):
            return today
        if w in ('tomorrow', 'tmr', 'tmrw'):
            return today + timedelta(days=1)
        if m.group(2):
            return today + timedelta(days=int(m.group(2)))
        if m.group(3):
            return today + timedelta(days=(days.index(m.group(3).lower()) - today.weekday() - 1) % 7 + 1)
        try:
            d = date(today.year, int(m.group(4)), int(m.group(5)))
            return d.replace(year=today.year + 1) if d < today else d
        except ValueError:
            return None

    def iso(m):
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    # first match wins: ISO date anywhere; "due/by/on <date>" anywhere; a bare <date> at the end (709dd26 rule)
    rules = [(r'(?:\b(?:due|by|on)\s+)?\b(\d{4})-(\d{2})-(\d{2})\b', iso),
             (r'\b(?:due|by|on)\s+' + expr + r'(?![\w/])', to_date),
             (r'\b' + expr + r'\s*$', to_date)]
    for i, (rx, conv) in enumerate(rules):
        for m in re.finditer(rx, t, re.I):
            due = conv(m)
            if due:
                t = ' '.join((t[:m.start()] + ' ' + t[m.end():]).split())
                break
        if due:
            if i == 0:  # ISO won: drop a losing "due/by/on <date>" too, so it doesn't stay in the title
                rx2, conv2 = rules[1]
                for m in re.finditer(rx2, t, re.I):
                    if conv2(m):
                        t = ' '.join((t[:m.start()] + ' ' + t[m.end():]).split())
                        break
            break
    return t[:255], due, course


@profile_bp.route('/quick-add', methods=['POST'])
@login_required
def quick_add():
    from flask import jsonify
    uid = session['user_id']
    data = request.get_json(silent=True) or {}
    raw = data.get('text')
    if raw is not None and not isinstance(raw, str):
        return jsonify(ok=False, error='Text must be a string.'), 400
    name, due, course = parse_quick((raw or '')[:1000])
    if not name:
        return jsonify(ok=False, error='Type what you need to do.'), 400
    # critic-3 (quick-add): a task needs a class the user owns + a valid due date
    owned = query("SELECT course_id, course_code, course_name FROM usercourses WHERE id = %s", (uid,)) or []
    if not owned:
        return jsonify(ok=False, error='Add your first class before adding a task.'), 400
    cid = None
    if course:
        key = course.lower().replace(' ', '')
        cid = next((r['course_id'] for r in owned if (r['course_code'] or '').lower().replace(' ', '') == key), None) or \
            next((r['course_id'] for r in owned if (r['course_name'] or '').lower().replace(' ', '') == key), None)
        if cid is None:
            return jsonify(ok=False, error=f'No class matches #{course}.'), 400
    elif data.get('course_id') not in (None, ''):
        cid = next((r['course_id'] for r in owned if str(r['course_id']) == str(data.get('course_id'))), None)
        if cid is None:
            return jsonify(ok=False, error='Pick one of your classes.'), 400
    else:  # default to the last-used class
        last = query('SELECT course_id FROM todolist WHERE user_id = %s AND course_id IS NOT NULL '
                     'ORDER BY task_id DESC LIMIT 1', (uid,), one=True)
        ids = {r['course_id'] for r in owned}
        cid = last['course_id'] if last and last['course_id'] in ids else (owned[0]['course_id'] if len(owned) == 1 else None)
        if cid is None:
            return jsonify(ok=False, error='Which class? Add #CODE, e.g. "#CSC4710".'), 400
    if due is None and isinstance(data.get('due_date'), str) and data.get('due_date'):
        try:
            due = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify(ok=False, error='Due date must be YYYY-MM-DD.'), 400
    kind = 'deadline' if data.get('kind') == 'deadline' and cid else 'task'
    if kind == 'deadline':
        query('INSERT INTO coursedeadlines (course_id, deadline_name, deadline_date, is_completed) VALUES (%s,%s,%s,0)',
              (cid, name, datetime.combine(due, datetime.min.time()).replace(hour=23, minute=59) if due else apptime.now_local()), commit=True)
    else:
        query('INSERT INTO todolist (user_id, task_name, due_date, is_completed, course_id, progress, category) '
              'VALUES (%s,%s,%s,0,%s,0,%s)', (uid, name, due, cid, 'task'), commit=True)
    return jsonify(ok=True, kind=kind, name=name, due=due.strftime('%a %b %-d') if due else None,
                   nudge=None if due else 'Add a due date?')


# ---- Roots + Branches data (Functionality) ----

# r7g: the sage course tint's dot was #68AB3A (read as crown green); it is yellow-lime so chip dot + flower stand out
def _load_class_tints():
    """ONE source for class colours: static/ui/data/class_tints.json (also fetched by zen.html ?v=2)."""
    import json as _json
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'ui', 'data', 'class_tints.json')) as fh:
            return {k.upper(): v.upper() for k, v in _json.load(fh)['tints'].items()}
    except Exception:
        return {}

CLASS_TINTS = _load_class_tints()
DOT_OVERRIDES = CLASS_TINTS  # _deepen reads the tints file, so dots and tints can't drift
DEFAULT_CLASS_DOT = CLASS_TINTS.get('#CFDCC6', '#C6D93B')  # colourless class -> lime

def _deepen(hexc, keep=0.55):
    """Darken and saturate a pastel course color so small dots stay distinguishable."""
    if (hexc or '').upper() in DOT_OVERRIDES:
        return DOT_OVERRIDES[(hexc or '').upper()]
    try:
        import colorsys
        h = (hexc or '').lstrip('#'); r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
        hh, l, sat = colorsys.rgb_to_hls(r, g, b)
        r, g, b = colorsys.hls_to_rgb(hh, l * keep, min(1.0, sat * 0.6 + 0.35))
        return '#%02X%02X%02X' % (int(r * 255), int(g * 255), int(b * 255))
    except Exception:
        return '#3F7D4E'

def class_dot_colour(stored):
    """r7h: the ONE class-dot colour for every page (tree chips/flowers, To-Do, sessions, zen, profile chips):
    the stored pastel course tint deepened by _deepen, with DOT_OVERRIDES applied (sage -> lime #C6D93B).
    An empty stored colour (colourless class) returns lime #C6D93B (DEFAULT_CLASS_DOT, from class_tints.json)
    on every page, including To-Do, Calendar and Me; that is intended. Only an invalid (non-#RRGGBB)
    stored colour returns '' so callers keep their own fallback."""
    if not stored:
        return DEFAULT_CLASS_DOT  # colourless class: lime from class_tints.json, never sage
    if not re.match(r'^#[0-9A-Fa-f]{6}$', stored):
        return ''
    return _deepen(stored)


@profile_bp.route('/roots/data')
@login_required
def roots_data():
    """Everything the Roots dashboard draws, from real data only."""
    from datetime import date, timedelta
    from flask import jsonify
    uid = session['user_id']
    today = apptime.today_local()
    courses = fill_display_colours(query('SELECT course_id, course_name, course_code, color FROM usercourses WHERE id = %s', (uid,)) or [], uid)
    sess = query('SELECT course_id, minutes, started_at, completed FROM studysessions WHERE user_id = %s', (uid,)) or []
    todos = query('SELECT course_id, COUNT(*) AS n FROM todolist WHERE user_id = %s AND is_completed = 1 AND course_id IS NOT NULL GROUP BY course_id', (uid,)) or []
    grades = query('SELECT course_id, item_name, weight FROM grades WHERE user_id = %s', (uid,)) or []
    ids = [c['course_id'] for c in courses]
    dls = []
    if ids:
        ph = ','.join(['%s'] * len(ids))
        dls = query(f'SELECT deadline_id, course_id, deadline_name, deadline_date, is_completed FROM coursedeadlines WHERE course_id IN ({ph})', tuple(ids)) or []

    def d10(v):
        return date.fromisoformat(str(v)[:10])

    mins, focus_fl = {}, {}
    for s in sess:
        mins[s['course_id']] = mins.get(s['course_id'], 0) + int(s['minutes'] or 0)
        if s.get('completed'):
            focus_fl[s['course_id']] = focus_fl.get(s['course_id'], 0) + 1
    done_todo = {t['course_id']: int(t['n']) for t in todos}
    weight = {(g['course_id'], (g['item_name'] or '').strip().lower()): float(g['weight']) for g in grades}

    branches = []
    for c in courses:
        cid = c['course_id']
        done_dl = sum(1 for d in dls if d['course_id'] == cid and d['is_completed'])
        branches.append({'course_id': cid, 'name': c['course_name'], 'code': c['course_code'] or '',
                         'color': c['color'], 'dot': class_dot_colour(c['color']) or _deepen(c['color']), 'minutes': mins.get(cid, 0),
                         'leaves': mins.get(cid, 0) // 60,          # one leaf per hour studied
                         'done_deadlines': done_dl,  # finished assignments only (v33 flowers)
                         'focus_flowers': focus_fl.get(cid, 0),        # focus sessions whose timer reached 0
                         'flowers': done_todo.get(cid, 0) + done_dl + focus_fl.get(cid, 0)})  # tasks + deadlines + full sessions
    roots = []
    for d in dls:
        if d['is_completed']:
            continue
        due = d10(d['deadline_date'])
        win = min(due, today) - timedelta(days=14)  # recent study for this course counts toward every open root
        studied = sum(int(s['minutes'] or 0) for s in sess
                      if s['course_id'] == d['course_id'] and win <= d10(apptime.to_local(as_dt(s['started_at']))) <= today)
        roots.append({'deadline_id': d['deadline_id'], 'course_id': d['course_id'], 'name': d['deadline_name'],
                      'due': due.isoformat(), 'days_left': (due - today).days,
                      'weight': weight.get((d['course_id'], d['deadline_name'].strip().lower())),  # null if no matching grade item
                      'studied_minutes': studied, 'dashed': studied == 0,
                      'actions': {'done_url': url_for('user_courses_bp.api_deadline_done', deadline_id=d['deadline_id']),
                                  'edit_url': url_for('user_courses_bp.api_deadline_edit', deadline_id=d['deadline_id'])}})
    from api_tree import dated_task_roots  # same root rule as /api/tree (deadlines + open dated class tasks)
    try:
        tdue = query('SELECT task_id, course_id, task_name, is_completed, due_date FROM todolist WHERE user_id = %s', (uid,)) or []
    except Exception:
        tdue = []
    for r in dated_task_roots(tdue, set(ids), today):
        r.update({'weight': None, 'studied_minutes': 0, 'dashed': True})
        roots.append(r)
    roots.sort(key=lambda r: r['days_left'])
    st = user_stats(uid)
    try:
        from plant import POTS
        pk = (get_profile(uid) or {}).get('pot_key') or 'pot_terracotta'
        pc = POTS.get(pk) or POTS['pot_terracotta']
        pot = {'key': pk, 'color': pc[0], 'shade': pc[1], 'pattern': pc[3]}
    except Exception:
        pot = {'key': 'pot_terracotta', 'color': '#C46A43', 'shade': '#B35B36', 'pattern': None}
    prof = get_profile(uid) or {}
    garden = {t: (prof.get(col) or None) for t, (_l, col) in GARDEN_TYPES.items() if t not in ('decor', 'species')}
    garden['decor'] = [k for k in (prof.get('decor_keys') or '').split(',') if k]
    # sky: what to draw in light mode; sky_night: what to draw in dark mode (Clear night only while on the default)
    garden['sky'] = sky_key_of(prof)
    garden['sky_night'] = DEFAULT_SKY_NIGHT if garden['sky'] == DEFAULT_SKY else garden['sky']
    garden['sky_is_default'] = garden['sky'] == DEFAULT_SKY
    garden['colors'] = {k: GARDEN_META[k].get('colors') for k in
                        [v for v in garden.values() if isinstance(v, str)] + garden['decor'] if k in GARDEN_META}
    import json as _json
    from flask import Response
    payload = {'garden': garden, 'pot': pot, 'species': species_json(prof.get('species_key')), 'today': today.isoformat(), 'streak': st.get('streak', 0),
                    'studied_today': any(d10(apptime.to_local(as_dt(s['started_at']))) == today for s in sess),
                    'branches': branches,
                    'roots': [r for r in roots if r['days_left'] <= 21],   # next 3 weeks drawn as roots
                    'later': [r for r in roots if r['days_left'] > 21]}   # folded into a "later" list
    # json.dumps keeps insertion order (jsonify sorts keys), so species fields arrive in the documented order
    return Response(_json.dumps(payload, default=str), mimetype='application/json')


@profile_bp.route('/u/<username>/tree.json')
@login_required
def friend_tree(username):
    """Oak-kit tree data for a FRIEND's profile (friends only; flower labels redacted)."""
    from flask import jsonify
    from friends import relation
    from api_tree import build_tree
    r = query('SELECT id FROM users WHERE username = %s', (username,))
    if not r:
        abort(404)
    rel, _ = relation(session['user_id'], r[0]['id'])
    if rel not in ('self', 'friends'):
        abort(403)
    d = build_tree(r[0]['id'])
    if rel != 'self':
        for b in d.get('branches', []):
            for f in b.get('flowers', []) or []:
                f['label'] = {'task': 'Task done', 'deadline': 'Deadline met', 'focus': 'Focus session'}.get(f.get('kind'), 'Flower')
    return jsonify(d)
