"""zen-fs-fix: full-screen Zen markup/CSS and 500 page copy."""
import os, re, tempfile
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(), 'prody_test.sqlite3'))
from _jobs_helpers import client_for, make_user  # noqa: E402


def _zen():
    return client_for(make_user()).get('/zen').get_data(as_text=True)


def test_picker_offers_tulip_and_pink_rose():
    html = _zen()
    pick = re.search(r'<div class="zfl-pick".*?</div>', html, re.S).group(0)
    labels = re.findall(r'role="radio"[^>]*>([^<]+)</button>', pick)
    assert labels == ['Yellow tulip', 'Pink rose']
    assert 'peony' not in pick.lower() and 'Pink peony' not in pick
    # saved peony migrates to camellia; unknown falls back to tulip
    assert "f==='peony'" in html and 'camellia' in html


def test_fullscreen_hides_droplet_and_close_buttons():
    html = _zen()
    assert 'html.zen-full .zen-main .zen-ic{display:none!important}' in html  # rain droplet + fullscreen x
    assert 'html.zen-full .zen.running .zfl-pick' in html and 'html.zen-full .zen.running .zen-len' in html
    assert 'env(safe-area-inset-top)' in html and '#2A2530' in html and 'blur(12px)' in html
    assert 'width:150px;height:150px' in html and 'width:210px;height:210px' in html


def test_error_page_copy_and_oak():
    from unittest import mock
    import app as appmod
    c = client_for(make_user())
    with mock.patch.dict(appmod.app.config, {'PROPAGATE_EXCEPTIONS': False, 'TESTING': False}), \
            mock.patch.dict(appmod.app.view_functions, {'dashboard': mock.Mock(side_effect=RuntimeError('boom'))}):
        r = c.get('/dashboard')
    assert r.status_code == 500
    html = r.get_data(as_text=True)
    assert 'Something went wrong on our end.' in html and 'Something wilted' not in html
    assert 'garden/scenes/tree-scene.webp' in html and 'err-oak' in html


def test_buddy_chips_empty_vs_history():
    import app as appmod
    uid = make_user()
    c = client_for(uid)
    html = c.get('/buddy').get_data(as_text=True)
    if 'id="buddySuggest"' not in html:
        return  # AI not configured in this env: no chips/input at all
    assert 'class="fp-suggest" id="buddySuggest"' in html
    assert 'id="buddyIdeas"' in html and 'aria-expanded="false" hidden>' in html
    from flask import render_template
    with appmod.app.test_request_context('/buddy'):
        from flask import session
        session['user_id'] = uid
        out = render_template('buddy.html', messages=[{'role': 'user', 'content': 'hi'}], ai_ready=True, capped=False, resting=False, draft='')
    assert 'fp-suggest is-off' in out and 'aria-expanded="false">💡 Ideas' in out
    assert 'env(safe-area-inset-bottom' in out


def test_buddy_phone_pins_input_and_clips_log():
    """Design: input fixed above tab bar; message list scrolls inside the card, never under the header."""
    html = client_for(make_user()).get('/buddy').get_data(as_text=True)
    compact = ' '.join(html.split())
    assert '.fp-chat .chat-input{position:fixed' in compact
    assert 'bottom:calc(62px + 14px + env(safe-area-inset-bottom' in compact
    assert 'body:has(.fp-chat) .content{flex:1 1 auto;min-height:0' in compact
    assert '.fp-chat .chat-log{flex:1 1 auto;min-height:0' in compact
    assert 'overflow-y:auto' in compact and 'overscroll-behavior:contain' in compact
    assert '.fp-chat{flex:1 1 auto;min-height:0' in compact and 'overflow:hidden' in compact
    assert 'fc.scrollIntoView' not in html and "scrollIntoView({block:'end'})" not in html


def test_buddy_empty_has_no_welcome_bubble():
    """Empty chat must not draw any msg-row / avatar bubble above the prompts (both themes)."""
    import app as appmod
    from flask import render_template, session
    uid = make_user()
    with appmod.app.test_request_context('/buddy'):
        session['user_id'] = uid
        for ai_ready in (True, False):
            html = render_template(
                'buddy.html', messages=[], ai_ready=ai_ready, capped=False, resting=not ai_ready, draft='',
            )
            assert 'class="msg-row"' not in html
            assert "Hi, I'm" not in html
            assert 'napping in the shade' not in html
            assert 'fp-empty' in html
            assert 'id="buddyAvSrc"' in html and 'buddy-av' in html
    # live page (AI may or may not be configured) also has no welcome bubble when empty
    html = client_for(uid).get('/buddy').get_data(as_text=True)
    assert 'class="msg-row"' not in html
    assert "Hi, I'm" not in html


def test_fullscreen_zfl_win_no_square_frame():
    """Design: flower sits on scene in fullscreen — transparent win, no rounded square."""
    html = _zen()
    rule = [ln for ln in html.splitlines() if 'html.zen-full .zfl-win,html.clay.is-zen.zen-full .zfl-win{' in ln][0]
    assert 'background:transparent' in rule
    assert 'border-radius:20px' not in rule
    assert 'rgba(255,255,255,.06)' not in rule
