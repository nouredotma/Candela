/**
 * CHATROOM-P — Client-Side JavaScript
 * Handles: polling messages, polling online users, sending heartbeat,
 * sending messages via fetch API, rendering messages into the DOM,
 * auto-scrolling to bottom, image attachments, creating rooms.
 */

// ══════════════════════════════════════════════════════════════════════════
// State
// ══════════════════════════════════════════════════════════════════════════

let currentMessages = null;     // Cache of messages to detect new ones
let selectedFile = null;        // Currently selected file for attachment


// ══════════════════════════════════════════════════════════════════════════
// Polling — Messages (every 2 seconds)
// ══════════════════════════════════════════════════════════════════════════

/**
 * Fetch all messages for the current room and update the feed.
 */
function pollMessages() {

    fetch(`/messages/${CURRENT_ROOM}`)
        .then(res => res.json())
        .then(messages => {
            // Re-render if messsage list is new or count changed
            if (currentMessages === null || messages.length !== currentMessages.length) {
                const isInitial = (currentMessages === null);
                currentMessages = messages;
                renderMessages(messages);
                
                // If initial load, scroll immediately and also after a short delay 
                // to account for layout shifts
                if (isInitial) {
                    scrollToBottom();
                    setTimeout(scrollToBottom, 100);
                    setTimeout(scrollToBottom, 500);
                } else {
                    scrollToBottom();
                }
            }
        })
        .catch(err => console.error("Error polling messages:", err));
}

// Poll messages every 2 seconds
setInterval(pollMessages, 2000);


// ══════════════════════════════════════════════════════════════════════════
// Polling — Online Users (every 5 seconds)
// ══════════════════════════════════════════════════════════════════════════

/**
 * Fetch online users for the current room and update the sidebar.
 */
function pollOnlineUsers() {

    fetch(`/online/${CURRENT_ROOM}`)
        .then(res => res.json())
        .then(users => {
            renderOnlineUsers(users);
            updateOnlineCount(users.length);
        })
        .catch(err => console.error("Error polling online users:", err));
}

// Poll online users every 5 seconds
setInterval(pollOnlineUsers, 5000);


// ══════════════════════════════════════════════════════════════════════════
// Heartbeat — Every 5 seconds
// ══════════════════════════════════════════════════════════════════════════

/**
 * Send a heartbeat to the server to mark the user as online.
 */
function sendHeartbeat() {

    fetch("/heartbeat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: CURRENT_ROOM })
    })
    .catch(err => console.error("Heartbeat error:", err));
}

// Send heartbeat every 5 seconds
setInterval(sendHeartbeat, 5000);

// Send initial heartbeat immediately
sendHeartbeat();


// ══════════════════════════════════════════════════════════════════════════
// Polling — Invitations (every 5 seconds)
// ══════════════════════════════════════════════════════════════════════════

/**
 * Check for pending invitations.
 */
function pollInvitations() {
    if (!UNLOCKED) return; // Don't poll if room is locked (blurred)

    fetch("/get-invitations")
        .then(res => res.json())
        .then(invites => {
            if (Array.isArray(invites)) {
                invites.forEach(inv => {
                    renderInvitationToast(inv);
                });
            }
        })
        .catch(err => console.error("Error polling invitations:", err));
}

// Poll invitations every 5 seconds
setInterval(pollInvitations, 5000);


// ══════════════════════════════════════════════════════════════════════════
// Rendering — Messages
// ══════════════════════════════════════════════════════════════════════════

/**
 * Predefined set of warm, light "code colors" for avatar placeholders.
 * Each color is unique, lighter, and warmer than the original palette.
 */
const PLACEHOLDER_COLORS = [
    "#5865F2", "#57F287", "#FEE75C", "#EB459E", "#ED4245",
    "#99AAB5", "#5865F2", "#57F287", "#FEE75C", "#EB459E",
    "#ED4245", "#99AAB5", "#5865F2", "#57F287", "#FEE75C",
    "#EB459E", "#ED4245", "#99AAB5", "#5865F2", "#57F287",
];

/**
 * Deterministically pick a color from the palette based on the username.
 */
