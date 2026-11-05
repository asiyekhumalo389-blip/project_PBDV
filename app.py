# app.py - Bandozee Traditional Attire E-commerce Platform
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mail import Mail, Message
import sqlite3
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
import hashlib
import time
import secrets
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = 'bandozee_secret_key_2023_durban'

# Email configuration for Gmail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'  # Replace with your Gmail
app.config['MAIL_PASSWORD'] = 'your_app_password'     # Replace with App Password
app.config['MAIL_DEFAULT_SENDER'] = 'your_email@gmail.com'
app.config['MAIL_DEBUG'] = False
app.config['MAIL_SUPPRESS_SEND'] = False

mail = Mail(app)

# File upload configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Admin credentials
ADMIN_EMAIL = 'admin@bandozee.co.za'
ADMIN_PASSWORD_HASH = hashlib.sha256('admin123'.encode()).hexdigest()

def get_db_connection():
    """Create a new database connection"""
    try:
        conn = sqlite3.connect('bandozee.db', timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    """Initialize the database and create tables if they do not exist."""
    try:
        conn = sqlite3.connect('bandozee.db')
        c = conn.cursor()
        
        # Users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                address TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Products table
        c.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                rental_price REAL,
                description TEXT,
                category TEXT,
                subcategory TEXT,
                gender TEXT,
                image_url TEXT,
                stock INTEGER DEFAULT 0,
                available_for_rent INTEGER DEFAULT 0
            )
        ''')
        
        # Orders table
        c.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                total REAL,
                status TEXT,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        # Order items table
        c.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                price REAL,
                FOREIGN KEY(order_id) REFERENCES orders(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        ''')
        
        # Rentals table
        c.execute('''
            CREATE TABLE IF NOT EXISTS rentals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                rental_days INTEGER,
                total_price REAL,
                status TEXT,
                rental_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        ''')
        
        # Password reset tokens table
        c.execute('''
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reset_token TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        # Messages table (NEW)
        c.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
       
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Database initialization error: {e}")
        return False

def cleanup_expired_tokens():
    """Remove expired password reset tokens"""
    try:
        conn = get_db_connection()
        if conn:
            c = conn.cursor()
            c.execute("DELETE FROM password_resets WHERE expires_at < datetime('now')")
            conn.commit()
            conn.close()
            print("Cleaned up expired password reset tokens")
    except Exception as e:
        print(f"Error cleaning up expired tokens: {e}")

# Initialize database and cleanup
cleanup_expired_tokens()

# ==================== ROUTES ====================

@app.route('/')
def index():
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database connection error. Please try again.', 'danger')
            return render_template('index.html', featured_products=[])
        
        c = conn.cursor()
        c.execute("SELECT * FROM products LIMIT 6")
        featured_products = c.fetchall()
        conn.close()
        
        return render_template('index.html', featured_products=featured_products)
    except Exception as e:
        flash('Error loading products.', 'danger')
        return render_template('index.html', featured_products=[])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form.get('fullName', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            address = request.form.get('address', '').strip()
            phone = request.form.get('phone', '').strip()
            
            if not all([name, email, password]):
                flash('Please fill in all required fields.', 'danger')
                return render_template('register.html')
            
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            
            conn = get_db_connection()
            if conn is None:
                flash('Database connection error. Please try again.', 'danger')
                return render_template('register.html')
            
            c = conn.cursor()
            c.execute("INSERT INTO users (name, email, password, address, phone) VALUES (?, ?, ?, ?, ?)",
                     (name, email, hashed_password, address, phone))
            conn.commit()
            
            c.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = c.fetchone()
            conn.close()
            
            if user:
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Registration failed. Please try again.', 'danger')
                
        except sqlite3.IntegrityError:
            flash('Email already registered. Please use a different email.', 'danger')
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'danger')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        try:
            conn = get_db_connection()
            if conn is None:
                flash('Database error. Please try again.', 'danger')
                return render_template('login.html')
            
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, hashed_password))
            user = c.fetchone()
            conn.close()
            
            if user:
                session['user_id'] = user[0]
                session['user_name'] = user[1]
                session['user_email'] = user[2]
                flash('Login successful!', 'success')
                return redirect(url_for('products'))
            else:
                flash('Invalid email or password.', 'danger')
        except Exception as e:
            flash('Login error. Please try again.', 'danger')
    
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template('forgot_password.html')
        
        try:
            conn = get_db_connection()
            if conn is None:
                flash('Database error. Please try again.', 'danger')
                return render_template('forgot_password.html')
            
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = c.fetchone()
            
            if user:
                # Generate a 6-digit OTP
                otp = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
                expires_at = datetime.now() + timedelta(minutes=30)
                
                # Store the reset token
                c.execute('''INSERT INTO password_resets (user_id, reset_token, expires_at, used, created_at) 
                             VALUES (?, ?, ?, 0, ?)''', 
                             (user['id'], otp, expires_at, datetime.now()))
                conn.commit()
                
                # Save email + otp in session
                session['reset_email'] = email
                session['reset_otp'] = otp
                
                if app.config.get('MAIL_SUPPRESS_SEND', False):
                    flash(f'Development Mode: OTP for {email} is: {otp} (Expires in 30 minutes)', 'info')
                else:
                    try:
                        msg = Message('Bandozee - Password Reset OTP', recipients=[email])
                        msg.body = f"Your OTP is: {otp} (Valid for 30 minutes)"
                        mail.send(msg)
                        flash('OTP sent to your email address.', 'success')
                    except Exception as e:
                        flash(f'Email service unavailable. Your OTP is: {otp}', 'warning')
            
            else:
                flash('If your email is registered, you will receive an OTP shortly.', 'info')
            
            conn.close()
            return redirect(url_for('verify_otp'))
            
        except Exception as e:
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('forgot_password.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    email = session.get('reset_email')
    
    if not email:
        flash('Invalid request.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        
        if not otp or len(otp) != 6:
            flash('Please enter a valid 6-digit OTP.', 'danger')
            return render_template('verify_otp.html', email=email)
        
        try:
            conn = get_db_connection()
            if conn is None:
                flash('Database error. Please try again.', 'danger')
                return render_template('verify_otp.html', email=email)
            
            c = conn.cursor()
            c.execute('''SELECT pr.*, u.email 
                         FROM password_resets pr 
                         JOIN users u ON pr.user_id = u.id 
                         WHERE u.email = ? AND pr.used = 0 AND pr.expires_at > datetime('now') 
                         ORDER BY pr.created_at DESC LIMIT 1''', (email,))
            reset_record = c.fetchone()
            
            if reset_record and reset_record['reset_token'] == otp:
                # OTP is valid
                session['reset_user_email'] = email
                session['reset_token'] = otp
                flash('OTP verified successfully! You can now reset your password.', 'success')
                return redirect(url_for('reset_password'))
            else:
                flash('Invalid or expired OTP. Please try again.', 'danger')
            
            conn.close()
            
        except Exception as e:
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('verify_otp.html', email=email)

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_user_email' not in session or 'reset_token' not in session:
        flash('Please request a password reset first.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not new_password or not confirm_password:
            flash('Please fill in all fields.', 'danger')
            return render_template('reset_password.html')
        
        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html')
        
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('reset_password.html')
        
        try:
            conn = get_db_connection()
            if conn is None:
                flash('Database error. Please try again.', 'danger')
                return render_template('reset_password.html')
            
            c = conn.cursor()
            hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
            
            # Update user's password
            c.execute("UPDATE users SET password = ? WHERE email = ?", 
                     (hashed_password, session['reset_user_email']))
            
            # Mark the reset token as used
            c.execute('''UPDATE password_resets SET used = 1 
                         WHERE user_id = (SELECT id FROM users WHERE email = ?) 
                         AND reset_token = ?''', 
                     (session['reset_user_email'], session['reset_token']))
            
            conn.commit()
            conn.close()
            
            # Clear session
            session.pop('reset_user_email', None)
            session.pop('reset_token', None)
            session.pop('reset_email', None)
            session.pop('reset_otp', None)
            
            flash('Password reset successfully! You can now login with your new password.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('reset_password.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/products')
def products():
    if 'user_id' not in session:
        flash('Please login to view products.', 'warning')
        return redirect(url_for('login'))
    
    category = request.args.get('category', '')
    gender = request.args.get('gender', '')
    
    conn = get_db_connection()
    c = conn.cursor()
    
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if gender:
        query += " AND gender = ?"
        params.append(gender)
    
    c.execute(query, params)
    products = c.fetchall()
    conn.close()
    
    return render_template('products.html', products=products, category=category, gender=gender)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    if 'user_id' not in session:
        flash('Please login to view product details.', 'warning')
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database error.', 'danger')
            return redirect(url_for('products'))
        
        c = conn.cursor()
        c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        product = c.fetchone()
        conn.close()
        
        if product:
            return render_template('product-detail.html', product=product)
        else:
            flash('Product not found.', 'danger')
            return redirect(url_for('products'))
    except Exception as e:
        flash('Error loading product.', 'danger')
        return redirect(url_for('products'))

@app.route('/rentals')
def rentals():
    if 'user_id' not in session:
        flash('Please login to view rental products.', 'warning')
        return redirect(url_for('login'))
    
    gender = request.args.get('gender', '')
    
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database error.', 'danger')
            return render_template('rentals.html', rental_products=[], gender=gender)
        
        c = conn.cursor()
        
        if gender:
            c.execute("SELECT * FROM products WHERE available_for_rent = 1 AND gender = ?", (gender,))
        else:
            c.execute("SELECT * FROM products WHERE available_for_rent = 1")
            
        rental_products = c.fetchall()
        conn.close()
        
        return render_template('rentals.html', rental_products=rental_products, gender=gender)
    except Exception as e:
        flash('Error loading rental products.', 'danger')
        return render_template('rentals.html', rental_products=[], gender=gender)

@app.route('/rent-product/<int:product_id>', methods=['POST'])
def rent_product(product_id):
    if 'user_id' not in session:
        flash('Please login to rent products.', 'warning')
        return redirect(url_for('login'))
    
    try:
        rental_days = int(request.form['rental_days'])
        
        conn = get_db_connection()
        if conn is None:
            flash('Database error.', 'danger')
            return redirect(url_for('rentals'))
        
        c = conn.cursor()
        c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        product = c.fetchone()
        
        if not product:
            flash('Product not found.', 'danger')
            return redirect(url_for('rentals'))
        
        rental_price = product[3]
        total_price = rental_price * rental_days
        
        c.execute('''INSERT INTO rentals (user_id, product_id, rental_days, total_price, status)
                     VALUES (?, ?, ?, ?, 'pending')''',
                 (session['user_id'], product_id, rental_days, total_price))
        rental_id = c.lastrowid
        
        conn.commit()
        conn.close()
        
        flash(f'Rental request submitted successfully! Rental ID: #{rental_id}', 'success')
        return redirect(url_for('rentals'))
    except Exception as e:
        flash('Error processing rental request.', 'danger')
        return redirect(url_for('rentals'))

# Cart Routes
@app.route('/add-to-cart-purchase/<int:product_id>')
def add_to_cart_purchase(product_id):
    if 'user_id' not in session:
        flash('Please login to add products to cart.', 'warning')
        return redirect(url_for('login'))
    
    # Get quantity from query parameter
    quantity = int(request.args.get('quantity', 1))
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    conn.close()
    
    if product:
        cart = session.get('cart', [])
        
        item_exists = False
        for item in cart:
            if item['id'] == product_id and item['type'] == 'purchase':
                item['quantity'] += quantity
                item['price'] = product[2] * item['quantity']
                item_exists = True
                break
        
        if not item_exists:
            cart.append({
                'id': product[0],
                'name': product[1],
                'price': product[2] * quantity,
                'rental_price': product[3],
                'image': product[8],
                'quantity': quantity,
                'type': 'purchase',
                'rental_days': 0
            })
        
        session['cart'] = cart
        flash(f'✅ {quantity} product(s) added to cart for purchase!', 'success')
    else:
        flash('Product not found.', 'danger')
    
    return redirect(request.referrer or url_for('products'))

@app.route('/add-to-cart-rental/<int:product_id>', methods=['POST'])
def add_to_cart_rental(product_id):
    if 'user_id' not in session:
        flash('Please login to rent products.', 'warning')
        return redirect(url_for('login'))
    
    try:
        rental_days = int(request.form.get('rental_days', 1))
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM products WHERE id = ? AND available_for_rent = 1", (product_id,))
        product = c.fetchone()
        conn.close()
        
        if not product:
            flash('Product not available for rental.', 'danger')
            return redirect(request.referrer or url_for('products'))
        
        cart = session.get('cart', [])
        
        item_exists = False
        for item in cart:
            if item['id'] == product_id and item['type'] == 'rental':
                item['rental_days'] += rental_days
                item['price'] = product[3] * item['rental_days']
                item_exists = True
                break
        
        if not item_exists:
            total_rental_price = product[3] * rental_days
            cart.append({
                'id': product[0],
                'name': product[1],
                'price': total_rental_price,
                'rental_price': product[3],
                'image': product[8],
                'quantity': 1,
                'type': 'rental',
                'rental_days': rental_days
            })
        
        session['cart'] = cart
        flash(f'📅 Product added to cart for rental ({rental_days} days)!', 'success')
        
    except Exception as e:
        flash('Error adding product to rental cart.', 'danger')
    
    return redirect(request.referrer or url_for('products'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash('Please login to view your cart.', 'warning')
        return redirect(url_for('login'))
        
    cart_items = session.get('cart', [])
    total = sum(item['price'] for item in cart_items)
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/remove-from-cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', [])
    item_removed = False
    
    for item in cart:
        if item['id'] == product_id:
            cart.remove(item)
            item_removed = True
            break
    
    session['cart'] = cart
    
    if item_removed:
        flash('Item removed from cart.', 'info')
    else:
        flash('Item not found in cart.', 'warning')
    
    return redirect(url_for('cart'))

@app.route('/update-cart-quantity/<int:product_id>', methods=['POST'])
def update_cart_quantity(product_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    try:
        data = request.get_json()
        new_quantity = int(data.get('quantity', 1))
        
        if new_quantity < 1:
            return jsonify({'success': False, 'error': 'Quantity cannot be less than 1'})
        
        cart = session.get('cart', [])
        
        for item in cart:
            if item['id'] == product_id and item['type'] == 'purchase':
                item['quantity'] = new_quantity
                # Calculate price based on unit price (price divided by current quantity)
                unit_price = item.get('rental_price', item['price'] / max(1, item.get('quantity', 1)))
                item['price'] = unit_price * new_quantity
                break
        
        session['cart'] = cart
        
        # Calculate new total
        total = sum(item['price'] for item in cart)
        
        return jsonify({
            'success': True, 
            'total': total,
            'message': 'Quantity updated successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash('Please login to complete your purchase.', 'warning')
        return redirect(url_for('login'))
        
    cart_items = session.get('cart', [])
    if not cart_items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('products'))
    
    total = sum(item['price'] for item in cart_items)
    
    if request.method == 'POST':
        try:
            # Get form data
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip()
            address = request.form.get('address', '').strip()
            city = request.form.get('city', '').strip()
            postal_code = request.form.get('postal_code', '').strip()
            payment_method = request.form.get('payment_method', '').strip()
            
            # Validate required fields
            if not all([full_name, email, address, city, postal_code, payment_method]):
                flash('Please fill in all required fields.', 'danger')
                return render_template('checkout.html', cart_items=cart_items, total=total)
            
            conn = get_db_connection()
            if conn is None:
                flash('Database error.', 'danger')
                return render_template('checkout.html', cart_items=cart_items, total=total)
            
            c = conn.cursor()
            
            # Update user information with shipping details
            shipping_address = f"{address}, {city}, {postal_code}"
            c.execute("UPDATE users SET name = ?, email = ?, address = ? WHERE id = ?",
                     (full_name, email, shipping_address, session['user_id']))
            
            # Create order
            c.execute("INSERT INTO orders (user_id, total, status) VALUES (?, ?, ?)",
                     (session['user_id'], total, 'pending'))
            order_id = c.lastrowid
            
            # Add order items
            for item in cart_items:
                c.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                         (order_id, item['id'], item['quantity'], item['price']))
            
            conn.commit()
            conn.close()
            
            # Clear cart
            session.pop('cart', None)
            
            flash(f'Order placed successfully! Order ##{order_id}', 'success')
            return redirect(url_for('order_confirmation', order_id=order_id))
            
        except Exception as e:
            flash(f'Error processing order: {str(e)}', 'danger')
    
    return render_template('checkout.html', cart_items=cart_items, total=total)

@app.route('/update-rental-days/<int:product_id>', methods=['POST'])
def update_rental_days(product_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    try:
        data = request.get_json()
        new_rental_days = int(data.get('rental_days', 1))
        
        if new_rental_days < 1:
            return jsonify({'success': False, 'error': 'Rental days cannot be less than 1'})
        
        cart = session.get('cart', [])
        
        for item in cart:
            if item['id'] == product_id and item['type'] == 'rental':
                item['rental_days'] = new_rental_days
                item['price'] = item['rental_price'] * new_rental_days
                break
        
        session['cart'] = cart
        
        # Calculate new total
        total = sum(item['price'] for item in cart)
        
        return jsonify({
            'success': True, 
            'total': total,
            'message': 'Rental days updated successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
    
@app.route('/order-confirmation/<int:order_id>')
def order_confirmation(order_id):
    if 'user_id' not in session:
        flash('Please login to view order confirmation.', 'warning')
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get order details with customer information
        c.execute('''SELECT o.*, u.name, u.email, u.phone, u.address 
                     FROM orders o 
                     JOIN users u ON o.user_id = u.id 
                     WHERE o.id = ? AND o.user_id = ?''', 
                 (order_id, session['user_id']))
        order = c.fetchone()
        
        if not order:
            flash('Order not found.', 'danger')
            return redirect(url_for('my_orders'))
        
        # Get order items
        c.execute('''SELECT oi.*, p.name, p.image_url 
                     FROM order_items oi 
                     JOIN products p ON oi.product_id = p.id 
                     WHERE oi.order_id = ?''', (order_id,))
        order_items = c.fetchall()
        
        conn.close()
        
        return render_template('order-confirmation.html',
                             order_id=order_id,
                             order_date=order['order_date'],
                             total_amount=order['total'],
                             customer_name=order['name'],
                             customer_email=order['email'],
                             customer_phone=order['phone'],
                             shipping_address=order['address'],
                             order_items=order_items)
        
    except Exception as e:
        flash('Error loading order confirmation.', 'danger')
        return redirect(url_for('my_orders'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        
        if not all([name, email, subject, message]):
            flash('Please fill in all required fields.', 'danger')
            return render_template('contact.html')
        
        try:
            conn = get_db_connection()
            if conn is None:
                flash('Database error. Please try again.', 'danger')
                return render_template('contact.html')
            
            c = conn.cursor()
            c.execute('''INSERT INTO messages (name, email, subject, message) 
                         VALUES (?, ?, ?, ?)''', (name, email, subject, message))
            conn.commit()
            conn.close()
            
            flash('Your message has been sent successfully! We will get back to you soon.', 'success')
            return redirect(url_for('contact'))
        except Exception as e:
            flash('Error sending message. Please try again.', 'danger')
    
    return render_template('contact.html')

# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        if email == ADMIN_EMAIL and hashed_password == ADMIN_PASSWORD_HASH:
            session['admin_logged_in'] = True
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials.', 'danger')
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database error.', 'danger')
            return render_template('admin.html', product_count=0, user_count=0, pending_orders=0, active_rentals=0, recent_orders=[], recent_users=[], recent_rentals=[], total_messages=0, new_messages=0)
        
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM products")
        product_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        pending_orders = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM rentals WHERE status = 'active'")
        active_rentals = c.fetchone()[0]
        
        # Message statistics (NEW)
        c.execute("SELECT COUNT(*) FROM messages")
        total_messages = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM messages WHERE status = 'new'")
        new_messages = c.fetchone()[0]
        
        c.execute("SELECT * FROM orders ORDER BY order_date DESC LIMIT 5")
        recent_orders = c.fetchall()
        
        c.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 5")
        recent_users = c.fetchall()
        
        c.execute("SELECT * FROM rentals ORDER BY rental_date DESC LIMIT 5")
        recent_rentals = c.fetchall()
        
        conn.close()
        
        return render_template('admin.html', 
                             product_count=product_count,
                             user_count=user_count,
                             pending_orders=pending_orders,
                             active_rentals=active_rentals,
                             recent_orders=recent_orders,
                             recent_users=recent_users,
                             recent_rentals=recent_rentals,
                             total_messages=total_messages,
                             new_messages=new_messages)
    except Exception as e:
        flash('Error loading dashboard.', 'danger')
        return render_template('admin.html', 
                             product_count=0,
                             user_count=0,
                             pending_orders=0,
                             active_rentals=0,
                             recent_orders=[],
                             recent_users=[],
                             recent_rentals=[],
                             total_messages=0,
                             new_messages=0)

@app.route('/admin/products')
def admin_products():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database error.', 'danger')
            return render_template('admin_products.html', products=[])
        
        c = conn.cursor()
        c.execute("SELECT * FROM products")
        products = c.fetchall()
        conn.close()
        
        return render_template('admin_products.html', products=products)
    except Exception as e:
        flash('Error loading products.', 'danger')
        return render_template('admin_products.html', products=[])

@app.route('/admin/customers')
def admin_customers():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database error.', 'danger')
            return render_template('admin_customers.html', customers=[])
        
        c = conn.cursor()
        c.execute("SELECT * FROM users")
        customers = c.fetchall()
        conn.close()
        
        return render_template('admin_customers.html', customers=customers)
    except Exception as e:
        flash('Error loading customers.', 'danger')
        return render_template('admin_customers.html', customers=[])

@app.route('/admin/rentals')
def admin_rentals():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database error.', 'danger')
            return render_template('admin_rentals.html', rentals=[])
        
        c = conn.cursor()
        c.execute('''SELECT r.*, u.name as customer_name, u.email, u.phone, p.name as product_name 
                     FROM rentals r 
                     JOIN users u ON r.user_id = u.id 
                     JOIN products p ON r.product_id = p.id 
                     ORDER BY r.rental_date DESC''')
        rentals = c.fetchall()
        conn.close()
        
        return render_template('admin_rentals.html', rentals=rentals)
    except Exception as e:
        flash('Error loading rentals.', 'danger')
        return render_template('admin_rentals.html', rentals=[])

# ==================== ADMIN MESSAGES ROUTES (NEW) ====================

@app.route('/admin/messages')
def admin_messages():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database error.', 'danger')
            return render_template('admin_messages.html', messages=[])
        
        c = conn.cursor()
        c.execute("SELECT * FROM messages ORDER BY created_at DESC")
        messages = c.fetchall()
        conn.close()
        
        return render_template('admin_messages.html', messages=messages)
    except Exception as e:
        flash('Error loading messages.', 'danger')
        return render_template('admin_messages.html', messages=[])

@app.route('/admin/messages/update_status/<int:message_id>/<status>')
def admin_update_message_status(message_id, status):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Not authenticated'})
    
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'error': 'Database error'})
        
        c = conn.cursor()
        c.execute("UPDATE messages SET status = ? WHERE id = ?", (status, message_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/messages/delete/<int:message_id>')
def admin_delete_message(message_id):
    if not session.get('admin_logged_in'):
        flash('Not authenticated.', 'danger')
        return redirect(url_for('admin_messages'))
    
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Database error.', 'danger')
            return redirect(url_for('admin_messages'))
        
        c = conn.cursor()
        c.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        conn.commit()
        conn.close()
        
        flash('Message deleted successfully!', 'success')
    except Exception as e:
        flash('Error deleting message.', 'danger')
    
    return redirect(url_for('admin_messages'))

# ==================== ADMIN PRODUCT CRUD ====================

@app.route('/admin/add-product', methods=['GET', 'POST'])
def admin_add_product():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        try:
            name = request.form['name']
            price = float(request.form['price'])
            rental_price = float(request.form['rental_price'])
            description = request.form['description']
            category = request.form['category']
            subcategory = request.form['subcategory']
            gender = request.form['gender']
            stock = int(request.form['stock'])
            available_for_rent = 1 if 'available_for_rent' in request.form else 0
            
            image_url = '/static/images/placeholder.jpg'
            if 'product_image' in request.files:
                file = request.files['product_image']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(file_path)
                    image_url = f'/static/uploads/{unique_filename}'
            
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('''INSERT INTO products 
                         (name, price, rental_price, description, category, subcategory, gender, image_url, stock, available_for_rent)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (name, price, rental_price, description, category, subcategory, gender, image_url, stock, available_for_rent))
            conn.commit()
            conn.close()
            
            flash('Product added successfully!', 'success')
            return redirect(url_for('admin_products'))
        except Exception as e:
            flash(f'Error adding product: {str(e)}', 'danger')
    
    return render_template('admin_add_product.html')

