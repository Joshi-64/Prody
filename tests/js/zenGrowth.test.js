const t = require('node:test'), a = require('node:assert'), Z = require('../../static/js/zenGrowth.js');
const M = 60000, N = 220, CONTACT = 14, FPS = 30;
const INTRO_MS = CONTACT / FPS * 1000; // ≈466.67ms

t.test('1-minute timer', () => {
  const s = Z.create(M, 0);
  a.equal(Z.frameIndex(Z.progress(s, 0), N), 0);
  a.equal(Z.frameIndex(Z.progress(s, 30000), N), 110);
  a.equal(Z.frameIndex(Z.progress(s, M), N), N - 1);
  a.equal(Z.frameIndex(Z.progress(s, 5 * M), N), N - 1);
});
t.test('25-minute timer', () => {
  const D = 25 * M, s = Z.create(D, 1000);
  a.equal(Z.progress(s, 1000 + D / 4), 0.25);
  a.equal(Z.frameIndex(Z.progress(s, 1000 + D / 4), N), 55);
  a.equal(Z.frameIndex(Z.progress(s, 1000 + D - 1), N), N - 1);
});
t.test('pause freezes, resume continues', () => {
  let s = Z.create(M, 0);
  s = Z.pause(s, 20000);
  a.equal(Z.progress(s, 50000), 20000 / M);
  s = Z.resume(s, 50000);
  a.equal(Z.progress(s, 60000), 30000 / M);
  a.deepEqual(Z.pause(Z.pause(s, 61000), 70000).banked, 31000);
  a.equal(Z.resume(s, 99999).startedAt, s.startedAt);
});
t.test('clock skew and bad input are safe', () => {
  const s = Z.create(0, 1000);
  a.equal(Z.progress(Z.create(M, 1000), 500), 0);
  a.equal(Z.progress(s, 5000), 1);
});
t.test('frame urls match flower_grow names', () => {
  a.equal(Z.frameUrl('/static/zen/tulip_png', 'tulip', 0), '/static/zen/tulip_png/tulip_0001.png');
  a.equal(Z.frameUrl('x', 'peony', 219), 'x/peony_0220.png');
});

t.test('soil contact N=14 for tulip and peony at 30fps', () => {
  a.equal(Z.SOIL_CONTACT.tulip, 14);
  a.equal(Z.SOIL_CONTACT.peony, 14);
  a.equal(Z.INTRO_FPS, 30);
  a.equal(Z.soilContact('tulip'), 14);
  a.ok(Math.abs(Z.introMs('tulip') - INTRO_MS) < 0.01);
});

function assertIntroAndGrowth(durationMs, label) {
  // t=0 → frame 0 (1-based frame 1)
  a.equal(Z.displayFrame(0, durationMs, N, CONTACT), 0, label + ' start');
  // mid-intro: halfway through 14 frames ≈ frame 7 (0-based 6)
  a.equal(Z.displayFrame(INTRO_MS / 2, durationMs, N, CONTACT), Math.floor((INTRO_MS / 2 / 1000) * FPS), label + ' mid-intro');
  // last intro instant (just before intro ends) → frame 13 (1-based 14)
  a.equal(Z.displayFrame(INTRO_MS - 0.001, durationMs, N, CONTACT), CONTACT - 1, label + ' contact');
  // just after intro → first growth frame index 14 (1-based 15)
  a.equal(Z.displayFrame(INTRO_MS, durationMs, N, CONTACT), CONTACT, label + ' first growth');
  // mid growth (halfway through remaining time) → about halfway through frames 15..220
  const rem = durationMs - INTRO_MS;
  const mid = Z.displayFrame(INTRO_MS + rem / 2, durationMs, N, CONTACT);
  const expectedMid = CONTACT + Math.floor(0.5 * (N - CONTACT));
  a.equal(mid, expectedMid, label + ' mid growth');
  // end → last frame
  a.equal(Z.displayFrame(durationMs, durationMs, N, CONTACT), N - 1, label + ' end');
  a.equal(Z.displayFrame(durationMs * 2, durationMs, N, CONTACT), N - 1, label + ' past end');
}

t.test('frame math with intro at 1 minute', () => assertIntroAndGrowth(1 * M, '1m'));
t.test('frame math with intro at 5 minutes', () => assertIntroAndGrowth(5 * M, '5m'));
t.test('frame math with intro at 25 minutes', () => assertIntroAndGrowth(25 * M, '25m'));

t.test('reduced motion shows contact frame then grows', () => {
  a.equal(Z.displayFrame(0, M, N, CONTACT, true), CONTACT - 1);
  a.equal(Z.displayFrame(M / 2, M, N, CONTACT, true), CONTACT + Math.floor(0.5 * (N - CONTACT)));
  a.equal(Z.displayFrame(M, M, N, CONTACT, true), N - 1);
});
