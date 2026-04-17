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
let selectedImageFile = null;   // Currently selected image for attachment


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
                currentMessages = messages;
                renderMessages(messages);
                scrollToBottom();
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
// Rendering — Messages
// ══════════════════════════════════════════════════════════════════════════

/**
 * Render all messages into the messages feed div.
 * @param {Array} messages - Array of message objects
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

        html += `<div class="message-item ${isOwn ? 'own' : ''}">`;
        html += `  <div class="message-avatar">${initial}</div>`;
        html += `  <div class="message-content">`;
        html += `    <div class="message-header">`;
        html += `      <span class="message-username">${escapeHtml(msg.username)}</span>`;
        html += `      <span class="message-timestamp">${msg.timestamp}</span>`;
        html += `    </div>`;

        if (msg.message) {
            html += `    <div class="message-text">${escapeHtml(msg.message)}</div>`;
        }

        // Show image if attached
        if (msg.image) {
            html += `    <img class="message-image" src="/static/uploads/${msg.image}" alt="attachment" onclick="window.open(this.src, '_blank')">`;
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
        const initial = users[i].charAt(0).toUpperCase();
        html += `<li class="online-user-item">`;
        html += `  <div class="online-avatar-container">`;
        html += `    <div class="online-user-avatar">${initial}</div>`;
        html += `    <div class="online-user-dot"></div>`;
        html += `  </div>`;
        html += `  <span class="online-user-name">${escapeHtml(users[i])}</span>`;
        html += `</li>`;
    }

    list.innerHTML = html;
}

/**
 * Update the online count in the chat header.
 * @param {number} count - Number of online users
 */
function updateOnlineCount(count) {
    const el = document.getElementById("online-count");
    el.textContent = count + " online";
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

    // Must have either text or image
    if (!messageText && !selectedImageFile) {
        return;
    }

    // If there's an image, upload it first
    if (selectedImageFile) {
        uploadImage(selectedImageFile, function(filename) {
            // Send the message with image filename
            postMessage(messageText, filename);
            clearImagePreview();
        });
    } else {
        postMessage(messageText, null);
    }

    // Clear input
    input.value = "";
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
 * Upload an image file to the server.
 * @param {File} file - The image file
 * @param {Function} callback - Called with the uploaded filename
 */
function uploadImage(file, callback) {
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
 * Handle image file selection — show preview.
 */
function handleImageSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    selectedImageFile = file;

    // Show preview
    const reader = new FileReader();
    reader.onload = function(e) {
        const previewDiv = document.getElementById("image-preview");
        const previewImg = document.getElementById("preview-img");
        previewImg.src = e.target.result;
        previewDiv.style.display = "inline-block";
    };
    reader.readAsDataURL(file);
}

/**
 * Clear the image preview and reset selection.
 */
function clearImagePreview() {
    selectedImageFile = null;
    document.getElementById("image-preview").style.display = "none";
    document.getElementById("preview-img").src = "";
    document.getElementById("image-upload").value = "";
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

    if (!roomName) {
        errorDiv.textContent = "Room name is required.";
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


// ══════════════════════════════════════════════════════════════════════════
// Utility Functions
// ══════════════════════════════════════════════════════════════════════════

/**
 * Auto-scroll messages feed to the bottom.
 */
function scrollToBottom() {
    const feed = document.getElementById("messages-feed");
    feed.scrollTop = feed.scrollHeight;
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


// ══════════════════════════════════════════════════════════════════════════
// Event Listeners
// ══════════════════════════════════════════════════════════════════════════

// Send message on clicking Send button
document.getElementById("send-btn").addEventListener("click", sendMessage);

// Send message on pressing Enter key
document.getElementById("message-input").addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        sendMessage();
    }
});

// Image attachment selection
document.getElementById("image-upload").addEventListener("change", handleImageSelect);

// Remove image preview
document.getElementById("remove-image").addEventListener("click", clearImagePreview);

// Create room button
document.getElementById("create-room-btn").addEventListener("click", createRoom);

// Modal Controls
const createModal = document.getElementById("create-modal");
document.getElementById("open-create-modal").addEventListener("click", () => {
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


// ══════════════════════════════════════════════════════════════════════════
// Initial Load
// ══════════════════════════════════════════════════════════════════════════

// Load messages and online users immediately on page load
pollMessages();
pollOnlineUsers();
