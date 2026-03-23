import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from werkzeug.utils import secure_filename
from datetime import date, datetime
from fpdf import FPDF
from flask import make_response
import random 

app = Flask(__name__)
app.secret_key = "agri_rental_full_project_key"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.secret_key = "secret_key_here"

# --- DATABASE CONNECTION ---
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- INITIALIZE DATABASE ---
def init_db():
    conn = get_db_connection()
    
    # 1. Vendor Table
    # Part of init_db() in app.py
    conn.execute(''' 
    CREATE TABLE IF NOT EXISTS vendor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_name TEXT NOT NULL,
        owner_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        city TEXT NOT NULL,
        password TEXT NOT NULL,
        status TEXT DEFAULT 'Pending'
    )
''')
    
    # 2. Customer Table
    # Replace the customer table section in init_db()
    conn.execute('''
    CREATE TABLE IF NOT EXISTS customer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        phone TEXT NOT NULL,
        city TEXT NOT NULL,
        address TEXT NOT NULL,
        id_proof TEXT  -- For storing the Aadhaar/ID image filename
    )
''')

    # 3. Equipment Table
    conn.execute('''CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_id INTEGER,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        description TEXT,
        price_per_day REAL NOT NULL,
        availability TEXT DEFAULT 'Available',
        image TEXT,
        FOREIGN KEY (vendor_id) REFERENCES vendor (id)
    )
''')

    # 4. Bookings Table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER,
            customer_id INTEGER,
            vendor_id INTEGER,
            booking_date TEXT,
            total_price REAL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (equipment_id) REFERENCES equipment (id),
            FOREIGN KEY (customer_id) REFERENCES customer (id)
        )
    ''')

    # 5. Feedback & Inquiries
    conn.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT, email TEXT, message TEXT, rating INTEGER,
            date_submitted TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT, subject TEXT, message TEXT,
            date_submitted TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # CLOSE ONCE AT THE VERY END
    conn.commit()
    conn.close()

# --- GENERAL ROUTES ---
@app.route('/')
def home():
    conn = get_db_connection()
    # Fetch all equipment to display on the home page
    rows = conn.execute('SELECT * FROM equipment').fetchall()
    conn.close()
    
    items = []
    if rows:
        for row in rows:
            item = dict(row)
            # Fix the "None" values for the Home Page
            item['category'] = item.get('category') or "General"
            item['description'] = item.get('description') or "Quality equipment."
            item['price_per_day'] = item.get('price_per_day') or 0
            
            if not item.get('image'):
                item['image'] = 'default.png'
                
            items.append(item)
            
    # Make sure this matches your actual home page HTML filename!
    return render_template('index.html', items=items)

# --- ADMIN ROUTES ---
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    print(f"Request Method: {request.method}") # This tells you if the page is being hit
    if request.method == 'POST':
        # Using .get() ensures it doesn't crash if the HTML name is slightly off
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"Login Attempt: {username}") # Check your terminal for this!

        if username == 'admin' and password == 'admin':
            session['admin_logged_in'] = True
            flash('Welcome Admin!')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid Admin Credentials!')
            return redirect(url_for('admin_login'))
            
    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    v_count = conn.execute('SELECT count(*) FROM vendor').fetchone()[0]
    e_count = conn.execute('SELECT count(*) FROM equipment').fetchone()[0]
    c_count = conn.execute('SELECT count(*) FROM customer').fetchone()[0]
    vendors = conn.execute('SELECT * FROM vendor').fetchall()
    conn.close()
    return render_template('admin_dashboard.html', v_count=v_count, e_count=e_count, c_count=c_count,vendors=vendors)

@app.route('/admin_manage_vendors')
def admin_manage_vendors():
    conn = get_db_connection()
    # This grabs EVERY vendor so you can see them all
    vendors = conn.execute('SELECT * FROM vendor').fetchall()
    conn.close()
    return render_template('admin_manage_vendors.html', vendors=vendors)


# Merged Route for Customers and Equipment
@app.route('/admin_view/<data_type>')
def admin_view_data(data_type):
    if not session.get('admin_logged_in'): 
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    if data_type == 'vendors':
        # Fetches all vendors to show Pending/Approved status
        rows = conn.execute('SELECT * FROM vendor').fetchall()
        title = "Vendors"
    elif data_type == 'customers':
        # Fetches all registered customers
        rows = conn.execute('SELECT * FROM customer').fetchall()
        title = "Customers"
    elif data_type == 'equipment':
        # Fetches all equipment listed by all vendors
        rows = conn.execute('SELECT * FROM equipment').fetchall()
        title = "Equipment"
    else:
        conn.close()
        return redirect(url_for('admin_dashboard'))
    
    conn.close()
    return render_template('admin_view_data.html', rows=rows, title=title)

@app.route('/admin_approve_vendor/<int:vendor_id>/<action>', methods=['GET', 'POST'])
def admin_approve_vendor(vendor_id, action):
    conn = get_db_connection()
    if action == 'approve':
        vendor_date = request.form.get('vendor_date')
        # Changes status so vendor can login and equipment becomes visible
        conn.execute("UPDATE vendor SET status = 'Approved', verification_date = ? WHERE id = ?", (vendor_date, vendor_id,))
    elif action == 'reject':
        # Deletes the vendor entirely if rejected
        conn.execute("DELETE FROM vendor WHERE id = ?", (vendor_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_view_data', data_type='vendors'))

@app.route('/delete_vendor/<int:vendor_id>')
def delete_vendor(vendor_id):
    if 'admin_id' not in session and not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    # This removes the vendor record completely from the database
    conn.execute('DELETE FROM vendor WHERE id = ?', (vendor_id,))
    conn.commit()
    conn.close()
    
    flash("Vendor record deleted successfully.")
    return redirect(url_for('admin_dashboard'))

# --- VENDOR ROUTES ---
import sqlite3 # Make sure this is at the top of app.py!

@app.route('/vendor_register', methods=['GET', 'POST'])
def vendor_register():
    if request.method == 'POST':
        govt_id = request.form.get('government_id')
        shop = request.form.get('shop_name')
        owner = request.form.get('owner_name')
        email = request.form.get('email')
        city = request.form.get('city')
        pwd = request.form.get('password')
        
        conn = get_db_connection()
        try:
            # FIXED: Added the correct number of '?' and moved 'Pending' into the values list
            conn.execute('''
                INSERT INTO vendor (shop_name, government_id, owner_name, email, city, password, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (shop, govt_id, owner, email, city, pwd, 'Pending'))
            
            conn.commit()
            flash('Registered Successfully! Please wait for Admin Approval.') 
            return redirect(url_for('vendor_login'))
        except Exception as e:
            print(f"Error: {e}") # This helps you see the real error in your terminal
            flash('Registration failed. Email might already exist!')
            return redirect(url_for('vendor_register'))
        finally:
            conn.close()
            
    return render_template('vendor_registration.html')
