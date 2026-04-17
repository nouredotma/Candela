"""
CHATROOM-P — Flask Chatroom Web App
A real-time chatroom where users can join rooms, chat, and see who's online.
No registration required to chat, but optional account creation to reserve a username.
"""

import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from flask_session import Session
import bcrypt

# ── Flask App Setup ──────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "chatroom_secret_key_2026"

# Server-side session configuration
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(os.path.dirname(__file__), "flask_session")
app.config["SESSION_PERMANENT"] = False
Session(app)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MESSAGES_DIR = os.path.join(DATA_DIR, "messages")
ROOMS_FILE = os.path.join(DATA_DIR, "rooms.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ONLINE_FILE = os.path.join(DATA_DIR, "online.json")
UPLOADS_DIR = os.path.join(BASE_DIR, "static", "uploads")


# ── Helper Functions ─────────────────────────────────────────────────────────

def init_data():
    """Initialize all JSON files and directories if they don't exist."""
    # Create directories
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MESSAGES_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    # Initialize rooms.json with default "general" room
    if not os.path.exists(ROOMS_FILE):
        default_rooms = [
            {"name": "general", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        ]
        save_json(ROOMS_FILE, default_rooms)

    # Initialize users.json
    if not os.path.exists(USERS_FILE):
        save_json(USERS_FILE, [])

    # Initialize online.json
    if not os.path.exists(ONLINE_FILE):
        save_json(ONLINE_FILE, {})

    # Initialize messages file for "general" room
    general_messages = os.path.join(MESSAGES_DIR, "general.json")
    if not os.path.exists(general_messages):
        save_json(general_messages, [])


def load_json(filepath):
    """Load and return data from a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filepath, data):
    """Save data to a JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_online_users(room):
    """Return list of users currently online in a room (heartbeat within 15s)."""
    online = load_json(ONLINE_FILE)
    if room not in online:
        return []

    now = datetime.now()
    active_users = []
    for username, last_seen in online[room].items():
        last_seen_time = datetime.strptime(last_seen, "%Y-%m-%d %H:%M:%S")
        # User is online if heartbeat was within last 15 seconds
        if (now - last_seen_time) < timedelta(seconds=15):
            active_users.append(username)

    return active_users


def is_username_taken_in_room(username, room):
    """Check if a username is already active in a room."""
    online_users = get_online_users(room)
    return username in online_users


def is_username_registered(username):
    """Check if a username belongs to a registered account."""
    users = load_json(USERS_FILE)
    for user in users:
        if user["username"].lower() == username.lower():
            return True
    return False


def get_sanitized_rooms():
    """Returns all rooms, stripping out passwords to safely send to frontend."""
    rooms = load_json(ROOMS_FILE)
    for r in rooms:
        if "password" in r:
            del r["password"]
    return rooms


def is_room_secure(room_name):
    """Check if a room requires a password."""
    rooms = load_json(ROOMS_FILE)
    for r in rooms:
        if r["name"] == room_name:
            return r.get("is_secure", False)
    return False


def check_room_access(room_name):
    """Returns True if the user has access to the room (not secure, or unlocked in session)."""
    if not is_room_secure(room_name):
        return True
    unlocked_rooms = session.get("unlocked_rooms", [])
    return room_name in unlocked_rooms


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Index/join page."""
    rooms = get_sanitized_rooms()
    return render_template("index.html", rooms=rooms)


@app.route("/join", methods=["POST"])
def join():
    """Set username in session, redirect to room."""
    username = request.form.get("username", "").strip()
    room = request.form.get("room", "general").strip()

    # Validate input
    if not username:
        rooms = get_sanitized_rooms()
        return render_template("index.html", rooms=rooms, error="Username is required.")

    # Check if username is registered (guest trying to use a registered name)
    if is_username_registered(username) and not session.get("logged_in"):
        rooms = get_sanitized_rooms()
        return render_template("index.html", rooms=rooms, error="This username is registered, please login.")

    # Check for duplicate username in the room
    if is_username_taken_in_room(username, room):
        rooms = get_sanitized_rooms()
        return render_template("index.html", rooms=rooms, error="Username is already taken in this room.")

    # Set session
    session["username"] = username
    session["room"] = room

    return redirect(f"/chat/{room}")


@app.route("/chat/<room>")
def chat(room):
    """Main chat page."""
    # Check if user has a username in session
    if "username" not in session:
        return redirect("/")

    # Check if room exists
    safe_rooms = get_sanitized_rooms()
    room_names = [r["name"] for r in safe_rooms]
    if room not in room_names:
        return redirect("/")

    # Update session room
    session["room"] = room
    
    is_secure = is_room_secure(room)
    is_unlocked = check_room_access(room)

    return render_template("chat.html", room=room, username=session["username"], rooms=safe_rooms, is_secure=is_secure, is_unlocked=is_unlocked)


@app.route("/send", methods=["POST"])
def send():
    """Save a new message to room's JSON file."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.json
    room = data.get("room", session.get("room", "general"))
    
    if not check_room_access(room):
        return jsonify({"error": "Room is secure and locked"}), 403

    message_text = data.get("message", "").strip()
    image = data.get("image", None)

    if not message_text and not image:
        return jsonify({"error": "Message cannot be empty"}), 400

    # Build message object
    msg = {
        "username": session["username"],
        "message": message_text,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "text"
    }

    # If there's an image attachment
    if image:
        msg["image"] = image
        msg["type"] = "image"

    # Load existing messages and append
    messages_file = os.path.join(MESSAGES_DIR, f"{room}.json")
    if os.path.exists(messages_file):
        messages = load_json(messages_file)
    else:
        messages = []

    messages.append(msg)
    save_json(messages_file, messages)

    return jsonify({"status": "ok"})


@app.route("/messages/<room>")
def messages(room):
    """Return all messages for a room as JSON."""
    if not check_room_access(room):
        return jsonify({"error": "Room is secure and locked"}), 403

    messages_file = os.path.join(MESSAGES_DIR, f"{room}.json")
    if os.path.exists(messages_file):
        msgs = load_json(messages_file)
    else:
        msgs = []
    return jsonify(msgs)


@app.route("/rooms")
def rooms():
    """Return list of all rooms as JSON."""
    room_list = get_sanitized_rooms()
    return jsonify(room_list)


@app.route("/online/<room>")
def online(room):
    """Return list of online users in room as JSON."""
    if not check_room_access(room):
        return jsonify([])

    users = get_online_users(room)
    return jsonify(users)


@app.route("/create-room", methods=["POST"])
def create_room():
    """Create a new room."""
    data = request.json
    room_name = data.get("name", "").strip().lower().replace(" ", "-")
    password = data.get("password", "").strip()

    if not room_name:
        return jsonify({"error": "Room name is required"}), 400

    # Load existing rooms
    rooms = load_json(ROOMS_FILE)
    room_names = [r["name"] for r in rooms]

    if room_name in room_names:
        return jsonify({"error": "Room already exists"}), 400

    # Add new room
    rooms.append({
        "name": room_name,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_secure": bool(password),
        "password": password if password else None
    })
    save_json(ROOMS_FILE, rooms)
    
    # Unlock for the creator
    if password:
        session_unlocked = session.get("unlocked_rooms", [])
        session_unlocked.append(room_name)
        session["unlocked_rooms"] = session_unlocked

    # Create empty messages file for the room
    messages_file = os.path.join(MESSAGES_DIR, f"{room_name}.json")
    save_json(messages_file, [])

    return jsonify({"status": "ok", "name": room_name})


@app.route("/register", methods=["POST"])
def register():
    """Register account (username + password, bcrypt hashed)."""
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    # Check if username is already registered
    users = load_json(USERS_FILE)
    for user in users:
        if user["username"].lower() == username.lower():
            return jsonify({"error": "Username is already registered"}), 400

    # Hash password with bcrypt
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    users.append({
        "username": username,
        "password": hashed.decode("utf-8")
    })
    save_json(USERS_FILE, users)

    # Auto-login after registration
    session["username"] = username
    session["logged_in"] = True

    return jsonify({"status": "ok"})


@app.route("/login", methods=["POST"])
def login():
    """Login to account."""
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    # Find user
    users = load_json(USERS_FILE)
    for user in users:
        if user["username"].lower() == username.lower():
            # Verify password
            if bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
                session["username"] = user["username"]
                session["logged_in"] = True
                return jsonify({"status": "ok"})
            else:
                return jsonify({"error": "Incorrect password"}), 401

    return jsonify({"error": "User not found"}), 404


@app.route("/logout")
def logout():
    """Logout, clear session."""
    session.clear()
    return redirect("/")


@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    """Called every 5s by JS to mark user as online in room."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.json
    room = data.get("room", session.get("room", "general"))
    
    if not check_room_access(room):
        return jsonify({"error": "Room is secure and locked"}), 403

    online = load_json(ONLINE_FILE)

    if room not in online:
        online[room] = {}

    online[room][session["username"]] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_json(ONLINE_FILE, online)

    return jsonify({"status": "ok"})


@app.route("/upload", methods=["POST"])
def upload():
    """Upload an image attachment."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    room = session.get("room", "general")
    if not check_room_access(room):
        return jsonify({"error": "Room is secure and locked"}), 403

    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{session['username']}_{timestamp}_{file.filename}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    file.save(filepath)

    return jsonify({"status": "ok", "filename": filename})


@app.route("/unlock-room", methods=["POST"])
def unlock_room():
    """Unlock a secure room with a password."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.json
    room_name = data.get("room", "").strip()
    password = data.get("password", "").strip()

    rooms = load_json(ROOMS_FILE)
    room_data = next((r for r in rooms if r["name"] == room_name), None)

    if not room_data:
        return jsonify({"error": "Room not found"}), 404

    if not room_data.get("is_secure"):
        return jsonify({"status": "ok"})

    if room_data.get("password") == password:
        unlocked = session.get("unlocked_rooms", [])
        if room_name not in unlocked:
            unlocked.append(room_name)
            session["unlocked_rooms"] = unlocked
            session.modified = True
        return jsonify({"status": "ok"})
    else:
        return jsonify({"error": "Incorrect password"}), 401


# ── Initialize and Run ───────────────────────────────────────────────────────
init_data()
app.run(debug=True)
