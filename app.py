from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import date
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key")

DB_NAME = "database.db"

# ---------------- DB CONNECTION ----------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- INIT DB ----------------
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        secret1 TEXT,
        secret2 TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        expense_date TEXT,
        category TEXT,
        amount REAL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS salary(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        amount REAL
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- HOME ----------------
@app.route('/')
def home():
    return render_template("home.html")

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = None

    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        s1 = request.form['secret1'].lower().strip()
        s2 = request.form['secret2'].lower().strip()

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE username=?", (u,))
        if cursor.fetchone():
            msg = "User already exists"
        else:
            hashed_password = generate_password_hash(p)

            cursor.execute("""
                INSERT INTO users (username, password, secret1, secret2)
                VALUES (?, ?, ?, ?)
            """, (u, hashed_password, s1, s2))

            conn.commit()
            conn.close()
            return redirect(url_for('login'))

        conn.close()

    return render_template("register.html", msg=msg)

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username=?", (u,))
        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user["password"], p):
            session['user'] = u
            return redirect(url_for('app_home'))
        else:
            error = "Invalid credentials"

    msg = session.pop('msg', None)
    return render_template("login.html", error=error, msg=msg)

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- FORGOT PASSWORD ----------------
@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    msg = None

    if request.method == 'POST':
        u = request.form['username']
        s1 = request.form['secret1'].lower().strip()
        s2 = request.form['secret2'].lower().strip()
        new_pass = request.form['new_password']

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id FROM users
            WHERE username=? AND secret1=? AND secret2=?
        """, (u, s1, s2))

        user = cursor.fetchone()

        if user:
            hashed_password = generate_password_hash(new_pass)

            cursor.execute("""
                UPDATE users
                SET password=?
                WHERE username=?
            """, (hashed_password, u))

            conn.commit()
            conn.close()

            session['msg'] = "Password updated successfully ✔️"
            return redirect(url_for('login'))
        else:
            msg = "Wrong details ❌"

        conn.close()

    return render_template("forgot.html", msg=msg)

# ---------------- MAIN APP ----------------
@app.route('/app', methods=['GET', 'POST'])
def app_home():

    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    conn = get_db()
    cursor = conn.cursor()

    # ---------------- SALARY ----------------
    if request.method == 'POST' and request.form.get('type') == 'salary':
        salary = request.form.get('salary')

        if salary:
            cursor.execute("DELETE FROM salary WHERE username=?", (user,))
            cursor.execute("""
                INSERT INTO salary (username, amount)
                VALUES (?, ?)
            """, (user, float(salary)))

            conn.commit()

    # ---------------- EXPENSE ----------------
    if request.method == 'POST' and request.form.get('type') == 'expense':
        category = request.form.get('category')
        amount = request.form.get('amount')

        if category and amount:
            amount = float(amount)
            today = date.today().strftime("%Y-%m-%d")

            cursor.execute("""
                SELECT id, amount FROM expenses
                WHERE username=? AND expense_date=? AND category=?
            """, (user, today, category))

            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE expenses
                    SET amount=?
                    WHERE id=?
                """, (existing["amount"] + amount, existing["id"]))
            else:
                cursor.execute("""
                    INSERT INTO expenses (username, expense_date, category, amount)
                    VALUES (?, ?, ?, ?)
                """, (user, today, category, amount))

            conn.commit()

    # ---------------- DATA ----------------
    today = date.today().strftime("%Y-%m-%d")
    month_start = date.today().replace(day=1).strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT * FROM expenses
        WHERE username=? AND expense_date=?
        ORDER BY id DESC
    """, (user, today))
    expenses = cursor.fetchall()

    cursor.execute("""
        SELECT COALESCE(SUM(amount),0)
        FROM expenses
        WHERE username=? AND expense_date BETWEEN ? AND ?
    """, (user, month_start, today))
    total = cursor.fetchone()[0]

    cursor.execute("""
        SELECT amount FROM salary
        WHERE username=?
        ORDER BY id DESC
        LIMIT 1
    """, (user,))
    salary_row = cursor.fetchone()

    salary = salary_row["amount"] if salary_row else 0
    remaining = max(salary - total, 0)

    conn.close()

    return render_template(
        "app.html",
        user=user,
        expenses=expenses,
        total=total,
        salary=salary,
        remaining=remaining
    )

# ---------------- EDIT ----------------
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):

    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        amount = float(request.form['amount'])

        cursor.execute("""
            UPDATE expenses
            SET amount=?
            WHERE id=?
        """, (amount, id))

        conn.commit()
        conn.close()
        return redirect(url_for('app_home'))

    cursor.execute("SELECT * FROM expenses WHERE id=?", (id,))
    expense = cursor.fetchone()

    conn.close()
    return render_template("edit.html", expense=expense)

# ---------------- DELETE ----------------
@app.route('/delete/<int:id>')
def delete(id):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM expenses WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for('app_home'))

# ---------------- VIEW ----------------
@app.route('/view')
def view():

    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    selected_date = request.args.get('date')

    conn = get_db()
    cursor = conn.cursor()

    if selected_date:
        cursor.execute("""
            SELECT * FROM expenses
            WHERE username=? AND expense_date=?
        """, (user, selected_date))
        title = "Daily Expenses"
    else:
        cursor.execute("""
            SELECT * FROM expenses WHERE username=?
        """, (user,))
        title = "All Expenses"

    expenses = cursor.fetchall()
    conn.close()

    return render_template(
        "view.html",
        expenses=expenses,
        title=title,
        user=user,
        selected_date=selected_date
    )

# ---------------- ADD OLD EXPENSE ----------------
@app.route('/add_old', methods=['POST'])
def add_old():

    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']

    expense_date = request.form['expense_date']
    category = request.form['category']
    amount = float(request.form['amount'])

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, amount FROM expenses
        WHERE username=? AND expense_date=? AND category=?
    """, (user, expense_date, category))

    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE expenses
            SET amount=?
            WHERE id=?
        """, (existing["amount"] + amount, existing["id"]))
    else:
        cursor.execute("""
            INSERT INTO expenses (username, expense_date, category, amount)
            VALUES (?, ?, ?, ?)
        """, (user, expense_date, category, amount))

    conn.commit()
    conn.close()

    return redirect(url_for('view', date=expense_date))

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)