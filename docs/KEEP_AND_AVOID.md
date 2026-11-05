# Prody clay redesign: keep and avoid

Decisions so far. Check new art and UI against this list before review.

## Keep
- The 3D clay look across the whole app: soft, cozy colours, the tree as the star. Every tree shares the same light texture on bark, leaves and grass (between the v9 and v10 passes: not flat, not busy).
- Oak, cherry and pine are the launch trees. The other four show as coming-soon silhouettes.
- Home tree, clean mode (default): no task tags or overlays. One small glowing badge floats above the tree for alerts. One badge, one meaning, hidden at zero; "needs care" wins over "coming up".
- Home tree, garden mode (opt-in switch in the Today sheet): tasks grow on the home tree as the tree's own item.
- Tapping the badge opens a separate Branches view for that branch. Class chips sit up top, with a dot under any class that needs checking.
- Each tree grows its own item on its branches, attached with real stems and leaves:
  - Oak: acorns. Green = upcoming, ripe brown = done, dried and cracked = overdue.
  - Cherry: buds and open blossoms sitting on top of the wood. Overdue = a bare node dropping a few petals. Finished work builds up pink clusters. Thin dotted lines link each blossom to its task.
  - Pine: cones.
- Cherry scene: hot spring, stone lantern, stepping stones, petal carpet, a soft Mount Fuji.
- Pine scene: jagged alpine peaks, warmer bark, two pinecones, a path ending at the tree (approved v1_2).
- Oak scene: the picnic blanket. Grass runs to the bottom edge in every scene.
- Animations ship as transparent PNG sprite sheets (fixed square frames, same pivot every frame).
- Backend, data models, API and app logic stay as they are. The home reads `GET /api/tree`.

## Avoid
- Flowers or buds that look pasted on, with no stems or leaves growing out of the branch.
- Task tags, previews or overlays on the clean home tree.
- The heavy grey wilted flower for overdue, and hanging blossom stalks on the cherry.
- The overdue signpost (dropped).
- A Fuji-style mountain in the pine scene (too close to the cherry).
- The willow (scrapped) and maple (lost to pine as the third tree).
- WebM animations: iPhone Safari won't play them with transparency.
- Texture that's too flat or too busy.
- Paid tools: no Fal, Krea or paid Runway.
- The old Three.js 3D plant (broken: a file it needs is missing).
- Red, pulsing alerts, streak guilt and countdown pressure anywhere on the tree.
