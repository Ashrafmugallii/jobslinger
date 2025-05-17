from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mail import Mail, Message
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from flask_bcrypt import Bcrypt
from datetime import date
import sqlite3
from collections import Counter


# --- Flask Setup ---
app = Flask(__name__)
app.secret_key = 'super-secret-key'  # 🔐 Replace with something stronger
bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # or your email provider
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'aam282@njit.edu'        # 🔐 use env var later
app.config['MAIL_PASSWORD'] = 'thng mtyl qyhq hnmo'    # 🔐 use env var later
mail = Mail(app)

# --- User Model ---    
class User(UserMixin):
    def __init__(self, id, email, password):
        self.id = id
        self.email = email
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(id=user[0], email=user[1], password=user[2])
    return None
def send_followup_reminders():
    today = datetime.today().strftime('%Y-%m-%d')
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    c.execute('''
        SELECT users.email, jobs.company, jobs.role, jobs.follow_up_due
        FROM jobs
        JOIN users ON jobs.user_id = users.id
        WHERE jobs.follow_up_due <= ? AND jobs.status != 'Offer' AND jobs.status != 'Rejected'
    ''', (today,))
    
    reminders = c.fetchall()
    conn.close()

    for email, company, role, follow_date in reminders:
        msg = Message(
            subject='🔔 Follow-Up Reminder - JobSlinger',
            sender='your_email@gmail.com',
            recipients=[email],
            body=f"Reminder: You planned to follow up with {company} for the {role} role by {follow_date}."
        )
        mail.send(msg)
# --- Initialize Database ---
def init_db():
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            company TEXT,
            role TEXT,
            location TEXT,
            remote TEXT,
            date_applied TEXT,
            salary TEXT,
            source TEXT,
            job_type TEXT,
            priority TEXT,
            contact TEXT,
            follow_up_due TEXT,
            link TEXT,
            resume TEXT,
            status TEXT,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()


# --- Routes ---

@app.route('/')
@login_required
def index():
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    c.execute('SELECT * FROM jobs WHERE user_id = ?', (current_user.id,))
    jobs = c.fetchall()
    conn.close()
    return render_template('index.html', jobs=jobs)

from datetime import date, timedelta

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        company = request.form['company']
        role = request.form['role']
        location = request.form['location']
        remote = request.form['remote']
        date_applied = request.form['date_applied']
        salary = request.form['salary']
        source = request.form['source']
        job_type = request.form['job_type']
        priority = request.form['priority']
        contact = request.form['contact']
        follow_up_due = request.form['follow_up_due']
        link = request.form['link']
        resume = request.form['resume']
        status = request.form['status']
        notes = request.form['notes']

        conn = sqlite3.connect('jobs.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO jobs (
                user_id, company, role, location, remote, date_applied, salary,
                source, job_type, priority, contact, follow_up_due,
                link, resume, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            current_user.id, company, role, location, remote, date_applied, salary,
            source, job_type, priority, contact, follow_up_due,
            link, resume, status, notes
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    today = date.today().isoformat()
    follow_up_default = (date.today() + timedelta(days=14)).isoformat()
    return render_template('add.html', today=today, follow_up_default=follow_up_default)


@app.route('/edit/<int:job_id>', methods=['GET', 'POST'])
@login_required
def edit(job_id):
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()

    if request.method == 'POST':
        company = request.form['company']
        role = request.form['role']
        link = request.form['link']
        resume = request.form['resume']
        status = request.form['status']
        notes = request.form['notes']

        c.execute('''UPDATE jobs SET company=?, role=?, link=?, resume=?, status=?, notes=?
                     WHERE id=? AND user_id=?''',
                  (company, role, link, resume, status, notes, job_id, current_user.id))
        conn.commit()
        conn.close()
        flash('Job updated.', 'success')
        return redirect(url_for('index'))

    c.execute('SELECT * FROM jobs WHERE id = ? AND user_id = ?', (job_id, current_user.id))
    job = c.fetchone()
    conn.close()

    if job:
        return render_template('edit.html', job=job)
    else:
        flash('Job not found.', 'danger')
        return redirect(url_for('index'))

@app.route('/delete/<int:job_id>')
@login_required
def delete(job_id):
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    c.execute('DELETE FROM jobs WHERE id = ? AND user_id = ?', (job_id, current_user.id))
    conn.commit()
    conn.close()
    flash('Job deleted.', 'info')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        hashed = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = sqlite3.connect('jobs.db')
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (email, password) VALUES (?, ?)', (email, hashed))
            conn.commit()
            flash('Registration successful. You can log in now.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already registered.', 'danger')
        conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('jobs.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = c.fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user[2], password):
            user_obj = User(id=user[0], email=user[1], password=user[2])
            login_user(user_obj)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))
