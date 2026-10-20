from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db import get_db_connection

tasks_bp = Blueprint('tasks_bp', __name__)

@tasks_bp.route('/tasks', methods=['GET', 'POST'])
def manage_tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if request.method == 'POST':
            task_name = request.form.get('task_name')
            due_date = request.form.get('due_date') or None

            if task_name:
                cursor.execute(
                    "INSERT INTO todolist (user_id, task_name, due_date) VALUES (%s, %s, %s)",
                    (user_id, task_name, due_date)
                )
                conn.commit()
                flash("Task added successfully!", "success")
            return redirect(url_for('tasks_bp.manage_tasks'))

        cursor.execute(
            "SELECT * FROM todolist WHERE user_id = %s ORDER BY is_completed ASC, due_date ASC",
            (user_id,)
        )
        tasks = cursor.fetchall()
        return render_template('tasks.html', tasks=tasks)
    finally:
        cursor.close()
        conn.close()

@tasks_bp.route('/tasks/complete/<int:task_id>', methods=['POST'])
def complete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE todolist SET is_completed = TRUE WHERE task_id = %s AND user_id = %s",
            (task_id, user_id)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('tasks_bp.manage_tasks'))