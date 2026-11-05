
// Pure helpers mirroring garden.js cutscene guards (item 9).
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

function makeCut() {
  let busy = false, cutDir = 0, viewHidden = true, hash = '', stack = [];
  let opens = 0, closes = 0, skips = 0;
  function open(fromPop) {
    if (busy || !viewHidden) return false;
    cutDir = 1; busy = true; opens++;
    if (!fromPop && hash !== '#branches') { stack.push('#branches'); hash = '#branches'; }
    viewHidden = false;
    return true;
  }
  function finishOpen() { if (cutDir !== 1) return; busy = false; cutDir = 0; }
  function close(fromPop) {
    if (viewHidden && cutDir !== 1) return false;
    if (!fromPop && hash === '#branches') {
      // simulate history.back -> popstate -> close(true)
      stack.pop(); hash = stack[stack.length - 1] || '';
      return close(true);
    }
    cutDir = -1; busy = true; closes++;
    return true;
  }
  function finishClose() { if (cutDir !== -1) return; viewHidden = true; busy = false; cutDir = 0; }
  function skip() {
    if (cutDir === 1) { skips++; finishOpen(); return 'open-end'; }
    if (cutDir === -1) { skips++; finishClose(); return 'close-end'; }
    return null;
  }
  function pop() {
    // browser back while open
    stack.pop(); hash = stack[stack.length - 1] || '';
    close(true);
  }
  return {
    open, finishOpen, close, finishClose, skip, pop,
    get state() { return { busy, cutDir, viewHidden, hash, stack: stack.slice(), opens, closes, skips }; }
  };
}

describe('branches cutscene state', () => {
  it('plays open every tap (no seen flag) and survives open/back x3', () => {
    const c = makeCut();
    for (let i = 0; i < 3; i++) {
      assert.equal(c.open(false), true);
      c.finishOpen();
      assert.equal(c.state.viewHidden, false);
      c.close(false); // UI back -> popstate close
      c.finishClose();
      assert.equal(c.state.viewHidden, true);
      assert.equal(c.state.busy, false);
      assert.equal(c.state.hash, '');
    }
    assert.equal(c.state.opens, 3);
    assert.equal(c.state.closes, 3);
    assert.equal(c.state.stack.length, 0); // no history growth
  });

  it('rapid taps while busy are ignored', () => {
    const c = makeCut();
    assert.equal(c.open(false), true);
    assert.equal(c.open(false), false);
    assert.equal(c.open(false), false);
    c.skip();
    assert.equal(c.state.busy, false);
    assert.equal(c.state.opens, 1);
    assert.equal(c.state.skips, 1);
  });

  it('skip during close lands on clean tree', () => {
    const c = makeCut();
    c.open(false); c.finishOpen();
    c.close(false);
    assert.equal(c.state.cutDir, -1);
    assert.equal(c.skip(), 'close-end');
    assert.equal(c.state.viewHidden, true);
    assert.equal(c.state.busy, false);
  });

  it('popstate back closes without pushing', () => {
    const c = makeCut();
    c.open(false); c.finishOpen();
    const before = c.state.stack.length;
    c.pop();
    c.finishClose();
    assert.ok(c.state.stack.length < before || c.state.stack.length === 0);
    assert.equal(c.state.viewHidden, true);
  });
});
