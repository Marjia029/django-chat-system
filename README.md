# Real-Time Chat Application - System Architecture

## Overview

This is a real-time chat application built with Django that allows users to send messages, share files, and receive instant notifications. The system uses WebSockets for real-time communication and REST APIs for fetching historical data.

**Key Features:**
- Real-time messaging via WebSocket connections
- Support for text, images, videos, audio, and file attachments
- End-to-end encryption support
- Smart notification system
- Read receipts and message status tracking
- Presence tracking (know when users have chats open)

---
## Technology Stack

| Component | Technology |
|-----------|-----------|
| **Backend Framework** | Django (Python) |
| **REST API** | Django REST Framework |
| **WebSocket Support** | Django Channels (ASGI) |
| **Database** | PostgreSQL |
| **Cache & Message Broker** | Redis |
| **File Storage** | Django Media Files (filesystem) |
| **Authentication** | Django Auth System |

---

## System Architecture

```
┌─────────────┐
│   Client    │ (Web/Mobile)
│ (Frontend)  │
└──────┬──────┘
       │
       ├─────── HTTP/REST ────────┐
       │                          │
       └─────── WebSocket ────────┤
                                  │
                         ┌────────▼────────┐
                         │  Django Server  │
                         │   (+ Channels)  │
                         └────────┬────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
            ┌───────▼──────┐ ┌───▼────┐ ┌─────▼─────┐
            │    Database  │ │ Redis  │ │   Files   │
            │              │ │ Cache  │ │  Storage  │
            └──────────────┘ └────────┘ └───────────┘
```

---
## Project Structure
```text
chat_system_backend/
├── manage.py                   # Django command-line utility
├── requirements.txt            # Python dependencies 
├── .env                        # Environment variables 
├── media/                      # Directory where user uploaded files 
│   └── chat_files/             # Files, Photos storage
│
├── core/                       # Project Configuration 
│   ├── __init__.py
│   ├── asgi.py                 # ASGI entry point for WebSockets
│   ├── settings.py             # Global settings 
│   ├── urls.py                 # Main HTTP URL routing
│   └── wsgi.py                 # WSGI entry point for synchronous HTTP
│
├── accounts/                   # App: User Authentication & Profiles
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py               # Custom User model
│   ├── serializers.py          # Serializers for Login, Signup, User Profile
│   ├── urls.py                 # Routes like /api/auth/login/
│   └── views.py                # Views for JWT authentication
│
├── chat/                       # App: Real-time Messaging
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── consumers.py            # WebSocket logic (ChatConsumer)
│   ├── models.py               # Message model
│   ├── routing.py              # WebSocket URL routing (ws/chat/...)
│   ├── serializers.py          # MessageSerializer (for history/API)
│   ├── urls.py                 # Routes like /api/chat/history/
│   └── views.py                # Views for fetching message history
│
└── notifications/              # App: Alerts & Signals
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── models.py               # Notification model
    ├── serializers.py          # NotificationSerializer
    ├── signals.py              # Logic to auto-create notifications
    ├── urls.py                 # Routes like /api/notifications/
    └── views.py                # Views for listing/marking read notifications
```
## Core Components

### 1. ChatConsumer (WebSocket Handler)

**File:** `chat/consumers.py`

This is the heart of real-time communication. It handles WebSocket connections and manages all live message exchanges.

**What it does:**
- Accepts WebSocket connections from authenticated users
- Receives messages from clients
- Saves messages to the database
- Routes messages to recipients in real-time
- Tracks which conversations users have open (using Redis)
- Handles file uploads (base64 encoded)
- Marks notifications as seen when users open chats

**WebSocket Message Types:**

1. **chat_message** - Send a message
   ```json
   {
     "type": "chat_message",
     "recipient_id": 123,
     "content": "Hello!",
     "message_type": "text",
     "is_encrypted": false
   }
   ```

2. **open_chat** - Tell server you opened a conversation
   ```json
   {
     "type": "open_chat",
     "chat_with": 123
   }
   ```

3. **close_chat** - Tell server you closed a conversation
   ```json
   {
     "type": "close_chat",
     "chat_with": 123
   }
   ```

### 2. REST API Views

**File:** `chat/views.py` (chat app)

These are standard HTTP endpoints for fetching data.

**ConversationListView** (`GET /api/conversations/`)
- Returns list of all your conversations
- Shows last message, timestamp, unread count
- Paginated results
- Sorted by most recent activity

