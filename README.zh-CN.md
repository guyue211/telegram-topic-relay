# Telegram Topic Relay

[中文](./README.zh-CN.md) | [English](./README.en.md)

一个把 **Telegram 私聊消息** 自动转进 **管理群话题（Topics）** 的 webhook 中继服务。

## 这项目是干嘛的
用户私聊 bot 后：
1. 消息自动进入你的管理群
2. 每个用户对应一个独立话题
3. 你直接在话题里回复
4. bot 再把消息原路发回用户

适合拿来做：
- 私聊客服
- 私域承接
- 广告线索收集
- 无广告的 Telegram 双向中继

## 已有功能
- webhook 模式
- 按用户自动建 / 复用 / 重建话题
- 资料卡与 pin
- 标签面板、标签搜索、标签下用户列表
- 黑名单面板
- 历史记录、清空记录、刷新资料、重命名话题
- systemd / Docker 部署

## 环境要求
- Linux
- Python 3.10+
- HTTPS 域名
- Telegram bot token
- 开启 Topics 的 supergroup
- Nginx 或其他反向代理

## 快速开始
### 1）配置
```bash
cp config.example.json config.json
```

示例：
```json
{
  "bot_token": "YOUR_BOT_TOKEN",
  "admin_id": 123456789,
  "listen_host": "127.0.0.1",
  "listen_port": 8780,
  "webhook_secret": "CHANGE_ME"
}
```

### 2）启动
```bash
chmod +x run_webhook.sh
./run_webhook.sh
```

### 3）反向代理
```nginx
location /telegram-relay/webhook {
    proxy_pass http://127.0.0.1:8780/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Telegram-Bot-Api-Secret-Token $http_x_telegram_bot_api_secret_token;
}

location /telegram-relay/health {
    proxy_pass http://127.0.0.1:8780/health;
}
```

### 4）设置 webhook
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/telegram-relay/webhook" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>" \
  -d 'allowed_updates=["message","callback_query"]' \
  -d "drop_pending_updates=true"
```

## 群话题模式怎么用
1. 把 bot 拉进已开启 Topics 的 supergroup
2. 去 BotFather 关闭隐私模式
3. 在群里发送 `/bindgroup`
4. 后续用户私聊 bot，消息会自动进入管理群话题
5. 你直接在话题里回复即可

## 常用命令
- `/bindgroup`
- `/unbindgroup`
- `/tags`
- `/tagsearch 关键词`
- `/blacklist`
- `/stats`
- `/help`
- `/ban`
- `/unban`
- `/tag 标签名`
- `/untag 标签名`
- `/history`
- `/clear`
- `/profile`
- `/rename`

## 健康检查
```bash
curl http://127.0.0.1:8780/health
curl https://your-domain.com/telegram-relay/health
```

## 仓库
- GitHub: https://github.com/guyue211/telegram-topic-relay
