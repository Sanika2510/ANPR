from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/admin_login', methods=['POST'])
def admin_login():
    username = request.form['username']
    password = request.form['password']
    # Add logic to validate admin credentials
    return redirect(url_for('admin_home'))

@app.route('/common_person_login', methods=['POST'])
def common_person_login():
    username = request.form['username']
    password = request.form['password']
    # Add logic to validate common person credentials
    return redirect(url_for('common_person_home'))

@app.route('/register_user', methods=['POST'])
def register_user():
    username = request.form['username']
    password = request.form['password']
    # Add logic to register the new user
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