function getAvatarColor(username) {
    if (!username) return PLACEHOLDER_COLORS[0];
    let hash = 0;
    for (let i = 0; i < username.length; i++) {
        hash = username.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % PLACEHOLDER_COLORS.length;
    return PLACEHOLDER_COLORS[index];
}

/**
 * Generate HTML for an avatar (image, dicebear SVG, or the new logo placeholder).
 */
function getAvatarHtml(avatar, username) {
    if (avatar && avatar.type === "dicebear") {
        const parts = avatar.value.split(":");
        return `<img src="https://api.dicebear.com/9.x/${parts[0]}/svg?seed=${parts[1]}" alt="avatar" style="width:100%;height:100%;object-fit:cover;">`;
    } else if (avatar && avatar.type === "upload") {
        return `<img src="/static/uploads/${avatar.value}" alt="avatar" style="width:100%;height:100%;object-fit:cover;">`;
    }
    
    // Placeholder logic: Random background color + Candela logo
    const bgColor = getAvatarColor(username);
    return `
        <div class="avatar-placeholder" style="background-color: ${bgColor}">
            <img src="/static/img/avatar.png" class="placeholder-logo" alt="Candela">
        </div>
    `;
}

/**
 * Render all messages into the messages feed div.
 */
function renderMessages(messages) {
    const feed = document.getElementById("messages-feed");

    if (messages.length === 0) {
        feed.innerHTML = `
            <div class="empty-state">
                <p style="font-weight: 700; color: #fff; margin-bottom: 4px; font-size: 16px;">Welcome to #${CURRENT_ROOM}!</p>
                <p>This is the start of the conversation. Be the first to say something!</p>
            </div>
        `;
        return;
    }

    let html = "";
    for (let i = 0; i < messages.length; i++) {
        const msg = messages[i];
        const isOwn = msg.username === CURRENT_USER;
        const initial = msg.username.charAt(0).toUpperCase();
        const avatarHtml = getAvatarHtml(msg.user_avatar, msg.username);

        html += `<div class="message-item ${isOwn ? 'own' : ''}">`;
        html += `  <div class="message-avatar">${avatarHtml}</div>`;
        html += `  <div class="message-content">`;
        html += `    <div class="message-header">`;
        html += `      <span class="message-username">${escapeHtml(msg.username)}</span>`;
        html += `      <span class="message-timestamp">${formatTimestamp(msg.timestamp)}</span>`;
        html += `    </div>`;

        if (msg.message) {
            const isBig = isSingleEmoji(msg.message);
            html += `    <div class="message-text ${isBig ? 'big-emoji-text' : ''}">${escapeHtml(msg.message)}</div>`;
        }

        // Show image or file if attached
        if (msg.image) {
            const isImg = /\.(jpg|jpeg|png|gif|webp)$/i.test(msg.image);
            const isPdf = /\.pdf$/i.test(msg.image);
            
            let imgSrc = msg.image;
            if (!imgSrc.startsWith("http")) {
                imgSrc = `/static/uploads/${msg.image}`;
            }

            if (isImg) {
                html += `    <img class="message-attachment message-image" src="${imgSrc}" alt="attachment" onclick="openLightbox(this.src)" onload="scrollToBottom()">`;
            } else if (isPdf) {
                html += `    <div class="message-attachment message-file message-pdf" onclick="window.open('/static/uploads/${msg.image}', '_blank')">`;
                html += `       <i class="bi bi-file-earmark-pdf-fill me-2"></i>`;
                html += `       <span>${escapeHtml(msg.image)}</span>`;
                html += `    </div>`;
            } else {
                html += `    <div class="message-attachment message-file" onclick="window.open('/static/uploads/${msg.image}', '_blank')">`;
                html += `       <i class="bi bi-file-earmark-arrow-down me-2"></i>`;
                html += `       <span>${escapeHtml(msg.image)}</span>`;
                html += `    </div>`;
            }
        }

        html += `  </div>`;
        html += `</div>`;
    }

    feed.innerHTML = html;
}


// ══════════════════════════════════════════════════════════════════════════
// Rendering — Online Users
// ══════════════════════════════════════════════════════════════════════════

/**
 * Render online users list in the right sidebar.
 * @param {Array} users - Array of username strings
 */
function renderOnlineUsers(users) {
    const list = document.getElementById("online-users-list");

    if (users.length === 0) {
        list.innerHTML = `
            <li class="online-user-item">
                <span class="online-user-name" style="color:#ff0000;">No one is online</span>
            </li>
        `;
        return;
    }

    let html = "";
    for (let i = 0; i < users.length; i++) {
        const user = users[i];
        const initial = user.username.charAt(0).toUpperCase();
        const avatarHtml = getAvatarHtml(user.avatar, user.username);

        html += `<li class="online-user-item">`;
        html += `  <div class="online-avatar-container">`;
        html += `    <div class="online-user-avatar">${avatarHtml}</div>`;
        html += `    <div class="online-user-dot"></div>`;
        html += `  </div>`;
        html += `  <span class="online-user-name">${escapeHtml(user.username)}</span>`;
        html += `</li>`;
    }

    list.innerHTML = html;
}

/**
 * Update the online count in the sidebar header.
 * @param {number} count - Number of online users
 */
function updateOnlineCount(count) {
    const el = document.getElementById("online-count");
    if (el) el.textContent = count + " online";
}


// ══════════════════════════════════════════════════════════════════════════
// Sending Messages
// ══════════════════════════════════════════════════════════════════════════

/**
 * Send a message (and optional image) to the server.
 */
function sendMessage() {
    const input = document.getElementById("message-input");
    const messageText = input.value.trim();

    // Must have either text or file
    if (!messageText && !selectedFile) {
        return;
    }

    // Capture file and clear input immediately
    const fileToUpload = selectedFile;
    input.value = "";
    clearFilePreview(); 

    if (fileToUpload) {
        uploadFile(fileToUpload, function(filename) {
            postMessage(messageText, filename);
        });
    } else {
        postMessage(messageText, null);
    }

    input.focus();
}

/**
 * Post a message to the server via fetch.
 * @param {string} message - Message text
 * @param {string|null} image - Uploaded image filename or null
 */
function postMessage(message, image) {
    const body = {
        room: CURRENT_ROOM,
        message: message
    };

    if (image) {
        body.image = image;
    }

    fetch("/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            console.error("Send error:", data.error);
        } else {
            // Immediately poll for new messages
            pollMessages();
        }
    })
    .catch(err => console.error("Error sending message:", err));
}

/**
 * Upload a file to the server.
 * @param {File} file - The file to upload
 * @param {Function} callback - Called with the uploaded filename
 */
function uploadFile(file, callback) {
    const formData = new FormData();
    formData.append("image", file);

    fetch("/upload", {
        method: "POST",
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            console.error("Upload error:", data.error);
        } else {
            callback(data.filename);
        }
    })
    .catch(err => console.error("Error uploading image:", err));
}


// ══════════════════════════════════════════════════════════════════════════
// Image Attachment
// ══════════════════════════════════════════════════════════════════════════

