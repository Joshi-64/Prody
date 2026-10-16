import mysql.connector
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
import requests
from ics import Calendar
from config_ai import prody_ai_key

#Create the blueprint object for calendar object
calendar_bp = Blueprint('calendar_bp', __name__)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': "Your Password Here",  # Update with your local MySQL password
    'database': 'prody_dev',
}

def get_db():
  return mysql.connector.connect(**db_config)

#define function to view calendar, add events manally, and input events automatically
@calendar_bp.route('/calendar', methods=['GET', 'POST'])
def view_calendar():
    #Check if user in session
    if "user_id" not in session:
        return(redirect(url_for('login')))
    user_id = session.get('user_id')

    #access db and retrieve calendar information
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    calendar_info = []

    #Access database to recieve calendar information by user id
    try:
        cursor.execute("SELECT * FROM CalendarEvents WHERE id = %s", (user_id,))
        calendar_info = cursor.fetchall()
    except:
        flash('Error Showing Calendar', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return render_template('calendar.html', events=calendar_info)
    
#For manual inseretion of calendar events
@calendar_bp.route('/calendar/add_manual', methods=['POST']) 
def add_manual():
    if "user_id" not in session:
        return redirect(url_for('login'))

    #Send request for users to enter events manually
    user_id = session.get('user_id')
    event_name = request.form.get('event_name')
    event_date = request.form.get('event_date')

    #Insert event information into table
    conn = get_db()
    cursor = conn.cursor()
    insert_events = "INSERT INTO CalendarEvents (id, event_name, event_date, is_ai_recommended) VALUES (%s, %s, %s, %s)"
    cursor.execute(insert_events, (user_id, event_name, event_date, False))
    
    conn.commit()   
    cursor.close()
    conn.close()
    return redirect(url_for('calendar_bp.view_calendar'))   

#Add calendar events by linking ics calendar link to expand calendar integration easily
@calendar_bp.route('/calendar/automatic_add', methods=['GET', 'POST'])
def automatic_add():
    if "user_id" not in session:
        return redirect(url_for('login'))

    #Get ics url request from user
    ical_url = request.form.get('calendar_url')
    user_id = session.get('user_id')

    #If link valid, insert each event into the calendar
    if ical_url:
        try:
            response = requests.get(ical_url, timeout =10)
            if response.status_code == 200:
                cal = Calendar(response.text)

                conn = get_db()
                cursor = conn.cursor()

                sql = "INSERT INTO calendarevents (id, event_name, event_date,is_ai_recommended) VALUES (%s, %s, %s, %s) "
                for count, event in enumerate(cal.events):
                    if count >= 50:
                        break
                        
                    event_date = event.begin.format('YYYY-MM-DD HH:mm:ss')
                    title = event.name if event.name else 'Untitled Event'
                    cursor.execute(sql, (user_id, title, event_date, False))
                conn.commit()
                cursor.close()
                conn.close()
                flash('Calendar successfully synced!', 'success')
            else:
                flash('Invalid link. Could not fetch data.', 'danger')
        except Exception as e:
            print(f"Error parsing ical {e}")
            flash('Error parsing calendar file. Make sure it is a valid iCal link', 'danger')
    
    return redirect(url_for('calendar_bp.view_calendar'))
    

#Access database caledar events and prompt ai to reccomend study sessions. Input into calendar events table
@calendar_bp.route('/calendar/ai_reccomended_schedule', methods=["GET", 'POST'])
def ai_recomended_schedule():
    user_id = session.get('user_id')

    #Select calendar events from database
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT event_name, event_date FROM CalendarEvents WHERE id =%s", (user_id,))
    calender_events_all = cursor.fetchall()

    #User optionally input schedule restrictions
    constraints_input = request.form.get('user_constraints', 'N/A')
    
    # Select course deadlines by for that user
    course_deadlines_all =[]
    try:
        cursor.execute("SELECT usercourses.course_name, coursedeadlines.deadline_name, coursedeadlines.deadline_date FROM usercourses INNER JOIN coursedeadlines ON usercourses.course_id = coursedeadlines.course_id WHERE usercourses.id = %s ", (user_id,))
        course_deadlines_all = cursor.fetchall()
    except:
        course_deadlines_all = None
        flash("No Added Course Deadlines", 'danger')
    
    prompt = f"""
    You are an automated backend data parsing engine. You must output raw data rows.
    Student Schedule: {calender_events_all}
    Course Deadlines: {course_deadlines_all}
    User Scheduling Restrictions: {constraints_input}
    
    Generate exactly 3 study blocks based on this data.
    
    CRITICAL STRUCTURE REQUIREMENT: You must output your answer exactly like the example rows below. Do not include introductory text, conversational reasoning paragraphs, or markdown code block backticks (```). Any extra text will break the computer program reading your file.
    
    Output Format Example:
    Study for Math Exam|2026-10-20 15:30:00
    Review Biology Lab|2026-10-21 16:00:00
    
    Provide only the pipe-separated values, one per line:
    """

    #Use open router to provide ai capabilities
    headers = {
        "Authorization": f"Bearer {prody_ai_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openrouter/free", 
        "messages": [{"role": "user", "content": prompt}]
    }
    response = None
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=45)
        print(response.status_code)
        if response.status_code == 200:
            
            api_data = response.json()
            ai_output = api_data['choices'][0]['message']['content'].strip()
            
            conn = get_db()
            cursor = conn.cursor()
            sql = "INSERT INTO calendarevents (id, event_name, event_date, is_ai_recommended, flag_status) VALUES (%s, %s, %s, %s, %s)"

            inserted_count = 0
            lines = ai_output.split('\n')
            for line in lines:
                line = line.strip()
                print(line)
                # Safely parse lines containing the pipe delimiter
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        event_name = parts[0].strip()
                        event_date = parts[1].strip()
                        cursor.execute(sql, (user_id, event_name, event_date, True, 'is_pending'))
                        inserted_count += 1

            if inserted_count > 0:
                conn.commit()
                flash('AI Study Schedule generated successfully!', 'success')
                session['review_mode_active'] = True 
            else:
                flash('AI returned data in an unexpected format. Please try again.', 'danger')
                session['review_mode_active'] = False 

           
                
        else:
            status = response.status_code if response else 'Unknown'
            text = response.text if response else 'No response text'
            print(f"OpenRouter Connection Error Status {status}: {text}")
            flash('AI Service is temporarily unavailable.', 'danger')
            session['review_mode_active'] = False

    except Exception as e:
        print(f"OpenRouter Exception: {e}")
        flash('AI Service encountered an error. Check your config key.', 'danger')
        session['review_mode_active'] = False

    cursor.close()
    conn.close()
            
    return redirect(url_for('calendar_bp.view_calendar'))   


