"""Preview entry. Prefer Turso when PRODY_USE_TURSO is opted in and TURSO_* are set;
otherwise ephemeral SQLite. No automatic test-account / demo seeding on boot.
Manual seeds (seed_demo.py / pp_seed.py) are opt-in CLI only. Do not point at TiDB/MySQL from this entry.
"""
import os, sys, tarfile, glob

def _truthy(v):
    return (v or '').strip().lower() in ('1', 'true', 'yes', 'on')

_has_turso = (
    _truthy(os.environ.get('PRODY_USE_TURSO'))
    and bool(os.environ.get('TURSO_DATABASE_URL') and os.environ.get('TURSO_AUTH_TOKEN'))
    and (os.environ.get('VERCEL_ENV') or '').strip().lower() != 'production'
)
if not _has_turso:
    # Ephemeral preview DB (resets every cold start) — when Turso is not opted in.
    os.environ['PRODY_DB'] = 'sqlite'
    os.environ['PRODY_SQLITE_PATH'] = '/tmp/prody_preview.db'
for _k in ('PRODY_DB_HOST', 'PRODY_DB_USER', 'PRODY_DB_PASSWORD', 'PRODY_DB_NAME', 'PRODY_DB_PORT'):
    os.environ.pop(_k, None)
if os.environ.get('GEMINI_API_KEY') and not os.environ.get('PRODY_AI_KEY'):
    os.environ['PRODY_AI_KEY'] = os.environ['GEMINI_API_KEY']
    os.environ.setdefault('PRODY_AI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai')
    os.environ.setdefault('PRODY_AI_MODEL', 'gemini-flash-lite-latest')
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DST = '/tmp/pp_app'
if not os.path.exists(os.path.join(_DST, 'app.py')):
    os.makedirs(_DST, exist_ok=True)
    _tgz = '/tmp/pp_bundle.tar'
    with open(_tgz, 'wb') as out:
        for part in sorted(glob.glob(os.path.join(_ROOT, 'bundle.part*'))):
            out.write(open(part, 'rb').read())
    with tarfile.open(_tgz) as t:
        t.extractall(_DST)
sys.path.insert(0, _DST)
os.chdir(_DST)
from app import app  # noqa: E402,F401
import db as _db  # noqa: E402
print('pp_db: backend=%s turso=%s' % (_db.DB_BACKEND, _has_turso))

# Schema only — never create demo/test users or todos on cold start.
try:
    from db import init_db, DB_BACKEND
    init_db()
    print('pp_boot: schema ok backend=%s' % DB_BACKEND)
except Exception as e:  # noqa: BLE001
    print('pp_boot: init_db failed %r' % (e,))