@app.route('/vendor_login', methods=['GET', 'POST'])
def vendor_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        vendor = conn.execute('SELECT * FROM vendor WHERE email = ? AND password = ?', (email, password)).fetchone()
        conn.close()
        
        if vendor:
            # IMPORTANT: This must match what your sales/dashboard routes look for
            session['vendor_id'] = vendor['id'] 
            session['role'] = 'vendor'
            flash("Login Successful!")
            return redirect(url_for('vendor_dashboard'))
        else:
            flash("Invalid Email or Password")
            
    return render_template('vendor_login.html')

@app.route('/vendor_dashboard')
def vendor_dashboard():
    # Use 'vendor_id' as that is your standard session key
    if 'vendor_id' not in session: 
        return redirect(url_for('vendor_login'))
    
    conn = get_db_connection()
    
    # 1. Real count of equipment
    total_equip = conn.execute('SELECT COUNT(*) FROM equipment WHERE vendor_id = ?', (session['vendor_id'],)).fetchone()[0]
    
    # 2. Real count of bookings
    total_bookings = conn.execute('SELECT COUNT(*) FROM bookings WHERE vendor_id = ?', (session['vendor_id'],)).fetchone()[0]
    
    # 3. Total Earnings (Using ABS to remove the minus symbol)
    total_revenue = conn.execute('SELECT SUM(ABS(total_price)) FROM bookings WHERE vendor_id = ? AND payment_status = "Paid"', (session['vendor_id'],)).fetchone()[0] or 0
    
    conn.close()
    
    return render_template('vendor_dashboard.html', 
                           total_equip=total_equip, 
                           total_bookings=total_bookings, 
                           total_revenue=total_revenue)

import os
from werkzeug.utils import secure_filename

