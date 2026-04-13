import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
import sqlite3
import os

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "routinetracker_secret_2024")

DB = "tasks.db"

def get_db():
    return sqlite3.connect(DB, timeout=10, check_same_thread=False)

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        status TEXT,
        task_time TEXT
    )""")
    conn.commit()
    conn.close()

def send_sms(message):
    if not TWILIO_AVAILABLE:
        return
    try:
        sid = os.getenv("TWILIO_SID")
        auth = os.getenv("TWILIO_AUTH")
        from_no = os.getenv("TWILIO_FROM")
        to_no = os.getenv("USER_PHONE")
        if sid and auth and from_no and to_no:
            client = TwilioClient(sid, auth)
            client.messages.create(body=message, from_=from_no, to=to_no)
    except Exception as e:
        print("SMS error:", e)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"].strip()
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
            conn.commit()
            conn.close()
            return redirect("/login")
        except Exception:
            error = "An account with that email already exists."
    return render_template("register.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"].strip()
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
            user = c.fetchone()
            conn.close()
            if user:
                session["user_id"] = user[0]
                session["user_email"] = user[1]
                return redirect("/")
            else:
                error = "Invalid email or password."
        except Exception as e:
            error = "Something went wrong. Please try again."
            print("Login error:", e)
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect("/login")
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM tasks WHERE user_id=? ORDER BY task_time ASC", (session["user_id"],))
        tasks = c.fetchall()
        conn.close()
    except Exception as e:
        print("Index error:", e)
        tasks = []
    total = len(tasks)
    done = sum(1 for t in tasks if t[3] == "Done")
    not_done = total - done
    return render_template("index.html", tasks=tasks, total=total, done=done, not_done=not_done, email=session.get("user_email",""))

@app.route("/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect("/login")
    try:
        name = request.form["name"].strip()
        task_time = request.form["time"]
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO tasks (user_id, name, status, task_time) VALUES (?, ?, ?, ?)",
                  (session["user_id"], name, "Not Done", task_time))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Add error:", e)
    return redirect("/")

@app.route("/toggle/<int:task_id>")
def toggle(task_id):
    if "user_id" not in session:
        return redirect("/login")
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT status FROM tasks WHERE id=? AND user_id=?", (task_id, session["user_id"]))
        row = c.fetchone()
        if row:
            new_status = "Done" if row[0] == "Not Done" else "Not Done"
            c.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, task_id))
            conn.commit()
        conn.close()
    except Exception as e:
        print("Toggle error:", e)
    return redirect("/")

@app.route("/delete/<int:task_id>")
def delete(task_id):
    if "user_id" not in session:
        return redirect("/login")
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, session["user_id"]))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Delete error:", e)
    return redirect("/")

@app.route("/check-reminders")
def check_reminders():
    try:
        conn = get_db()
        c = conn.cursor()
        now = datetime.now().strftime("%H:%M")
        c.execute("SELECT name, task_time FROM tasks WHERE status='Not Done' AND task_time=?", (now,))
        due = c.fetchall()
        conn.close()
        for task in due:
            send_sms(f"Routine Tracker Reminder: '{task[0]}' is due now!")
        return f"Checked at {now}. {len(due)} reminder(s) sent.", 200
    except Exception as e:
        return f"Error: {e}", 500

if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)