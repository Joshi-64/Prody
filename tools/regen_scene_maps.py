"""Regenerate garden scene maps + plates for new scene art.

Maps encoding (read by static/garden/tree-scene.js):
  R = tree matte (alpha of the tree layer; also the plate 'hole')
  G = inside the tree: sway weight (0 at trunk base -> 1 at canopy top);
      outside the tree: steam plume zone
  B = background motion: cloud drift above `split`, tufts/water below it
Plate = the background with the tree removed (shown only behind the tree while it moves).

Method: register the old scene art to the new art (OpenCV ECC, affine), warp the
old maps onto the new art with that transform (nearest for R/B masks would lose
soft edges, so linear), then rebuild the plate from the NEW art by inpainting under
the dilated tree matte (Telea r=15 + blur, same recipe as clay_set/v4_code/prep.py).
Usage: python3 tools/regen_scene_maps.py OLD_DIR NEW_DIR OUT_DIR
"""
import sys, cv2, numpy as np
old, new, out = sys.argv[1:4]
for n in ('tree', 'cherry', 'pine'):
    a = cv2.imread(f'{old}/{n}-scene.webp'); b = cv2.imread(f'{new}/{n}-scene.webp')
    ga, gb = (cv2.cvtColor(x, cv2.COLOR_BGR2GRAY).astype(np.float32) for x in (a, b))
    M = np.eye(2, 3, dtype=np.float32)
    cc, M = cv2.findTransformECC(ga, gb, M, cv2.MOTION_AFFINE,
                                 (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), None, 5)
    h, w = b.shape[:2]
    maps = cv2.imread(f'{old}/{n}-maps.png')
    if np.abs(M - np.eye(2, 3)).max() > 0.05:   # real move: warp the maps
        maps = cv2.warpAffine(maps, M, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
    hole = (maps[..., 2] > 4).astype(np.uint8) * 255
    hole = cv2.dilate(hole, np.ones((17, 17), np.uint8))
    plate = cv2.inpaint(b, hole, 15, cv2.INPAINT_TELEA)
    plate = np.where(hole[..., None] > 0, cv2.GaussianBlur(plate, (0, 0), 12), plate)
    cv2.imwrite(f'{out}/{n}-maps.png', maps, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    cv2.imwrite(f'{out}/{n}-plate.webp', plate, [cv2.IMWRITE_WEBP_QUALITY, 80])
    print(n, 'ecc', round(cc, 5), 'shift_px', M[:, 2].round(3).tolist(), 'scale', M[0, 0].round(4), M[1, 1].round(4))