**MessageHistoryView** (`GET /api/messages/{user_id}/`)
- Returns full message history with a specific user
- Automatically marks unread messages as read
- Ordered by timestamp

### 3. Notification System

**File:** `signals.py`

Uses Django signals to automatically create notifications when messages are sent.

**How it works:**
1. User A sends a message to User B
2. Message is saved to database
3. Django's `post_save` signal triggers
4. System checks Redis: "Does User B have the chat with User A open?"
   - **If YES**: Don't create notification (they're already reading)
   - **If NO**: Create notification and push it via WebSocket
5. Notification is sent to User B in real-time

**File:** `views.py` (notifications app)

API endpoints for managing notifications:
- `GET /api/notifications/` - List all notifications
- `POST /api/notifications/{id}/read/` - Mark one as read
- `POST /api/notifications/read-all/` - Mark all as read
- `POST /api/notifications/seen-all/` - Mark all as seen

---

## How Messages Flow

### Sending a Message

```
1. User A types message and clicks send
        ↓
2. Client sends WebSocket message to server
        ↓
3. ChatConsumer receives message
        ↓
4. Consumer checks: Does User B exist?
        ↓
5. Consumer checks Redis: Does User B have chat with User A open?
        ↓
6. Save message to database (mark as read if chat is open)
        ↓
7. Send message back to User A (confirmation)
        ↓
8. Broadcast message to User B via WebSocket
        ↓
9. If chat wasn't open: Create notification → Push to User B
```

### Reading Messages

```
1. User B opens conversation with User A
        ↓
2. Client sends "open_chat" WebSocket message
        ↓
3. Consumer adds "User A" to User B's Redis set of open chats
        ↓
4. Consumer marks all notifications from User A as seen
        ↓
5. Client fetches message history via REST API
        ↓
6. API marks all unread messages from User A as read
        ↓
7. Messages displayed to User B
```

---

## Redis Usage

Redis serves two critical purposes:

### 1. Channels Layer (Message Broker)
- Allows multiple Django servers to communicate
- Routes WebSocket messages between different server instances
- Enables horizontal scaling

### 2. Presence Tracking
- Stores which chats each user has open
- Key structure: `open_chats:{user_id}` → Set of user IDs

**Example:**
```
# User 42 has chats open with users 10, 15, and 20
Redis Key: "open_chats:42"
Redis Value: Set {10, 15, 20}
```

**Why this matters:**
- If someone sends a message while you have the chat open → marked as read immediately
- If someone sends a message while chat is closed → marked as unread + notification sent

---

## Database Schema

### Message Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `sender` | ForeignKey(User) | Who sent the message |
| `recipient` | ForeignKey(User) | Who receives the message |
| `content` | Text | Message text (can be encrypted) |
| `message_type` | String | "text", "image", "video", "audio", "file" |
| `file` | File | Uploaded file (if any) |
| `file_name` | String | Original filename |
| `file_size` | Integer | Size in bytes |
| `file_type` | String | MIME type |
| `timestamp` | DateTime | When message was sent |
| `is_read` | Boolean | Has recipient read it? |
| `is_encrypted` | Boolean | Is content encrypted? |

**Indexes needed:**
- `(sender, recipient, timestamp)` - For conversation queries
- `(recipient, is_read)` - For unread count

### Notification Model

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `user` | ForeignKey(User) | Who gets the notification |
| `notification_type` | String | Type (e.g., "message") |
| `message` | Text | Notification text |
| `related_message` | ForeignKey(Message) | Associated message |
| `is_read` | Boolean | Has user read it? |
| `is_seen` | Boolean | Has user seen it? (acknowledged) |
| `created_at` | DateTime | When created |

**Difference between `is_seen` and `is_read`:**
- `is_seen`: User saw the notification badge (acknowledged it exists)
- `is_read`: User clicked and opened the notification

---

## API Reference

### Chat Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/conversations/` | List all conversations with metadata |
| `GET` | `/api/messages/{user_id}/` | Get message history with a user |

### Notification Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/notifications/` | List all notifications + unseen count |
| `POST` | `/api/notifications/{id}/read/` | Mark specific notification as read |
| `POST` | `/api/notifications/read-all/` | Mark all notifications as read |
| `POST` | `/api/notifications/seen-all/` | Mark all notifications as seen |

### WebSocket Connection

**URL:** `ws://your-domain/ws/chat/`

**Authentication:** Must be logged in (Django session/token)

---

## Security Features

### Authentication & Authorization
- All WebSocket connections require authentication
- Anonymous users are immediately disconnected
- Users can only access their own conversations
- All API endpoints require `IsAuthenticated` permission

