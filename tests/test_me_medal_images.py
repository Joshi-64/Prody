"""Every Me garden-medal image path must resolve to an on-disk static/spot asset (light + dark)."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _medal_imgs_from_profiles():
    src = open(os.path.join(ROOT, 'profiles.py'), encoding='utf-8').read()
    # tuples: (key, img, name, desc, earned_expr) inside the medals = [ ... ] block
    block = re.search(r"medals = \[(.*?)\]\n\s*medals = \[dict\(key=k, img=img", src, re.S)
    assert block, 'medals list with img field not found in profiles.py'
    imgs = re.findall(r"'([a-z0-9_]+)'\s*,\s*'([^']+)'\s*,\s*'[^']+'\s*,\s*'[^']+'\s*,", block.group(1))
    # fallback: dict literals with img=
    if not imgs:
        imgs = [(m.group(1), m.group(2)) for m in re.finditer(
            r"\(\s*'([a-z0-9_]+)'\s*,\s*'(badge_[a-z0-9_]+)'\s*,", block.group(1))]
    assert imgs, 'no medal img mappings parsed'
    return imgs


def test_every_medal_image_exists_on_disk():
    spot = os.path.join(ROOT, 'static', 'ui', 'icons')
    imgs = _medal_imgs_from_profiles()
    assert len(imgs) >= 5
    missing = []
    for key, img in imgs:
        for name in (f'{img}.svg', f'{img}_dark.svg'):
            path = os.path.join(spot, name)
            if not os.path.isfile(path):
                missing.append(f'{key} -> {name}')
    assert not missing, 'medal spot assets missing: ' + ', '.join(missing)
    # text lock: full canopy copy says Tree, not Plant
    src = open(os.path.join(ROOT, 'profiles.py'), encoding='utf-8').read()
    assert 'Tree fully grown' in src and 'Plant fully grown' not in src
