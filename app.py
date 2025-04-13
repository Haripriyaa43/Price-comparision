from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import re
import requests
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(days=30)

# SQLite Database Setup
def get_db():
    db = sqlite3.connect('app.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with get_db() as db:
        # Create tables if they don't exist
        db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        db.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            rating REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Insert sample products if table is empty
        if db.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
            sample_products = [
                ('iPhone 13', 'Electronics', 59990.00, 4.5),
                ('Samsung Galaxy S22', 'Electronics', 54999.00, 4.3),
                ('Nike Air Max', 'Footwear', 8999.00, 4.7),
                ('Adidas T-Shirt', 'Clothing', 1999.00, 4.2),
                ('MacBook Pro', 'Electronics', 129990.00, 4.8),
                ("Levi's Jeans", 'Clothing', 3999.00, 4.1),
                ('Sony Headphones', 'Electronics', 14990.00, 4.4),
                ('Puma Running Shoes', 'Footwear', 5999.00, 4.0)
            ]
            db.executemany('INSERT INTO products (name, category, price, rating) VALUES (?, ?, ?, ?)', sample_products)
        db.commit()

# Initialize database
init_db()

# reCAPTCHA Configuration (test keys)
RECAPTCHA_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
RECAPTCHA_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"

# Helper Functions
def is_gmail(email):
    return re.match(r'^[a-zA-Z0-9._%+-]+@gmail\.com$', email)

def is_valid_phone(phone):
    return phone and len(phone) == 10 and phone.isdigit()

def verify_recaptcha(response_token):
    if app.debug:  # Skip verification in development
        return True
    data = {
        'secret': RECAPTCHA_SECRET_KEY,
        'response': response_token
    }
    response = requests.post(RECAPTCHA_VERIFY_URL, data=data)
    return response.json().get('success', False)

def user_exists(email, phone):
    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE email = ? AND phone = ?",
            (email, phone)
        ).fetchone()
        return user is not None

def get_products(filters=None):
    with get_db() as db:
        base_query = "SELECT * FROM products"
        params = []
        
        if filters:
            conditions = []
            if filters.get('category'):
                conditions.append("category = ?")
                params.append(filters['category'])
            if filters.get('min_price'):
                conditions.append("price >= ?")
                params.append(float(filters['min_price']))
            if filters.get('max_price'):
                conditions.append("price <= ?")
                params.append(float(filters['max_price']))
            if filters.get('search'):
                conditions.append("name LIKE ?")
                params.append(f"%{filters['search']}%")
            
            if conditions:
                base_query += " WHERE " + " AND ".join(conditions)
        
        if filters and filters.get('sort'):
            if filters['sort'] == 'price_asc':
                base_query += " ORDER BY price ASC"
            elif filters['sort'] == 'price_desc':
                base_query += " ORDER BY price DESC"
            elif filters['sort'] == 'rating':
                base_query += " ORDER BY rating DESC"
        
        products = db.execute(base_query, params).fetchall()
        return products

def get_categories():
    with get_db() as db:
        categories = db.execute("SELECT DISTINCT category FROM products").fetchall()
        return [row['category'] for row in categories]

# Routes
@app.route('/')
def home():
    if 'email' in session and 'phone' in session:
        if user_exists(session['email'], session['phone']):
            return redirect('/index')
    return redirect('/sign-up')

@app.route('/sign-up', methods=['GET', 'POST'])
def signup():
    if 'email' in session and 'phone' in session:
        if user_exists(session['email'], session['phone']):
            return redirect('/index')

    if request.method == 'POST':
        if not verify_recaptcha(request.form.get('g-recaptcha-response')):
            flash("Please complete the reCAPTCHA verification")
            return redirect('/sign-up')

        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        if not is_gmail(email):
            flash("Only Gmail addresses (@gmail.com) are allowed")
            return redirect('/sign-up')

        if not is_valid_phone(phone):
            flash("Phone number must be 10 digits")
            return redirect('/sign-up')

        try:
            with get_db() as db:
                if db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone():
                    flash("Email already registered. Please sign in.")
                    return redirect('/sign-in')
                
                db.execute(
                    "INSERT INTO users (email, phone) VALUES (?, ?)",
                    (email, phone)
                )
                db.commit()
                
                session.permanent = True
                session['email'] = email
                session['phone'] = phone
                return redirect('/index')
        except Exception as e:
            flash("Registration failed. Please try again.")
            return redirect('/sign-up')

    return render_template('sign-up.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

@app.route('/sign-in', methods=['GET', 'POST'])
def signin():
    if 'email' in session and 'phone' in session:
        if user_exists(session['email'], session['phone']):
            return redirect('/index')

    if request.method == 'POST':
        if not verify_recaptcha(request.form.get('g-recaptcha-response')):
            flash("Please complete the reCAPTCHA verification")
            return redirect('/sign-in')

        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        try:
            with get_db() as db:
                user = db.execute(
                    "SELECT * FROM users WHERE email = ? AND phone = ?",
                    (email, phone)
                ).fetchone()
                
                if not user:
                    flash("Account not found. Please sign up first.")
                    return redirect('/sign-up')
                
                session.permanent = True
                session['email'] = email
                session['phone'] = phone
                return redirect('/index')
        except Exception as e:
            flash("Login failed. Please try again.")
            return redirect('/sign-in')

    return render_template('sign-in.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

@app.route('/index', methods=['GET', 'POST'])
def index():
    if 'email' not in session or 'phone' not in session:
        return redirect('/sign-up')
    
    if not user_exists(session['email'], session['phone']):
        session.clear()
        flash("Your account no longer exists. Please sign up.")
        return redirect('/sign-up')
    
    filters = {}
    if request.method == 'POST':
        filters = {
            'search': request.form.get('search', '').strip(),
            'category': request.form.get('category', '').strip(),
            'min_price': request.form.get('min_price', '').strip(),
            'max_price': request.form.get('max_price', '').strip(),
            'sort': request.form.get('sort', '').strip()
        }
    
    products = get_products(filters)
    categories = get_categories()
    
    return render_template(
        'index.html',
        products=products,
        categories=categories,
        filters=filters
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/sign-in')

if __name__ == '__main__':
    # Remove this line to prevent the error:
    # if os.path.exists('app.db'):
    #     os.remove('app.db')
    
    init_db()  # This will create the database if it doesn't exist
    app.run(debug=True)