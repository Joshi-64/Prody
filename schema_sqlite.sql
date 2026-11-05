-- Prody schema SQLite fallback, used when PRODY_DB=sqlite
-- app.py also runs these CREATE TABLE IF NOT EXISTS statements on startup.

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(255) UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) CHECK (role IN ('student','admin')) DEFAULT 'student',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME NULL
);

CREATE TABLE IF NOT EXISTS usercourses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    id INT NOT NULL,
    user_id INT,
    course_name VARCHAR(255) NOT NULL,
    course_code VARCHAR(100) DEFAULT '',
    subject VARCHAR(100) DEFAULT '',
    color VARCHAR(20) DEFAULT '#CFDCC6',
    branch_slot INT NULL,
    verified BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS calendarevents (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT NOT NULL,
    event_name VARCHAR(255) NOT NULL,
    event_date DATETIME NOT NULL,
    duration_minutes INT DEFAULT 60,
    is_ai_recommended BOOLEAN DEFAULT FALSE,
    flag_status VARCHAR(20) NULL,
    source_deadline_id INT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS todolist (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    due_date DATE,
    is_completed BOOLEAN DEFAULT FALSE,
    course_id INT NULL,
    progress INT DEFAULT 0,
    category VARCHAR(20) DEFAULT 'task',
    completed_at DATETIME NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS coursedeadlines (
    deadline_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INT NOT NULL,
    deadline_name VARCHAR(255) NOT NULL,
    deadline_date DATETIME NOT NULL,
    is_completed BOOLEAN DEFAULT FALSE,
    completed_at DATETIME NULL,
    grade_id INT NULL
);

CREATE TABLE IF NOT EXISTS studysessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT NOT NULL,
    course_id INT NULL,
    label VARCHAR(255) DEFAULT 'Focus session',
    minutes INT NOT NULL,
    started_at DATETIME NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS grades (
    grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT NOT NULL,
    course_id INT NOT NULL,
    item_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) DEFAULT 'Assignment',
    score DECIMAL(5,2) NOT NULL,
    weight DECIMAL(5,2) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chatmessages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS userprofiles (
    user_id INT PRIMARY KEY,
    display_name VARCHAR(80) DEFAULT '',
    bio VARCHAR(300) DEFAULT '',
    pronouns VARCHAR(40) DEFAULT '',
    university VARCHAR(120) DEFAULT '',
    major VARCHAR(120) DEFAULT '',
    class_year VARCHAR(10) DEFAULT '',
    avatar_path VARCHAR(255) DEFAULT '',
    pot_key VARCHAR(50) DEFAULT 'pot_basket',
    acc_keys VARCHAR(200) DEFAULT '',
    scene_key VARCHAR(50) DEFAULT '',
    sky_key VARCHAR(50) DEFAULT 'sky_clear_day',
    plant_name VARCHAR(40) DEFAULT 'Prody',
    plant_stage_seen INT DEFAULT 0,
    theme_key VARCHAR(50) DEFAULT 'theme_sky',
    frame_key VARCHAR(50) DEFAULT '',
    name_key VARCHAR(50) DEFAULT '',
    pinned_badges VARCHAR(200) DEFAULT '',
    soil_key VARCHAR(50) DEFAULT '',
    flower_key VARCHAR(50) DEFAULT '',
    leaves_key VARCHAR(50) DEFAULT '',
    decor_keys VARCHAR(200) DEFAULT '',
    species_key VARCHAR(50) DEFAULT 'species_classic',
    show_on_leaderboard BOOLEAN NOT NULL DEFAULT 0,
    semester_start DATE NULL,
    semester_end DATE NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS userinventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT NOT NULL,
    item_key VARCHAR(50) NOT NULL,
    price_paid INT NOT NULL DEFAULT 0,
    purchased_at DATETIME NOT NULL,
    UNIQUE (user_id, item_key),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- v4: growth-stage milestones for each student's Prody plant
CREATE TABLE IF NOT EXISTS plantmilestones (
    milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INT NOT NULL,
    stage VARCHAR(30) NOT NULL,
    hours_at DECIMAL(7,1) DEFAULT 0,
    reached_at DATETIME NOT NULL,
    UNIQUE (user_id, stage),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plantcare (
    user_id INT NOT NULL,
    cared_on DATE NOT NULL,
    PRIMARY KEY (user_id, cared_on),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS journalentries (
    user_id INT NOT NULL,
    entry_date DATE NOT NULL,
    mood VARCHAR(10),
    body TEXT,
    updated_at DATETIME,
    PRIMARY KEY (user_id, entry_date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS friendships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_id INTEGER NOT NULL,
    addressee_id INTEGER NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    accepted_at DATETIME NULL,
    user_lo INTEGER NULL,
    user_hi INTEGER NULL,
    UNIQUE (requester_id, addressee_id),
    FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (addressee_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS friend_request_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes (db.py runs these after adding any missing columns)
CREATE INDEX IF NOT EXISTS ix_sessions_user_started ON studysessions (user_id, started_at);
CREATE INDEX IF NOT EXISTS ix_todo_user_done ON todolist (user_id, is_completed);
CREATE INDEX IF NOT EXISTS ix_events_user_start ON calendarevents (user_id, event_date);
CREATE INDEX IF NOT EXISTS ix_grades_user ON grades (user_id);
CREATE INDEX IF NOT EXISTS ix_inventory_user ON userinventory (user_id);
CREATE INDEX IF NOT EXISTS ix_deadlines_course ON coursedeadlines (course_id);
CREATE INDEX IF NOT EXISTS ix_deadlines_course_done ON coursedeadlines (course_id, is_completed);
CREATE INDEX IF NOT EXISTS ix_deadlines_grade ON coursedeadlines (grade_id);
CREATE INDEX IF NOT EXISTS ix_chat_user ON chatmessages (user_id);
CREATE INDEX IF NOT EXISTS ix_journal_user ON journalentries (user_id);
CREATE INDEX IF NOT EXISTS ix_friend_addressee ON friendships (addressee_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_course_branch_slot ON usercourses (id, branch_slot);
CREATE UNIQUE INDEX IF NOT EXISTS uq_friend_lohi ON friendships (user_lo, user_hi);
CREATE INDEX IF NOT EXISTS ix_frlog_user_time ON friend_request_log (user_id, created_at);

-- study rooms (Coder): Jitsi + shared whiteboard strokes
CREATE TABLE IF NOT EXISTS studyrooms (
    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INT NOT NULL,
    title VARCHAR(120) NOT NULL,
    course_id INT NULL,
    jitsi_name VARCHAR(80) NOT NULL,
    join_token VARCHAR(64) NOT NULL,
    friends_can_join BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS studyroom_members (
    room_id INT NOT NULL,
    user_id INT NOT NULL,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (room_id, user_id)
);
CREATE TABLE IF NOT EXISTS studyroom_strokes (
    stroke_id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INT NOT NULL,
    user_id INT NOT NULL,
    data TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_strokes_room ON studyroom_strokes (room_id, stroke_id);

-- fn-features: DMs + discussion boards
CREATE TABLE IF NOT EXISTS dm_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_dm_pair_time ON dm_messages (sender_id, recipient_id, id);
CREATE INDEX IF NOT EXISTS ix_dm_inbox ON dm_messages (recipient_id, id);
CREATE INDEX IF NOT EXISTS ix_dm_sender ON dm_messages (sender_id, id);

CREATE TABLE IF NOT EXISTS forum_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope VARCHAR(20) NOT NULL,
    course_id INTEGER NULL,
    university VARCHAR(120) DEFAULT '',
    author_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    pinned BOOLEAN NOT NULL DEFAULT 0,
    hidden BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_forum_scope ON forum_threads (scope, created_at);
CREATE INDEX IF NOT EXISTS ix_forum_course ON forum_threads (course_id, created_at);

CREATE TABLE IF NOT EXISTS forum_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES forum_threads(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_forum_replies_thread ON forum_replies (thread_id, id);

-- Per-course concept checklist (acad-r1)
CREATE TABLE IF NOT EXISTS courseconcepts (
    concept_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Review' CHECK (status IN ('Mastered','Review')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES usercourses(course_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_concepts_course ON courseconcepts (course_id);