@app.route('/admin/edit-product/<int:product_id>', methods=['GET', 'POST'])
def admin_edit_product(product_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        if request.method == 'POST':
            name = request.form['name']
            price = float(request.form['price'])
            rental_price = float(request.form['rental_price'])
            description = request.form['description']
            category = request.form['category']
            subcategory = request.form['subcategory']
            gender = request.form['gender']
            stock = int(request.form['stock'])
            available_for_rent = 1 if 'available_for_rent' in request.form else 0
            
            c.execute("SELECT image_url FROM products WHERE id = ?", (product_id,))
            current_product = c.fetchone()
            image_url = current_product['image_url'] if current_product else '/static/images/placeholder.jpg'
            
            if 'product_image' in request.files:
                file = request.files['product_image']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(file_path)
                    image_url = f'/static/uploads/{unique_filename}'
            
            c.execute('''UPDATE products SET 
                         name=?, price=?, rental_price=?, description=?, category=?, subcategory=?, gender=?, 
                         image_url=?, stock=?, available_for_rent=?
                         WHERE id=?''',
                     (name, price, rental_price, description, category, subcategory, gender, image_url, stock, available_for_rent, product_id))
            conn.commit()
            conn.close()
            
            flash('Product updated successfully!', 'success')
            return redirect(url_for('admin_products'))
        
        c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        product = c.fetchone()
        conn.close()
        
        if not product:
            flash('Product not found.', 'danger')
            return redirect(url_for('admin_products'))
        
        return render_template('admin_edit_product.html', product=product)
    except Exception as e:
        flash('Error editing product.', 'danger')
        return redirect(url_for('admin_products'))

@app.route('/admin/delete-product/<int:product_id>')
def admin_delete_product(product_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()
        
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        flash('Error deleting product.', 'danger')
    
    return redirect(url_for('admin_products'))

@app.route('/admin/delete-customer/<int:customer_id>')
def admin_delete_customer(customer_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Check if customer has orders or rentals
        c.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (customer_id,))
        order_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM rentals WHERE user_id = ?", (customer_id,))
        rental_count = c.fetchone()[0]
        
        if order_count > 0 or rental_count > 0:
            flash('Cannot delete customer with existing orders or rentals.', 'danger')
        else:
            c.execute("DELETE FROM users WHERE id = ?", (customer_id,))
            conn.commit()
            flash('Customer deleted successfully!', 'success')
        
        conn.close()
    except Exception as e:
        flash('Error deleting customer.', 'danger')
    
    return redirect(url_for('admin_customers'))

@app.route('/admin/update-rental-status/<int:rental_id>/<status>')
def admin_update_rental_status(rental_id, status):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE rentals SET status = ? WHERE id = ?", (status, rental_id))
        conn.commit()
        conn.close()
        
        flash(f'Rental status updated to {status}!', 'success')
    except Exception as e:
        flash('Error updating rental status.', 'danger')
    
    return redirect(url_for('admin_rentals'))

# Admin orders page - FIXED: Only one definition remains
@app.route('/admin/orders')
def admin_orders():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''SELECT o.*, u.name, u.email 
                     FROM orders o 
                     JOIN users u ON o.user_id = u.id 
                     ORDER BY o.order_date DESC''')
        orders = c.fetchall()
        conn.close()
    except Exception as e:
        flash('Error loading orders.', 'error')
        orders = []
    
    return render_template('admin_orders.html', orders=orders)

# Admin order status update
@app.route('/admin/update_order_status', methods=['POST'])
def admin_update_order_status():
    if not session.get('admin_logged_in'):
        flash('Please login as admin.', 'error')
        return redirect(url_for('admin_login'))
    
    order_id = request.form.get('order_id')
    new_status = request.form.get('status')
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        conn.commit()
        conn.close()
        
        flash(f'Order #{order_id} status updated to {new_status}!', 'success')
    except Exception as e:
        flash('Error updating order status.', 'error')
    
    return redirect(url_for('admin_dashboard'))

# Customer order tracking
@app.route('/order-tracking')
def order_tracking():
    order_id = request.args.get('order_id')
    order = None
    order_items = []
    
    if order_id:
        try:
            conn = get_db_connection()
            if conn is None:
                flash('Database connection error.', 'error')
                return render_template('order_tracking.html', order=None, order_items=[])
            
            c = conn.cursor()
            
            # Get the order
            c.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = c.fetchone()
            
            if order:
                # Get order items
                c.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
                order_items = c.fetchall()
                
                # Get all products for display
                c.execute("SELECT * FROM products")
                products = c.fetchall()
                
                # Get all users for display
                c.execute("SELECT * FROM users")
                users = c.fetchall()
                
                conn.close()
                
                return render_template('order_tracking.html', 
                                     order=order, 
                                     order_items=order_items,
                                     products=products,
                                     users=users)
            else:
                conn.close()
                flash('Order not found. Please check your Order ID.', 'error')
                return render_template('order_tracking.html', order=None, order_items=[])
                
        except Exception as e:
            flash(f'Error retrieving order information: {str(e)}', 'error')
            return render_template('order_tracking.html', order=None, order_items=[])
    
    # If no order_id provided, just show the tracking page
    return render_template('order_tracking.html', order=None, order_items=[])

# Customer's order history
@app.route('/my-orders')
def my_orders():
    if 'user_id' not in session:
        flash('Please login to view your orders.', 'warning')
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY order_date DESC", (session['user_id'],))
        orders = c.fetchall()
        
        order_details = []
        for order in orders:
            c.execute("SELECT oi.*, p.name, p.image_url FROM order_items oi JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?", (order[0],))
            items = c.fetchall()
            order_details.append({
                'order': order,
                'items': items
            })
        
        conn.close()
    except Exception as e:
        flash('Error retrieving your orders.', 'error')
        order_details = []
    
    return render_template('my_orders.html', order_details=order_details)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Admin logged out successfully.', 'info')
    return redirect(url_for('index'))

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# ==================== APPLICATION START ====================

if __name__ == '__main__':
    print("🚀 Initializing Bandozee Application...")
    print(f"📁 Database location: {os.path.abspath('bandozee.db')}")
    
    db_exists_before = os.path.exists('bandozee.db')
    if db_exists_before:
        print("📊 Existing database found - data will be preserved")
    else:
        print("🆕 No existing database - creating new one")
    
    if init_db():
        print("✅ Database initialized successfully")
        
        conn = sqlite3.connect('bandozee.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM products")
        product_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages")
        message_count = c.fetchone()[0]
        conn.close()
        
        print(f"👥 Users in database: {user_count}")
        print(f"🛍️ Products in database: {product_count}")
        print(f"📨 Messages in database: {message_count}")
        print("📍 Application available at: http://127.0.0.1:5000")
        print("🔑 Admin login: admin@bandozee.co.za / admin123")
        print("=" * 60)
        
        app.run(debug=True, host='127.0.0.1', port=5000, use_reloader=False)
    else:
        print("❌ Failed to initialize database")