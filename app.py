"""
CHATROOM-P — Flask Chatroom Web App
A real-time chatroom where users can join rooms, chat, and see who's online.
No registration required to chat, but optional account creation to reserve a username.

Storage: Supabase (PostgreSQL)
"""

import os
import string
import random
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from flask_session import Session
import re
import bcrypt
from dotenv import load_dotenv
from supabase import create_client, Client

# ── Load environment variables ───────────────────────────────────────────────
load_dotenv()

# ── Flask App Setup ──────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "chatroom_secret_key_2026"

# Server-side session configuration
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(os.path.dirname(__file__), "flask_session")
app.config["SESSION_PERMANENT"] = False
Session(app)

# ── Supabase Client Setup ────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in .env file")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Paths (only for local file uploads) ──────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


# ── Helper Functions ─────────────────────────────────────────────────────────

def utcnow():
    """Return current UTC time as ISO string for Supabase."""
    return datetime.now(timezone.utc).isoformat()


def get_online_users(room):
    """Return list of users currently online in a room (heartbeat within 15s)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=15)).isoformat()
    result = supabase.table("online_users") \
        .select("username") \
        .eq("room", room) \
        .gte("last_seen", cutoff) \
        .execute()
    return [r["username"] for r in result.data]


def is_username_taken_in_room(username, room):
    """Check if a username is already active in a room."""
    online_users = get_online_users(room)
    return username in online_users


def is_username_registered(username):
    """Check if a username belongs to a registered account."""
    result = supabase.table("users") \
        .select("username") \
        .ilike("username", username) \
        .execute()
    return len(result.data) > 0


def get_sanitized_rooms():
    """Returns all rooms, stripping out passwords to safely send to frontend."""
    result = supabase.table("rooms") \
        .select("name, creator, created_at, is_secure") \
        .execute()
    return result.data


def is_room_secure(room_name):
    """Check if a room requires a password."""
    result = supabase.table("rooms") \
        .select("is_secure") \
        .eq("name", room_name) \
        .execute()
    if result.data:
        return result.data[0].get("is_secure", False)
    return False


def check_room_access(room_name):
    """Returns True if the user has access to the room (not secure, or unlocked in session, or authorized)."""
    if not is_room_secure(room_name):
        return True

    # Check session
    unlocked_rooms = session.get("unlocked_rooms", [])
    if room_name in unlocked_rooms:
        return True

    # Check persistent authorized users
    if "username" in session:
        # Check if user is creator
        room_result = supabase.table("rooms") \
            .select("creator") \
            .eq("name", room_name) \
            .execute()
        if room_result.data and room_result.data[0]["creator"] == session["username"]:
            return True

        # Check authorized_users table
        auth_result = supabase.table("room_authorized_users") \
            .select("username") \
            .eq("room_name", room_name) \
            .eq("username", session["username"]) \
            .execute()
        if auth_result.data:
            return True

    return False


def get_all_online_users():
    """Return a list of all users online across all rooms."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=15)).isoformat()
    result = supabase.table("online_users") \
        .select("username") \
        .gte("last_seen", cutoff) \
        .execute()

    # Deduplicate (user may be in multiple rooms)
    return list(set(r["username"] for r in result.data))


def get_user_avatars(usernames):
    """Return a mapping of usernames to their avatars."""
    if not usernames:
        return {}

    result = supabase.table("users") \
        .select("username, avatar_type, avatar_value") \
        .in_("username", usernames) \
        .execute()

    avatar_map = {}
    # Initialize all requested usernames with None
    for u in usernames:
        avatar_map[u] = None

    for row in result.data:
        if row["avatar_type"] and row["avatar_value"]:
            avatar_map[row["username"]] = {
                "type": row["avatar_type"],
                "value": row["avatar_value"]
            }

    return avatar_map


