from flask import Flask, request, render_template, jsonify, session, redirect, url_for, flash # Import flash for messages
from flask_socketio import SocketIO, emit, disconnect
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy # NEW: For database interaction
from werkzeug.security import generate_password_hash, check_password_hash # NEW: For password hashing

import time

app = Flask(__name__)

# --- Database Configuration (NEW) ---
# SQLite database file path
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
# Disable tracking modifications for better performance (unless you specifically need it)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app) # Initialize SQLAlchemy

# --- Flask App Configuration (Existing) ---
app.config['SECRET_KEY'] = 'your_super_long_and_secret_key_1234567890abcdef' # !!! CHANGE THIS IN PRODUCTION !!!
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)


# --- User Model (NEW) ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# --- Chatbot Logic (unchanged) ---
knowledge_base = {
    "hello": "Hi there! How can I help you today?",
    "hi": "Hello! What can I do for you?",
    "how are you": "I'm just a bot, but I'm doing great! Thanks for asking.",
    "your name": "I am a simple chatbot created to assist you.",
    "bye": "Goodbye! Have a great day!",
    "thanks": "You're welcome!",
    "thank you": "You're very welcome!",
    "hours": "Our operating hours are from 9 AM to 5 PM, Monday to Friday.",
    "address": "We are located at 123 Chatbot Street, Botville.",
    "contact": "You can reach us at support@example.com or call us at 555-123-4567.",
    "services": "We offer AI solutions, web development, and IT consulting.",
}

def get_bot_response(user_input):
    user_input_lower = user_input.lower()
    response = "I'm sorry, I don't understand that. Please try rephrasing or ask about 'hours', 'address', or 'contact'."
    if user_input_lower in knowledge_base:
        response = knowledge_base[user_input_lower]
    else:
        for key, value in knowledge_base.items():
            if key in user_input_lower:
                response = value
                break
    return response

# --- Multi-User Chat System Logic (modified to use session username) ---
messages = [] # In-memory message store for multi-user chat

@socketio.on('connect')
def handle_connect():
    # Print the full session dictionary to see its contents
    print(f"DEBUG_SOCKETIO: Client connected. Session on connect: {dict(session)}")
    username = session.get('username')
    if not username:
        print(f"DEBUG_SOCKETIO: Unauthorized client (no username in session) trying to connect: {request.sid}")
        disconnect()
        return

    print(f'DEBUG_SOCKETIO: Client {username} connected to multi-user chat: {request.sid}')
    emit('history', messages, room=request.sid)
    emit('message', {'sender': 'System', 'message': f'{username} has joined the chat.'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username', 'Anonymous (session lost)') # Added debug fallback
    print(f'DEBUG_SOCKETIO: Client {username} disconnected from multi-user chat: {request.sid}')
    emit('message', {'sender': 'System', 'message': f'{username} has left the chat.'}, broadcast=True)

@socketio.on('message')
def handle_message(data):
    username = session.get('username')
    if not username:
        print(f"DEBUG_SOCKETIO: Message from unauthorized client (session lost during message): {request.sid}")
        return

    user_message = data.get('message', '').strip()
    if not user_message:
        return

    message_data = {
        'sender': username,
        'message': user_message,
        'timestamp': time.time()
    }
    messages.append(message_data)
    emit('message', message_data, broadcast=True)

# --- FLASK ROUTES (modified for more verbose session debugging) ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username') # Use .get()
        password = request.form.get('password')

        print(f"DEBUG_REGISTER: Attempting to register username: {username}") # Debug print

        if not username or not password:
            flash('Username and password cannot be empty.')
            print("DEBUG_REGISTER: Username or password empty.")
            return render_template('register.html')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.')
            print(f"DEBUG_REGISTER: Username '{username}' already exists.")
            return render_template('register.html')

        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! You can now log in.')
        print(f"DEBUG_REGISTER: User '{username}' registered successfully.")
        return redirect(url_for('login'))
    print("DEBUG_REGISTER: Displaying registration form (GET).")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        print(f"DEBUG_LOGIN: Already logged in as {session['username']}, redirecting to chat_system.")
        return redirect(url_for('chat_system_page'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        print(f"DEBUG_LOGIN: Attempting login for username: {username}") # Debug print

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['username'] = username # Store username in session
            print(f"DEBUG_LOGIN: Login successful for '{username}'. Session after login: {dict(session)}") # Debug print
            flash('Login successful!')
            return redirect(url_for('chat_system_page'))
        else:
            flash('Invalid username or password.')
            print(f"DEBUG_LOGIN: Invalid login attempt for '{username}'.") # Debug print
            return render_template('login.html')
    print("DEBUG_LOGIN: Displaying login form (GET).")
    return render_template('login.html')

@app.route('/')
def home():
    if 'username' in session:
        print(f"DEBUG_HOME: User '{session['username']}' accessing home page.")
        return f"""
        <h1>Welcome back, {session['username']}!</h1>
        <p>This server hosts two chat systems:</p>
        <ul>
            <li><a href='/chatbot'>Go to Simple Chatbot</a></li>
            <li><a href='/chat_system'>Go to Multi-User Chat System</a></li>
        </ul>
        <p><a href='/logout'>Logout</a></p>
        """
    print("DEBUG_HOME: Anonymous user accessing home page.")
    return """
    <h1>Welcome!</h1>
    <p>This server hosts two chat systems:</p>
    <ul>
        <li><a href='/chatbot'>Go to Simple Chatbot</a></li>
        <li><a href='/login'>Login to Multi-User Chat System</a></li>
        <li><a href='/register'>Register for Multi-User Chat System</a></li>
    </ul>
    """

@app.route('/logout')
def logout():
    username = session.pop('username', None)
    print(f"DEBUG_LOGOUT: User '{username}' logged out. Session after logout: {dict(session)}")
    flash('You have been logged out.')
    return redirect(url_for('home'))

@app.route('/chatbot')
def chatbot_page():
    return render_template('chatbot.html')

@app.route('/chatbot/chat', methods=['POST'])
def chatbot_api():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({'response': 'No message provided'}), 400
    bot_response = get_bot_response(user_message)
    return jsonify({'response': bot_response})

@app.route('/chat_system')
def chat_system_page():
    if 'username' not in session:
        print("DEBUG_CHAT_SYSTEM: User not logged in, redirecting to login.")
        flash('Please login to access the multi-user chat.')
        return redirect(url_for('login'))
    print(f"DEBUG_CHAT_SYSTEM: User '{session['username']}' accessing chat system page.")
    return render_template('chat_system.html', username=session['username'])

# --- Main execution ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, port=5000,)