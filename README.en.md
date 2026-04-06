# Telegram Topic Relay

[中文](./README.zh-CN.md) | [English](./README.en.md)

Telegram Topic Relay is a webhook-based service that routes Telegram private chats into forum topics in a management group.

## Features

- Webhook mode, no `getUpdates` polling
- Route private messages into a management group
- Auto create or recreate topics per user
- Pin profile card when a topic is created/recreated
- Do not repeat profile card for every follow-up message
- Reply to user directly inside the topic
- Tags, ban/unban, history, clear history, refresh profile, rename topic
- systemd-friendly deployment
- Docker-ready

## Project Structure

```text
telegram-topic-relay/
├── README.md
├── README.zh-CN.md
├── README.en.md
├── .gitignore
├── config.example.json
├── relay_webhook.py
├── run_webhook.sh
├── telegram-topic-relay.service
├── Dockerfile
└── docker-compose.yml
```

## Quick Start

### 1. Configure

```bash
cp config.example.json config.json
```

Example:

```json
{
  "bot_token": "YOUR_BOT_TOKEN",
  "admin_id": 123456789,
  "listen_host": "127.0.0.1",
  "listen_port": 8780,
  "webhook_secret": "CHANGE_ME"
}
```

### 2. Run locally

```bash
chmod +x run_webhook.sh
./run_webhook.sh
```

### 3. Configure reverse proxy

Example Nginx:

```nginx
location /telegram-relay/webhook {
    proxy_pass http://127.0.0.1:8780/;
    proxy_set_header X-Telegram-Bot-Api-Secret-Token $http_x_telegram_bot_api_secret_token;
}

location /telegram-relay/health {
    proxy_pass http://127.0.0.1:8780/health;
}
```

### 4. Set webhook

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/telegram-relay/webhook" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>" \
  -d 'allowed_updates=["message","callback_query"]' \
  -d "drop_pending_updates=true"
```

## Group Topic Workflow

1. Add the bot to a forum-enabled supergroup.
2. Disable BotFather privacy mode.
3. Send `/bindgroup` in the group.
4. User sends private message to the bot.
5. Bot creates/reuses a topic for the user.
6. Admin replies directly inside the topic.

## Admin Commands

- `/bindgroup`
- `/unbindgroup`
- `/ban`
- `/unban`
- `/tag tag-name`
- `/untag tag-name`
- `/history`
- `/clear`
- `/profile`
- `/rename`

## Buttons

- `🚫 Ban / ✅ Unban`
- `🧾 History`
- `🏷 Tag hint`
- `🧹 Clear`
- `👤 Refresh`
- `✏️ Rename`

## Blacklist Panel

Currently implemented as a profile-card-driven moderation flow:
- ban/unban button
- `/ban` and `/unban`
- banned users are blocked from normal delivery flow

The next step can be a dedicated `/blacklist` panel command and paginated management view.

## Docker

Build:

```bash
docker build -t telegram-topic-relay .
```

Run:

```bash
docker compose up -d
```

## Health Check

```bash
curl http://127.0.0.1:8780/health
curl https://your-domain.com/telegram-relay/health
```

## Repository

- GitHub: https://github.com/guyue211/telegram-topic-relay
