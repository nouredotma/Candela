"""
CHATROOM-P — Flask Chatroom Web App
A real-time chatroom where users can join rooms, chat, and see who's online.
No registration required to chat, but optional account creation to reserve a username.
"""

import os
import json
import string
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from flask_session import Session
import re
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
    rooms = []
    if os.path.exists(ROOMS_FILE):
        try:
            rooms = load_json(ROOMS_FILE)
        except:
            rooms = []
    
    # Ensure "general" exists
    if not any(r["name"] == "general" for r in rooms):
        rooms.insert(0, {
            "name": "general", 
            "creator": "System",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_secure": False
        })
        save_json(ROOMS_FILE, rooms)

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
    sanitized = []
    for r in rooms:
        r_copy = r.copy()
        if "password" in r_copy:
            del r_copy["password"]
        sanitized.append(r_copy)
    return sanitized


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


def get_user_avatars(usernames):
    """Return a mapping of usernames to their avatars."""
    users = load_json(USERS_FILE)
    avatar_map = {}
    for username in usernames:
        user_data = next((u for u in users if u["username"].lower() == username.lower()), None)
        avatar_map[username] = user_data.get("avatar") if user_data else None
    return avatar_map


def sync_user_data_update(old_username, new_username):
    """Sync username change across all messages and room creators."""
    # 1. Update Room Creators
    if os.path.exists(ROOMS_FILE):
        rooms = load_json(ROOMS_FILE)
        changed = False
        for r in rooms:
            if r.get("creator", "").lower() == old_username.lower():
                r["creator"] = new_username
                changed = True
        if changed:
            save_json(ROOMS_FILE, rooms)

    # 2. Update all message files
    for filename in os.listdir(MESSAGES_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(MESSAGES_DIR, filename)
            try:
                msgs = load_json(filepath)
                changed_msgs = False
                for m in msgs:
                    if m.get("username", "").lower() == old_username.lower():
                        m["username"] = new_username
                        changed_msgs = True
                if changed_msgs:
                    save_json(filepath, msgs)
            except:
                continue

    # 3. Update online.json
    if os.path.exists(ONLINE_FILE):
        online = load_json(ONLINE_FILE)
        changed_online = False
        for room in online:
            room_users = online[room]
            # Find matching keys (case-insensitive)
            matches = [u for u in room_users.keys() if u.lower() == old_username.lower()]
            for m in matches:
                timestamp = room_users.pop(m)
                room_users[new_username] = timestamp
                changed_online = True
        if changed_online:
            save_json(ONLINE_FILE, online)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Index/join page. If already logged in, redirect to general."""
    if "username" in session:
        return redirect("/chat/general")
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
        return redirect("/chat/general")

    # Update session room
    session["room"] = room
    
    is_secure = is_room_secure(room)
    is_unlocked = check_room_access(room)

    # Find the creator of the room
    all_rooms = load_json(ROOMS_FILE)
    room_info = next((r for r in all_rooms if r["name"] == room), None)
    room_creator = room_info.get("creator") if room_info else None

    # Check if user is registered
    is_registered = session.get("logged_in", False)

    # Get avatar info for the user
    user_avatar = None
    if is_registered:
        users = load_json(USERS_FILE)
        user_data = next((u for u in users if u["username"].lower() == session["username"].lower()), None)
        if user_data:
            user_avatar = user_data.get("avatar", None)

    return render_template("chat.html", 
                           room=room, 
                           username=session["username"], 
                           rooms=safe_rooms, 
                           is_secure=is_secure, 
                           is_unlocked=is_unlocked,
                           room_creator=room_creator,
                           is_registered=is_registered,
                           user_avatar=user_avatar)


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
        "type": data.get("type", "text")
    }

    # If there's a file attachment (image or PDF)
    if image:
        msg["image"] = image
        if image.lower().endswith(".pdf"):
            msg["type"] = "pdf"
        elif msg["type"] != "gif":
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

    messages_file = os.path.join(MESSAGES_DIR, f"{room}.json")
    if os.path.exists(messages_file):
        msgs = load_json(messages_file)
        # Add avatar info to each message
        usernames = list(set(m["username"] for m in msgs))
        avatar_map = get_user_avatars(usernames)
        for m in msgs:
            m["user_avatar"] = avatar_map.get(m["username"])
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

    usernames = get_online_users(room)
    avatar_map = get_user_avatars(usernames)
    
    detailed_users = []
    for u in usernames:
        detailed_users.append({
            "username": u,
            "avatar": avatar_map.get(u)
        })
    return jsonify(detailed_users)


@app.route("/create-room", methods=["POST"])
def create_room():
    """Create a new room."""
    data = request.json
    room_name = data.get("name", "").strip().lower().replace(" ", "-")
    password = data.get("password", "").strip()

    if not room_name:
        return jsonify({"error": "Room name is required"}), 400

    # Validate room name (alphanumeric, hyphens, underscores only)
    if not re.match(r"^[a-z0-9-_]+$", room_name):
        return jsonify({"error": "Room name can only contain letters, numbers, hyphens, and underscores."}), 400

    # Load existing rooms
    rooms = load_json(ROOMS_FILE)
    room_names = [r["name"] for r in rooms]

    if room_name in room_names:
        return jsonify({"error": "Room already exists"}), 400

    # Add new room
    rooms.append({
        "name": room_name,
        "creator": session.get("username", "Guest"),
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
    """Upload an image or PDF attachment."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    room = session.get("room", "general")
    if not check_room_access(room):
        return jsonify({"error": "Room is secure and locked"}), 403

    if "image" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Validate file type (images + PDF)
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return jsonify({"error": "File type not allowed"}), 400

    # Generate short unique filename: Candela_<6 random chars>.<ext>
    short_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    filename = f"Candela_{short_id}{ext}"
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


@app.route("/delete-room", methods=["POST"])
def delete_room():
    """Delete a room. Only the creator can do this."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.json
    room_name = data.get("room", "").strip()

    if room_name == "general":
        return jsonify({"error": "Cannot delete the general room"}), 403

    rooms = load_json(ROOMS_FILE)
    room_idx = next((i for i, r in enumerate(rooms) if r["name"] == room_name), -1)

    if room_idx == -1:
        return jsonify({"error": "Room not found"}), 404

    # Authorization check
    if rooms[room_idx].get("creator") != session["username"]:
        return jsonify({"error": "Only the creator can delete this room"}), 403

    # Delete room entry
    del rooms[room_idx]
    save_json(ROOMS_FILE, rooms)

    # Delete messages file
    messages_file = os.path.join(MESSAGES_DIR, f"{room_name}.json")
    if os.path.exists(messages_file):
        os.remove(messages_file)

    # Clean up online users for this room
    online = load_json(ONLINE_FILE)
    if room_name in online:
        del online[room_name]
        save_json(ONLINE_FILE, online)

    return jsonify({"status": "ok"})


@app.route("/profile", methods=["GET"])
def profile_info():
    """Return current user's profile information."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    is_registered = session.get("logged_in", False)
    avatar = None

    if is_registered:
        users = load_json(USERS_FILE)
        user_data = next((u for u in users if u["username"].lower() == session["username"].lower()), None)
        if user_data:
            avatar = user_data.get("avatar", None)

    return jsonify({
        "username": session["username"],
        "is_registered": is_registered,
        "avatar": avatar
    })


@app.route("/update-username", methods=["POST"])
def update_username():
    """Update the current user's username."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    if not session.get("logged_in"):
        return jsonify({"error": "Only registered users can change their username"}), 403

    data = request.json
    new_username = data.get("username", "").strip()

    if not new_username:
        return jsonify({"error": "Username is required"}), 400

    if len(new_username) < 2:
        return jsonify({"error": "Username must be at least 2 characters"}), 400

    if len(new_username) > 20:
        return jsonify({"error": "Username must be 20 characters or less"}), 400

    old_username = session["username"]

    # Check if new username is already taken (by another user)
    users = load_json(USERS_FILE)
    for user in users:
        if user["username"].lower() == new_username.lower() and user["username"].lower() != old_username.lower():
            return jsonify({"error": "Username is already taken"}), 400

    # Update in users.json
    for user in users:
        if user["username"].lower() == old_username.lower():
            user["username"] = new_username
            break

    save_json(USERS_FILE, users)

    # Sync historical data (messages, rooms)
    sync_user_data_update(old_username, new_username)

    # Update session
    session["username"] = new_username

    return jsonify({"status": "ok", "username": new_username})


@app.route("/update-password", methods=["POST"])
def update_password():
    """Update the current user's password."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    if not session.get("logged_in"):
        return jsonify({"error": "Only registered users can change their password"}), 403

    data = request.json
    current_password = data.get("current_password", "").strip()
    new_password = data.get("new_password", "").strip()

    if not current_password or not new_password:
        return jsonify({"error": "Both current and new password are required"}), 400

    if len(new_password) < 4:
        return jsonify({"error": "New password must be at least 4 characters"}), 400

    # Verify current password
    users = load_json(USERS_FILE)
    user_data = next((u for u in users if u["username"].lower() == session["username"].lower()), None)

    if not user_data:
        return jsonify({"error": "User not found"}), 404

    if not bcrypt.checkpw(current_password.encode("utf-8"), user_data["password"].encode("utf-8")):
        return jsonify({"error": "Current password is incorrect"}), 401

    # Update password
    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
    user_data["password"] = hashed.decode("utf-8")
    save_json(USERS_FILE, users)

    return jsonify({"status": "ok"})


@app.route("/update-avatar", methods=["POST"])
def update_avatar():
    """Update the current user's avatar (DiceBear style+seed or uploaded image)."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    if not session.get("logged_in"):
        return jsonify({"error": "Only registered users can change their avatar"}), 403

    data = request.json
    avatar_type = data.get("type", "")  # "dicebear" or "upload"
    avatar_value = data.get("value", "")  # style:seed or filename

    if not avatar_type or not avatar_value:
        return jsonify({"error": "Avatar data is required"}), 400

    users = load_json(USERS_FILE)
    for user in users:
        if user["username"].lower() == session["username"].lower():
            user["avatar"] = {
                "type": avatar_type,
                "value": avatar_value
            }
            break

    save_json(USERS_FILE, users)

    return jsonify({"status": "ok"})


@app.route("/upload-avatar", methods=["POST"])
def upload_avatar():
    """Upload an avatar image file."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    if "avatar" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["avatar"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Validate file type (images only)
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return jsonify({"error": "Only image files are allowed"}), 400

    # Generate unique filename
    short_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    filename = f"avatar_{short_id}{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    file.save(filepath)

    # Save to user record
    users = load_json(USERS_FILE)
    for user in users:
        if user["username"].lower() == session["username"].lower():
            user["avatar"] = {
                "type": "upload",
                "value": filename
            }
            break

    save_json(USERS_FILE, users)

    return jsonify({"status": "ok", "filename": filename})


@app.route("/register-guest", methods=["POST"])
def register_guest():
    """Register a guest user — sets a password and marks them as registered."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    if session.get("logged_in"):
        return jsonify({"error": "You are already registered"}), 400

    data = request.json
    password = data.get("password", "").strip()

    if not password:
        return jsonify({"error": "Password is required"}), 400

    if len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters"}), 400

    username = session["username"]

    # Check if already registered
    users = load_json(USERS_FILE)
    for user in users:
        if user["username"].lower() == username.lower():
            return jsonify({"error": "This username is already registered"}), 400

    # Hash and save
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    users.append({
        "username": username,
        "password": hashed.decode("utf-8")
    })
    save_json(USERS_FILE, users)

    # Mark session as logged in
    session["logged_in"] = True

    return jsonify({"status": "ok"})


# ── Initialize and Run ───────────────────────────────────────────────────────
init_data()
app.run(debug=True)