# Notice we now allow BOTH 'GET' (viewing) and 'POST' (submitting)
@app.route('/add_equipment', methods=['GET', 'POST'])
def add_equipment():
    if 'vendor_id' not in session:
        return redirect(url_for('vendor_login'))
    
    if request.method == 'POST':
        vendor_id = session['vendor_id']
        name = request.form.get('name')
        category = request.form.get('category')
        description = request.form.get('description')
        
        # 1. FIXED: Capture both Hourly and Daily prices
        price_per_day = request.form.get('price_per_day')
        price_per_hour = request.form.get('price_per_hour')
        
        # GET THE STATUS FROM THE FORM
        status = request.form.get('status') 
        
        image_file = request.files.get('image')
        filename = 'default.png'
        
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join('static/uploads', filename))
        
        conn = get_db_connection()
        
        # 2. FIXED: Added 'price_per_hour' to the INSERT command
        conn.execute('''
            INSERT INTO equipment (vendor_id, name, type, description, price_per_day, price_per_hour, image, availability)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (vendor_id, name, category, description, price_per_day, price_per_hour, filename, 'Available'))
        
        conn.commit()
        conn.close()
        
        flash('Equipment added successfully!')
        return redirect(url_for('vendor_dashboard'))
        
    return render_template('add_equipment.html')
@app.route('/edit_equipment/<int:equipment_id>', methods=['GET', 'POST'])
def edit_equipment(equipment_id):
    if 'vendor_id' not in session:
        return redirect(url_for('vendor_login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Get the updated data from the form
        name = request.form['name']
        type = request.form['type']
        price = request.form['price_per_day']
        desc = request.form['description']
        
        # Update the database record
        conn.execute('''UPDATE equipment 
                        SET name = ?, type = ?, price_per_day = ?, description = ? 
                        WHERE id = ? AND vendor_id = ?''', 
                     (name, type, price, desc, equipment_id, session['vendor_id']))
        conn.commit()
        conn.close()
        return redirect(url_for('vendor_manage_equipment'))

    # GET request: Load the current data to show in the form
    equipment = conn.execute('SELECT * FROM equipment WHERE id = ? AND vendor_id = ?', 
                           (equipment_id, session['vendor_id'])).fetchone()
    conn.close()
    return render_template('edit_equipment.html', equipment=equipment)

@app.route('/delete_equipment/<int:equipment_id>')
def delete_equipment(equipment_id):
    # Security: Ensure only the logged-in vendor can delete their own items
    if 'vendor_id' not in session:
        return redirect(url_for('vendor_login'))
    
    conn = get_db_connection()
    # This SQL command removes the specific item from the database
    conn.execute('DELETE FROM equipment WHERE id = ? AND vendor_id = ?', 
                 (equipment_id, session['vendor_id']))
    conn.commit()
    conn.close()
    
    # Redirect back to the list so you can see it is gone
    return redirect(url_for('vendor_manage_equipment'))
    

@app.route('/vendor_manage_equipment')
def vendor_manage_equipment():
    if 'vendor_id' not in session:
        return redirect(url_for('vendor_login'))
    
    conn = get_db_connection()
    # Fetch only items belonging to the logged-in vendor
    items = conn.execute('SELECT * FROM equipment WHERE vendor_id = ?', 
                        (session['vendor_id'],)).fetchall()
    search_query = request.args.get('search', '') # Get search term from the URL
    conn = get_db_connection()
    
    if search_query:
        # Filter by name or type using the LIKE operator
        query = "SELECT * FROM equipment WHERE vendor_id = ? AND (name LIKE ? OR type LIKE ?)"
        rows = conn.execute(query, (session['vendor_id'], f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        # Default view: show all items for this vendor
        rows = conn.execute('SELECT * FROM equipment WHERE vendor_id = ?', (session['vendor_id'],)).fetchall()
    conn.close()
    return render_template('vendor_manage_equipment.html', items=rows, search_query=search_query)

@app.route('/vendor_view_bookings')
def vendor_view_bookings():
    if 'vendor_id' not in session:
        return redirect(url_for('vendor_login'))
    
    vendor_id = session['vendor_id']
    conn = get_db_connection()
    
    # We JOIN the equipment table for the name and the customer table for their name
    query = '''
        SELECT 
            b.id, 
            e.name AS equipment_name,
            c.name AS customer_name, 
            c.id_proof,
            b.start_date, 
            b.end_date, 
            b.total_price, 
            b.status 
        FROM bookings b
        JOIN equipment e ON b.equipment_id = e.id
        JOIN customer c ON b.customer_id = c.id
        WHERE b.vendor_id = ?
        ORDER BY b.id DESC
    '''
    bookings = conn.execute(query, (vendor_id,)).fetchall()
    conn.close()
    
    return render_template('vendor_view_bookings.html', bookings=bookings)

# --- CUSTOMER REGISTRATION ---
from flask import flash, session, redirect, url_for, request, render_template

@app.route('/customer_register', methods=['GET', 'POST'])
def customer_register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')
        city = request.form.get('city')
        address = request.form.get('address')

        id_file = request.files.get('id_proof')
        filename = ""
        
        if id_file:
            # Save the file to your uploads folder
            filename = id_file.filename
            upload_path = os.path.join('static/uploads', filename)
            id_file.save(upload_path)
        
        # --- Start Modification: Generate OTP and Save to Session ---
        otp = str(random.randint(1000, 9999))
        session['customer_otp'] = otp
        session['temp_customer_data'] = {
            'name': name,
            'email': email,
            'password': password,
            'phone': phone,
            'city': city,
            'address': address,
            'id_proof': filename  # Added this to the session
        }
        
        flash(f'Verification Code Sent to {phone}: {otp}')
        return redirect(url_for('verify_customer'))
        # --- End Modification ---

    return render_template('customer_register.html')

@app.route('/verify_customer', methods=['GET', 'POST'])
def verify_customer():
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        
        if entered_otp == session.get('customer_otp'):
            data = session.get('temp_customer_data')
            conn = get_db_connection()
            try:
                # This is your original INSERT query, now inside the verification check
                conn.execute('''INSERT INTO customer (name, email, password, phone, city, address, id_proof) 
                                VALUES (?, ?, ?, ?, ?, ?)''', 
                             (data['name'], data['email'], data['password'], data['phone'], data['city'], data['address'], data['id_proof']))
                conn.commit()
                
                # Clear temporary session data
                session.pop('customer_otp', None)
                session.pop('temp_customer_data', None)
                
                flash('Registration Successful! Please Login.')
                return redirect(url_for('customer_login'))
            except Exception as e:
                flash(f'Error: {str(e)}')
                return redirect(url_for('customer_register'))
            finally:
                conn.close()
        else:
            flash('Invalid OTP. Please try again.')
            
    return render_template('verify_otp.html')
@app.route('/resend_otp')
def resend_otp():
    if 'temp_customer_data' in session:
        # Generate a new code
        new_otp = str(random.randint(1000, 9999))
        session['customer_otp'] = new_otp
        
        phone = session['temp_customer_data']['phone']
        flash(f'New Verification Code Sent to {phone}: {new_otp}')
        return redirect(url_for('verify_customer'))
    
    flash("Session expired. Please register again.")
    return redirect(url_for('customer_register'))

# --- CUSTOMER LOGIN ---
@app.route('/customer_login', methods=['GET', 'POST'])
def customer_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM customer WHERE email = ? AND password = ?', 
                           (email, password)).fetchone()
        conn.close()
        
        if user:
            # Storing info in session to use across the site
            session['user_id'] = user['id']
            session['customer_name'] = user['name'] 
            return redirect(url_for('customer_dashboard'))
        else:
            flash('Invalid Email or Password', 'danger')
            return redirect(url_for('customer_login'))
            
    return render_template('customer_login.html')

# --- CUSTOMER HOME (Where they see tractors) ---
@app.route('/customer_home')
def customer_home():
    if 'customer_id' not in session:
        return redirect(url_for('customer_login'))

    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM equipment').fetchall()
    conn.close()
    
    items = []
    if rows:
        for row in rows:
            item = dict(row)
            
            # --- THE FIX IS HERE ---
            # If the image is None, force it to be 'default.png'
            if not item.get('image'):
                item['image'] = 'default.png'
            
            # Fix other empty fields to prevent "None" text
            item['category'] = item.get('category') or "General"
            item['price_per_day'] = item.get('price_per_day') or 0
            
            items.append(item)
            
    return render_template('customer_home.html', items=items)

@app.route('/customer_dashboard')
def customer_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('customer_login'))
    
    cid = session['user_id']
    conn = get_db_connection()
    
    # 1. NEW: Fetch only equipment that is NOT currently booked
    # This checks if today's date falls between any existing booking dates
    available_query = '''
        SELECT * FROM equipment 
        WHERE id NOT IN (
            SELECT equipment_id FROM bookings 
            WHERE status = 'Confirmed' 
            AND date('now') BETWEEN date(start_date) AND date(end_date)
        )
    '''
    available_equipment = conn.execute(available_query).fetchall()
    
    # 2. Get the stats for your cards
    total = conn.execute('SELECT COUNT(*) FROM bookings WHERE customer_id = ?', (cid,)).fetchone()[0]
    
    # Updated: Now we count 'Confirmed' as the active stat instead of 'Pending'
    active_bookings = conn.execute('SELECT COUNT(*) FROM bookings WHERE customer_id = ? AND status = "Confirmed"', (cid,)).fetchone()[0]
    
    completed = conn.execute('SELECT COUNT(*) FROM bookings WHERE customer_id = ? AND status IN ("Completed", "Returned")', (cid,)).fetchone()[0]
    
    feedback_query = '''
        SELECT COUNT(*) FROM bookings 
        WHERE customer_id = ? AND status IN ("Completed", "Returned") 
        AND id NOT IN (SELECT booking_id FROM feedback)
    '''
    feedback_count = conn.execute(feedback_query, (cid,)).fetchone()[0]

    stats = {
        'total': total,
        'active': active_bookings, # Renamed from 'pending'
        'completed': completed,
        'feedback': feedback_count,
        'available_count': len(available_equipment) # New stat for the guide
    }
    
    conn.close()
    # Passing both stats and the equipment list to your HTML
    return render_template('customer_dashboard.html', stats=stats, items=available_equipment)

from datetime import datetime

@app.route('/book_equipment/<int:id>', methods=['GET', 'POST'])
def book_equipment(id):
    if 'user_id' not in session:
        return redirect(url_for('customer_login'))
    
    conn = get_db_connection()
    item_row = conn.execute('''
        SELECT equipment.*, shop_name 
        FROM equipment 
        JOIN vendor ON equipment.vendor_id = vendor.id 
        WHERE equipment.id = ?
    ''', (id,)).fetchone()
    
    if not item_row:
        conn.close()
        return "Equipment not found", 404

    item = dict(item_row)

    if request.method == 'POST':
        # 1. Combine Date and Time from the form
        start_date_str = request.form['start_date']
        start_time_str = request.form['start_time']
        end_date_str = request.form['end_date']
        end_time_str = request.form['end_time']
        
        start_full = f"{start_date_str} {start_time_str}"
        end_full = f"{end_date_str} {end_time_str}"
        
        start_dt = datetime.strptime(start_full, '%Y-%m-%d %H:%M')
        end_dt = datetime.strptime(end_full, '%Y-%m-%d %H:%M')
        
        # 2. Calculate total duration in hours
        duration_delta = end_dt - start_dt
        total_hours = duration_delta.total_seconds() / 3600
        
        # 3. FIXED: Tiered Pricing Logic (Hours vs Days)
        if total_hours < 24:
            # Hourly Preference logic
            # Uses price_per_hour column we added to your DB earlier
            base_price = total_hours * float(item.get('price_per_hour', 0))
        else:
            # Daily Package logic
            total_days = total_hours / 24
            base_price = total_days * float(item.get('price_per_day', 0))
            
        # 4. FIXED: Add 18% GST
        gst_amount = base_price * 0.18
        final_total = round(base_price + gst_amount, 2)
        
        booking_date = datetime.now().strftime('%Y-%m-%d')

        # 5. Insert with calculated price and GST
        cursor = conn.execute('''
            INSERT INTO bookings (
                equipment_id, customer_id, vendor_id, 
                start_date, end_date, booking_date, 
                total_price, status
            ) 
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Confirmed')
        ''', (id, session['user_id'], item['vendor_id'], start_full, end_full, booking_date, final_total))
        
        booking_id = cursor.lastrowid 
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('payment', booking_id=booking_id))

    conn.close()
    return render_template('book_equipment.html', item=item)
@app.route('/customer_bookings')
def my_bookings():
    if 'user_id' not in session:
        return redirect(url_for('customer_login'))
    
    cid = session['user_id']
    conn = get_db_connection()
    
    # This query joins the equipment table so we can see the Name and Price
    query = '''
        SELECT 
            b.id, 
            e.name, 
            e.type, 
            v.shop_name,
            b.start_date, 
            b.end_date, 
            b.total_price, 
            b.booking_date, 
            b.status,
            e.image
        FROM bookings b
        JOIN equipment e ON b.equipment_id = e.id
        JOIN vendor v ON e.vendor_id = v.id
        WHERE b.customer_id = ?
        ORDER BY b.id DESC
    '''
    bookings = conn.execute(query, (cid,)).fetchall()
    conn.close()
    
    return render_template('customer_bookings.html', bookings=bookings)

@app.route('/give_feedback/<int:booking_id>', methods=['GET', 'POST'])
def give_feedback(booking_id):
    # 1. CHANGED: Match 'user_id' from your login session
    if 'user_id' not in session:
        return redirect(url_for('customer_login'))

    if request.method == 'POST':
        rating = request.form.get('rating')
        comment = request.form.get('comment')
        
        conn = get_db_connection()
        
        # 2. Get the vendor_id and equipment_id from the booking first
        # This is needed so the Admin knows which vendor/machine the feedback is for.
        booking = conn.execute('SELECT vendor_id, equipment_id FROM bookings WHERE id = ?', (booking_id,)).fetchone()
        
        # 3. INSERT into a separate feedback table (matches Video logic)
        conn.execute('''
            INSERT INTO feedback (booking_id, customer_id, vendor_id, equipment_id, rating, comment)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (booking_id, session['user_id'], booking['vendor_id'], booking['equipment_id'], rating, comment))
        
        conn.commit()
        conn.close()

        flash("Thank you! Feedback submitted.")
        # 4. CHANGED: Correct redirect name
        return redirect(url_for('my_bookings'))

    return render_template('give_feedback.html', booking_id=booking_id)
