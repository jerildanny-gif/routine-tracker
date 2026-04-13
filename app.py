import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
import sqlite3
from plyer import notification

app = Flask(__name__)
app.secret_key = "secret123"

DB = "tasks.db"

# ---------- DATABASE CONNECTION ----------
def get_db():
    return sqlite3.connect(DB, timeout=10, check_same_thread=False)

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        status TEXT,
        task_time TEXT
    )
    """)

    conn.commit()
    conn.close()

# ---------- LOGIN SYSTEM ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
            conn.commit()
        except:
            return "User already exists"
        conn.close()
        return redirect('/login')

    return render_template("register.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            return redirect('/')
        else:
            return "Invalid login"

    return render_template("login.html")


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ---------- TASK SYSTEM ----------
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE user_id=?", (session['user_id'],))
    tasks = c.fetchall()
    conn.close()

    total = len(tasks)
    done = len([t for t in tasks if t[3] == "Done"])

    return render_template("index.html", tasks=tasks, total=total, done=done)


@app.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect('/login')

    name = request.form['name']
    task_time = request.form['time']

    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO tasks (user_id, name, status, task_time) VALUES (?, ?, ?, ?)",
              (session['user_id'], name, "Not Done", task_time))
    conn.commit()
    conn.close()
    return redirect('/')


@app.route('/toggle/<int:id>')
def toggle(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT status FROM tasks WHERE id=?", (id,))
    result = c.fetchone()

    if not result:
        return redirect('/')

    status = result[0]
    new_status = "Done" if status == "Not Done" else "Not Done"

    c.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, id))
    conn.commit()
    conn.close()
    return redirect('/')


@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/')


# ---------- REMINDER SYSTEM ----------
def reminder_loop():
    while True:
        try:
            conn = get_db()
            c = conn.cursor()

            now = datetime.now()
            current_time = now.strftime("%H:%M")

            c.execute("SELECT name, task_time FROM tasks WHERE status='Not Done'")
            tasks = c.fetchall()

            for task in tasks:
                if task[1] == current_time:
                    notification.notify(
                        title="Routine Tracker 🔔",
                        message=f"Task: {task[0]}",
                        timeout=10
                    )

                    print(f"🔔 Reminder: {task[0]}")

            conn.close()

        except Exception as e:
            print("Reminder error:", e)

        time.sleep(60)


# ---------- MAIN ----------
if __name__ == "__main__":
    init_db()

    t = threading.Thread(target=reminder_loop)
    t.daemon = True
    t.start()

    app.run(debug=False)