def sync_user_data_update(old_username, new_username):
    """Sync username change across all messages and room creators."""
    # 1. Update Room Creators
    supabase.table("rooms") \
        .update({"creator": new_username}) \
        .ilike("creator", old_username) \
        .execute()

    # 2. Update all messages
    supabase.table("messages") \
        .update({"username": new_username}) \
        .ilike("username", old_username) \
        .execute()

    # 3. Update online_users
    supabase.table("online_users") \
        .update({"username": new_username}) \
        .ilike("username", old_username) \
        .execute()

    # 4. Update room_authorized_users
    supabase.table("room_authorized_users") \
        .update({"username": new_username}) \
        .ilike("username", old_username) \
        .execute()

    # 5. Update invitations (both requester and target)
    supabase.table("invitations") \
        .update({"requester": new_username}) \
        .ilike("requester", old_username) \
        .execute()
    supabase.table("invitations") \
        .update({"target_user": new_username}) \
        .ilike("target_user", old_username) \
        .execute()


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Index/join page. If already logged in, redirect to general."""
    if "username" in session:
        return redirect("/chat/general")
    rooms = get_sanitized_rooms()
    return render_template("index.html", rooms=rooms, supabase_url=SUPABASE_URL)


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
    room_result = supabase.table("rooms") \
        .select("creator") \
        .eq("name", room) \
        .execute()
    room_creator = room_result.data[0]["creator"] if room_result.data else None

    # Check if user is registered
    is_registered = session.get("logged_in", False)

    # Get avatar info for the user
    user_avatar = None
    if is_registered:
        user_result = supabase.table("users") \
            .select("avatar_type, avatar_value") \
            .ilike("username", session["username"]) \
            .execute()
        if user_result.data:
            row = user_result.data[0]
            if row["avatar_type"] and row["avatar_value"]:
                user_avatar = {
                    "type": row["avatar_type"],
                    "value": row["avatar_value"]
                }

    return render_template("chat.html",
                           room=room,
                           username=session["username"],
                           rooms=safe_rooms,
                           is_secure=is_secure,
                           is_unlocked=is_unlocked,
                           room_creator=room_creator,
                           is_registered=is_registered,
                           user_avatar=user_avatar,
                           supabase_url=SUPABASE_URL)


@app.route("/send", methods=["POST"])
def send():
    """Save a new message to the messages table."""
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

    # Determine message type
    msg_type = data.get("type", "text")
    if image:
        if image.lower().endswith(".pdf"):
            msg_type = "pdf"
        elif msg_type != "gif":
            msg_type = "image"

    # Insert into Supabase
    supabase.table("messages").insert({
        "room": room,
        "username": session["username"],
        "message": message_text,
        "type": msg_type,
        "image": image
    }).execute()

    return jsonify({"status": "ok"})


@app.route("/messages/<room>")
def messages(room):
    """Return all messages for a room as JSON."""
    result = supabase.table("messages") \
        .select("*") \
        .eq("room", room) \
        .order("created_at", desc=False) \
        .execute()

    msgs = result.data

    # Add avatar info to each message
    usernames = list(set(m["username"] for m in msgs))
    avatar_map = get_user_avatars(usernames)

    response = []
    for m in msgs:
        response.append({
            "username": m["username"],
            "message": m["message"],
            "timestamp": m["created_at"],
            "type": m["type"],
            "image": m.get("image"),
            "user_avatar": avatar_map.get(m["username"])
        })

    return jsonify(response)


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

    # Check if room already exists
    existing = supabase.table("rooms") \
        .select("name") \
        .eq("name", room_name) \
        .execute()

    if existing.data:
        return jsonify({"error": "Room already exists"}), 400

    # Insert new room
    supabase.table("rooms").insert({
        "name": room_name,
        "creator": session.get("username", "Guest"),
        "is_secure": bool(password),
        "password": password if password else None
    }).execute()

    # Add creator to authorized users
    creator_username = session.get("username", "Guest")
    supabase.table("room_authorized_users").insert({
        "room_name": room_name,
        "username": creator_username
    }).execute()

    # Unlock for the creator in session
    if password:
        session_unlocked = session.get("unlocked_rooms", [])
        session_unlocked.append(room_name)
        session["unlocked_rooms"] = session_unlocked

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
    existing = supabase.table("users") \
        .select("username") \
        .ilike("username", username) \
        .execute()

    if existing.data:
        return jsonify({"error": "Username is already registered"}), 400

    # Hash password with bcrypt
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    supabase.table("users").insert({
        "username": username,
        "password": hashed.decode("utf-8")
    }).execute()

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
    result = supabase.table("users") \
        .select("username, password") \
        .ilike("username", username) \
        .execute()

    if not result.data:
        return jsonify({"error": "User not found"}), 404

    user = result.data[0]

    # Verify password
    if bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
        session["username"] = user["username"]
        session["logged_in"] = True
        return jsonify({"status": "ok"})
    else:
        return jsonify({"error": "Incorrect password"}), 401


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

    # Upsert: update last_seen if exists, insert if not
    supabase.table("online_users").upsert({
        "room": room,
        "username": session["username"],
        "last_seen": utcnow()
    }, on_conflict="room,username").execute()

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

    # Save locally first, then upload to Supabase, then delete local file
    try:
        file.save(filepath)
        with open(filepath, 'rb') as f:
            supabase.storage.from_("candela-uploads").upload(
                path=filename,
                file=filepath,
                file_options={"content-type": file.mimetype}
            )
        os.remove(filepath)
    except Exception as e:
        print("Upload Error:", e)
        return jsonify({"error": "Failed to upload to cloud storage"}), 500

    return jsonify({"status": "ok", "filename": filename})


@app.route("/unlock-room", methods=["POST"])
def unlock_room():
    """Unlock a secure room with a password."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.json
    room_name = data.get("room", "").strip()
    password = data.get("password", "").strip()

    result = supabase.table("rooms") \
        .select("name, is_secure, password") \
        .eq("name", room_name) \
        .execute()

    if not result.data:
        return jsonify({"error": "Room not found"}), 404

    room_data = result.data[0]

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

    # Get room data
    result = supabase.table("rooms") \
        .select("name, creator") \
        .eq("name", room_name) \
        .execute()

    if not result.data:
        return jsonify({"error": "Room not found"}), 404

    room_data = result.data[0]

    # Authorization check
    if room_data["creator"] != session["username"]:
        return jsonify({"error": "Only the creator can delete this room"}), 403

    # Delete room (room_authorized_users will CASCADE delete)
    supabase.table("rooms").delete().eq("name", room_name).execute()

    # Delete messages for this room
    supabase.table("messages").delete().eq("room", room_name).execute()

    # Clean up online users for this room
    supabase.table("online_users").delete().eq("room", room_name).execute()

    return jsonify({"status": "ok"})