from flask import make_response
from fpdf import FPDF

@app.route('/download_invoice/<int:booking_id>')
def download_invoice(booking_id):
    if 'user_id' not in session:
        return redirect(url_for('customer_login'))
    
    conn = get_db_connection()
    query = '''
        SELECT b.id, e.name as equip_name, c.name as cust_name, 
               v.shop_name, b.start_date, b.end_date, 
               b.total_price, b.booking_date
        FROM bookings b
        JOIN equipment e ON b.equipment_id = e.id
        JOIN customer c ON b.customer_id = c.id
        JOIN vendor v ON b.vendor_id = v.id
        WHERE b.id = ?
    '''
    row = conn.execute(query, (booking_id,)).fetchone()
    conn.close()
    
    if not row: return "Invoice not found", 404

    # Tax Math
    total = abs(row['total_price'])
    base = total / 1.18
    gst = total - base

    pdf = FPDF()
    pdf.add_page()
    
    # 1. HEADER AREA
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "AGRIRENT EQUIPMENT RENTALS", 0, 1, 'C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 5, "Official Payment Receipt", 0, 1, 'C')
    pdf.ln(10)

    # 2. BOOKING & CUSTOMER INFO (Boxed Look)
    pdf.set_draw_color(220, 220, 220)
    pdf.set_fill_color(250, 250, 250)
    pdf.rect(10, 35, 190, 25, 'F')
    
    pdf.set_xy(15, 40)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 5, "Booking ID:", 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(70, 5, f"#BK-00{row['id']}", 0)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 5, "Date:", 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(50, 5, f"{row['booking_date']}", 0, 1)
    
    pdf.set_x(15)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 5, "Customer:", 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(70, 5, str(row['cust_name']), 0)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 5, "Vendor:", 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(50, 5, str(row['shop_name']), 0, 1)
    pdf.ln(15)

    # 3. DESCRIPTION TABLE
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(100, 8, "DESCRIPTION", 'B', 0)
    pdf.cell(50, 8, "PERIOD", 'B', 0, 'C')
    pdf.cell(40, 8, "AMOUNT", 'B', 1, 'R')

    pdf.ln(2)
    pdf.set_font("Arial", '', 10)
    # Equipment Name
    pdf.cell(100, 10, f"{row['equip_name']}", 0, 0)
    # Rental Period
    pdf.cell(50, 10, f"{row['start_date'][:10]} to {row['end_date'][:10]}", 0, 0, 'C')
    # Total Price
    pdf.cell(40, 10, f"INR {total:,.2f}", 0, 1, 'R')
    pdf.ln(5)

    # 4. SUMMARY BOX (Right Aligned)
    pdf.line(130, pdf.get_y(), 200, pdf.get_y()) 
    pdf.ln(2)
    
    pdf.set_x(130)
    pdf.cell(35, 7, "Item Price:", 0, 0)
    pdf.cell(35, 7, f"INR {base:,.2f}", 0, 1, 'R')
    
    pdf.set_x(130)
    pdf.cell(35, 7, "GST (18%):", 0, 0)
    pdf.cell(35, 7, f"INR {gst:,.2f}", 0, 1, 'R')
    
    # Final Double Line for Total
    pdf.set_draw_color(0, 0, 0)
    pdf.line(130, pdf.get_y()+1, 200, pdf.get_y()+1)
    pdf.line(130, pdf.get_y()+2, 200, pdf.get_y()+2)
    
    pdf.ln(4)
    pdf.set_x(130)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(35, 10, "AMOUNT PAID:", 0, 0)
    pdf.cell(35, 10, f"INR {total:,.2f}", 0, 1, 'R')

    # 5. FOOTER
    pdf.set_y(-25)
    pdf.set_font("Arial", 'I', 9)
    pdf.cell(190, 5, "Thank you for your business!", 0, 1, 'C')

    # Output to Browser
    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers.set('Content-Disposition', 'attachment', filename=f'invoice_{booking_id}.pdf')
    response.headers.set('Content-Type', 'application/pdf')
    return response