/**
 * Handle file selection — show preview.
 */
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    selectedFile = file;

    const previewDiv = document.getElementById("image-preview");
    const previewImg = document.getElementById("preview-img");
    const pdfPreview = document.getElementById("pdf-preview-info");

    // Reset both preview types
    previewImg.style.display = "none";
    if (pdfPreview) pdfPreview.style.display = "none";

    // Show preview if image
    const isImg = file.type.startsWith("image/");
    const isPdf = file.type === "application/pdf";

    if (isImg) {
        const reader = new FileReader();
        reader.onload = function(e) {
            previewImg.src = e.target.result;
            previewImg.style.display = "block";
            previewDiv.style.display = "inline-block";
        };
        reader.readAsDataURL(file);
    } else if (isPdf) {
        // Show PDF icon + filename
        previewImg.style.display = "none";
        if (pdfPreview) {
            pdfPreview.querySelector(".pdf-preview-name").textContent = file.name;
            pdfPreview.style.display = "flex";
        }
        previewDiv.style.display = "inline-block";
    } else {
        // Fallback for other file types
        previewImg.src = "";
        previewImg.style.display = "none";
        previewDiv.style.display = "inline-block";
    }
}

/**
 * Clear the file preview and reset selection.
 */
function clearFilePreview() {
    selectedFile = null;
    document.getElementById("image-preview").style.display = "none";
    document.getElementById("preview-img").src = "";
    document.getElementById("preview-img").style.display = "none";
    const pdfPreview = document.getElementById("pdf-preview-info");
    if (pdfPreview) pdfPreview.style.display = "none";
    document.getElementById("file-upload").value = "";
}


// ══════════════════════════════════════════════════════════════════════════
// Room Creation
// ══════════════════════════════════════════════════════════════════════════

/**
 * Create a new room via fetch and navigate to it.
 */
function createRoom() {
    const input = document.getElementById("new-room-name");
    const pwdInput = document.getElementById("new-room-password");
    const roomName = input.value.trim().toLowerCase().replace(/\s+/g, '-');
    const roomPassword = pwdInput ? pwdInput.value.trim() : "";
    const errorDiv = document.getElementById("create-room-error");
    
    // Clear previous error
    errorDiv.style.display = "none";
    errorDiv.textContent = "";

    if (!roomName) {
        errorDiv.textContent = "Room name is required.";
        errorDiv.style.display = "block";
        return;
    }

    // Validate room name (alphanumeric, hyphens, underscores only)
    const roomNameRegex = /^[a-z0-9-_]+$/;
    if (!roomNameRegex.test(roomName)) {
        errorDiv.textContent = "Room name can only contain letters, numbers, hyphens, and underscores.";
        errorDiv.style.display = "block";
        return;
    }

    fetch("/create-room", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: roomName, password: roomPassword })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            errorDiv.textContent = data.error;
            errorDiv.style.display = "block";
        } else {
            // Close modal and navigate
            document.getElementById("create-modal").style.display = "none";
            window.location.href = `/chat/${data.name}`;
        }
    })
    .catch(err => {
        errorDiv.textContent = "Error creating room.";
        errorDiv.style.display = "block";
    });
}

/**
 * Unlock a secure room via fetch.
 */
function unlockRoom() {
    const pwdInput = document.getElementById("room-password-input");
    const password = pwdInput.value.trim();
    const errorDiv = document.getElementById("unlock-error");
    
    // Clear previous error
    errorDiv.style.display = "none";
    errorDiv.textContent = "";

    if (!password) {
        errorDiv.textContent = "Please enter a password.";
        errorDiv.style.display = "block";
        return;
    }

    fetch("/unlock-room", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: CURRENT_ROOM, password: password })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            errorDiv.textContent = data.error;
            errorDiv.style.display = "block";
        } else {
            // Success
            UNLOCKED = true;
            document.getElementById("secure-room-overlay").style.display = "none";
            document.getElementById("chat-content-wrapper").classList.remove("secure-blurred");
            
            // Resume polling immediately
            pollMessages();
            pollOnlineUsers();
            sendHeartbeat();
        }
    })
    .catch(err => {
        errorDiv.textContent = "Error unlocking room.";
        errorDiv.style.display = "block";
    });
}

/**
 * Show a floating toast notification.
 * @param {string} message - Message to display
 * @param {string} type - 'success' or 'error'
 */
function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast-message ${type}`;
    
    // Choose icon
    const icon = type === "success" ? "bi-check-circle-fill" : "bi-exclamation-circle-fill";
    
    toast.innerHTML = `<i class="bi ${icon}"></i><span>${message}</span>`;
    container.appendChild(toast);

    // Remove from DOM after animation completes
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

/**
 * Perform actual room deletion.
 */
function confirmDeleteRoom() {
    const errorDiv = document.getElementById("delete-room-error");
    
    fetch("/delete-room", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: CURRENT_ROOM })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            errorDiv.textContent = data.error;
            errorDiv.style.display = "block";
        } else {
            // Success — save toast for after redirect and go to general
            localStorage.setItem("pending_toast", JSON.stringify({
                message: `#${CURRENT_ROOM} deleted successfully.`,
                type: "success"
            }));
            window.location.href = "/chat/general";
        }
    })
    .catch(err => {
        errorDiv.textContent = "Error deleting room.";
        errorDiv.style.display = "block";
    });
}

/**
 * Render a special invitation toast with a 10-second timer.
 */
function renderInvitationToast(inv) {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = "toast-message invitation";
    
    toast.innerHTML = `
        <div class="invitation-header">
            <i class="bi bi-envelope-heart-fill"></i>
            <span>Room Invitation</span>
        </div>
        <div class="invitation-body">
            <strong>${escapeHtml(inv.requester)}</strong> invited you to join <strong>#${escapeHtml(inv.room)}</strong>.
        </div>
        <div class="invitation-footer">
            <button class="btn-decline-invitation" onclick="this.closest('.toast-message').remove()">Decline</button>
            <button class="btn-accept-invitation">Accept</button>
        </div>
        <div class="invitation-timer">
            <div class="invitation-timer-progress"></div>
        </div>
    `;

    container.appendChild(toast);

    // Accept logic
    toast.querySelector(".btn-accept-invitation").addEventListener("click", () => {
        acceptInvitation(inv.room);
        toast.remove();
    });

    // Auto-remove after 10 seconds
    const timer = setTimeout(() => {
        if (toast.parentNode) {
            toast.style.animation = "toastOut 0.4s forwards";
            setTimeout(() => toast.remove(), 400);
        }
    }, 10000);

    // Stop timer if accepted/declined manually
    toast.addEventListener("remove", () => clearTimeout(timer));
}