@calendar_bp.route('/ai_accept')
def accept_route():
    current_user = session.get('user_id')
    session.pop('review_mode_active', None)
    #If user accepts events uptate table
    conn = get_db()
    cursor = conn.cursor()
    sql = "UPDATE calendarevents SET flag_status='confirmed' WHERE id =%s AND flag_status = 'is_pending' "
    
    cursor.execute(sql, (current_user,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('AI recommendations successfully saved to your active schedule!', 'success')
    return redirect(url_for('calendar_bp.view_calendar')) 

@calendar_bp.route('/ai_reject')
def reject_route():
    current_user = session.get('user_id')
    #If user accepts events uptate table
    conn = get_db()
    cursor = conn.cursor()
    sql = "DELETE FROM calendarevents WHERE flag_status='is_pending' AND  id =%s  "
        
    cursor.execute(sql, (current_user,))
    conn.commit()
    cursor.close()
    conn.close()
    session.pop('review_mode_active', None)
    flash('AI study schedule pitch discarded.', 'info')
    return redirect(url_for('calendar_bp.view_calendar')) 

@calendar_bp.route('/calendar/delete/<int:record_id>')
def delete_event_endpoint(record_id):
    if "user_id" not in session:
        return redirect(url_for('login'))
    current_user = session.get('user_id')
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # SQL structure to delete exactly ONE specific row item, verifying it belongs to this active user
        sql = "DELETE FROM calendarevents WHERE event_id = %s AND id = %s"
        cursor.execute(sql, (record_id, current_user))
        conn.commit()
        flash('Event successfully removed from your schedule.', 'success')
    except Exception as e:
        print(f"Deletion failed: {e}")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('calendar_bp.view_calendar'))