@app.route('/customer_browse_equipment')
def customer_browse_equipment():
    if 'user_id' not in session:
        return redirect(url_for('customer_login'))
    
    search_query = request.args.get('search', '')
    conn = get_db_connection()
    
    # 1. FIXED: Changed '=' to 'IN' for the status check
    # 2. FIXED: Removed the date('now') check so it's hidden immediately once confirmed
    base_query = '''
        SELECT equipment.*, vendor.shop_name, vendor.city
        FROM equipment 
        JOIN vendor ON equipment.vendor_id = vendor.id 
        WHERE vendor.status = 'Approved'
        AND equipment.id NOT IN (
            SELECT equipment_id 
            FROM bookings 
            WHERE status IN ('Confirmed', 'Completed')
            OR (status = 'Returned' AND datetime(return_time, '+1 hour') > datetime('now'))
        )
    '''
    
    if search_query:
        # We wrap the original filters in parentheses to keep the availability logic strong
        final_query = base_query + " AND (name LIKE ? OR vendor.city LIKE ? OR type LIKE ?)"
        rows = conn.execute(final_query, 
                            ('%'+search_query+'%', '%'+search_query+'%', '%'+search_query+'%')).fetchall()
    else:
        rows = conn.execute(base_query).fetchall()
        
    conn.close()
    
    # Note: I removed the extra 'equipment_list' line to keep your code efficient
    return render_template('customer_browse_equipment.html', equipment=rows)
