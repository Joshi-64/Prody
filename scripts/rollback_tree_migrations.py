"""Roll back the tree migrations (docs/migrations_plan.md). Uses the same backend as the app:
PRODY_DB=sqlite (+ PRODY_SQLITE_PATH) or MySQL via PRODY_DB_* env vars. Idempotent.
Also remove the new entries from db.py/_NEW_COLUMNS first, or init_db() will re-add them on next start.
Usage: python scripts/rollback_tree_migrations.py [--yes]"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402

INDEXES = [('uq_course_branch_slot', 'usercourses'), ('ix_deadlines_grade', 'coursedeadlines'),
           ('ix_deadlines_course_done', 'coursedeadlines')]
COLUMNS = [('todolist', 'completed_at'), ('coursedeadlines', 'completed_at'), ('coursedeadlines', 'grade_id'),
           ('userprofiles', 'semester_start'), ('userprofiles', 'semester_end'), ('usercourses', 'branch_slot')]


def main():
    if '--yes' not in sys.argv:
        print(f'Would drop {INDEXES} and {COLUMNS} on backend={db.DB_BACKEND}. Re-run with --yes.')
        return
    conn = db.get_db_connection()
    cur = conn.cursor()
    try:
        for name, table in INDEXES:
            if db._index_exists(cur, table, name):
                cur.execute(f'DROP INDEX {name}' if db.DB_BACKEND == 'sqlite' else f'DROP INDEX {name} ON {table}')
                print('dropped index', name)
        for table, col in COLUMNS:
            if col in db._columns(cur, table):
                cur.execute(f'ALTER TABLE {table} DROP COLUMN {col}')  # SQLite >= 3.35
                print('dropped column', table, col)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