@app.route("/profile", methods=["GET"])
def profile_info():
    """Return current user's profile information."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    is_registered = session.get("logged_in", False)
    avatar = None

    if is_registered:
        result = supabase.table("users") \
            .select("avatar_type, avatar_value") \
            .ilike("username", session["username"]) \
            .execute()
        if result.data:
            row = result.data[0]
            if row["avatar_type"] and row["avatar_value"]:
                avatar = {
                    "type": row["avatar_type"],
                    "value": row["avatar_value"]
                }

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
    existing = supabase.table("users") \
        .select("username") \
        .ilike("username", new_username) \
        .execute()

    if existing.data and existing.data[0]["username"].lower() != old_username.lower():
        return jsonify({"error": "Username is already taken"}), 400

    # Update in users table
    supabase.table("users") \
        .update({"username": new_username}) \
        .ilike("username", old_username) \
        .execute()

    # Sync historical data (messages, rooms, etc.)
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
    result = supabase.table("users") \
        .select("password") \
        .ilike("username", session["username"]) \
        .execute()

    if not result.data:
        return jsonify({"error": "User not found"}), 404

    user_data = result.data[0]

    if not bcrypt.checkpw(current_password.encode("utf-8"), user_data["password"].encode("utf-8")):
        return jsonify({"error": "Current password is incorrect"}), 401

    # Update password
    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
    supabase.table("users") \
        .update({"password": hashed.decode("utf-8")}) \
        .ilike("username", session["username"]) \
        .execute()

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

    supabase.table("users") \
        .update({
            "avatar_type": avatar_type,
            "avatar_value": avatar_value
        }) \
        .ilike("username", session["username"]) \
        .execute()

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

    # Save locally first, then upload to Supabase, then delete
    try:
        file.save(filepath)
        with open(filepath, 'rb') as f:
            supabase.storage.from_("candela-uploads").upload(
                path=filename,
                file=filepath,
                file_options={"content-type": file.mimetype}
            )
        os.remove(filepath)
    except Exception as e:
        print("Upload Avatar Error:", e)
        return jsonify({"error": "Failed to upload avatar to cloud storage"}), 500

    # Save to user record in Supabase
    supabase.table("users") \
        .update({
            "avatar_type": "upload",
            "avatar_value": filename
        }) \
        .ilike("username", session["username"]) \
        .execute()

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
    existing = supabase.table("users") \
        .select("username") \
        .ilike("username", username) \
        .execute()

    if existing.data:
        return jsonify({"error": "This username is already registered"}), 400

    # Hash and save
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    supabase.table("users").insert({
        "username": username,
        "password": hashed.decode("utf-8")
    }).execute()

    # Mark session as logged in
    session["logged_in"] = True

    return jsonify({"status": "ok"})


@app.route("/all-online")
def all_online():
    """Return all online users across the site for invitations."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    usernames = get_all_online_users()
    # Filter out self
    usernames = [u for u in usernames if u != session["username"]]

    avatar_map = get_user_avatars(usernames)

    detailed_users = []
    for u in usernames:
        detailed_users.append({
            "username": u,
            "avatar": avatar_map.get(u)
        })
    return jsonify(detailed_users)