@app.route('/admin_view_bookings')
def admin_view_bookings():
    # Make sure this matches your login session key (admin_id or admin_logged_in)
    if 'admin_id' not in session and not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
   # Updated to match your 'vendor' table and 'shop_name' column
    query = '''
    SELECT 
        b.id, 
        c.name as customer_name, 
        e.name as equipment_name, 
        v.shop_name as vendor_name, 
        b.total_price, 
        b.status, 
        b.booking_date 
    FROM bookings b
    JOIN customer c ON b.customer_id = c.id
    JOIN equipment e ON b.equipment_id = e.id
    JOIN vendor v ON b.vendor_id = v.id
    ORDER BY b.id DESC
    '''
    bookings_data = conn.execute(query).fetchall()
    conn.close()
    return render_template('admin_view_bookings.html', bookings=bookings_data)

@app.route('/admin_view_feedback')
def admin_view_feedback():
    if 'admin_id' not in session and not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    # Updated to match your 'vendor' table and 'shop_name' column
    query = '''
        SELECT 
            f.id, 
            c.name as customer_name,
            e.name as equipment_name, 
            v.shop_name as vendor_name,
            f.rating, 
            f.comment as feedback_message
        FROM feedback f
        LEFT JOIN bookings b ON f.booking_id = b.id
        LEFT JOIN customer c ON b.customer_id = c.id
        LEFT JOIN equipment e ON b.equipment_id = e.id
        LEFT JOIN vendor v ON e.vendor_id = v.id
        ORDER BY f.id DESC
    '''
    feedback_data = conn.execute(query).fetchall()
    conn.close()
    return render_template('admin_view_feedback.html', feedbacks=feedback_data)
