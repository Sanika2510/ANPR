import os
from flask import Flask, request, render_template, redirect, session, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import cv2
import numpy as np
import pytesseract
import mysql.connector
import secrets
import logging
import re
from flask_mail import Mail, Message
from flask import flash


logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = secrets.token_hex(24)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'kalyanibharsat123@gmail.com'
app.config['MAIL_PASSWORD'] = 'adwo mmtp eqys hpzw'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

mysql_host = 'localhost'
mysql_user = 'root'
mysql_password = 'root'
mysql_database = 'project'

def get_mysql_connection():
    return mysql.connector.connect(
        host=mysql_host,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database
    )

def create_tables():
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS info (
                Id INT AUTO_INCREMENT PRIMARY KEY,
                Case_number VARCHAR(20),
                Date DATE,
                City VARCHAR(20),
                Image MEDIUMBLOB,
                Vehicle_number VARCHAR(20),
                State VARCHAR(20),
                Fine VARCHAR(10)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS login (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role ENUM('admin', 'std', 'user') NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE paid_fines (
            id INT AUTO_INCREMENT PRIMARY KEY,
            Case_number VARCHAR(255) NOT NULL,
            Fine DECIMAL(10, 2) NOT NULL,
            Date_paid TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        conn.commit()
    except mysql.connector.Error as err:
        logging.error(f"Error creating tables: {err}")
    finally:
        if conn:
            conn.close()

create_tables()

def process_image(img_path):
    img = cv2.imread(img_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    bfilter = cv2.bilateralFilter(gray, 11, 17, 17)
    edged = cv2.Canny(bfilter, 30, 200)
    
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

    location = None
    for contour in contours:
        approx = cv2.approxPolyDP(contour, 10, True)
        if len(approx) == 4:
            location = approx
            break

    if location is None:
        return None, "Could not locate the number plate.", None, False

    mask = np.zeros(gray.shape, np.uint8)
    new_image = cv2.drawContours(mask, [location], 0, 255, -1)
    new_image = cv2.bitwise_and(img, img, mask=mask)

    (x, y) = np.where(mask == 255)
    (x1, y1) = (np.min(x), np.min(y))
    (x2, y2) = (np.max(x), np.max(y))
    cropped_image = gray[x1:x2 + 1, y1:y2 + 1]

    text = pytesseract.image_to_string(cropped_image, config='--psm 8')
    
    state = detect_state(text)
    formatted_text = format_license_plate(text.strip())
    if formatted_text:
        if not is_valid_license_plate(formatted_text):
            return None, text.strip(), state, False

        font = cv2.FONT_HERSHEY_SIMPLEX
        res = cv2.putText(img, text=formatted_text, org=(location[0][0][0], location[1][0][1] + 60),
                          fontFace=font, fontScale=1, color=(0, 255, 0), thickness=2, lineType=cv2.LINE_AA)
        res = cv2.rectangle(img, tuple(location[0][0]), tuple(location[2][0]), (0, 255, 0), 3)

        _, img_encoded = cv2.imencode('.jpg', res)
        img_blob = img_encoded.tobytes()

        return img_blob, formatted_text, state, True
    else:
        return None, "No text detected.", None, False

def is_valid_license_plate(text):
    pattern = r'^[A-Z]{2} \d{2} [A-Z]{2} \d{4}$'
    return re.match(pattern, text) is not None

def format_license_plate(text):
    pattern = r'([A-Z]{2})(\d{2})([A-Z]{2})(\d{4})'
    match = re.match(pattern, text)
    if match:
        return f"{match.group(1)} {match.group(2)} {match.group(3)} {match.group(4)}"
    return text

def detect_state(text):
    state_codes = {
        'DL': 'Delhi',
        'MH': 'Maharashtra',
        'HR': 'Haryana',
    }
    
    for code, state in state_codes.items():
        if code in text:
            return state
    
    return "Unknown"

@app.route('/')
def home():
    if 'username' not in session:
        return redirect('/login')
    return redirect('/admin_home') if session.get('role') == 'admin' else redirect('/std')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        if role not in ['admin', 'std','user']:
            return "Invalid role", 400
        
        hashed_password = generate_password_hash(password)
        
        conn = get_mysql_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO login (username, password, role)
                VALUES (%s, %s, %s)
            ''', (username, hashed_password, role))
            conn.commit()
        except mysql.connector.Error as err:
            conn.rollback()
            logging.error(f"Error: {err}")
            return f"Error: {err}", 500
        finally:
            conn.close()
        
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT password, role FROM login WHERE username = %s', (username,))
        result = cursor.fetchone()
        conn.close()
        logging.debug(f"Fetched result for username {username}: {result}")
        if result and check_password_hash(result[0], password):
            session['username'] = username
            session['role'] = result[1]
            logging.debug(f"User {username} has role {result[1]}")
            if result[1] == 'admin':
                return redirect('/admin_home')
            elif result[1] == 'std':
                return redirect('/std')
            elif result[1] == 'user':
                return redirect('/user')
            else:
                logging.error(f"Unknown role {result[1]} for user {username}")
                return "Invalid role", 400

        logging.debug(f"Invalid credentials for username {username}")
        return "Invalid credentials", 401

    return render_template('login.html')
@app.route('/admin_home')
def admin_home():
    if 'username' in session and session.get('role') == 'admin':
        return render_template('admin_home.html')
    return redirect('/')

@app.route('/std')
def std():
    if 'username' in session and session.get('role') == 'std':
        return render_template('std.html')
    return redirect('/')

@app.route('/user')
def user():
    if 'username' in session and session.get('role') == 'user':
        return render_template('user.html')
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect('/')

@app.route('/upload')
def upload_form():
    if 'username' in session and session.get('role') in ['admin', 'std']:
        return render_template('upload.html')
    return redirect('/')

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return redirect(request.url)
    
    case_number = request.form['case_number']
    date = request.form['date']
    city = request.form['city']
    file = request.files['file']
    
    if file.filename == '':
        return redirect(request.url)
    
    if file and case_number and date and city:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            img_blob, text, state, is_valid = process_image(file_path)
            if not is_valid:
                return render_template('result2.html', image_path=file_path, text=text, case_number=case_number, city=city, state=state)
                
            if img_blob:
                conn = get_mysql_connection()
                cursor = conn.cursor()
                
                try:
                    fine_amount = 'No'
                    if not is_valid_license_plate(text):
                        fine_amount = 'No'
                    
                    cursor.execute('''
                        INSERT INTO info (Case_number, Date, City, Image, Vehicle_number, State, Fine)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ''', (case_number, date, city, img_blob, text, state, fine_amount))
                    conn.commit()
                except mysql.connector.Error as err:
                    conn.rollback()
                    logging.error(f"Error: {err}")
                    return f"Error: {err}", 500
                finally:
                    conn.close()
                success_message = f"Number plate detected: {text} is valid."
                return render_template('result.html', image_path=file_path, text=text, state=state, fine=fine_amount)
            else:
                return "Error processing image", 500
        except Exception as e:
            logging.error(f"Error: {e}")
            return f"Error: {e}", 500
    else:
        return "Missing required fields", 400


@app.route('/issue_fine', methods=['POST'])
def issue_fine():
    case_number = request.form['case_number']
    date = request.form['date']
    city = request.form['city']
    state = request.form['state']
    fine = request.form['fine']
    vehicle_number = request.form['vehicle_number']
    user_email = request.form['user_email']
    image = request.files['image']
    
    try:
        img_blob = image.read()

        if not all([case_number, date, city, img_blob, vehicle_number, state, fine, user_email]):
            return "Missing required fields", 400

        conn = get_mysql_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO info (Case_number, Date, City, Image, Vehicle_number, State, Fine)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (case_number, date, city, img_blob, vehicle_number, state, fine))
            conn.commit()

            msg = Message(f"Fine Issued: Case Number {case_number}", sender='your_email@gmail.com', recipients=[user_email])
            msg.body = f"Dear user, please pay your fine for case number {case_number} due to vehicle number {vehicle_number}."
            msg.attach(image.filename, 'image/jpeg', img_blob)
            mail.send(msg)
            logging.info(f"Email sent to {user_email}")

            return redirect('/upload_form?fine_issued=true')
        except mysql.connector.Error as err:
            conn.rollback()
            logging.error(f"Database Error: {err}")
            return f"Database Error: {err}", 500
        except Exception as e:
            logging.error(f"Error: {e}")
            return f"Error: {e}", 500
        finally:
            conn.close()

    except Exception as e:
        logging.error(f"General Error: {e}")
        return f"General Error: {e}", 500

    
@app.route('/invalid_format')
def invalid_format():
    return render_template('invalid_format.html')

@app.route('/view_records')
def view_records():
    if 'username' in session and session.get('role') == 'admin':
        conn = get_mysql_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT Id, Case_number, Fine FROM info WHERE Status = 'Paid'")
        paid_records = cursor.fetchall()

        for record in paid_records:
            cursor.execute('''
                INSERT INTO paid_fines (Case_number, Fine, Date_paid)
                VALUES (%s, %s, NOW())  -- Assuming you want to set Date_paid to current timestamp
            ''', (record[1], record[2]))
            cursor.execute('DELETE FROM info WHERE Id = %s', (record[0],))

        conn.commit()

        cursor.execute("SELECT Id, Case_number, Date, City, Vehicle_number, State, Fine FROM info WHERE Status IS NULL")
        records = cursor.fetchall()

        cursor.execute('SELECT Case_number, Fine, Date_paid FROM paid_fines')
        paid_fines = cursor.fetchall()

        conn.close()

        return render_template('view_records.html', records=records, paid_fines=paid_fines)
    
    return redirect('/')


@app.route('/edit_record/<int:record_id>', methods=['POST'])
def edit_record(record_id):
    if 'username' in session and session.get('role') == 'admin':
        conn = get_mysql_connection()
        cursor = conn.cursor()

        case_number = request.form['case_number']
        date = request.form['date']
        city = request.form['city']
        fine = request.form['fine']

        try:
            fine_amount = float(fine) if fine != 'Paid' else 0
            status = 'Paid' if fine == 'Paid' else None

            if status == 'Paid':
                cursor.execute('''
                    INSERT INTO paid_fines (Case_number, Fine)
                    SELECT Case_number, Fine FROM info WHERE Id = %s
                ''', (record_id,))
                cursor.execute('DELETE FROM info WHERE Id = %s', (record_id,))
            else:
                cursor.execute('''
                    UPDATE info
                    SET Case_number = %s, Date = %s, City = %s, Fine = %s, Status = %s
                    WHERE Id = %s
                ''', (case_number, date, city, fine_amount, status, record_id))

            conn.commit()
            flash('Record updated successfully!', 'success')
            return redirect('/view_records')
        except ValueError:
            flash('Invalid fine value.', 'error')
        except mysql.connector.Error as err:
            conn.rollback()
            logging.error(f"Error: {err}")
            flash(f"Error: {err}", 'error')
        finally:
            conn.close()

    return redirect('/')

@app.route('/delete_record/<int:record_id>', methods=['POST'])
def delete_record(record_id):
    if 'username' in session and session.get('role') == 'admin':
        conn = get_mysql_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM info WHERE Id = %s', (record_id,))
            conn.commit()
            return redirect('/view_records')
        except mysql.connector.Error as err:
            conn.rollback()
            logging.error(f"Error: {err}")
            return f"Error: {err}", 500
        finally:
            conn.close()
    return redirect('/')

@app.route('/view_fines', methods=['POST', 'GET'])
def view_fines():
    if 'username' not in session or session.get('role') != 'user':
        return redirect('/login')
    
    if request.method == 'POST':
        vehicle_number = request.form['vehicle_number']
        
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True) 
        try:
            cursor.execute('''
                SELECT Case_number, Date, City, Fine
                FROM info
                WHERE Vehicle_number = %s
            ''', (vehicle_number,))
            fines = cursor.fetchall()
        except mysql.connector.Error as err:
            logging.error(f"Database Error: {err}")
            return f"Database Error: {err}", 500
        finally:
            conn.close()

        return render_template('view_fines.html', fines=fines, vehicle_number=vehicle_number)

    return render_template('view_fines.html', fines=None)

@app.route('/pay_fine', methods=['POST'])
def pay_fine():
    case_number = request.form['case_number']
    
    qr_code_url = f"https://example.com/qr_code?case_number={case_number}"
    
    conn = get_mysql_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE info
        SET Fine = 'Paid'
        WHERE Case_number = %s
    ''', (case_number,))
    conn.commit()
    conn.close()
    
    return render_template('payment.html', qr_code_url=qr_code_url, case_number=case_number)
@app.route('/payment_success', methods=['POST'])
def payment_success():
    case_number = request.form['case_number']
    payment_method = request.form['payment_method']
    file = request.files['file']
    transaction_id = request.form['transaction_id']

    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)

    conn = get_mysql_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO paid_fines (Case_number, Fine)
            VALUES (%s, 'Paid')
        ''', (case_number,))
        
        cursor.execute('DELETE FROM info WHERE Case_number = %s AND Fine = %s', (case_number, 'Paid'))
        
        conn.commit()
        flash('Payment processed successfully!', 'success')
    except mysql.connector.Error as err:
        conn.rollback()
        logging.error(f"Database Error: {err}")
        flash(f"Database Error: {err}", 'error')
    finally:
        conn.close()

    return render_template('payment_success.html', transaction_id=transaction_id)


if __name__ == "__main__":
    app.run(debug=True, port=8000)
