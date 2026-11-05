-- NOT RUN. Needs the owner's yes before it touches live MySQL. Additive only, no existing data changes.
CREATE TABLE IF NOT EXISTS plantcare_utc (user_id INT NOT NULL PRIMARY KEY, last_at DATETIME NOT NULL);
-- Then set PRODY_ADD_PLANTCARE_UTC=1 on the app.
-- Rollback: unset the flag, then DROP TABLE plantcare_utc;
