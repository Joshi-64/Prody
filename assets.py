"""Content-hashed /static URLs + long-term caching.

Every /static/... URL in an HTML or CSS response is rewritten to /static/...?v=<sha1[:10] of the
file> (hand-written ?v=N numbers are replaced), so a changed file always gets a new URL.
Only a request whose ?v= equals the current hash is served `public, max-age=31536000, immutable`;
anything else revalidates (no-cache). CSS hashes cover the CSS *after* rewriting, so a changed image
inside a stylesheet also changes the stylesheet's URL. File hashes are cached by (mtime_ns, size); a
CSS entry also records the hash of every /static file it references, and is reused only while the
CSS file's own key and each dependency's (stat-cached, so cheap) hash are unchanged.

Tree kit art is loaded by tree_kit.js from kit.json file names, so it can't be rewritten in HTML:
pages get `window.__AV={dir:hash}` (one hash per kit dir, over every file in it) and tree_kit.js
appends ?v=<dir hash>. The static handler accepts that dir hash for files inside that dir.
"""
import hashlib, os, re, time
from flask import request

STATIC_ROOT = None
KIT_DIRS = ('img/oak_kit', 'img/soil_v1f')
_URL_RE = re.compile(r'''(?<=["'(=\s])/static/([A-Za-z0-9_./@-]+\.[A-Za-z0-9]+)(\?v=[A-Za-z0-9._-]*)?(?=["')\s&>])''')
_cache = {}
DIR_TTL = 2.0


def _key(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def rewrite(text, deps=None):
    def sub(m):
        h = file_hash(m.group(1))
        if deps is not None:
            deps.append((m.group(1), h))
        return '/static/' + m.group(1) + ('?v=' + h if h else (m.group(2) or ''))
    return _URL_RE.sub(sub, text)


def css_text(rel, deps=None):
    full = os.path.join(STATIC_ROOT, rel)
    return rewrite(open(full, encoding='utf-8').read(), deps)


def file_hash(rel):
    rel = rel.lstrip('/')
    full = os.path.normpath(os.path.join(STATIC_ROOT, rel))
    if not full.startswith(STATIC_ROOT + os.sep):
        return None
    k = _key(full)
    if k is None:
        return None
    hit = _cache.get(full)
    if hit and hit[0] == k and all(file_hash(d) == dh for d, dh in hit[2]):
        return hit[1]
    deps = []
    if rel.endswith('.css'):
        _cache[full] = (k, None, ())  # guards against a stylesheet that references itself
        data = css_text(rel, deps).encode()
    else:
        data = open(full, 'rb').read()
    h = hashlib.sha1(data).hexdigest()[:10]
    _cache[full] = (k, h, tuple(d for d in deps if d[0].lstrip('/') != rel))
    return h


def dir_hash(rel):
    full = os.path.join(STATIC_ROOT, rel)
    hit = _cache.get(('dir', full))
    if hit and time.monotonic() - hit[2] < DIR_TTL:
        return hit[1]  # re-stat ~1.7k kit files at most every DIR_TTL s, not per request
    sig = []
    for dp, _, fs in os.walk(full):
        for f in fs:
            p = os.path.join(dp, f)
            sig.append((os.path.relpath(p, full), _key(p)))
    sig.sort()
    if hit and hit[0] == sig:
        _cache[('dir', full)] = (sig, hit[1], time.monotonic())
        return hit[1]
    h = hashlib.sha1()
    for name, _ in sig:
        h.update(name.encode())
        h.update(open(os.path.join(full, name), 'rb').read())
    v = h.hexdigest()[:10]
    _cache[('dir', full)] = (sig, v, time.monotonic())
    return v


def manifest():
    m = {d: dir_hash(d) for d in KIT_DIRS if os.path.isdir(os.path.join(STATIC_ROOT, d))}
    # nav-perf: kit.json by its own file hash, the same ?v= the HTML rewrite gives the dashboard preload,
    # so tree_kit.js and the preload share one immutable cache entry on every page.
    kh = file_hash('img/oak_kit/kit.json')
    if kh:
        m['img/oak_kit/kit.json'] = kh
    return m


def valid_version(rel, v):
    if not v:
        return False
    if v == file_hash(rel):
        return True
    return any(rel.startswith(d + '/') and v == dir_hash(d) for d in KIT_DIRS)


def register(app):
    global STATIC_ROOT
    STATIC_ROOT = os.path.realpath(app.static_folder)

    @app.context_processor
    def _asset_globals():
        return {'asset_manifest': manifest}

    # Registered last => runs first among after_request hooks (before CSRF injection and compression).
    @app.after_request
    def _hash_urls(resp):
        if resp.direct_passthrough and resp.mimetype == 'text/css' and request.path.startswith('/static/') \
                and resp.status_code == 200:
            resp.direct_passthrough = False
            resp.set_data(css_text(request.path[len('/static/'):]))
            return resp
        if resp.mimetype == 'text/html' and not resp.direct_passthrough and resp.status_code < 300 \
                and not resp.headers.get('Content-Encoding'):
            html = resp.get_data(as_text=True)
            if '/static/' in html:
                resp.set_data(rewrite(html))
        return resp