/**
 * Handle accepting an invitation.
 */
function acceptInvitation(roomName) {
    fetch("/accept-invitation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: roomName })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "ok") {
            // Join the room
            window.location.href = `/chat/${roomName}`;
        }
    })
    .catch(err => console.error("Error accepting invitation:", err));
}

/**
 * Open the invite modal and fetch all online users.
 */
function openInviteFriendsModal() {
    const modal = document.getElementById("invite-modal");
    const list = document.getElementById("invite-online-list");
    const errorDiv = document.getElementById("invite-room-error");
    
    errorDiv.style.display = "none";
    list.innerHTML = `<li class="text-center py-4"><div class="spinner-border text-primary spinner-border-sm"></div></li>`;
    modal.style.display = "flex";

    fetch("/all-online")
        .then(res => res.json())
        .then(users => {
            if (users.length === 0) {
                list.innerHTML = `<li class="text-center py-4 text-muted" style="font-size: 13px;">No other users are online right now.</li>`;
                return;
            }

            let html = "";
            users.forEach(user => {
                const initial = user.username.charAt(0).toUpperCase();
                const avatarHtml = getAvatarHtml(user.avatar, user.username);
                
                html += `
                    <li class="online-user-item">
                        <div class="user-main-info">
                            <div class="online-avatar-container">
                                <div class="online-user-avatar">${avatarHtml}</div>
                                <div class="online-user-dot"></div>
                            </div>
                            <span class="online-user-name">${escapeHtml(user.username)}</span>
                        </div>
                        <button class="btn-invite-user" onclick="sendInvitation('${escapeHtml(user.username)}', this)">Invite</button>
                    </li>
                `;
            });
            list.innerHTML = html;
        })
        .catch(() => {
            list.innerHTML = `<li class="text-center py-4 text-danger">Error loading users.</li>`;
        });
}

function sendInvitation(targetUser, btn) {
    if (btn.disabled) return;

    fetch("/invite-user", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_user: targetUser, room: CURRENT_ROOM })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            showToast(data.error, "error");
        } else {
            showToast(`Invitation sent to ${targetUser}!`);
            
            // Start 10s countdown cooldown
            btn.disabled = true;
            btn.classList.add("invited");
            let timeLeft = 10;
            
            const countdownInterval = setInterval(() => {
                btn.textContent = `${timeLeft}s`;
                timeLeft--;
                
                if (timeLeft < 0) {
                    clearInterval(countdownInterval);
                    btn.textContent = "Invite";
                    btn.disabled = false;
                    btn.classList.remove("invited");
                }
            }, 1000);
            
            // Initial set
            btn.textContent = "10s";
        }
    })
    .catch(err => showToast("Error sending invitation", "error"));
}


// ══════════════════════════════════════════════════════════════════════════
// Utility Functions
// ══════════════════════════════════════════════════════════════════════════

/**
 * Auto-scroll messages feed to the bottom.
 */
function scrollToBottom() {
    const feed = document.getElementById("messages-feed");
    if (!feed) return;
    
    // Force immediate scroll
    feed.scrollTop = feed.scrollHeight;
    
    // Use requestAnimationFrame for extra reliability during layout cycles
    window.requestAnimationFrame(() => {
        feed.scrollTop = feed.scrollHeight;
    });
}

/**
 * Format an ISO 8601 timestamp into a readable local time string.
 * Shows "Today HH:MM", "Yesterday HH:MM", or "YYYY-MM-DD HH:MM".
 * @param {string} isoString - ISO 8601 timestamp from Supabase
 * @returns {string} — Formatted timestamp
 */
