# Prody - Student Productivity Platform

Prody is a Flask and MySQL app for student scheduling. Sprint 3 adds shared database access, automatic table setup, course deadlines, calendar sync, AI study planning, and a to-do tracker.

## Prerequisites

- Python 3.x
- MySQL Server, with a database named `prody_dev`

## Database setup

Create the database once:

```sql
CREATE DATABASE IF NOT EXISTS prody_dev;
```

Set the local MySQL host, user, password, and database in `DB_CONFIG` inside `db.py`. That file is the only place credentials are stored.

On startup, `init_db()` runs from `app.py` and creates any missing tables:

- `users`
- `usercourses`
- `coursedeadlines`
- `calendarevents`
- `todolist`

Existing tables are left in place.

## Run the app

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000.

For AI study planning, create `config_ai.py` in the project folder and set `prody_ai_key` to the OpenRouter API key. That file is gitignored. Without it, the calendar still loads and the AI action reports that the service is unavailable.

## Implemented use cases

### Use Case 1: User Management / Authentication

Registration, login, and logout use Flask sessions and Werkzeug password hashes stored in the MySQL `users` table. Administrators can open `/admin` to list accounts.

### Use Case 2: Course and Deadline Management

Students add courses in `usercourses` and deadlines in `coursedeadlines`. Saving a deadline also adds it to `calendarevents`.

### Use Cases 3 and 4: Calendar Integration and AI Study Planning

`calendarevents` stores manual events, imported iCal events, and AI-suggested study blocks. Suggested blocks stay pending until the student keeps or discards them.

### Use Case 6: To-Do List and Concept Tracker

`todolist` supports adding a task, listing tasks for the signed-in user, and marking a task complete.
