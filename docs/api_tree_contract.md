# `/api/tree` data contract (draft v0.2, Round 1, planning only)

One read-only JSON feed the tree draws from: branches, flowers, roots, park.
`GET /api/tree` with `@login_required`. Always the session user's own data (no `user_id` param).
It reuses logic already in `profiles.roots_data()` (`/roots/data`), `plant.py` (semester progress, stage) and `profiles.park_scene()`. Plan: factor those into helpers and have both routes call them, not copy them.

## Top level
| field | type | notes |
|---|---|---|
| `version` | int | contract version, starts at `1` |
| `today` | `YYYY-MM-DD` | server date used for every calculation |
| `semester` | object | `start`, `end` (dates), `progress` 0..1 (time elapsed) |
| `tree` | object | `stage_idx` int 0..5, `stage` string (plant.py names), `growth` 0..1 |
| `branches` | array | one per class, sorted by `slot` |
| `roots` | array | all open deadlines, sorted by `days_left` asc (no `later` list) |
| `overflow` | array | classes beyond the 8th: `{course_id, name, code, color}`, listed but not drawn |
| `park` | object | park state |

## branches[]
| field | type | range / notes |
|---|---|---|
| `course_id` | int | `usercourses.course_id` |
| `name`, `code` | string | `course_name`, `course_code` |
| `color` | `#RRGGBB` | `usercourses.color`; `dot` = deepened color |
| `slot` | int | 0..7 (max 8 drawn), fixed position on trunk. Alternates sides: even = left, odd = right, lower slot = lower on trunk |
| `side` | `"left"`/`"right"` | derived from slot |
| `length` | float | 0..1. `0.15 + 0.85 * clamp(0.5*semester.progress + 0.5*done_ratio)`, where done_ratio = finished / total items for that class. Never 0 so a new class is visible |
| `minutes` | int | total study minutes; `leaves` = minutes // 60 |
| `flower_count` | int | = len(flowers) |
| `flowers` | array | see below, capped at 24 drawn (`flowers_more` int for the rest) |

### flowers[]
| field | type | notes |
|---|---|---|
| `id` | string | `"task:12"`, `"deadline:7"`, `"focus:33"` |
| `kind` | `task` / `deadline` / `focus` | todolist done, coursedeadlines done, studysessions.completed |
| `label` | string | item name |
| `pos` | float 0..1 | position along branch (0 = trunk end). Ordered by completion time when it exists, else by id |
| `done_at` | date or null | **null today for task/deadline (no column, see gaps)** |

## roots[]
| field | type | range / notes |
|---|---|---|
| `deadline_id`, `course_id` | int | |
| `name` | string | `deadline_name` |
| `due` | `YYYY-MM-DD` | |
| `days_left` | int | can be negative (overdue) |
| `depth` | float | 0..1. `clamp(days_left / days_until_semester_end)`; due today ~0, at/after term end = 1, overdue = 0 and flagged. If `days_until_semester_end <= 0`, depth = 1 for any future deadline |
| `overdue` | bool | `days_left < 0` |
| `weight` | float or null | `grades.weight` of the grade linked to this deadline by id (set via the grade-entry picker); null if none linked. No name matching |
| `studied_minutes` | int | course study in the 14 days before due |
| `dashed` | bool | `studied_minutes == 0` |
| `actions` | object | `done_url`, `edit_url` (existing routes) |

## park
| field | type | notes |
|---|---|---|
| `layers` | array of `{key, light, dark}` | from `park_scene()`, draw order |
| `under_tree` | object or null | stage >= mature |
| `visitor_slots` | string[] | scenery keys friends can occupy |
| `friends` | array | `{username, display_name, avatar_url, slot}`; only filled for the owner (privacy stays as in `park_scene`), empty for public views |
| `owned_items` | string[] | `userinventory.item_key` that are park items |
| `sky`, `sky_night` | string | from `sky_key_of()` |