function formatTimestamp(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString; // Fallback if unparseable

    const now = new Date();
    const h = String(date.getHours()).padStart(2, '0');
    const mi = String(date.getMinutes()).padStart(2, '0');
    const timeStr = `${h}:${mi}`;

    // Check if same calendar day
    const isToday = date.toDateString() === now.toDateString();
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    const isYesterday = date.toDateString() === yesterday.toDateString();

    if (isToday) return `Today ${timeStr}`;
    if (isYesterday) return `Yesterday ${timeStr}`;

    const y = date.getFullYear();
    const mo = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${mo}-${d} ${timeStr}`;
}

/**
 * Escape HTML special characters to prevent XSS.
 * @param {string} text - Raw text
 * @returns {string} — Escaped HTML string
 */
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Check if the message contains only a single emoji.
 * @param {string} text - The message text
 * @returns {boolean}
 */
function isSingleEmoji(text) {
    if (!text) return false;
    const trimmed = text.trim();
    
    // 1. Check if it's in our emoji picker list
    if (typeof OPENMOJI_DATA !== "undefined" && OPENMOJI_DATA.some(item => item.emoji === trimmed)) {
        return true;
    }
    
    // 2. Check for single emoji using regex (basic detection)
    // Matches most common single emoji characters
    const emojiRegex = /^(\u00a9|\u00ae|[\u2000-\u3300]|\ud83c[\ud000-\udfff]|\ud83d[\ud000-\udfff]|\ud83e[\ud000-\udfff])$/;
    if (emojiRegex.test(trimmed)) return true;

    // 3. Fallback: If it's 1-2 chars long and looks like an emoji (high-surrogate)
    if (trimmed.length > 0 && trimmed.length <= 2) {
        const charCode = trimmed.charCodeAt(0);
        if (charCode >= 0xD800 && charCode <= 0xDBFF) {
            return true;
        }
    }

    return false;
}


// ══════════════════════════════════════════════════════════════════════════
// Event Listeners
// ══════════════════════════════════════════════════════════════════════════

// Send message on pressing Enter key
document.getElementById("message-input").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        sendMessage();
    }
});

// File attachment selection
document.getElementById("file-upload").addEventListener("change", handleFileSelect);

// Remove file preview
document.getElementById("remove-image").addEventListener("click", function(e) {
    e.stopPropagation(); // Don't trigger send when clicking remove
    clearFilePreview();
});

// Send on clicking the preview itself
document.getElementById("image-preview").addEventListener("click", sendMessage);

// Create room button
document.getElementById("create-room-btn").addEventListener("click", createRoom);

/**
 * MutationObserver to ensure we scroll when the DOM changes
 */
const scrollObserver = new MutationObserver(() => {
    scrollToBottom();
});

const messagesFeed = document.getElementById("messages-feed");
if (messagesFeed) {
    scrollObserver.observe(messagesFeed, { childList: true, subtree: true });
}

// Modal Controls
const createModal = document.getElementById("create-modal");
document.getElementById("open-create-modal").addEventListener("click", () => {
    // Clear previous errors when opening the modal
    const err = document.getElementById("create-room-error");
    if (err) {
        err.style.display = "none";
        err.textContent = "";
    }
    createModal.style.display = "flex";
    document.getElementById("new-room-name").focus();
});

document.getElementById("close-modal").addEventListener("click", () => {
    createModal.style.display = "none";
});

// Profile Dropdown Toggle
const profileTrigger = document.getElementById("profile-trigger");
const profileDropdown = document.getElementById("profile-dropdown");

profileTrigger.addEventListener("click", (e) => {
    e.stopPropagation();
    profileDropdown.classList.toggle("active");
});

// Close modal on click outside
window.addEventListener("click", (e) => {
    if (e.target === createModal) {
        createModal.style.display = "none";
    }
    // Close profile dropdown if clicking outside
    if (!profileTrigger.contains(e.target)) {
        profileDropdown.classList.remove("active");
    }
});

// Create room on Enter in the room name input
document.getElementById("new-room-name").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        createRoom();
    }
});
const newRoomPwdObj = document.getElementById("new-room-password");
if (newRoomPwdObj) {
    newRoomPwdObj.addEventListener("keydown", function(e) {
        if (e.key === "Enter") {
            e.preventDefault();
            createRoom();
        }
    });
}

// Unlock Room Event Listeners
const unlockBtn = document.getElementById("unlock-btn");
const roomPwdInput = document.getElementById("room-password-input");
if (unlockBtn && roomPwdInput) {
    unlockBtn.addEventListener("click", unlockRoom);
    
    roomPwdInput.addEventListener("keydown", function(e) {
        if (e.key === "Enter") {
            e.preventDefault();
            unlockRoom();
        }
    });
}

// Delete Room Event Listeners
const deleteModal = document.getElementById("delete-modal");
const openDeleteBtn = document.getElementById("open-delete-modal");
const closeDeleteBtn = document.getElementById("close-delete-modal");
const cancelDeleteBtn = document.getElementById("cancel-delete-btn");
const confirmDeleteBtn = document.getElementById("confirm-delete-btn");

if (openDeleteBtn) {
    openDeleteBtn.addEventListener("click", () => {
        // Check online users for warning
        fetch(`/online/${CURRENT_ROOM}`)
            .then(res => res.json())
            .then(users => {
                // Filter out current user
                const others = users.filter(u => u !== CURRENT_USER);
                const warningDiv = document.getElementById("online-warning");
                const countSpan = document.getElementById("online-warning-count");
                
                if (others.length > 0) {
                    countSpan.textContent = others.length;
                    warningDiv.style.display = "block";
                } else {
                    warningDiv.style.display = "none";
                }
                
                deleteModal.style.display = "flex";
            })
            .catch(() => {
                deleteModal.style.display = "flex";
            });
    });
}
if (closeDeleteBtn) closeDeleteBtn.addEventListener("click", () => deleteModal.style.display = "none");
if (cancelDeleteBtn) cancelDeleteBtn.addEventListener("click", () => deleteModal.style.display = "none");
if (confirmDeleteBtn) confirmDeleteBtn.addEventListener("click", confirmDeleteRoom);


// Invite Friends Event Listeners
const inviteModal = document.getElementById("invite-modal");
const openInviteBtn = document.getElementById("open-invite-modal");
const closeInviteBtn = document.getElementById("close-invite-modal");

if (openInviteBtn) {
    openInviteBtn.addEventListener("click", openInviteFriendsModal);
}
if (closeInviteBtn) {
    closeInviteBtn.addEventListener("click", () => {
        inviteModal.style.display = "none";
    });
}
window.addEventListener("click", (e) => {
    if (e.target === inviteModal) {
        inviteModal.style.display = "none";
    }
});


// ══════════════════════════════════════════════════════════════════════════
// Initial Load
// ══════════════════════════════════════════════════════════════════════════

// Load messages and online users immediately on page load
pollMessages();
pollOnlineUsers();

// Check for pending toasts from previous page actions (like deletion)
const pendingToast = localStorage.getItem("pending_toast");
if (pendingToast) {
    const toastData = JSON.parse(pendingToast);
    // Use a small timeout to ensure DOM is fully ready and visible
    setTimeout(() => {
        showToast(toastData.message, toastData.type);
        localStorage.removeItem("pending_toast");
    }, 300);
}


// ══════════════════════════════════════════════════════════════════════════
// Lightbox Functionality
// ══════════════════════════════════════════════════════════════════════════

const lightbox = document.getElementById("lightbox");
const lightboxImg = document.getElementById("lightbox-img");
const lightboxDownload = document.getElementById("lightbox-download");
const lightboxClose = document.getElementById("lightbox-close");

/**
 * Open the lightbox with the given image source.
 * @param {string} src - Source URL of the image
 */
function openLightbox(src) {
    if (!lightbox || !lightboxImg || !lightboxDownload) return;
    lightboxImg.src = src;
    lightboxDownload.href = src;
    lightbox.style.display = "flex";
}

/**
 * Close the lightbox.
 */
function closeLightbox() {
    if (!lightbox || !lightboxImg) return;
    lightbox.style.display = "none";
    lightboxImg.src = "";
}

// Close on 'X' button
if (lightboxClose) {
    lightboxClose.addEventListener("click", (e) => {
        e.stopPropagation();
        closeLightbox();
    });
}

// Close on clicking outside the image
if (lightbox) {
    lightbox.addEventListener("click", (e) => {
        if (e.target === lightbox) {
            closeLightbox();
        }
    });
}

// Export to window so its callable from dynamic HTML
window.openLightbox = openLightbox;

// ══════════════════════════════════════════════════════════════════════════
// Media Picker (Emoji)
// ══════════════════════════════════════════════════════════════════════════

const mediaPickerPopup = document.getElementById("media-picker-popup");
const btnEmojiPicker = document.getElementById("btn-emoji-picker");
const emojiGrid = document.getElementById("emoji-grid");
const messageInput = document.getElementById("message-input");

// Toggle popup
function toggleMediaPicker() {
    if (mediaPickerPopup.style.display === "none" || mediaPickerPopup.style.display === "") {
        mediaPickerPopup.style.display = "flex";
    } else {
        mediaPickerPopup.style.display = "none";
    }
}

// Event listeners for popup buttons
if (btnEmojiPicker) {
    btnEmojiPicker.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleMediaPicker();
    });
}

// Close popup when clicking outside
window.addEventListener("click", (e) => {
    if (mediaPickerPopup && 
        mediaPickerPopup.style.display === "flex" && 
        !mediaPickerPopup.contains(e.target) && 
        !btnEmojiPicker.contains(e.target)) {
        mediaPickerPopup.style.display = "none";
    }
});

// Render Emojis from OPENMOJI_DATA
if (emojiGrid && typeof OPENMOJI_DATA !== "undefined") {
    let emojiHtml = "";
    OPENMOJI_DATA.forEach(item => {
        emojiHtml += `<button class="emoji-btn" data-emoji="${item.emoji}" title="${item.hexcode}">${item.emoji}</button>`;
    });
    emojiGrid.innerHTML = emojiHtml;

    // Attach click listeners
    const emojiBtns = emojiGrid.querySelectorAll(".emoji-btn");
    emojiBtns.forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const emojiChar = btn.dataset.emoji;
            if (messageInput) {
                messageInput.value += emojiChar;
                messageInput.focus();
            }
        });
    });
}


// ══════════════════════════════════════════════════════════════════════════
// Profile Modal
// ══════════════════════════════════════════════════════════════════════════

const profileModal = document.getElementById("profile-modal");
const closeProfileBtn = document.getElementById("close-profile-modal");

// DiceBear avatar styles to offer
const DICEBEAR_STYLES = [
    "adventurer",
    "avataaars",
    "lorelei",
    "notionists"
];

// Seeds for generating avatar variations
const DICEBEAR_SEEDS = [
    "Felix", "Aneka", "Luna", "Milo", "Zara",
    "Rocky", "Bella", "Max", "Sophie", "Oscar",
    "Nala", "Leo", "Coco", "Buddy", "Daisy"
];

let currentDicebearStyle = DICEBEAR_STYLES[0];
let selectedAvatarValue = null;

/**
 * Open the profile modal and initialize the avatar display.
 */
function openProfileModal() {
    profileModal.style.display = "flex";
    profileDropdown.classList.remove("active");

    // Show correct view based on registration status
    document.getElementById("profile-registered-view").style.display = IS_REGISTERED ? "block" : "none";
    document.getElementById("profile-guest-view").style.display = IS_REGISTERED ? "none" : "block";

    // Initialize avatar display
    initProfileAvatar();

    // Render DiceBear style tabs and grid
    if (IS_REGISTERED) {
        renderDicebearStyleTabs();
        renderDicebearGrid(currentDicebearStyle);
    }
}

/**
 * Initialize the profile avatar display based on saved data.
 */
function initProfileAvatar() {
    const avatarDisplay = document.getElementById("profile-avatar-display");
    if (!avatarDisplay) return;

    avatarDisplay.innerHTML = getAvatarHtml(USER_AVATAR, CURRENT_USER);
}

/**
 * Render the DiceBear style tabs.
 */
function renderDicebearStyleTabs() {
    const tabsContainer = document.getElementById("dicebear-style-tabs");
    if (!tabsContainer) return;

    let html = "";
    DICEBEAR_STYLES.forEach(style => {
        const isActive = style === currentDicebearStyle ? "active" : "";
        const displayName = style.replace(/-/g, " ");
        html += `<button class="dicebear-style-tab ${isActive}" data-style="${style}">${displayName}</button>`;
    });
    tabsContainer.innerHTML = html;

    // Attach click listeners
    tabsContainer.querySelectorAll(".dicebear-style-tab").forEach(tab => {
        tab.addEventListener("click", (e) => {
            e.stopPropagation();
            currentDicebearStyle = tab.dataset.style;
            tabsContainer.querySelectorAll(".dicebear-style-tab").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            renderDicebearGrid(currentDicebearStyle);
        });
    });
}

/**
 * Render the DiceBear avatar grid for a given style.
 * @param {string} style - DiceBear style name
 */
function renderDicebearGrid(style) {
    const grid = document.getElementById("dicebear-grid");
    if (!grid) return;

    let html = "";
    DICEBEAR_SEEDS.forEach(seed => {
        const url = `https://api.dicebear.com/9.x/${style}/svg?seed=${seed}`;
        const value = `${style}:${seed}`;
        const selectedClass = (selectedAvatarValue === value) ? "selected" : "";
        html += `<button class="dicebear-avatar-btn ${selectedClass}" data-value="${value}" data-url="${url}">
            <img src="${url}" alt="${seed}" loading="lazy">
        </button>`;
    });
    grid.innerHTML = html;

    // Click listeners for selecting
    grid.querySelectorAll(".dicebear-avatar-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            selectedAvatarValue = btn.dataset.value;

            // Visual selection
            grid.querySelectorAll(".dicebear-avatar-btn").forEach(b => b.classList.remove("selected"));
            btn.classList.add("selected");

            // Update avatar preview
            const avatarDisplay = document.getElementById("profile-avatar-display");
            avatarDisplay.innerHTML = `<img src="${btn.dataset.url}" alt="avatar">`;

            // Save to server
            saveDicebearAvatar(btn.dataset.value);
        });
    });
}

