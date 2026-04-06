# Telegram Topic Relay

默认文档：中文

- [中文文档](./README.zh-CN.md)
- [English Documentation](./README.en.md)

一个把 **Telegram 私聊消息** 自动转进 **管理群话题（Topics）** 的 webhook 中继服务。

## 适合谁用
- 私聊客服
- 私域承接
- 线索收集
- 不想忍受公益双向机器人广告的人

## 核心能力
- 私聊消息自动进入管理群话题
- 每个用户独立话题
- 直接在话题里回复用户
- 支持标签、黑名单、历史记录、资料卡
- 支持 webhook、systemd、Docker

## 快速开始
```bash
cp config.example.json config.json
chmod +x run_webhook.sh
./run_webhook.sh
```

配置好反向代理后，设置 webhook：

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/telegram-relay/webhook" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>" \
  -d 'allowed_updates=["message","callback_query"]' \
  -d "drop_pending_updates=true"
```

## 常用命令
- `/bindgroup`
- `/tags`
- `/tagsearch 关键词`
- `/blacklist`
- `/stats`
- `/help`

详细说明看中文文档：[`README.zh-CN.md`](./README.zh-CN.md)
