"""Garden zoom: second tap during open cutscene must skip to end state."""
import os, re
HERE = os.path.join(os.path.dirname(__file__), '..', 'static', 'ui', 'js', 'garden.js')


def test_open_branches_second_tap_skips():
    src = open(HERE, encoding='utf-8').read()
    # early re-entry while opening invokes cutSkip
    assert 'if (busy && cutDir === 1 && cutSkip)' in src
    assert 'cutSkip()' in src
    # skip handler cancels then finishes and pins dive.to transform
    assert 'cancelFinite([view, stage, blur, fly])' in src
    assert 'n.style.transform = dive.to' in src
    # stage also listens during open (tree tap)
    assert src.count("stage.addEventListener('pointerdown', cutSkip, true)") >= 2
