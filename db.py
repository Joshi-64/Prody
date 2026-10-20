import mysql.connector

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'YOUR_PASSWORD_HERE', #Enter your MYSQL Password
    'database': 'prody_dev',
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def _columns(cursor, table_name):
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    return {row[0] for row in cursor.fetchall()}


def _align_existing_columns(cursor):
    """Add columns that CREATE TABLE IF NOT EXISTS cannot add to an existing table."""
    course_columns = _columns(cursor, "usercourses")
    if "id" not in course_columns:
        cursor.execute("ALTER TABLE usercourses ADD COLUMN id INT NULL")
        if "user_id" in course_columns:
            cursor.execute("UPDATE usercourses SET id = user_id WHERE id IS NULL")
        cursor.execute("ALTER TABLE usercourses MODIFY COLUMN id INT NOT NULL")
        cursor.execute(
            """
            ALTER TABLE usercourses
            ADD CONSTRAINT fk_usercourses_id
            FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE
            """
        )
    cursor.execute("ALTER TABLE usercourses MODIFY COLUMN user_id INT NULL")

    if "flag_status" not in _columns(cursor, "calendarevents"):
        cursor.execute(
            "ALTER TABLE calendarevents ADD COLUMN flag_status VARCHAR(20) NULL"
        )


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'student'
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS usercourses (
                course_id INT AUTO_INCREMENT PRIMARY KEY,
                id INT NOT NULL,
                user_id INT,
                course_name VARCHAR(255) NOT NULL,
                course_code VARCHAR(100) DEFAULT '',
                FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS calendarevents (
                event_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                event_name VARCHAR(255) NOT NULL,
                event_date DATETIME NOT NULL,
                is_ai_recommended BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS todolist (
                task_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                task_name VARCHAR(255) NOT NULL,
                due_date DATE,
                is_completed BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS coursedeadlines (
                deadline_id INT AUTO_INCREMENT PRIMARY KEY,
                course_id INT NOT NULL,
                deadline_name VARCHAR(255) NOT NULL,
                deadline_date DATETIME NOT NULL
            )
            """
        )
        _align_existing_columns(cursor)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
