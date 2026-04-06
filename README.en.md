# Telegram Topic Relay

[中文](./README.zh-CN.md) | [English](./README.en.md)

A webhook relay that routes **Telegram private chats** into **management group topics**.

## What it does
When a user messages the bot:
1. the message goes into your management group
2. each user gets their own topic
3. you reply inside the topic
4. the bot sends the reply back to the user

Good for:
- private chat support
- lead intake
- traffic handoff
- ad-free Telegram two-way relay

## Features
- webhook mode
- auto create / reuse / recreate topics per user
- profile card and pin
- tag panel, tag search, tagged user list
- blacklist panel
- history, clear history, refresh profile, rename topic
- systemd / Docker deployment

## Quick Start
### 1) Configure
```bash
cp config.example.json config.json
```

```json
{
  "bot_token": "YOUR_BOT_TOKEN",
  "admin_id": 123456789,
  "listen_host": "127.0.0.1",
  "listen_port": 8780,
  "webhook_secret": "CHANGE_ME"
}
```

### 2) Run
```bash
chmod +x run_webhook.sh
./run_webhook.sh
```

### 3) Reverse proxy
```nginx
location /telegram-relay/webhook {
    proxy_pass http://127.0.0.1:8780/;
    proxy_set_header X-Telegram-Bot-Api-Secret-Token $http_x_telegram_bot_api_secret_token;
}

location /telegram-relay/health {
    proxy_pass http://127.0.0.1:8780/health;
}
```

### 4) Set webhook
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/telegram-relay/webhook" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>" \
  -d 'allowed_updates=["message","callback_query"]' \
  -d "drop_pending_updates=true"
```

## Usage
1. Add the bot to a forum-enabled supergroup
2. Disable BotFather privacy mode
3. Send `/bindgroup` in the group
4. Users message the bot in private
5. Reply directly inside the topic

## Repository
- GitHub: https://github.com/guyue211/telegram-topic-relay