/**
 * Save a DiceBear avatar selection to the server.
 * @param {string} value - style:seed format
 */
function saveDicebearAvatar(value) {
    fetch("/update-avatar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "dicebear", value: value })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            showToast(data.error, "error");
        } else {
            showToast("Avatar updated!", "success");
            // Update global state
            if (!USER_AVATAR) window.USER_AVATAR = {};
            window.USER_AVATAR.type = "dicebear";
            window.USER_AVATAR.value = value;
            // Update sidebar avatar
            updateSidebarAvatar("dicebear", value);
            
            // Refresh messages to show new avatar on old messages immediately
            currentMessages = null;
            pollMessages();
        }
    })
    .catch(() => showToast("Error saving avatar", "error"));
}

/**
 * Update the sidebar avatar to reflect changes.
 * @param {string} type - "dicebear", "upload", or "initial"
 * @param {string} value - avatar value
 */
function updateSidebarAvatar(type, value) {
    const sidebarAvatar = document.querySelector(".sidebar-footer .user-avatar");
    if (!sidebarAvatar) return;

    const avatarObj = (type && value) ? { type, value } : null;
    sidebarAvatar.innerHTML = getAvatarHtml(avatarObj, CURRENT_USER);
}

// ── Profile Modal: Username Edit Toggle ───────────────────────────────────

