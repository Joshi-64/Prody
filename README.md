# Prody — Student Productivity Platform

Prody is an all-in-one study hub for students, built at Georgia State (Software Engineering, Fall 2026) with **Python Flask** and **MySQL 8**.

## Features

| Area | What it does |
| --- | --- |
| Accounts (UC1) | Register (email format, 8+ char password, duplicate checks), log in with username **or** email, log out. Passwords hashed with Werkzeug scrypt. Flask sessions. |
| RBAC | `users.role` is `student` or `admin`. `/admin` redirects students to the dashboard with an alert. Self sign-up is always `student`; admins promote users in the Admin Console. |
| Dashboard | Today's agenda, upcoming deadlines, task progress ring, 7-day study chart, streak and points. |
| My Classes (UC2) | Add courses with a subject from a predefined list. Add deadlines (past dates rejected). Mark deadlines done or delete them. Deadlines are mirrored to the calendar. |
| My Calendar (UC3/4) | FullCalendar month, week, and list views. Click a day to add an event, click an event to delete it. Import `.ics` / `webcal://` links (duplicates skipped). **AI-suggested study blocks** appear in purple as *pending* until you keep or reject them, individually or all at once. |
| To-Do & Concepts (UC6) | Tasks with class and due date. Concept tracker with 0–100 % mastery sliders and progress bars. |
| Study Session | Pomodoro timer (25/50 focus, 5/15 break). Finished focus blocks are logged to `studysessions`. Manual logging is also available. |
| Time Studied | Chart.js analytics: daily minutes, minutes per class, time of day, and averages over 7, 14, or 30 days. |
| Achievements | Points, levels, study streaks, badges, and a student leaderboard. |
| Grades | Weighted average per class, letter grades, and an overall average. Scores must be 0–100 (“invalid input, please put in a percentage.”). |
| Study Buddy | AI tutor chat that knows your classes and tasks. History is saved and can be cleared. Without an AI key it shows “Study Buddy AI is unavailable right now. Please try again later.” |
| Profiles | Public profile at `/u/<username>`, plus an edit page with: avatar upload (PNG/JPG/GIF/WebP, 2 MB max, checked by file signature, saved to `static/uploads/avatars/`, initials used if there's no photo), display name, bio, pronouns, university, major, class year, up to 3 pinned badges, and a stats card. |
| Store | Points earned from studying buy profile decorations: banners (some animated), avatar frames and name effects. Items come in Common, Rare, Epic and Legendary tiers. You can preview an item before buying, and each item shows whether you own it or have it equipped. Balance = points earned minus points spent. |
| Admin Console | Platform stats, change roles, delete users. |
| Zen & Whiteboard | Zen focus room (timer + plant) and a simple whiteboard. |

## Setup (MySQL — default)

```bash
pip install -r requirements.txt
mysql -u root -p < schema.sql        # creates prody_dev and all tables (optional: app.py also creates missing tables)
```

Set your MySQL credentials in `DB_CONFIG` in `db.py`, or use the environment variables `PRODY_DB_HOST`, `PRODY_DB_USER`, `PRODY_DB_PASSWORD`, and `PRODY_DB_NAME`.

```bash
python app.py
```

Open http://127.0.0.1:5000. On startup, `init_db()` creates any missing tables and adds new columns to existing Sprint 3 tables, so you don't have to drop anything.

### Demo data

```bash
python seed_demo.py
```

This creates (or resets) the following accounts:
- Student: `demo_student` / `Student123!` (classes, deadlines, events, tasks, 30 days of study sessions, grades)
- Admin: `demo_admin` / `Admin123!`

### Quick local mode (no MySQL)

```bash
PRODY_DB=sqlite python seed_demo.py
PRODY_DB=sqlite python app.py
```

This uses `prody_dev.sqlite3` (gitignored) and `schema_sqlite.sql`. MySQL stays the default and is the supported target.

## AI configuration (optional)

AI features use any OpenAI-compatible API:

```bash
export PRODY_AI_KEY=sk-...                      # or OPENAI_API_KEY
export PRODY_AI_BASE_URL=https://api.openai.com/v1   # or https://openrouter.ai/api/v1
export PRODY_AI_MODEL=gpt-4o-mini
```

The Sprint 3 `config_ai.py` file with `prody_ai_key` (OpenRouter) still works. Without a key:
- **Plan my study time** uses the built-in planner. It places 90-minute blocks in free evening slots before your next deadlines.
- **Study Buddy** shows the “AI unavailable” message.

## Project layout

```
app.py              auth, dashboard, admin, error pages
db.py               MySQL connection (+ SQLite fallback adapter), init_db / migrations
helpers.py          login_required/admin_required, query helper, AI client, points/streak/badges
calendar_routes.py  calendar, .ics import, AI study plan keep/reject
user_courses.py     My Classes + deadlines
tasks.py            To-Do & concept tracker
study.py            focus timer, analytics, achievements
grades.py           grade tracker
profiles.py         profiles, avatar upload, decorations catalog, Store
buddy.py            Study Buddy chat
schema.sql          MySQL 8 schema   (schema_sqlite.sql for local mode)
templates/, static/ UI (design system in static/css/app.css, light/dark theme)
```

## Database tables

`users`, `usercourses`, `coursedeadlines`, `calendarevents` (`is_ai_recommended`, `flag_status` = `is_pending`/`confirmed`, `duration_minutes`), `todolist` (`category`, `progress`, `course_id`), `studysessions`, `grades`, `chatmessages`, `userprofiles` (profile fields + equipped `theme_key`/`frame_key`/`name_key`, `pinned_badges`), `userinventory` (owned items, `price_paid`).

## Design (v4: Prody the plant)

Prody, the study buddy, is also each student's plant. Plant logic and the SVG renderer are in `plant.py`. Styles are in `static/css/app.css`.
- **Growth:** `growth = 0.58 * min(hours/45, 1)^0.85 + 0.42 * course_progress`.
  - Course progress is half the share of the semester that has passed, plus half the share of deadlines and to-dos/concepts completed.
  - Hours alone top out around Bloom, so Flourishing also needs semester progress.
  - Stages: Seed, Sprout, Sapling, Leafy, Bloom (flowers) and Flourishing (flowers and fruit). Each stage is stored once in `plantmilestones` when first reached.
- **Mood:** studied in the last day = happy. After that the plant fades for about 5 idle days (wilted, faded colour, sad face, water drop). It never dies, and any focus session revives it.
- **Rendering:**
  - Deterministic per user: stem, branches (one per class, up to 6, with length weighted by that class's study time), two-tone leaves, flowers and fruit.
  - The face is on the pot. The plant sways gently, blinks, and plays a growth animation after a focus session (`/study/log` returns the new SVG).
  - All motion respects `prefers-reduced-motion`.
- **Store:** pots, accessories (up to 3 at once) and scenes render on the plant. Profile banners, frames and name styles are still sold and were recoloured to the new palette.
- **Palette:** off-white `#F7F4EE`, deep green `#2F5D46` (primary), sage `#A9BFA2`, terracotta `#B4593A` (pots and buy buttons), sand `#E9DFCB`, ink `#1F2420`.
  - Every text/background pair checked is at least 4.5:1 (WCAG AA). Placeholder text is lighter by design.
  - Dark mode is a warm forest green-black (`#121915`).
- **Type:** Instrument Serif for headings, Inter for body text.