### End-to-End Encryption Support
- Users have a `public_key` field
- Messages have an `is_encrypted` flag
- Public keys are shared with messages
- Actual encryption/decryption happens client-side
- Server stores encrypted content as-is (can't read it)

### Input Validation
- JSON parsing with error handling
- Recipient validation before saving messages
- File type and size validation
- Base64 decoding with exception handling

---

## Data Flow Diagrams

### Message Sending Flow

```
┌─────────┐                ┌──────────────┐               ┌─────────┐
│ User A  │                │    Server    │               │ User B  │
└────┬────┘                └──────┬───────┘               └────┬────┘
     │                            │                            │
     │  WebSocket: chat_message   │                            │
     │───────────────────────────>│                            │
     │                            │                            │
     │                            │ Save to Database           │
     │                            │────────┐                   │
     │                            │        │                   │
     │                            │<───────┘                   │
     │                            │                            │
     │      Confirmation          │                            │
     │<───────────────────────────│                            │
     │                            │                            │
     │                            │   WebSocket: chat_message  │
     │                            │───────────────────────────>│
     │                            │                            │
     │                            │ (If chat not open)         │
     │                            │                            │
     │                            │   WebSocket: notification  │
     │                            │───────────────────────────>│
     │                            │                            │
```

### Presence Tracking Flow

```
┌─────────┐                ┌──────────────┐               ┌───────┐
│ User B  │                │    Server    │               │ Redis │
└────┬────┘                └──────┬───────┘               └───┬───┘
     │                            │                            │
     │  WebSocket: open_chat      │                            │
     │  {chat_with: User A}       │                            │
     │───────────────────────────>│                            │
     │                            │                            │
     │                            │  SADD open_chats:B "A"     │
     │                            │───────────────────────────>│
     │                            │                            │
     │                            │  Mark notifications seen   │
     │                            │────────┐                   │
     │                            │        │                   │
     │                            │<───────┘                   │
     │                            │                            │
     │      Acknowledgment        │                            │
     │<───────────────────────────│                            │
     │                            │                            │
     
     (Later, when User A sends message)
     
     │                            │                            │
     │                            │  SISMEMBER open_chats:B "A"│
     │                            │───────────────────────────>│
     │                            │                            │
     │                            │        Returns: TRUE       │
     │                            │<───────────────────────────│
     │                            │                            │
     │                            │  → Mark message as read    │
     │                            │  → Skip notification       │
     │                            │                            │
```
---

## Key Design Decisions

### Why Redis for Presence Tracking?
- **Fast**: Microsecond latency for set operations
- **Simple**: SADD/SREM/SISMEMBER are perfect for tracking open chats
- **Ephemeral**: If user disconnects, we can clean up easily
- **Shared State**: Multiple servers can access same presence data

### Why Separate `is_seen` and `is_read`?
- **Better UX**: Badge disappears when seen (less annoying)
- **User Control**: Can see notifications without marking as "read"
- **Analytics**: Can track notification engagement separately

### Why Django Channels?
- **Native Django Integration**: Works seamlessly with Django auth, ORM, etc.
- **ASGI Standard**: Modern Python async standard
- **Group Broadcasting**: Easy to send messages to all user's connections
- **Scalable**: Can run multiple servers with Redis backend

### Why Store Encrypted Messages?
- **Zero-Knowledge**: Server can't read encrypted messages
- **Privacy**: Users control their encryption keys
- **Trust**: Users don't have to trust the server
- **Compliance**: Meets privacy regulations

---
## Installation & Setup 🛠️

## Prerequisites 🛠️
- Python 3.10+ (or compatible)
- Redis running locally (or accessible host)
- Virtual environment (recommended)


### 1. Clone the Repository
Start by cloning the project to your local machine:

```bash
git clone https://github.com/Marjia029/django-chat-system.git
cd django-chat-system

```

### 2. Set Up Virtual Environment

It is recommended to use a virtual environment to manage dependencies:

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate

```

### 3. Install Dependencies

Install all required Python packages:

```bash
pip install -r requirements.txt

```

**Note:** If `requirements.txt` is missing, install the core packages manually:
```bash
pip install django channels channels_redis djangorestframework djangorestframework-simplejwt python-dotenv redis daphne
```


### 4. Start Redis

The chat system requires Redis to handle real-time messages.

**Using Docker (Recommended):**

```bash
docker run -d -p 6379:6379 redis:7

```

**Or using local installation:**

* **Mac:** `brew services start redis`
* **Linux:** `sudo service redis-server start`
* **Windows:** Run `redis-server.exe`

### 5. Environment Configuration

Create your local environment file by copying the example:

```bash
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env

```

Open `.env` and configure your settings:

* `DJANGO_SECRET_KEY`: Add a secure random string
* `DEBUG`: Set to `True` for development
* `REDIS_HOST`: `127.0.0.1` (or your Docker IP)

### 6. Database Setup

Initialize the database and create an admin user:

```bash
python manage.py migrate
python manage.py createsuperuser

```

### 7. Run the Application

Start the Django development server (ASGI):

```bash
python manage.py runserver

```

The application will be available at:

* **HTTP:** `http://127.0.0.1:8000/`
* **WebSocket:** `ws://127.0.0.1:8000/ws/chat/`

---

## Postman / WebSocket testing guide 📬
1. Obtain JWT access tokens:
   - POST `/api/accounts/login/` with `{ "email": "user@example.com", "password": "pass" }`
   - Copy the `access` token from response.

2. Open a WebSocket connection for a user (recipient):
   - WS URL: `ws://localhost:8000/ws/chat/?token=<RECIPIENT_ACCESS_TOKEN>`
   - Immediately send:
     ```json
     {"type":"open_chat", "chat_with": <SENDER_ID>}
     ```
   - Expect ack:
     ```json
     {"type":"open_chat_ack","chat_with": <SENDER_ID>}
     ```
   - Confirm Redis membership (debug):
     ```bash
     redis-cli SMEMBERS open_chats:<RECIPIENT_ID>
     ```

3. Open sender WebSocket similarly with sender's token.

4. Send message from sender to recipient:
   ```json
   {"type":"chat_message","recipient_id": <RECIPIENT_ID>, "content":"Hello"}
   ```
   - Recipient should always receive a `chat_message` event with message payload.
   - If recipient has an open chat with sender (sent `open_chat`), **no** `notification` event should be delivered and no `Notification` DB record should be created.
   - If recipient does NOT have the chat open, a `notification` message will be created and pushed.

5. Close chat when done:
   ```json
   {"type":"close_chat","chat_with": <SENDER_ID>}
   ```
   - Expect ack: `{"type":"close_chat_ack","chat_with": <SENDER_ID>}`

---


## Troubleshooting 🐞
- WebSocket handshake rejected / invalid host: Ensure `DJANGO_ALLOWED_HOSTS` includes `localhost` or `127.0.0.1` and restart server.
- Token auth failing: Use `?token=<ACCESS_TOKEN>` in the WS URL and check server logs. The middleware logs token authentication attempts.
- Notifications still appear when chat is open: ensure `open_chat` was sent and Redis set contains the sender id for the recipient; check server logs and Redis contents.

---

## Notes & Tips 💡
- Current open-chat tracking is per-user; if multiple tabs exist, any open tab suppresses notifications for that chat. If you need per-tab behavior, change the Redis set semantics to use unique client ids instead of plain user ids.
- Small race conditions are possible if a message is sent at the exact moment the client opens the chat. Sending `open_chat` as early as possible on UI load reduces this.

---

If you'd like, I can:
- Add a Postman collection with WebSocket requests and examples you can import, or
- Add a short shell script to automate a basic end-to-end test.

Pick one and I'll add it. ✅

---


## Future Enhancements

### Features to Add
- [ ] Group chat support (multiple participants)
- [ ] Typing indicators
- [ ] Message reactions (emoji)
- [ ] Message editing and deletion
- [ ] Voice/video calling
- [ ] Message search
- [ ] User status (online/offline/away)
- [ ] Message threading/replies
- [ ] Push notifications for mobile

### Technical Improvements
- [ ] Message pagination in history view
- [ ] Direct S3 uploads with pre-signed URLs
- [ ] Rate limiting on message sending
- [ ] Database read replicas
- [ ] Elasticsearch for message search
- [ ] Message delivery receipts (sent/delivered/read)
- [ ] WebRTC for voice/video
- [ ] Background job queue (Celery) for notifications

---

## Conclusion

This chat application uses a modern architecture that combines:
- **Real-time communication** via WebSockets (Django Channels)
- **Traditional REST APIs** for data fetching
- **Smart presence tracking** with Redis
- **Automatic notifications** via Django signals
- **End-to-end encryption** support

The system is designed to scale horizontally and can support thousands of concurrent users with proper infrastructure. The separation of concerns makes it easy to maintain and extend with new features.