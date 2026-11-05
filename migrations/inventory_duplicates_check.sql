-- READ-ONLY. Counts duplicate purchases (same user, same item) in userinventory. Safe on live MySQL.
SELECT COUNT(*) AS duplicate_pairs, COALESCE(SUM(n - 1), 0) AS extra_rows, COALESCE(SUM(extra_paid), 0) AS extra_points_charged
FROM (SELECT user_id, item_key, COUNT(*) AS n, SUM(price_paid) - MIN(price_paid) AS extra_paid
      FROM userinventory GROUP BY user_id, item_key HAVING COUNT(*) > 1) d;
-- Is a unique index on (user_id, item_key) already there?
SELECT index_name, GROUP_CONCAT(column_name ORDER BY seq_in_index) AS cols
FROM information_schema.statistics
WHERE table_schema = DATABASE() AND table_name = 'userinventory' AND non_unique = 0
GROUP BY index_name;
