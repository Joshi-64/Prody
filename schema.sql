-- Prody schema (MySQL 8). Run once:  mysql -u root -p < schema.sql
-- app.py also runs these CREATE TABLE IF NOT EXISTS statements on startup.
CREATE DATABASE IF NOT EXISTS prody_dev;
USE prody_dev;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student','admin') DEFAULT 'student',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME NULL
);

CREATE TABLE IF NOT EXISTS usercourses (
    course_id INT AUTO_INCREMENT PRIMARY KEY,
    id INT NOT NULL,
    user_id INT,
    course_name VARCHAR(255) NOT NULL,
    course_code VARCHAR(100) DEFAULT '',
    subject VARCHAR(100) DEFAULT '',
    color VARCHAR(20) DEFAULT '#CFDCC6',
    branch_slot INT NULL,
    verified BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uq_course_branch_slot (id, branch_slot)
);

CREATE TABLE IF NOT EXISTS calendarevents (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    event_name VARCHAR(255) NOT NULL,
    event_date DATETIME NOT NULL,
    duration_minutes INT DEFAULT 60,
    is_ai_recommended BOOLEAN DEFAULT FALSE,
    flag_status VARCHAR(20) NULL,
    source_deadline_id INT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_events_user_start (user_id, event_date)
);

CREATE TABLE IF NOT EXISTS todolist (
    task_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    due_date DATE,
    is_completed BOOLEAN DEFAULT FALSE,
    course_id INT NULL,
    progress INT DEFAULT 0,
    category VARCHAR(20) DEFAULT 'task',
    completed_at DATETIME NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_todo_user_done (user_id, is_completed)
);

CREATE TABLE IF NOT EXISTS coursedeadlines (
    deadline_id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL,
    deadline_name VARCHAR(255) NOT NULL,
    deadline_date DATETIME NOT NULL,
    is_completed BOOLEAN DEFAULT FALSE,
    completed_at DATETIME NULL,
    grade_id INT NULL,
    INDEX ix_deadlines_course (course_id),
    INDEX ix_deadlines_course_done (course_id, is_completed),
    INDEX ix_deadlines_grade (grade_id)
);

CREATE TABLE IF NOT EXISTS studysessions (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    course_id INT NULL,
    label VARCHAR(255) DEFAULT 'Focus session',
    minutes INT NOT NULL,
    started_at DATETIME NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_sessions_user_started (user_id, started_at)
);

CREATE TABLE IF NOT EXISTS grades (
    grade_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    course_id INT NOT NULL,
    item_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) DEFAULT 'Assignment',
    score DECIMAL(5,2) NOT NULL,
    weight DECIMAL(5,2) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_grades_user (user_id)
);

CREATE TABLE IF NOT EXISTS chatmessages (
    message_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_chat_user (user_id)
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
    inventory_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    item_key VARCHAR(50) NOT NULL,
    price_paid INT NOT NULL DEFAULT 0,
    purchased_at DATETIME NOT NULL,
    UNIQUE (user_id, item_key),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_inventory_user (user_id)
);

-- v4: growth-stage milestones for each student's Prody plant
CREATE TABLE IF NOT EXISTS plantmilestones (
    milestone_id INT AUTO_INCREMENT PRIMARY KEY,
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
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_journal_user (user_id)
);

CREATE TABLE IF NOT EXISTS friendships (
    id INT AUTO_INCREMENT PRIMARY KEY,
    requester_id INT NOT NULL,
    addressee_id INT NOT NULL,
    status ENUM('pending','accepted') NOT NULL DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    accepted_at DATETIME NULL,
    user_lo INT NULL,
    user_hi INT NULL,
    UNIQUE KEY uq_friend_pair (requester_id, addressee_id),
    UNIQUE KEY uq_friend_lohi (user_lo, user_hi),
    FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (addressee_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_friend_addressee (addressee_id, status)
);

CREATE TABLE IF NOT EXISTS friend_request_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    created_at DATETIME NOT NULL,
    INDEX ix_frlog_user_time (user_id, created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- study rooms (Coder): Jitsi + shared whiteboard strokes
CREATE TABLE IF NOT EXISTS studyrooms (
    room_id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,
    title VARCHAR(120) NOT NULL,
    course_id INT NULL,
    jitsi_name VARCHAR(80) NOT NULL,
    join_token VARCHAR(64) NOT NULL,
    friends_can_join TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS studyroom_members (
    room_id INT NOT NULL,
    user_id INT NOT NULL,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (room_id, user_id)
);
CREATE TABLE IF NOT EXISTS studyroom_strokes (
    stroke_id INT AUTO_INCREMENT PRIMARY KEY,
    room_id INT NOT NULL,
    user_id INT NOT NULL,
    data MEDIUMTEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_strokes_room (room_id, stroke_id)
);

-- fn-features: DMs + discussion boards
CREATE TABLE IF NOT EXISTS dm_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT NOT NULL,
    recipient_id INT NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_dm_pair_time (sender_id, recipient_id, id),
    INDEX ix_dm_inbox (recipient_id, id),
    INDEX ix_dm_sender (sender_id, id)
);

CREATE TABLE IF NOT EXISTS forum_threads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    scope VARCHAR(20) NOT NULL,
    course_id INT NULL,
    university VARCHAR(120) DEFAULT '',
    author_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    pinned BOOLEAN NOT NULL DEFAULT 0,
    hidden BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_forum_scope (scope, created_at),
    INDEX ix_forum_course (course_id, created_at)
);

CREATE TABLE IF NOT EXISTS forum_replies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    thread_id INT NOT NULL,
    author_id INT NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES forum_threads(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_forum_replies_thread (thread_id, id)
);

-- Per-course concept checklist (acad-r1)
CREATE TABLE IF NOT EXISTS courseconcepts (
    concept_id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    status ENUM('Mastered','Review') NOT NULL DEFAULT 'Review',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES usercourses(course_id) ON DELETE CASCADE,
    INDEX ix_concepts_course (course_id)
);


