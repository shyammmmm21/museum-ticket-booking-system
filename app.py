from flask import Flask, render_template, redirect, url_for, request, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
import stripe
from flask_cors import CORS
from models import db  # Import the db from model.py
from chatbot import get_chatbot_response
from twilio.rest import Client
import random


app = Flask(__name__)
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://neondb_owner:npg_cMRhUP9X5TBL@ep-lucky-resonance-a1u4g96d-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
app.config['STRIPE_PUBLIC_KEY'] = 'pk_test_51R2udxQFJxlWlDpbPoAAibYucvR0qnNNAhh50sE0RO3r2QLRO1jc4G4SYaoCkQJci7iZrUb3PfQ2JkiaZ1YIWXf700hRU5NKcA'
app.config['STRIPE_SECRET_KEY'] = 'sk_test_51R2udxQFJxlWlDpbeojJgZRawSaqaLI1XxTJ9cZ4HzogRybbQJ2VUnPb7RxA8gk1fs7werG3Rh8KqU6ETfiFuTQo00yBl9Kj1n'

# Initialize the app with the db
db.init_app(app)

babel = Babel(app)
CORS(app)

stripe.api_key = app.config['STRIPE_SECRET_KEY']

# Twilio Credentials
TWILIO_ACCOUNT_SID = "ACc516b0f17ac530acaa907c790cbc99f9"
TWILIO_AUTH_TOKEN = "30da48f265d96b6f51e94c6bd117cbff"
TWILIO_PHONE_NUMBER = "+919825927350"

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def get_locale():
    return session.get('locale', 'en')

babel.init_app(app, locale_selector=get_locale)

@app.context_processor
def inject_get_locale():
    return dict(get_locale=get_locale)


@app.route('/set_locale/<locale>')
def set_locale(locale):
    session['locale'] = locale
    return redirect(request.referrer)

@app.route('/test_locale')
def test_locale():
    return f"Current locale: {get_locale()}"

@app.route('/logout')
def logout():
    # Logic to log out the user, e.g., clearing the session
    session.clear()
    return redirect(url_for('login'))  # Redirect to the login page or homepage

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/view')
def view():
    return render_template('view.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Process form data
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        
        # Here you can handle the form data, e.g., send an email, save to a database, etc.
        
        return "Thank you for your message!"  # Or redirect to a 'thank you' page
    return render_template('contact.html')



@app.route('/')
def home():
    return render_template('home.html')

# Generate OTP
def generate_otp():
    return str(random.randint(100000, 999999))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        mobile = request.form['mobile']

        if not mobile.startswith("+"):
            mobile = f"+91{mobile}"
            
        # Generate and store OTP
        otp = generate_otp()
        session['otp'] = otp
        session['username'] = username
        session['password'] = password
        session['mobile'] = mobile

        # Send OTP via Twilio
        try:
            client.messages.create(
                body=f"Your OTP is {otp}",
                from_="+16514326138",
                to="+919825927350"
            )
            flash("OTP sent to your mobile number.", "info")
            return redirect(url_for('verify_otp'))
        except Exception as e:
            flash(f"Error sending OTP: {e}", "danger")
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    from models import User
    if request.method == 'POST':
        user_otp = request.form['otp']
        if user_otp == session.get('otp'):
            # OTP verified, create user
            new_user = User(username=session['username'], password=session['password'], mobile=session['mobile'])
            new_user.set_password(session['password'])  # Hash the password before storing
            db.session.add(new_user)
            db.session.commit()

            # Clear session data
            session.pop('otp', None)
            session.pop('username', None)
            session.pop('password', None)
            session.pop('mobile', None)

            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for('login'))
        else:
            flash("Invalid OTP. Please try again.", "danger")

    return render_template('verify_otp.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        from models import User  # Import User model
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):  # Verify hashed password
            session['user_id'] = user.id
            return redirect(url_for('book_ticket'))
        else:
            flash("Invalid username or password.", "danger")

    return render_template('login.html')    

@app.route('/book_ticket', methods=['GET', 'POST'])
def book_ticket():
    if request.method == 'POST':
        from models import Ticket
        age = int(request.form['age'])
        if age < 18:
            return "You must be 18 or older to book a ticket."
        ticket = Ticket(
            name=request.form['name'],
            age=age,
            email=request.form['email'],
            user_id=session['user_id']
        )
        db.session.add(ticket)
        db.session.commit()
        return redirect(url_for('payment', ticket_id=ticket.id))
    return render_template('book_ticket.html')

@app.route('/my_tickets')
def my_tickets():
    from models import Ticket
    user_id = session['user_id']
    tickets = Ticket.query.filter_by(user_id=user_id).all()
    return render_template('my_tickets.html', tickets=tickets)

@app.route('/delete_ticket/<int:ticket_id>', methods=['POST'])
def delete_ticket(ticket_id):
    from models import Ticket
    Ticket.query.filter_by(id=ticket_id).delete()
    db.session.commit()
    return redirect(url_for('my_tickets'))

@app.route('/payment/<int:ticket_id>', methods=['GET', 'POST'])
def payment(ticket_id):
    if request.method == 'POST':
        try:
            stripe.PaymentIntent.create(
                amount=1000,  # amount in cents
                currency='usd',
                payment_method=request.form['payment_method_id'],
                confirmation_method='manual',
                confirm=True
            )
            return "Payment successful!"
        except Exception as e:
            return f"An error occurred: {str(e)}", 400  # Better error handling
    return render_template('payment.html', stripe_public_key=app.config['STRIPE_PUBLIC_KEY'], ticket_id=ticket_id)


@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    if request.method == 'POST':
        data = request.get_json()
        user_message = data.get('message')
        bot_response = get_chatbot_response(user_message)
        return jsonify({"response": bot_response})
    else:
        return render_template('chatbot.html')
    
@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()




if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    app.run(debug=True)
