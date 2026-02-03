# Chat System — README

## Overview ✅
This repository is a Django + Channels real-time chat system that uses Redis as the channel layer. It supports WebSocket-based chat messaging and real-time notifications. A Redis-based mechanism suppresses notifications for chats currently open by the recipient.

---

## Prerequisites 🛠️
- Python 3.10+ (or compatible)
- Redis running locally (or accessible host)
- Virtual environment (recommended)

Recommended packages (if you don't have a `requirements.txt`):
- django
- channels
- channels_redis
- daphne (optional)
- djangorestframework
- djangorestframework-simplejwt
- python-dotenv
- redis (Python client)

Install essentials quickly:

pip install django channels channels_redis djangorestframework djangorestframework-simplejwt python-dotenv redis

---

## Environment ✅
1. Copy `.env.example` to `.env` and update values for your environment:

cp .env.example .env

2. Important variables:
- `DJANGO_SECRET_KEY` — secret key
- `DJANGO_DEBUG` — True/False
- `DJANGO_ALLOWED_HOSTS` — comma-separated hosts (e.g. `localhost,127.0.0.1`)
- `REDIS_HOST`, `REDIS_PORT`
- Database variables (`DB_ENGINE`, `DB_NAME`, `DB_USER`, etc.)

> Do not commit `.env` to version control.

---

## Run the app (Development) ▶️
1. Ensure Redis is running: (Docker)

```bash
docker run --rm -p 6379:6379 redis:7
```

or run a locally installed Redis server.

2. Install python packages and create DB:

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt   # if you have one, else install packages above
python manage.py migrate
python manage.py createsuperuser
```

3. Start the Django development server (use this for local testing):

```bash
python manage.py runserver
```

The WebSocket ASGI application is served by the `runserver` command in development (Channels integrates with Django's dev server).

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

## Running tests ✅
- Make sure Redis is running (tests use Redis for the open-chat set):

```bash
python manage.py test notifications
```

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
