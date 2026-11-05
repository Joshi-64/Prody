-- NOT RUN. Needs the owner's yes before it touches live MySQL.
-- Pre-check: run migrations/inventory_duplicates_check.sql. Only run this if duplicate_pairs = 0
-- and no unique index on (user_id, item_key) is listed. If duplicates exist, stop and decide with the owner
-- (deleting rows refunds points).
CREATE UNIQUE INDEX uq_inventory_user_item ON userinventory (user_id, item_key);
-- Rollback: DROP INDEX uq_inventory_user_item ON userinventory;
