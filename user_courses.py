from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from db import get_db_connection

#Create the blueprint object for user_courses functionality
user_courses_bp = Blueprint('user_courses_bp', __name__)

#Let users add courses manually
@user_courses_bp.route('/add_courses', methods=['GET', 'POST'])
def add_courses():
    if "user_id" not in session:
        return(redirect(url_for('login')))
    user_id = session.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    
    course_name = request.form.get("course_name")

    if course_name:
        #Check to se if course already in database. If so flash message and if not add course to usercourses table
        try:
            cursor.execute("SELECT * FROM usercourses WHERE id = %s AND course_name = %s", (user_id, course_name))
            if not cursor.fetchone():
                sql = "INSERT INTO usercourses (id, course_name) VALUES (%s, %s)"
                cursor.execute(sql, (user_id, course_name))
                conn.commit()
                flash(f'Successfully added course: {course_name}', 'success')
            else:
                flash('You are already tracking this course!', 'warning')
        except Exception:
            flash('Error adding courses', 'danger')
    #Get all user courses 
    user_courses_list = []
    try:
        cursor.execute("SELECT * FROM usercourses WHERE id = %s", (user_id,))
        user_courses_list = cursor.fetchall()
    except Exception:
        user_courses_list = []
    finally:
        cursor.close()
        conn.close()
    return render_template('courses_and_deadlines.html', user_courses=user_courses_list)

#Let users add course deadlines per course. If course not already in database, add to usercourses
@user_courses_bp.route('/add_course_deadlines', methods=['GET', 'POST'])
def add_course_deadlines():
    if "user_id" not in session:
        return(redirect(url_for('login')))
    user_id = session.get('user_id')

    
    course_name = request.form.get("course_name")
    deadline_name = request.form.get("deadline_name")
    deadline_date = request.form.get('deadline_date')

    if course_name and deadline_name and deadline_date:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            #get a users course id related to inputted course
            cursor.execute("SELECT course_id FROM usercourses WHERE id = %s AND course_name = %s", (user_id,course_name))
            course_row = cursor.fetchone()
            
            if course_row:
                course_id = course_row["course_id"]
            else:
                sql_user_courses = "INSERT INTO usercourses (id, course_name) VALUES (%s, %s)"
                cursor.execute(sql_user_courses, (user_id, course_name))
                course_id = cursor.lastrowid
            
            sql = "INSERT INTO coursedeadlines (course_id, deadline_name, deadline_date ) VALUES (%s, %s,%s)"
            cursor.execute(sql, (course_id, deadline_name, deadline_date))
            #insert into calendar
            sql_calendar = "INSERT INTO calendarevents (user_id, event_name, event_date, is_ai_recommended) VALUES (%s, %s, %s, %s) "
            cursor.execute(sql_calendar, (user_id,deadline_name, deadline_date, False ))
            conn.commit()
            flash(f'Deadline tracked successfully for {course_name}!', 'success')
        except Exception:
            flash('Error adding course deadline', 'danger')
        

        finally:
            cursor.close()
            conn.close() 
        
    return redirect(url_for('user_courses_bp.add_courses'))
