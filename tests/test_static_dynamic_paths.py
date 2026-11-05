"""Literal dynamically-loaded /static paths in templates must resolve under static/.

Catches url_for(filename=...) and fetch/src strings that a rename sweep can miss
(e.g. Zen class_tints.json + gsap.min.js).
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, 'templates')
STATIC = os.path.join(ROOT, 'static')

_URL_FOR = re.compile(
    r"""url_for\(\s*['\"]static['\"]\s*,\s*filename\s*=\s*['\"]([^'\"]+)['\"]""",
    re.I,
)
_BARE = re.compile(r"""['\"](/static/[^'\"]+?)(?:\?[^'\"]*)?['\"]""")


def _collect():
    found = []
    for dirpath, _, files in os.walk(TEMPLATES):
        for name in files:
            if not name.endswith('.html'):
                continue
            path = os.path.join(dirpath, name)
            text = open(path, encoding='utf-8').read()
            rel = os.path.relpath(path, ROOT)
            for m in _URL_FOR.finditer(text):
                found.append((rel, m.group(1).lstrip('/')))
            for m in _BARE.finditer(text):
                s = m.group(1)
                if '{{' in s or '}}' in s:
                    continue
                found.append((rel, s[len('/static/'):]))
    return found


def test_zen_critically_named_dynamic_assets_exist():
    """Critic NO-GO pair: class tints JSON + gsap used by Zen scripts."""
    assert os.path.isfile(os.path.join(STATIC, 'ui', 'data', 'class_tints.json'))
    assert os.path.isfile(os.path.join(STATIC, 'ui', 'vendor', 'gsap.min.js'))
    zen = open(os.path.join(TEMPLATES, 'zen.html'), encoding='utf-8').read()
    assert 'filename="ui/data/class_tints.json"' in zen
    assert "filename='ui/vendor/gsap.min.js'" in zen
    assert 'filename="data/class_tints.json"' not in zen
    assert 'ui/js/vendor/gsap' not in zen


def test_template_static_filenames_exist_on_disk():
    missing = []
    for rel, fn in _collect():
        if '~' in fn or '{{' in fn:
            continue
        # directory prefixes used with ~ concat are not standalone files
        base = fn.rstrip('/')
        if '.' not in os.path.basename(base):
            continue
        full = os.path.join(STATIC, base)
        if not os.path.isfile(full):
            missing.append('%s -> static/%s' % (rel, base))
    assert not missing, 'template static paths missing on disk:\n' + '\n'.join(missing[:40])


def test_zen_flower_frame_sets_on_disk():
    for flower in ('tulip', 'camellia'):
        d = os.path.join(STATIC, 'zen', flower)
        frames = [f for f in os.listdir(d) if f.endswith('.webp')]
        assert len(frames) == 220, flower
        assert os.path.isfile(os.path.join(d, '%s_0001.webp' % flower))
        assert os.path.isfile(os.path.join(d, '%s_0220.webp' % flower))
    assert not os.path.exists(os.path.join(STATIC, 'zen', 'peony'))


def test_backend_class_tints_loader_reads_ui_data_file():
    """Debugger: profiles._load_class_tints must open static/ui/data (7th consumer), not static/data."""
    import json
    import os

    src = open(os.path.join(ROOT, 'profiles.py'), encoding='utf-8').read()
    assert "static', 'ui', 'data', 'class_tints.json'" in src
    assert "static', 'data', 'class_tints.json'" not in src

    path = os.path.join(STATIC, 'ui', 'data', 'class_tints.json')
    disk = json.load(open(path, encoding='utf-8'))
    assert isinstance(disk.get('tints'), dict) and len(disk['tints']) >= 1
    expect = {k.upper(): v.upper() for k, v in disk['tints'].items()}

    # Call the loader directly — do not importlib.reload(profiles); that rebinds
    # blueprint handlers and breaks frozen-clock tests (test_et_day).
    from profiles import _load_class_tints, CLASS_TINTS, DEFAULT_CLASS_DOT
    loaded = _load_class_tints()
    assert loaded, 'CLASS_TINTS empty — loader path still wrong'
    assert loaded == expect
    assert CLASS_TINTS == expect
    assert DEFAULT_CLASS_DOT == expect.get('#CFDCC6', '#C6D93B')
    # items4 already on shop path
    assert "static', 'shop', 'items.json'" in src
    assert os.path.isfile(os.path.join(STATIC, 'shop', 'items.json'))


def test_python_static_open_paths_not_pre_cleanup():
    """Sweep key Python modules for hard-coded pre-cleanup static roots that no longer exist."""
    import re

    stale = []
    for rel in ('profiles.py', 'plant.py', 'assets.py', 'app.py'):
        text = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        for m in re.finditer(r"join\([^)\n]*['\"]static['\"]\s*,\s*['\"]([^'\"]+)['\"]", text):
            first = m.group(1)
            # models dir intentionally absent (glb_models returns []); uploads is runtime-created
            if first in ('data', 'css', 'js', 'img', 'spot', 'oak_kit'):
                stale.append('%s uses static/%s' % (rel, first))
        if 'static/data/class_tints' in text or '/static/data/' in text:
            stale.append('%s still mentions static/data' % rel)
    assert not stale, stale


def test_shop_items_no_dead_species_preview_svg():
    """Four species must not keep obsolete trees/species/*_preview.svg svg fields."""
    import json
    path = os.path.join(STATIC, 'shop', 'items.json')
    data = json.load(open(path, encoding='utf-8'))
    items = data['items'] if isinstance(data, dict) else data
    targets = {
        'species_default',
        'species_cherry_blossom',
        'species_maple',
        'species_olive',
    }
    seen = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        iid = it.get('id')
        if iid in targets:
            seen.add(iid)
            assert 'svg' not in it, '%s still has svg=%r' % (iid, it.get('svg'))
            assert 'thumb' in it  # other art fields remain
        if isinstance(it.get('svg'), str):
            assert not it['svg'].endswith('_preview.svg'), (iid, it['svg'])
    assert seen == targets
    blob = open(path, encoding='utf-8').read()
    assert '_preview.svg' not in blob