from datetime import datetime, timedelta

@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()

    # --- Total Jobs ---
    c.execute('SELECT COUNT(*) FROM jobs WHERE user_id = ?', (current_user.id,))
    total_jobs = c.fetchone()[0]

    # --- Status Breakdown ---
    c.execute('SELECT status, COUNT(*) FROM jobs WHERE user_id = ? GROUP BY status', (current_user.id,))
    status_data = dict(c.fetchall())

    # --- Job Type Breakdown ---
    c.execute('SELECT job_type, COUNT(*) FROM jobs WHERE user_id = ? GROUP BY job_type', (current_user.id,))
    job_type_data = dict(c.fetchall())

    # --- Priority Breakdown ---
    c.execute('SELECT priority, COUNT(*) FROM jobs WHERE user_id = ? GROUP BY priority', (current_user.id,))
    priority_data = dict(c.fetchall())

    # --- Source Breakdown ---
    c.execute('SELECT source, COUNT(*) FROM jobs WHERE user_id = ? GROUP BY source', (current_user.id,))
    source_data = dict(c.fetchall())

    # --- Follow-Up Tracker Logic ---
    c.execute('SELECT company, role, follow_up_due FROM jobs WHERE user_id = ?', (current_user.id,))
    rows = c.fetchall()

# For the line chart (trend)
    c.execute("SELECT date_applied FROM jobs WHERE user_id = ?", (current_user.id,))
    date_rows = c.fetchall()
    date_counter = Counter(row[0] for row in date_rows)
    trend_data = sorted(date_counter.items(), key=lambda x: x[0])
    trend_dates = [d[0] for d in trend_data]
    trend_counts = [d[1] for d in trend_data]

# then in render_template(...)
    trend_dates=trend_dates,
    trend_counts=trend_counts,


    today = datetime.today()
    next_7_days = today + timedelta(days=7)

    followups = []
    for row in rows:
        try:
            follow_up_due = datetime.strptime(row[2], '%Y-%m-%d')
            if follow_up_due < today:
                urgency = "Overdue"
            elif today <= follow_up_due <= next_7_days:
                urgency = "Upcoming"
            else:
                urgency = "Future"
        except:
            urgency = "N/A"

        followups.append({
            "company": row[0],
            "role": row[1],
            "follow_up_due": row[2],
            "urgency": urgency
        })

    conn.close()

    return render_template(
        'dashboard.html',
        total_jobs=total_jobs,
        status_data=status_data,
        job_type_data=job_type_data,
        priority_data=priority_data,
        source_data=source_data,
        followups=followups,
        trend_dates=trend_dates,     # make sure this exists!
        trend_counts=trend_counts
    )

@app.route('/test-email')
def test_email():
    from datetime import datetime
    today = datetime.today().strftime('%Y-%m-%d')

    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    c.execute('''
        SELECT users.email, jobs.company, jobs.role, jobs.follow_up_due
        FROM jobs
        JOIN users ON jobs.user_id = users.id
        WHERE jobs.follow_up_due <= ? AND jobs.status != 'Offer' AND jobs.status != 'Rejected'
    ''', (today,))
    reminders = c.fetchall()
    conn.close()

    for email, company, role, due in reminders:
        msg = Message(
            subject="🔔 Follow-Up Reminder - JobSlinger",
            sender=app.config['MAIL_USERNAME'],
            recipients=[email],
            body=f"Hey! Just reminding you to follow up on {role} at {company} (due by {due})."
        )
        mail.send(msg)

    return "Reminders sent."

# --- Run App ---
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
