"""One-off: tag legacy deadline-mirror calendar rows (created before calendarevents.source_deadline_id existed)
with their deadline's id. Idempotent: only deadlines with no tagged row are considered, and a deadline is tagged
only when exactly ONE untagged 30-min row shares its user, name and date AND no other untagged deadline shares
that key. Ambiguous cases are skipped and reported. Dry run by default (or --dry-run); pass --apply to write.
Never runs at boot. Running it on a real DB needs the owner's yes.

    PRODY_DB=sqlite PRODY_SQLITE_PATH=/tmp/copy.sqlite3 python scripts/backfill_source_deadline_id.py [--dry-run|--apply]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import query  # noqa: E402


def main(apply=False):
    deadlines = query('SELECT d.deadline_id, c.id AS user_id, d.deadline_name, d.deadline_date FROM coursedeadlines d '
                      'JOIN usercourses c ON c.course_id = d.course_id WHERE NOT EXISTS (SELECT 1 FROM calendarevents e '
                      'WHERE e.source_deadline_id = d.deadline_id) ORDER BY d.deadline_id') or []
    keys = {}
    for d in deadlines:
        keys.setdefault((d['user_id'], d['deadline_name'], str(d['deadline_date'])), []).append(d)
    tagged = ambiguous = unmatched = 0
    for (uid, name, _), ds in keys.items():
        if len(ds) != 1:
            ambiguous += len(ds); print(f"skip (ambiguous: {len(ds)} deadlines) user {uid} '{name}'"); continue
        d = ds[0]
        rows = query('SELECT event_id FROM calendarevents WHERE user_id = %s AND source_deadline_id IS NULL '
                     'AND event_name = %s AND event_date = %s AND duration_minutes = 30',
                     (uid, name, d['deadline_date'])) or []
        if len(rows) != 1:
            if rows:
                ambiguous += 1; print(f"skip (ambiguous: {len(rows)} rows) deadline {d['deadline_id']}")
            else:
                unmatched += 1
            continue
        print(f"{'TAG' if apply else 'would tag'} event {rows[0]['event_id']} -> deadline {d['deadline_id']}")
        if apply:
            query('UPDATE calendarevents SET source_deadline_id = %s WHERE event_id = %s AND source_deadline_id IS NULL',
                  (d['deadline_id'], rows[0]['event_id']), commit=True)
        tagged += 1
    print(f"{tagged} row(s) {'tagged' if apply else 'to tag (dry run; pass --apply to write)'}, "
          f"{ambiguous} ambiguous skipped, {unmatched} with no mirror row")
    return tagged, ambiguous, unmatched


if __name__ == '__main__':
    main(apply='--apply' in sys.argv[1:] and '--dry-run' not in sys.argv[1:])
