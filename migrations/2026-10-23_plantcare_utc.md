# Migration note: plantcare_utc (for Leader)

**What:** a small new table, `plantcare_utc (user_id PK, last_at DATETIME)`, holding the UTC time of each user's last watering. `plantcare.cared_on` is a DATE only, so it can't hold the time.

**Why:** with it, a finished focus session waters the plant only when the user's local date is later than the last watering's **and** at least 20 real hours have passed, so changing the client's timezone offset can't give a second watering.

**Status:** file only, not run. The app uses it only when `PRODY_ADD_PLANTCARE_UTC=1` (off by default). With the flag off, the app ignores the client's offset and waters at most once per America/New_York day, worked out on the server, and nothing new is created in the database.

**Steps (after the owner's yes):** run `migrations/2026-10-23_plantcare_utc.sql`, then set `PRODY_ADD_PLANTCARE_UTC=1`.

**Rollback:** unset the flag, then `DROP TABLE plantcare_utc;`
