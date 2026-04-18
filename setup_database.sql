-- ═══════════════════════════════════════════════════════════════
-- Candela Chatroom — Supabase Database Schema
-- Run this ONCE in your Supabase SQL Editor (Dashboard → SQL Editor)
-- ═══════════════════════════════════════════════════════════════

-- 1. Users
CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    avatar_type TEXT,
    avatar_value TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Rooms
CREATE TABLE rooms (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    creator TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_secure BOOLEAN DEFAULT FALSE,
    password TEXT
);

-- 3. Room Authorized Users (junction table for secure rooms)
CREATE TABLE room_authorized_users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    room_name TEXT NOT NULL REFERENCES rooms(name) ON DELETE CASCADE,
    username TEXT NOT NULL,
    UNIQUE(room_name, username)
);

-- 4. Messages
CREATE TABLE messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    room TEXT NOT NULL,
    username TEXT NOT NULL,
    message TEXT DEFAULT '',
    type TEXT DEFAULT 'text',
    image TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fast lookup indexes for messages
CREATE INDEX idx_messages_room ON messages(room);
CREATE INDEX idx_messages_created_at ON messages(created_at);

-- 5. Online Users (presence tracking via heartbeat)
CREATE TABLE online_users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    room TEXT NOT NULL,
    username TEXT NOT NULL,
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(room, username)
);

CREATE INDEX idx_online_room ON online_users(room);

-- 6. Invitations
CREATE TABLE invitations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    target_user TEXT NOT NULL,
    room TEXT NOT NULL,
    requester TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_invitations_target ON invitations(target_user);

-- 7. Seed the default "general" room
INSERT INTO rooms (name, creator, is_secure)
VALUES ('general', 'System', FALSE);
