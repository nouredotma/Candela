<p align="center">
  <img src="static/img/logo.png" alt="Candela Logo" width="80">
</p>

<h1 align="center">Candela — Real-Time Chatroom</h1>

<p align="center">
  <strong>A premium, glassmorphism-styled chatroom web application built with Flask & Supabase.</strong><br>
  Join rooms instantly as a guest, or register to unlock profile customization, avatars, and more.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.x-000000?style=flat-square&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Supabase-PostgreSQL-3FCF8E?style=flat-square&logo=supabase&logoColor=white" alt="Supabase">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
</p>

---

<p align="center">
  <img src="static/img/login.png" alt="Candela App Preview" width="700" style="border-radius: 16px;">
</p>

---

## ✨ Features

- **Guest Access** — Jump into any public room instantly, no signup needed
- **Account Registration** — Register to reserve your username, set avatars, and manage your profile
- **Real-Time Chat** — Messages polled every 2 seconds with image, PDF, and GIF attachments
- **Emoji Picker** — Built-in emoji support with big-emoji rendering for single-emoji messages
- **Room System** — Create public or password-protected rooms, invite users, delete rooms
- **Room Invitations** — Room creators can invite online users via toast notifications with a 10-second timer
- **Profile Management** — DiceBear avatars (4 styles), custom image uploads, inline username editing
- **Glassmorphism UI** — Frosted-glass effects, gradient backgrounds, smooth animations throughout

---

## 🛠 Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.10+, Flask, Flask-Session, bcrypt |
| **Database** | Supabase (PostgreSQL) |
| **Frontend** | Vanilla JS, Vanilla CSS, Bootstrap 5.3, Bootstrap Icons |
| **APIs** | DiceBear (avatars), Google Fonts (Open Sans) |

---

## ⚙ Setup

### Prerequisites
- Python 3.10+
- A [Supabase](https://supabase.com) project (free tier works)

### 1. Clone & install

```bash
git clone https://github.com/nouredotma/Candela.git
cd Candela/CHATROOM-P
pip install -r requirements.txt
```

### 2. Configure Supabase

Create a `.env` file in the project root:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-secret-key
```

> **Where to find these:** Supabase Dashboard → Settings → API → Project URL and `service_role` secret key.

### 3. Create database tables

1. Open your Supabase Dashboard → **SQL Editor**
2. Paste the contents of `setup_database.sql`
3. Run **without RLS**

### 4. Run

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) — the app runs on port 5000 and is accessible on your local network.

---

## 📁 Project Structure

```
CHATROOM-P/
├── app.py                  # Flask backend — all routes and Supabase queries
├── requirements.txt        # Python dependencies
├── setup_database.sql      # One-time SQL script for Supabase table creation
├── .env                    # Supabase credentials (not committed)
│
├── templates/
│   ├── index.html          # Login/Join page (Guest, Login, Register tabs)
│   └── chat.html           # Main chat interface (3-column layout)
│
├── static/
│   ├── style.css           # Glassmorphism stylesheet
│   ├── chat.js             # Client-side logic (polling, rendering, interactions)
│   ├── emojis.js           # Emoji data
│   ├── img/                # Logo and login illustration
│   └── uploads/            # User-uploaded files (avatars, images, PDFs)
│
└── flask_session/          # Server-side session files (auto-generated)
```

---

## 🗄 Database

Candela uses **Supabase (PostgreSQL)** with 6 tables:

| Table | Purpose |
|---|---|
| `users` | Registered accounts (bcrypt-hashed passwords, avatar info) |
| `rooms` | Room definitions (name, creator, password, security status) |
| `room_authorized_users` | Users authorized to access password-protected rooms |
| `messages` | All chat messages across all rooms |
| `online_users` | Heartbeat-based presence tracking (15-second timeout) |
| `invitations` | Pending room invitations (60-second expiry) |

The schema is defined in `setup_database.sql`.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

<p align="center">
  Made with ❤️ by <strong>Noureddine</strong>
</p>
<p align="center">
  <img src="static/img/logo.png" alt="Candela" width="32">
</p>
