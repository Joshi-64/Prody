import os, shutil, subprocess
import pytest

HERE = os.path.dirname(__file__)
pytestmark = pytest.mark.skipif(not shutil.which('node'), reason='node not installed')


def test_functionality_node_suite_passes():
    """Functionality's zenGrowth.test.js (3798d51) + item-9 branches cutscene state machine."""
    tests = [
        os.path.join(HERE, 'js', 'zenGrowth.test.js'),
        os.path.join(HERE, 'js', 'branchesCutscene.test.js'),
    ]
    r = subprocess.run(['node', '--test', *tests], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'fail 0' in r.stdout or '# fail 0' in r.stdout
    assert 'pass ' in r.stdout


def test_webp_frame_urls_and_finish():
    js = os.path.abspath(os.path.join(HERE, '..', 'static', 'ui', 'js', 'zenGrowth.js'))
    out = subprocess.check_output(['node', '-e', """
const Z=require(process.argv[1]);let s=Z.create(25*60000,0);s=Z.pause(s,60000);
console.log([Z.frameUrl('/static/zen/tulip','tulip',219,'.webp'),Z.frameIndex(Z.progress(Z.finish(s),1),220)].join('|'));""", js], text=True)
    assert out.strip() == '/static/zen/tulip/tulip_0220.webp|219'
    out2 = subprocess.check_output(['node', '-e', """
const Z=require(process.argv[1]);
console.log(Z.frameUrl('/static/zen/camellia','camellia',0,'.webp'));""", js], text=True)
    assert out2.strip() == '/static/zen/camellia/camellia_0001.webp'
