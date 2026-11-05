# Tree data migrations (Oct 23 2026)

Closes gaps 1, 2, 3, 5 (as a grades link), 6 (index) and 7 from `docs/api_tree_contract.md`.
Everything runs inside `db.init_db()` on app start. Every step checks before it changes anything, so it is safe to run again. It only adds columns and indexes, and the backfills only fill NULLs.

## Changes
| # | Change | SQLite DDL | MySQL DDL |
|---|---|---|---|
| 1 | completion time | `ALTER TABLE todolist ADD COLUMN completed_at DATETIME NULL` (same for coursedeadlines) | same |
| 2 | semester dates | `ALTER TABLE userprofiles ADD COLUMN semester_start DATE NULL`, `... semester_end DATE NULL` | same |
| 3 | branch slot | `ALTER TABLE usercourses ADD COLUMN branch_slot INT NULL`; `CREATE UNIQUE INDEX IF NOT EXISTS uq_course_branch_slot ON usercourses (id, branch_slot)` | same ALTER; `CREATE UNIQUE INDEX uq_course_branch_slot ON usercourses (id, branch_slot)` (only if it's not in information_schema) |
| 4 | deadline → grade link | `ALTER TABLE coursedeadlines ADD COLUMN grade_id INT NULL` + `ix_deadlines_grade` | same |
| 5 | indexes | `ix_events_user_start` now on `(user_id, event_date)` (it used to point at a missing `start_time` column, so it was never created); new `ix_deadlines_course_done (course_id, is_completed)` | same; MySQL checks information_schema first |
| 6 | schema files synced | `schema.sql` and `schema_sqlite.sql` now contain every `_NEW_COLUMNS` column and every index | MySQL indexes are inline in CREATE TABLE |

Multiple NULLs are allowed in a UNIQUE index on both engines, so overflow classes (`branch_slot` NULL) are fine.
`grade_id` points to `grades.grade_id`. There's no category table: weight lives per grade row in `grades.py`. It has no hard FK, so deleting a grade won't fail. Readers should treat a dangling id as NULL. `deadline_name` is kept.
Semester fallback: `plant.semester_bounds(user_id)` returns the stored dates, or None. On None, use the `plant_state()` guess: start = sign-up (or the first deadline minus 7 days), end = the last deadline, else start + 16 weeks. Nothing calls it yet, so behavior is unchanged.

## Backfill (in `_migrate_tree`)
- `completed_at`: **not backfilled** (Debugger review, Oct 23). There's no real completion time for old rows, so they stay NULL. From now on the routes set it: `tasks.complete_task` and `toggle_deadline` set `datetime.now()` on check and NULL on uncheck. `set_progress` (100) and `/api/deadlines/<id>/done` keep the first time if the item is already done (`COALESCE`) and clear it when undone. The 13 deadline and 2 task values backfilled earlier were reset to NULL in prody_dev.sqlite3. prody_migtest was rebuilt without them.
- `branch_slot`: for each owner (`usercourses.id`), in `course_id` order (same as plant.py), fill the free slots 0–7. A 9th class or later stays NULL. Existing slots are never moved.
- `grade_id`: lowest `grade_id` in the same course whose trimmed, lowercased `item_name` equals `deadline_name`.
- New classes: `user_courses._insert_course` assigns the lowest free slot 0–7 (`next_branch_slot`), or NULL when all 8 are taken. If a concurrent insert takes the same slot, the unique index rejects it and the insert falls back to NULL. Seed scripts (`seed*.py`, `max_user.py`) still insert without a slot; the next `init_db()` fills those in.
- Applied: prody_dev.sqlite3 has 22/22 courses slotted, completed_at all NULL, 0 grade links (no names match).

## Rollback
`scripts/rollback_tree_migrations.py --yes` drops the 3 new indexes and 6 new columns (needs SQLite ≥ 3.35). It is idempotent. Without `--yes` it only prints what it would do. Remove the new `_NEW_COLUMNS` entries and the `_migrate_tree` call from db.py too, or the next start will add them back. The events-index fix is not rolled back. Backup of the pre-migration files: `/tmp/prody_root_backup_20261023_052945/`.

## Windows (PowerShell), from the repo folder
```powershell
# backup
Copy-Item prody_dev.sqlite3 prody_dev.backup.sqlite3
# run migration (SQLite)
$env:PRODY_DB = "sqlite"; python -c "import db; db.init_db(); print(db.LAST_MIGRATION)"
# run migration (MySQL): set PRODY_DB_HOST/USER/PASSWORD/NAME first
$env:PRODY_DB = "mysql"; python -c "import db; db.init_db(); print(db.LAST_MIGRATION)"
# rollback (dry run, then real)
python scripts\rollback_tree_migrations.py
python scripts\rollback_tree_migrations.py --yes
```

## Testing
- SQLite: tested on copies. Ran 3 times, row counts for all tables unchanged, no duplicate slots, integrity and foreign-key checks OK. An empty database also initialises twice cleanly. Rollback ran twice and returned columns and data to match the original.
- MySQL (MariaDB 11.8, 127.0.0.1:3306): prody_migtest was rebuilt from prody_dev. Migrated twice (idempotent), rolled back (dump matches prody_dev except the events-index fix), re-applied. Route tests passed on a prody_routetest copy, same as on SQLite.

## Grade ↔ deadline link (picker, 2026-10-23)
- Link stays on `coursedeadlines.grade_id`. Set only by id from the optional "Which deadline is this for?" picker on /grades; no name matching (migration step 4 no longer backfills).
- One deadline links at most one grade: picker lists only that user's, that class's deadlines with `grade_id IS NULL`; server rejects any other id (other user, other class, already linked) and saves neither grade nor link. Insert + link run in one transaction with a `grade_id IS NULL` guard.
- Deleting a grade clears its link. Old grades stay unlinked.

## Branch slot on class delete
- `delete_course` runs in one transaction; the freed `branch_slot` goes to the user's earliest overflow class (lowest `course_id`, as usercourses has no created_at).
