# Branches: motion spec

Two moments, both built on transform and opacity only (compositor-friendly on iPhone).
Code: `static/js/garden.js` (Branches view section). Art: `static/garden/branch/`.

## 1. Tree → Branches (once per visit)

Pressing the tree (or the badge, a `+N` bundle, or Today → Branches) plays a ~1.2 s cutscene.
The page is usable from about 0.9 s.

| Time (ms) | What happens |
| --- | --- |
| 0 | The tree squishes under the finger (existing spring). Home chrome (greeting, avatar, Today, tab bar) fades out over 220 ms. |
| 120–840 | **Camera push.** The live scene and a pre-blurred copy of the same art (`scenes/<scene>-blur.webp`) scale 2.5× together toward the canopy, aimed halfway between the press point and the canopy centre. Easing `cubic-bezier(.66,0,.24,1)`. |
| 300–720 | The blurred copy fades up, so the push reads as a focus pull rather than a zoom. |
| 160–1000 | **Fly-through.** Five leaves (oak) or petals (cherry) swell past the lens. Pine has none, because needles read as broken pieces. |
| 480 | The header and class chips drop in (340 ms). The paper sheet with the list rises from below (560 ms). |
| 560–1200 | **The branch grows.** The wood is revealed left to right behind a feathered edge. The leaves follow 170 ms later. The branch springs from −2.4° to 0 as it finishes. |
| as the growth reaches each node | **Work sprouts.** Acorns and cones drop in and swing to rest (780 ms). Buds and blossoms pop up from the wood (640 ms). |
| ~1080 | The class name and the "N/M harvested" pill fade in. |
| 900 | The WebGL scene goes to sleep (it's fully covered), saving battery. |

**Back** (button, swipe-back or Escape) reverses this in about 0.7 s:
- The sheet drops and the header fades.
- The camera pulls back out and the blur clears.
- The home chrome returns.

## 2. Switching classes

The branch stays; only what grows on it changes (~0.9 s):

1. The current items shrink back into their nodes, right to left, 30 ms apart.
2. The branch gives a small nod (−1.1°, then +0.45°).
3. The list words fade. The paper stays.
4. The new class's work sprouts left to right, 75 ms apart, and its list groups slide in.

## Reduced motion

No push, no fly-through, no growth or sprouting. The blurred backdrop and the page simply appear, and close is instant.

## Art

| File | What |
| --- | --- |
| `branch/<oak\|cherry\|pine>_wood.webp` | Bare clay branch with six node stubs, 1170×1080, transparent |
| `branch/<…>_leaf.webp` | Leaves or needle tufts only (wood held out), same frame |
| `branch/fly_<oak\|cherry>.webp` | Fly-through sprite |
| `scenes/<scene>-blur.webp` | Pre-blurred scene, 270×480 (blur is baked in, never a live CSS blur) |

Source: `branch_hero.blend` (scene `BranchHero`, script text `branch_hero.py`). Node positions are exported from it and live in `HANG_NODES` / `SIT_NODES` in `garden.js`.