## Example (5 classes, 6 deadlines; example data only)
```json
{
  "version": 1,
  "today": "2026-10-23",
  "semester": {"start": "2026-08-24", "end": "2026-12-14", "progress": 0.52},
  "tree": {"stage_idx": 3, "stage": "Young", "growth": 0.55},
  "branches": [
    {"course_id": 11, "name": "Calculus I", "code": "MATH 151", "color": "#CFDCC6", "dot": "#9DB38F",
     "slot": 0, "side": "left", "length": 0.64, "minutes": 840, "leaves": 14, "flower_count": 3,
     "flowers": [
       {"id": "deadline:41", "kind": "deadline", "label": "Problem set 4", "pos": 0.2, "done_at": null},
       {"id": "task:88", "kind": "task", "label": "Review limits", "pos": 0.5, "done_at": null},
       {"id": "focus:301", "kind": "focus", "label": "Focus session", "pos": 0.8, "done_at": "2026-10-20"}]},
    {"course_id": 12, "name": "Biology", "code": "BIO 101", "color": "#E8D3A9", "dot": "#C9AC70", "slot": 1, "side": "right", "length": 0.58, "minutes": 600, "leaves": 10, "flower_count": 2, "flowers": []},
    {"course_id": 13, "name": "English Comp", "code": "ENG 110", "color": "#C9D7E8", "dot": "#8FA8C8", "slot": 2, "side": "left", "length": 0.47, "minutes": 300, "leaves": 5, "flower_count": 1, "flowers": []},
    {"course_id": 14, "name": "History", "code": "HIST 120", "color": "#E5C4C4", "dot": "#C48E8E", "slot": 3, "side": "right", "length": 0.41, "minutes": 240, "leaves": 4, "flower_count": 0, "flowers": []},
    {"course_id": 15, "name": "Psychology", "code": "PSY 100", "color": "#D9CDE6", "dot": "#AE98C9", "slot": 4, "side": "left", "length": 0.15, "minutes": 0, "leaves": 0, "flower_count": 0, "flowers": []}
  ],
  "roots": [
    {"deadline_id": 50, "course_id": 13, "name": "Essay draft", "due": "2026-10-22", "days_left": -1, "depth": 0.0, "overdue": true, "weight": 10.0, "studied_minutes": 0, "dashed": true, "actions": {"done_url": "...", "edit_url": "..."}},
    {"deadline_id": 51, "course_id": 11, "name": "Quiz 3", "due": "2026-10-26", "days_left": 3, "depth": 0.06, "overdue": false, "weight": 5.0, "studied_minutes": 120, "dashed": false, "actions": {"done_url": "...", "edit_url": "..."}},
    {"deadline_id": 52, "course_id": 12, "name": "Lab report", "due": "2026-10-30", "days_left": 7, "depth": 0.13, "overdue": false, "weight": null, "studied_minutes": 45, "dashed": false, "actions": {"done_url": "...", "edit_url": "..."}},
    {"deadline_id": 53, "course_id": 14, "name": "Midterm", "due": "2026-11-04", "days_left": 12, "depth": 0.23, "overdue": false, "weight": 25.0, "studied_minutes": 0, "dashed": true, "actions": {"done_url": "...", "edit_url": "..."}},
    {"deadline_id": 54, "course_id": 15, "name": "Reading response", "due": "2026-11-12", "days_left": 20, "depth": 0.38, "overdue": false, "weight": null, "studied_minutes": 0, "dashed": true, "actions": {"done_url": "...", "edit_url": "..."}}
  ,
    {"deadline_id": 55, "course_id": 11, "name": "Final exam", "due": "2026-12-10", "days_left": 48, "depth": 0.92, "overdue": false, "weight": 30.0, "studied_minutes": 0, "dashed": true, "actions": {"done_url": "...", "edit_url": "..."}}
  ],
  "overflow": [],
  "park": {
    "layers": [{"key": "base", "light": "img/park/items/park_base_light.svg", "dark": "img/park/items/park_base_dark.svg"}],
    "under_tree": null,
    "visitor_slots": ["v_jogger_grass"],
    "friends": [{"username": "sam", "display_name": "Sam", "avatar_url": "/static/uploads/avatars/sam.png", "slot": "v_jogger_grass"}],
    "owned_items": ["path"],
    "sky": "sky_clear_day", "sky_night": "sky_clear_night"
  }
}
```

## Gaps in current tables (for Prody Data - Root)
1. **No completion timestamp** on `todolist` or `coursedeadlines`, so flowers can't be ordered or dated along a branch. Suggest `completed_at DATETIME NULL` on both, set when marked done.
2. **No semester / term bounds.** `plant.py` guesses from sign-up and deadlines (~16 weeks). Suggest `semester_start`, `semester_end` on `userprofiles` (or a small `terms` table) so branch length and root depth use real dates.
3. **No stable branch slot.** Order today is just query order, so branches would jump when a class is added or deleted. Suggest `usercourses.branch_slot INT NULL`.
4. **No per-class start/end**, so a class added mid-term grows as if it started in August. Optional `usercourses.started_on DATE`.
5. **Deadline weight is matched by name** to `grades.item_name` (fragile). Optional `coursedeadlines.weight DECIMAL(5,2) NULL`.
6. **`coursedeadlines` has no `user_id`**; ownership only via `usercourses`. Fine, but every query must join; worth an index on `coursedeadlines(course_id, is_completed)`.
7. **Schema files lag `db.py`**: `studysessions.completed`, `userprofiles.decor_keys/species_key/...` are added by `db.py` migrations but missing from `schema.sql` / `schema_sqlite.sql`. Should be synced.
8. `usercourses` has both `id` (owner) and nullable `user_id`; contract uses `id`. Worth a note or cleanup.
9. Tasks with `course_id IS NULL` have no branch. Proposal: count them toward `tree.growth` only, no flower.

## Decisions (Functionality, Oct 23)
- Root depth is relative to semester end, not a fixed 21 days; no `later` list.
- Max 8 branches; extras go in `overflow`.
- Depth now depends on gap 2 (semester dates); until that lands, use the `plant.py` fallback end date.

## Open questions for Functionality
- Should `/roots/data` be retired in favour of `/api/tree` later?