const btnEditToggle = document.getElementById("btn-edit-username-toggle");
const usernameDisplayWrapper = document.getElementById("username-display-wrapper");
const usernameEditWrapper = document.getElementById("username-edit-wrapper");
const btnCancelUsername = document.getElementById("btn-cancel-username");

if (btnEditToggle && usernameDisplayWrapper && usernameEditWrapper) {
    btnEditToggle.addEventListener("click", () => {
        usernameDisplayWrapper.style.display = "none";
        usernameEditWrapper.style.display = "flex";
        document.getElementById("profile-new-username").focus();
    });
}

if (btnCancelUsername) {
    btnCancelUsername.addEventListener("click", () => {
        usernameDisplayWrapper.style.display = "flex";
        usernameEditWrapper.style.display = "none";
        document.getElementById("username-change-error").style.display = "none";
    });
}

// ── Profile Modal: Panel Switching ────────────────────────────────────────

const btnTriggerPassword = document.getElementById("btn-trigger-password-view");
const btnBackToAvatar = document.getElementById("btn-back-to-avatar");
const avatarPanel = document.getElementById("avatar-settings-panel");
const passwordPanel = document.getElementById("password-settings-panel");

if (btnTriggerPassword && avatarPanel && passwordPanel) {
    btnTriggerPassword.addEventListener("click", () => {
        avatarPanel.style.display = "none";
        passwordPanel.style.display = "flex";
        btnTriggerPassword.classList.add("active-accent");
    });
}

if (btnBackToAvatar) {
    btnBackToAvatar.addEventListener("click", () => {
        avatarPanel.style.display = "flex";
        passwordPanel.style.display = "none";
        if (btnTriggerPassword) btnTriggerPassword.classList.remove("active-accent");
    });
}

// ── Profile Modal Event Listeners ────────────────────────────────────────

// Open profile modal from dropdown
const profileLink = document.querySelector(".dropdown-item:not(.logout)");
if (profileLink) {
    profileLink.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        openProfileModal();
    });
}

// Close profile modal
if (closeProfileBtn) {
    closeProfileBtn.addEventListener("click", () => {
        profileModal.style.display = "none";
    });
}

// Close on backdrop click
window.addEventListener("click", (e) => {
    if (e.target === profileModal) {
        profileModal.style.display = "none";
    }
});

// ── Avatar/Upload Toggle ─────────────────────────────────────────────────

const btnChooseAvatar = document.getElementById("btn-choose-avatar");
const btnChooseUpload = document.getElementById("btn-choose-upload");
const dicebearPicker = document.getElementById("dicebear-picker");
const uploadAvatarSection = document.getElementById("upload-avatar-section");

if (btnChooseAvatar && btnChooseUpload) {
    btnChooseAvatar.addEventListener("click", () => {
        btnChooseAvatar.classList.add("active");
        btnChooseUpload.classList.remove("active");
        if (dicebearPicker) dicebearPicker.style.display = "flex";
        if (uploadAvatarSection) uploadAvatarSection.style.display = "none";
    });

    btnChooseUpload.addEventListener("click", () => {
        btnChooseUpload.classList.add("active");
        btnChooseAvatar.classList.remove("active");
        if (dicebearPicker) dicebearPicker.style.display = "none";
        if (uploadAvatarSection) uploadAvatarSection.style.display = "flex";
    });
}

// ── Avatar File Upload ───────────────────────────────────────────────────