@app.route('/update_status/<int:id>/<string:status>')
def update_status(id, status):
    if 'vendor_id' not in session:
        return redirect(url_for('vendor_login'))
    
    conn = get_db_connection()
    # If the button 'Confirm' is pressed, status becomes 'Approved'
    # If the button 'Complete' is pressed, status becomes 'Completed'
    conn.execute('UPDATE bookings SET status = ? WHERE id = ?', (status, id))
    conn.commit()
    conn.close()
    return redirect(url_for('vendor_view_bookings'))
@app.route('/update_status_customer/<int:id>/<string:status>')
def update_status_customer(id, status):
    if 'user_id' not in session:
        return redirect(url_for('customer_login'))
    
    conn = get_db_connection()
    # This allows the 'Return' button to update the status to 'Returned'
    conn.execute('UPDATE bookings SET status = ? WHERE id = ?', (status, id))
    conn.commit()
    conn.close()
    flash(f"Status updated to {status}!")
    return redirect(url_for('my_bookings'))
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']

        conn = get_db_connection()
        conn.execute('INSERT INTO inquiries (name, email, subject, message) VALUES (?, ?, ?, ?)',
                     (name, email, subject, message))
        conn.commit()
        conn.close()

        flash("Your inquiry has been sent! We will get back to you soon.")
        return redirect(url_for('customer_home'))

    return render_template('contact.html')
@app.route('/send_inquiry', methods=['POST'])
def send_inquiry():
    # 1. Collect data from the Contact HTML form
    name = request.form.get('name')
    email = request.form.get('email')
    subject = request.form.get('subject')
    message_body = request.form.get('message')
    
    # 2. Combine subject and message for a cleaner Admin view
    full_message = f"Subject: {subject}\n\n{message_body}"
    
    conn = get_db_connection()
    # 3. Save to the inquiries table
    conn.execute('INSERT INTO inquiries (name, email, message) VALUES (?, ?, ?)',
                 (name, email, full_message))
    conn.commit()
    conn.close()
    
    flash("Message sent! We will get back to you soon.")
    return redirect(url_for('customer_home'))

@app.route('/admin_view_inquiries')
def admin_view_inquiries():
    # Security check to ensure only Admins can see this
    if 'admin_id' not in session and not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    # Fetch messages so the Admin can read what was sent
    inquiries_data = conn.execute('SELECT * FROM inquiries ORDER BY id DESC').fetchall()
    conn.close()
    
    return render_template('admin_view_inquiries.html', inquiries=inquiries_data)
