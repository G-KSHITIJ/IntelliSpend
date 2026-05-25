from flask import Flask, url_for, render_template, request, redirect, flash, session
import psycopg2
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")

#This hardens login sessions a bit.
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print("Database connection failed:", e)

@app.route('/')
def home():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = session.get('user_id')

    cursor.execute("""
        SELECT amount, category, date
        FROM expenses
        WHERE user_id = %s
    """, (user_id,))

    data = cursor.fetchall()

    cursor.execute("""
        SELECT amount
        FROM budget
        WHERE user_id = %s
        LIMIT 1
    """, (user_id,))

    budget_data = cursor.fetchone()
    total_spent = sum([float(row[0]) for row in data])
    budget = float(budget_data[0]) if budget_data else 0
    percent_used = ((total_spent / budget) * 100 if budget > 0 else 0)
    conn.close()
    category_data = {}

    for amount, category, date in data:
        amount = float(amount)
        if category in category_data:
            category_data[category] += amount
        else:
            category_data[category] = amount

    daily_data = {}

    for amount, category, date in data:
        amount = float(amount)
        if date in daily_data:
            daily_data[date] += amount
        else:
            daily_data[date] = amount

    insights = []
    highest_category = "No Data"

    if category_data:

        highest_category = max(category_data, key=category_data.get)

        highest_amount = category_data[highest_category]

        percentage = ((highest_amount / total_spent) * 100 if total_spent > 0 else 0)

        insights.append(f"You spend {percentage:.1f}% on {highest_category} 💸")

    days = datetime.now().day

    avg_daily = (total_spent / days if days > 0 else 0)

    if total_spent > 5000:
        insights.append("⚠️ Your spending is quite high this month!")

    if category_data.get("Food", 0) > 2000:
        insights.append("🍔 You are spending a lot on Food!")

    if category_data.get("Travel", 0) > 1500:
        insights.append("🚕 Travel expenses are high!")

    today = datetime.today()

    current_week = 0
    previous_week = 0

    for amount, category, date in data:

        try:
            exp_date = datetime.strptime(date, "%Y-%m-%d")
        except:
            continue

        diff = (today - exp_date).days

        if 0 <= diff <= 7:
            current_week += float(amount)

        elif 7 < diff <= 14:
            previous_week += float(amount)

    if current_week > previous_week:
        insights.append("📈 Your spending increased this week!")

    elif current_week < previous_week:
        insights.append("📉 Your spending decreased this week!")

    else:
        insights.append("😐 Spending is same as last week")

    return render_template(
        "index.html",
        category_data=category_data,
        daily_data=daily_data,
        total_spent=total_spent,
        budget=budget,
        percent_used=percent_used,
        insights=insights,
        highest_category=highest_category,
        avg_daily=avg_daily,
        username=session.get('username')
    )

@app.route('/add', methods=['POST'])
def add():

    if 'user_id' not in session:
        return redirect('/login')

    try:
        amount = float(request.form.get("amount"))

    except:
        flash("Invalid amount!")
        return redirect('/')

    category = request.form.get("category", "")
    date = request.form.get("date")

    category = category.strip().title()
    category = " ".join(category.split())

    if amount <= 0:
        flash("Amount must be positive!")
        return redirect('/')

    if not category:
        flash("Category cannot be empty!")
        return redirect('/')

    if len(category) > 20:
        flash("Category too long!")
        return redirect('/')

    if not category.replace(" ", "").isalnum():
        flash("Category should only contain letters and numbers")
        return redirect('/')

    user_id = session.get('user_id')
    add_expenses(amount, category, date, user_id)
    flash("Expense added successfully!")
    return redirect('/')

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        username = request.form.get("username").strip()
        email = request.form.get("email").strip()
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not username or not email or not password:
            flash("All fields are required!")
            return redirect('/register')

        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect('/register')

        if len(password) < 6:
            flash("Password must be at least 6 characters")
            return redirect('/register')

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                INSERT INTO users (username, email, password)
                VALUES (%s, %s, %s)
            """, (username, email, hashed_password))

            conn.commit()
            flash("Account created successfully✅!")
            return redirect('/login')

        except psycopg2.IntegrityError:

            conn.rollback()
            flash("Username already exists!")
            return redirect('/register')

        finally:
            conn.close()

    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM users
            WHERE username = %s
        """, (username,))

        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):

            session['user_id'] = user[0]
            session['username'] = user[1]

            return redirect('/')

        else:
            flash("❌ Invalid credentials")

    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = session.get('user_id')

    cursor.execute("""
        SELECT * FROM expenses
        WHERE user_id = %s
    """, (user_id,))

    expenses = cursor.fetchall()
    conn.close()

    return render_template("dashboard.html", expenses=expenses)

@app.route('/set_budget', methods=['POST'])
def set_budget():

    if 'user_id' not in session:
        return redirect('/login')

    amount = request.form.get("budget")
    user_id = session.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM budget
        WHERE user_id = %s
    """, (user_id,))

    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE budget
            SET amount = %s
            WHERE user_id = %s
        """, (amount, user_id))

    else:
        cursor.execute("""
            INSERT INTO budget(amount, user_id)
            VALUES(%s, %s)
        """, (amount, user_id))

    conn.commit()
    conn.close()
    return redirect('/')

def init_db():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses(
            id SERIAL PRIMARY KEY,
            amount REAL,
            category TEXT,
            date TEXT,
            user_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget(
            id SERIAL PRIMARY KEY,
            amount REAL,
            user_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()

def add_expenses(amount, category, date, user_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO expenses (amount, category, date, user_id)
        VALUES(%s, %s, %s, %s)
    """, (amount, category, date, user_id))

    conn.commit()
    conn.close()

@app.route('/delete/<int:id>')
def delete(id):

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = session.get('user_id')

    cursor.execute("""
        DELETE FROM expenses
        WHERE id = %s
        AND user_id = %s
    """, (id, user_id))

    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/summary')
def summary():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now()

    current_month = now.month
    current_year = now.year

    user_id = session.get('user_id')

    cursor.execute("""
        SELECT amount, category, date
        FROM expenses
        WHERE user_id = %s
        AND EXTRACT(MONTH FROM TO_DATE(date, 'YYYY-MM-DD')) = %s
        AND EXTRACT(YEAR FROM TO_DATE(date, 'YYYY-MM-DD')) = %s
    """, (user_id, current_month, current_year))

    data = cursor.fetchall()
    conn.close()
    total = 0

    for row in data:
        amount = float(row[0])
        total += amount
    category_summary = {}

    for row in data:
        amount = float(row[0])
        category = row[1]

        if category in category_summary:
            category_summary[category] += amount

        else:
            category_summary[category] = amount

    highest_category = "No Data"

    if category_summary:
        highest_category = max(category_summary, key=category_summary.get)

    days = now.day
    avg_daily = (total / days if days > 0 else 0)

    return render_template(
        "summary.html",
        total=total,
        category_summary=category_summary,
        highest_category=highest_category,
        avg_daily=avg_daily
    )

init_db()

if __name__ == "__main__":
    app.run(debug=True)