---
# v0.5: mapping to `lumen/oak_kit_v3_6c/kit.json` (`version: oak-kit-3`)
Replaces v0.4. The server sends **logical choices only**; the client composes pixels from kit.json. Rules from the kit `notes`: each piece's `attach_px` goes on the previous `tip_px`, the first piece goes on `socket_px` (authoritative, 2048 canvas), and pieces rotate about `attach_px` (angle > 0 = clockwise). Draw order: roots, `trunk_flare`, `trunk`, branches (each chain drawn tip to base), canopy clumps, flowers.

Top level adds `kit_version: "oak-kit-3"`, `stage` (1..3), `stage_scale` (1.0 / 1.1), `stage_boost` (bool).

## Stage
App `stage_idx` 0-1 = stage 1, 2-3 = stage 2, 4-5 = stage 3 (Design). The higher one in each pair = `stage_scale 1.1` + `stage_boost true` (more canopy clumps).

## Branches
| contract | kit | rule |
|---|---|---|
| `slot` 0..7 | `branch_slot_N`, N = slot + 1 | stored in `usercourses.branch_slot`. `branch_slot_N` gives the trunk `socket_px` and the chain heading `angle` (e.g. slot 1 = -61.3 degrees). Slots share sockets in pairs (1+8, 2+5, 3+4, 6+7) |
| `bend` | segment variant `am12 / am4 / ap0 / ap4 / ap12` | angle -12, -4, 0, +4, +12 of each segment on top of the heading. Default `0`; same bend for the whole chain |
| `length` 0..1 | `chain` | see table below |
| (last tip) | `canopy_clump_N` | placed on the final chain tip |

**Length to chain** (kit rule: `tip_m1` follows mid1, `tip_m2` follows mid2, `tip` follows mid3, `mid_loop` repeats between mid1 and mid2):
| `length` | `chain` sent |
|---|---|
| < 0.25 | `["base","mid1","tip_m1"]` |
| 0.25 to < 0.5 | `["base","mid1","mid2","tip_m2"]` (kit default chain) |
| 0.5 to < 0.75 | `["base","mid1","mid2","mid3","tip"]` |
| >= 0.75 | `["base","mid1", ...mid_loop x L, "mid2","mid3","tip"]`, `L = 1 + floor((length - 0.75) / 0.125)`, max 3 |
Piece name = `branch_<N>_<seg>_<bend>`, for example `branch_3_mid2_ap4`.

API: `"kit": {"slot": 3, "bend": "ap0", "chain": ["base","mid1","mid2","mid3","tip"]}`.

## Flowers to `bloom_px`
Each mid, `mid_loop` and tip piece has 6 `bloom_px`; the base has none. Points are filled in chain order (base to tip, kit point order within a piece), oldest `completed_at` first, then by id when it's NULL (rows from before the migration). Each flower sends `"bloom": {"seg": 2, "i": 4}`, where `seg` = index into `chain`. Capacity = 6 x (chain length - 1), between 12 and 42. The rest go to `flowers_more`.
| `kind` | piece |
|---|---|
| `task` | `flower_task` |
| `deadline` | `flower_deadline` |
| `focus` | `flower_focus` |
| open item (optional, after flowers) | `bud` |
Flowers are placed with their own `attach_px` (stem base) on the bloom point.

## Roots
The kit has 12 root pieces: 4 sockets (`root_1..4`, on `trunk_flare`) x 3 angles (`am12`, `ap0`, `ap12`). So **up to 12 roots are drawn, 3 per socket**.
- Order: overdue first, then by `days_left` ascending. The first 12 get a piece; the rest go to `roots_more` (same row shape, no `kit`).
- Assignment in that order: sockets 2, 3, 1, 4 (inner, then outer, alternating sides), with angle `ap0`, then `am12`, then `ap12` on each pass. So roots 1 to 4 are `ap0`, 5 to 8 are `am12`, 9 to 12 are `ap12`.
- `depth` 0..1 sets the length: the client scales the piece from `attach_px` toward `tip_px` by `0.35 + 0.65 * depth`. Overdue = depth 0 (shortest) plus `overdue: true`.
API: `"kit": {"socket": 2, "angle": "ap0", "scale": 0.81}`.

## Canopy clumps and early-stage art (Design, decided)
Top level adds `canopy_clumps` (int). The higher app stage in each pair gets 2 more clumps:
| app `stage_idx` | art `stage` | `canopy_clumps` |
|---|---|---|
| 0 / 1 | 1 | 3 / 5 |
| 2 / 3 | 2 | 5 / 7 |
| 4 / 5 | 3 | 7 / 8 |
Clumps use `canopy_clump_N` on the tips of the drawn branches first, in slot order. Max 8.

Until the owner locks the oak, art stages 1 and 2 use the stage-3 trunk, canopy and clump pieces scaled to 0.6x (stage 1) and 0.8x (stage 2). This multiplies with `stage_scale`. Top level adds `art_scale` (0.6 / 0.8 / 1.0).

Roots: at most 3 per socket (approved by Design).