@app.route('/vendor_sales')
def vendor_sales():
    if 'vendor_id' not in session: 
        return redirect(url_for('vendor_login'))
    
    vendor_id = session['vendor_id']
    conn = get_db_connection()
    
    # 1. UPDATED QUERY: Joins with the NEW 'feedback' table
    # We use abs(b.total_price) to fix the minus symbol error
    sales = conn.execute('''
        SELECT b.id, e.name as equip_name, c.name as cust_name, 
               abs(b.total_price) as total_price, 
               f.rating, f.comment as feedback_message, b.booking_date
        FROM bookings b
        JOIN equipment e ON b.equipment_id = e.id
        JOIN customer c ON b.customer_id = c.id
        LEFT JOIN feedback f ON b.id = f.booking_id
        WHERE b.vendor_id = ? AND b.status IN ('Completed', 'Returned', 'Reviewed')
    ''', (vendor_id,)).fetchall()
    
    # 2. TOTAL REVENUE: Sums the cleaned positive prices
    total_revenue = sum(row['total_price'] for row in sales) if sales else 0
    
    conn.close()
    return render_template('vendor_sales.html', sales=sales, total_revenue=total_revenue)

@app.route('/vendor_feedback')
def vendor_feedback():
    if 'vendor_id' not in session:
        return redirect(url_for('vendor_login'))
    
    conn = get_db_connection()
    # FIX: We join with 'equipment' to get the name and 'customer' to get the buyer's name
    feedbacks = conn.execute('''
        SELECT c.name as cust_name, e.name as equip_name, 
               f.rating, f.comment as feedback_message
        FROM feedback f
        JOIN bookings b ON f.booking_id = b.id
        JOIN customer c ON b.customer_id = c.id
        JOIN equipment e ON b.equipment_id = e.id
        WHERE b.vendor_id = ?
    ''', (session['vendor_id'],)).fetchall()
    
    conn.close()
    return render_template('vendor_feedback.html', feedbacks=feedbacks)
@app.route('/vendor_analytics')
def vendor_analytics():
    if 'vendor_id' not in session: 
        return redirect(url_for('vendor_login'))
        
    vendor_id = session['vendor_id']
    conn = get_db_connection()
    
    # STATUS COUNTS for the analytics dashboard
    stats = conn.execute('''
        SELECT status, COUNT(*) as count 
        FROM bookings 
        WHERE vendor_id = ? 
        GROUP BY status
    ''', (vendor_id,)).fetchall()
    
    conn.close()
    return render_template('vendor_analytics.html', stats=stats)

@app.route('/logout')
def logout():
    # 1. Clear all user data from the session
    session.clear() 
    
    # 2. Show a quick message to the user
    flash("You have been logged out successfully.") 
    
    # 3. Send the user back to the main login page
    # Replace 'index' with the name of your main login function if different
    return redirect(url_for('home'))
@app.route('/contact')
def contact_page():
    return render_template('contact.html')
@app.route('/search_equipment', methods=['GET'])
def search_equipment():
    query = request.args.get('query', '')
    conn = get_db_connection()
    
    # Search by equipment name or category
    if query:
        # Use % wildcard for partial matches
        search_results = conn.execute('''
            SELECT * FROM equipment 
            WHERE name LIKE ? OR category LIKE ?
        ''', ('%' + query + '%', '%' + query + '%')).fetchall()
    else:
        results = conn.execute("SELECT * FROM equipment WHERE name LIKE ?", 
                          ('%'+query+'%',)).fetchall()
    
    conn.close()
    # Return to the dashboard but with the filtered results
    return render_template('customer_dashboard.html', equipment=results)
@app.route('/payment/<int:booking_id>', methods=['GET', 'POST'])
def payment(booking_id):
    if 'user_id' not in session:
        return redirect(url_for('customer_login'))

    conn = get_db_connection()
    # 1. Fetch booking and ensure it belongs to the logged-in customer
    booking = conn.execute('SELECT * FROM bookings WHERE id = ? AND customer_id = ?', 
                           (booking_id, session['user_id'])).fetchone()
    
    if not booking:
        conn.close()
        flash("Unauthorized access or booking not found.")
        return redirect(url_for('my_bookings'))

    # 2. Handle the "Confirm Payment" button click (The POST request)
    if request.method == 'POST':
        # Update database to 'Paid' permanently
        conn.execute('UPDATE bookings SET payment_status = "Paid" WHERE id = ?', (booking_id,))
        conn.commit()
        conn.close()
        
        # Calculate positive amount for the success screen
        display_price = abs(booking['total_price'])
        
        # IMPORTANT: We return the same page with success=True 
        # This tells your HTML to show the ✅ Success Overlay
        return render_template('payment.html', booking=booking, amount=display_price, success=True)

    # 3. Handle the initial page load (The GET request)
    conn.close()
    display_price = abs(booking['total_price'])
    return render_template('payment.html', booking=booking, amount=display_price)




if __name__ == '__main__':
    init_db()
    app.run(debug=True)
    