@app.route("/invite-user", methods=["POST"])
def invite_user():
    """Send an invitation to another user."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.json
    target_user = data.get("target_user")
    room_name = data.get("room")

    if not target_user or not room_name:
        return jsonify({"error": "Target user and room name required"}), 400

    # Security check: only creator can invite
    room_result = supabase.table("rooms") \
        .select("creator") \
        .eq("name", room_name) \
        .execute()

    if not room_result.data or room_result.data[0]["creator"] != session["username"]:
        return jsonify({"error": "Only the room creator can send invitations"}), 403

    # Check if already invited to this room
    existing_invite = supabase.table("invitations") \
        .select("id") \
        .eq("target_user", target_user) \
        .eq("room", room_name) \
        .execute()

    if not existing_invite.data:
        supabase.table("invitations").insert({
            "target_user": target_user,
            "room": room_name,
            "requester": session["username"]
        }).execute()

    return jsonify({"status": "ok"})


@app.route("/get-invitations")
def get_invitations():
    """Check for pending invitations for the current user."""
    if "username" not in session:
        return jsonify([])

    # Get invitations newer than 60 seconds
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()

    result = supabase.table("invitations") \
        .select("id, room, requester, created_at") \
        .eq("target_user", session["username"]) \
        .gte("created_at", cutoff) \
        .execute()

    valid_invites = []
    invite_ids = []
    for inv in result.data:
        valid_invites.append({
            "room": inv["room"],
            "requester": inv["requester"],
            "timestamp": inv["created_at"]
        })
        invite_ids.append(inv["id"])

    # Delete retrieved invitations to prevent re-popups
    if invite_ids:
        for inv_id in invite_ids:
            supabase.table("invitations").delete().eq("id", inv_id).execute()

    return jsonify(valid_invites)


@app.route("/accept-invitation", methods=["POST"])
def accept_invitation():
    """Accept an invitation to join a room."""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.json
    room_name = data.get("room")

    if not room_name:
        return jsonify({"error": "Room name required"}), 400

    # Verify room exists
    room_result = supabase.table("rooms") \
        .select("name") \
        .eq("name", room_name) \
        .execute()

    if not room_result.data:
        return jsonify({"error": "Room not found"}), 404

    # Add to authorized users (upsert to avoid duplicates)
    supabase.table("room_authorized_users").upsert({
        "room_name": room_name,
        "username": session["username"]
    }, on_conflict="room_name,username").execute()

    # Also unlock in current session
    unlocked = session.get("unlocked_rooms", [])
    if room_name not in unlocked:
        unlocked.append(room_name)
        session["unlocked_rooms"] = unlocked
        session.modified = True

    return jsonify({"status": "ok"})


# ── Initialize and Run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