const avatarFileInput = document.getElementById("avatar-file-upload");
if (avatarFileInput) {
    avatarFileInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;

        // Show preview
        const reader = new FileReader();
        reader.onload = function(ev) {
            const previewDiv = document.getElementById("avatar-upload-preview");
            const previewImg = document.getElementById("avatar-preview-img");
            if (previewImg) previewImg.src = ev.target.result;
            if (previewDiv) previewDiv.style.display = "block";

            // Update main avatar display
            const avatarDisplay = document.getElementById("profile-avatar-display");
            if (avatarDisplay) avatarDisplay.innerHTML = `<img src="${ev.target.result}" alt="avatar">`;
        };
        reader.readAsDataURL(file);

        // Upload to server
        const formData = new FormData();
        formData.append("avatar", file);

        fetch("/upload-avatar", {
            method: "POST",
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, "error");
            } else {
                showToast("Avatar uploaded!", "success");
                // Update global state
                if (!USER_AVATAR) window.USER_AVATAR = {};
                window.USER_AVATAR.type = "upload";
                window.USER_AVATAR.value = data.filename;
                updateSidebarAvatar("upload", data.filename);

                // Refresh messages to show new avatar on old messages immediately
                currentMessages = null;
                pollMessages();
            }
        })
        .catch(() => showToast("Error uploading avatar", "error"));
    });
}

// ── Save Username ────────────────────────────────────────────────────────

const btnSaveUsername = document.getElementById("btn-save-username");
if (btnSaveUsername) {
    btnSaveUsername.addEventListener("click", () => {
        const newUsername = document.getElementById("profile-new-username").value.trim();
        const errorDiv = document.getElementById("username-change-error");

        if (!newUsername) {
            errorDiv.textContent = "Username is required.";
            errorDiv.style.display = "block";
            return;
        }

        if (newUsername === CURRENT_USER) {
            errorDiv.textContent = "This is already your username.";
            errorDiv.style.display = "block";
            return;
        }

        errorDiv.style.display = "none";

        fetch("/update-username", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: newUsername })
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                errorDiv.textContent = data.error;
                errorDiv.style.display = "block";
            } else {
                showToast("Username updated! Refreshing...", "success");
                setTimeout(() => window.location.reload(), 1000);
            }
        })
        .catch(() => {
            errorDiv.textContent = "Error updating username.";
            errorDiv.style.display = "block";
        });
    });
}

// ── Save Password ────────────────────────────────────────────────────────

const btnSavePassword = document.getElementById("btn-save-password");
if (btnSavePassword) {
    btnSavePassword.addEventListener("click", () => {
        const currentPwd = document.getElementById("profile-current-password").value.trim();
        const newPwd = document.getElementById("profile-new-password").value.trim();
        const errorDiv = document.getElementById("password-change-error");
        const successDiv = document.getElementById("password-change-success");

        errorDiv.style.display = "none";
        successDiv.style.display = "none";

        if (!currentPwd || !newPwd) {
            errorDiv.textContent = "Both fields are required.";
            errorDiv.style.display = "block";
            return;
        }

        if (newPwd.length < 4) {
            errorDiv.textContent = "New password must be at least 4 characters.";
            errorDiv.style.display = "block";
            return;
        }

        fetch("/update-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ current_password: currentPwd, new_password: newPwd })
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                errorDiv.textContent = data.error;
                errorDiv.style.display = "block";
            } else {
                successDiv.textContent = "Password updated successfully!";
                successDiv.style.display = "block";
                document.getElementById("profile-current-password").value = "";
                document.getElementById("profile-new-password").value = "";
                showToast("Password changed!", "success");
            }
        })
        .catch(() => {
            errorDiv.textContent = "Error updating password.";
            errorDiv.style.display = "block";
        });
    });
}

// ── Guest Registration ───────────────────────────────────────────────────

const btnGuestRegister = document.getElementById("btn-guest-register");
if (btnGuestRegister) {
    btnGuestRegister.addEventListener("click", () => {
        const password = document.getElementById("guest-register-password").value.trim();
        const confirm = document.getElementById("guest-register-confirm").value.trim();
        const errorDiv = document.getElementById("guest-register-error");

        errorDiv.style.display = "none";

        if (!password) {
            errorDiv.textContent = "Password is required.";
            errorDiv.style.display = "block";
            return;
        }

        if (password.length < 4) {
            errorDiv.textContent = "Password must be at least 4 characters.";
            errorDiv.style.display = "block";
            return;
        }

        if (password !== confirm) {
            errorDiv.textContent = "Passwords do not match.";
            errorDiv.style.display = "block";
            return;
        }

        fetch("/register-guest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ password: password })
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                errorDiv.textContent = data.error;
                errorDiv.style.display = "block";
            } else {
                IS_REGISTERED = true;
                showToast("Account registered! Welcome aboard!", "success");

                // Switch views
                document.getElementById("profile-guest-view").style.display = "none";
                document.getElementById("profile-registered-view").style.display = "block";

                // Update badge and subtitle
                const badge = document.getElementById("profile-badge-status");
                if (badge) badge.innerHTML = '<i class="bi bi-patch-check-fill me-1"></i> Registered';
                
                const subtitle = document.getElementById("user-status-subtitle");
                if (subtitle) subtitle.textContent = "Registered Account";

                // Initialize registered features
                renderDicebearStyleTabs();
                renderDicebearGrid(currentDicebearStyle);
            }
        })
        .catch(() => {
            errorDiv.textContent = "Error registering account.";
            errorDiv.style.display = "block";
        });
    });
}

// ── Initialize sidebar avatar on page load ───────────────────────────────

if (USER_AVATAR) {
    updateSidebarAvatar(USER_AVATAR.type, USER_AVATAR.value);
} else {
    // Fallback to placeholder logic for current user
    updateSidebarAvatar(null, null);
}
