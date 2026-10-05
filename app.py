import mysql.connector
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
# Session secret key
app.secret_key = 'prody_dev_secret_key_2026'

# Local MySQL connection config
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your_local_mysql_password',  # Update with your local MySQL password
    'database': 'prody_dev',
}


def get_db():
  return mysql.connector.connect(**db_config)


@app.route('/')
def index():
  if 'user_id' in session:
    return redirect(url_for('dashboard'))
  return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
  if request.method == 'POST':
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'student')

    if not username or not email or not password:
      flash('Please fill out all required fields.', 'warning')
      return render_template('register.html')

    # Hash the password before storing
    hashed_pw = generate_password_hash(password)

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
      sql = (
          'INSERT INTO users (username, email, password_hash, role) VALUES'
          ' (%s, %s, %s, %s)'
      )
      cursor.execute(sql, (username, email, hashed_pw, role))
      conn.commit()
      flash('Account created successfully. Please log in.', 'success')
      return redirect(url_for('login'))
    except mysql.connector.IntegrityError:
      flash('That username or email is already taken.', 'danger')
    finally:
      cursor.close()
      conn.close()

  return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
  if request.method == 'POST':
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    # Verify user exists and password hash matches
    if user and check_password_hash(user['password_hash'], password):
      session['user_id'] = user['id']
      session['username'] = user['username']
      session['role'] = user['role']
      return redirect(url_for('dashboard'))
    else:
      flash('Invalid username or password.', 'danger')

  return render_template('login.html')


@app.route('/dashboard')
def dashboard():
  # Check if user is logged in
  if 'user_id' not in session:
    flash('You need to log in first.', 'warning')
    return redirect(url_for('login'))

  return render_template(
      'dashboard.html', username=session['username'], role=session['role']
  )


@app.route('/admin')
def admin():
  # Restrict route to admin role only
  if 'user_id' not in session:
    return redirect(url_for('login'))

  if session.get('role') != 'admin':
    flash('Access restricted to administrators.', 'danger')
    return redirect(url_for('dashboard'))

  conn = get_db()
  cursor = conn.cursor(dictionary=True)
  cursor.execute(
      'SELECT id, username, email, role, created_at FROM users ORDER BY'
      ' created_at DESC'
  )
  users = cursor.fetchall()
  cursor.close()
  conn.close()

  return render_template('admin.html', users=users)


@app.route('/logout')
def logout():
  session.clear()
  flash('You have been logged out.', 'info')
  return redirect(url_for('login'))


if __name__ == '__main__':
  app.run(debug=True, port=5000)