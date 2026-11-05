# Migration note: unique purchase per user and item (for Leader)

**What:** add `UNIQUE (user_id, item_key)` on `userinventory`, so the database itself refuses a second purchase of the same item.

**Status:** file only, not run. The app code (`592a19e` line of work) already locks the buy and treats a duplicate-key error as "already own it, no charge", so it works with or without the index.

**Why it may be missing:** `schema.sql` declares it, but a table created before that line would not have it.

**Steps (after the owner's yes):**
1. Run `migrations/inventory_duplicates_check.sql` (read-only).
2. If `duplicate_pairs = 0` and no unique index on (user_id, item_key) is listed, run `migrations/2026-10-23_inventory_unique.sql`.
3. If duplicates exist, stop: removing rows refunds points, so that needs an owner decision.

**Rollback:** `DROP INDEX uq_inventory_user_item ON userinventory;`

`init_db` adds the index only when `PRODY_ADD_INVENTORY_INDEX=1` (off by default), and skips it if duplicates exist.
