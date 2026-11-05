"""One-off: give classes whose stored colour is NULL/empty the palette colour they already DISPLAY
(helpers.null_colour_map: next unused palette colour per user, in course_id order). Classes with any explicit
colour - including the default #CFDCC6 - are never touched. Dry run by default; pass --apply to write.

    PRODY_DB=sqlite PRODY_SQLITE_PATH=/path/copy.sqlite3 python scripts/migrate_null_class_colours.py [--apply]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import null_colour_map, query  # noqa: E402


def main(apply=False):
    users = [r['id'] for r in (query("SELECT DISTINCT id FROM usercourses WHERE color IS NULL OR color = ''") or [])]
    plan = [(uid, cid, col) for uid in users for cid, col in sorted(null_colour_map(uid).items())]
    for uid, cid, col in plan:
        print(f"{'SET' if apply else 'would set'} user {uid} course {cid} -> {col}")
        if apply:
            query("UPDATE usercourses SET color = %s WHERE course_id = %s AND (color IS NULL OR color = '')", (col, cid), commit=True)
    print(f"{len(plan)} class(es) {'updated' if apply else 'to update (dry run; pass --apply to write)'}")
    return len(plan)


if __name__ == '__main__':
    main(apply='--apply' in sys.argv[1:])
