"""Every icon_names entry in fonts.css must exist as a liga/rlig ligature in the self-hosted woff2."""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, 'static', 'fonts', 'material-symbols-rounded-subset.woff2')
CSS = os.path.join(ROOT, 'static', 'css', 'fonts.css')


def _icon_names_from_css():
    text = open(CSS, encoding='utf-8').read()
    m = re.search(r'icon_names=([a-z_0-9,]+)', text)
    assert m, 'icon_names= missing from fonts.css'
    names = m.group(1).split(',')
    assert names == sorted(names), 'icon_names must stay sorted'
    return names


def _ligature_names(path):
    pytest.importorskip('fontTools')
    from fontTools.ttLib import TTFont
    font = TTFont(path)
    assert 'GSUB' in font, 'subset font missing GSUB'
    names = set()
    for lr in font['GSUB'].table.LookupList.Lookup:
        for sub in lr.SubTable:
            if lr.LookupType == 7:
                sub = sub.ExtSubTable
            if not hasattr(sub, 'ligatures'):
                continue
            for first, ligs in sub.ligatures.items():
                for lig in ligs:
                    comps = [first] + list(lig.Component)
                    chars = []
                    for g in comps:
                        if g == 'underscore':
                            chars.append('_')
                        elif len(g) == 1:
                            chars.append(g)
                    name = ''.join(chars)
                    if name:
                        names.add(name)
                    for suf in ('_outline', '_filled', '_rounded'):
                        if name.endswith(suf):
                            names.add(name[:-len(suf)])
    return names


def test_subset_woff2_covers_every_fonts_css_icon_name():
    want = _icon_names_from_css()
    assert 'smart_toy' in want  # the icon that previously landed in CSS without a rebuilt woff2
    have = _ligature_names(FONT)
    missing = sorted(set(want) - have)
    assert not missing, (
        'material-symbols-rounded-subset.woff2 is missing ligatures for: '
        + ', '.join(missing)
        + ' — rebuild from the Google Fonts CSS URL in fonts.css (Safari UA) and replace the woff2'
    )
