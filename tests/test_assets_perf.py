"""perf_r1: content-hashed static URLs, long cache only on the current hash."""
import hashlib, os, re, sys, tempfile
os.environ['PRODY_DB'] = 'sqlite'
os.environ.setdefault('PRODY_SQLITE_PATH', os.path.join(tempfile.mkdtemp(prefix='prody_assets_'), 'a.sqlite3'))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import app as prody_app  # noqa: E402
import assets  # noqa: E402


def c():
    prody_app.app.config.update(TESTING=True)
    return prody_app.app.test_client()


def test_html_static_urls_hashed():
    html = c().get('/login').get_data(as_text=True)
    urls = re.findall(r'/static/[^"\']+', html)
    assert urls and all(re.search(r'\?v=[0-9a-f]{10}$', u) for u in urls), urls
    assert 'fonts.googleapis.com' not in html and 'window.__AV=' in html


def test_long_cache_only_for_current_hash():
    r = c().get('/static/ui/css/app.css?v=' + assets.file_hash('ui/css/app.css'))
    assert 'immutable' in r.headers['Cache-Control'] and 'max-age=31536000' in r.headers['Cache-Control']
    assert c().get('/static/ui/css/app.css?v=29').headers['Cache-Control'] == 'no-cache'


def test_css_urls_hashed_and_css_hash_tracks_rewrite():
    css = c().get('/static/ui/css/garden.css').get_data(as_text=True)
    assert '?v=' in css or 'url(' in css
    assert assets.file_hash('ui/css/garden.css') == hashlib.sha1(css.encode()).hexdigest()[:10]


def test_css_hash_changes_when_referenced_image_changes_at_runtime(tmp_path):
    old_root = assets.STATIC_ROOT
    root = str(tmp_path.resolve())
    os.makedirs(os.path.join(root, 'css')); os.makedirs(os.path.join(root, 'img'))
    open(os.path.join(root, 'img', 'band.png'), 'wb').write(b'one')
    open(os.path.join(root, 'css', 'a.css'), 'w').write('.x{background:url(/static/img/band.png)}')
    assets.STATIC_ROOT = root
    try:
        before = assets.file_hash('css/a.css')
        assert assets.file_hash('css/a.css') == before
        st = os.stat(os.path.join(root, 'css', 'a.css'))
        open(os.path.join(root, 'img', 'band.png'), 'wb').write(b'two!')
        os.utime(os.path.join(root, 'css', 'a.css'), ns=(st.st_atime_ns, st.st_mtime_ns))
        after = assets.file_hash('css/a.css')
        assert after != before
        assert assets.rewrite('<link href="/static/css/a.css">') == '<link href="/static/css/a.css?v=%s">' % after
    finally:
        assets.STATIC_ROOT = old_root
