# Telegram Topic Relay

一个用于 Telegram 私聊转群话题的轻量 webhook 服务。

核心目标：
- 用户私聊 bot
- 在管理群中按用户自动创建 / 复用话题
- 管理员直接在对应话题里回复
- 支持资料卡、标签、拉黑、历史记录

## 功能特性

- webhook 模式，不走 `getUpdates` 轮询
- 私聊消息自动进入管理群话题
- 话题按用户自动创建
- 旧话题失效时自动重建
- 新建/重建话题时自动发送并 pin 资料卡
- 后续消息不重复刷名片
- 资料卡按钮：拉黑、解封、记录、清空、刷新、改名
- 管理命令：`/bindgroup`、`/unbindgroup`、`/ban`、`/unban`、`/tag`、`/untag`、`/history`、`/clear`、`/profile`、`/rename`

## 目录结构

```text
telegram-topic-relay/
├── README.md
├── .gitignore
├── config.example.json
├── relay_webhook.py
└── run_webhook.sh
```

## 运行要求

- Python 3.10+
- 一个 Telegram bot token
- 一个开启了 Topics/话题 的 Telegram supergroup
- 反向代理（推荐 Nginx）
- HTTPS 域名

## 配置

复制配置文件：

```bash
cp config.example.json config.json
```

填写：

```json
{
  "bot_token": "YOUR_BOT_TOKEN",
  "admin_id": 123456789,
  "listen_host": "127.0.0.1",
  "listen_port": 8780,
  "webhook_secret": "CHANGE_ME"
}
```

字段说明：

- `bot_token`: BotFather 提供的 token
- `admin_id`: 你的 Telegram 数字 ID
- `listen_host`: 本地监听地址
- `listen_port`: 本地监听端口
- `webhook_secret`: Telegram webhook secret token

## 启动

```bash
chmod +x run_webhook.sh
./run_webhook.sh
```

或后台运行：

```bash
nohup ./run_webhook.sh >/dev/null 2>&1 &
```

## Nginx 示例

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

## 设置 Telegram webhook

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/telegram-relay/webhook" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>" \
  -d 'allowed_updates=["message","callback_query"]' \
  -d "drop_pending_updates=true"
```

## 群话题模式使用流程

### 1. 把 bot 拉进群
把 bot 拉进一个开启了 Topics/话题的 supergroup。

### 2. 关闭 BotFather 隐私模式
在 `@BotFather` 中：
- `/mybots`
- 选择你的 bot
- `Bot Settings`
- `Group Privacy`
- 关闭

### 3. 在群里绑定管理群
管理员在群里发送：

```text
/bindgroup
```

绑定成功后，私聊消息会自动路由到这个群。

### 4. 用户私聊 bot
效果：
- 自动建 / 复用话题
- 首次会发送并 pin 资料卡
- 后续消息只推正文

### 5. 管理员在话题里回复
直接在对应话题里发消息即可回给用户。

## 按钮和命令

### 资料卡按钮
- `🚫 拉黑 / ✅ 解封`
- `🧾 记录`
- `🏷 标签`
- `🧹 清空`
- `👤 刷新`
- `✏️ 改名`

### 管理命令
- `/bindgroup`
- `/unbindgroup`
- `/ban`
- `/unban`
- `/tag 广告`
- `/untag 广告`
- `/history`
- `/clear`
- `/profile`
- `/rename`

## 行为说明

- 新建话题时：发送资料卡并 pin
- 重建话题时：发送资料卡并 pin
- 普通后续消息：只发正文
- 用户侧默认不再收到“已收到”回执
- 旧话题失效时：自动重建新话题

## 日志

服务会把日志写到：

```text
relay.log
```

建议记录以下信息：
- webhook 启动
- incoming message
- reply message
- callback query
- topic recreate
- Telegram API error

## 状态文件

运行时会生成：

- `state.json`
- `relay.log`
- `nohup.out`

这些文件不建议提交到 Git。

## 建议的后续优化

- 管理员备注名
- 自动关闭旧话题
- 标签搜索
- 黑名单独立面板
- 更细的错误上报
- systemd service 化

## 注意事项

- 删除话题后，系统会在下次收到该用户消息时自动新建话题
- 某些 Telegram callback 有时效，按钮点得太晚会超时，但现在不会阻断实际动作
- 如果话题创建失败，建议检查 bot 在群里的权限和 Topics 是否开启
