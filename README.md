# Telegram Topic Relay

一个把 **Telegram 私聊消息** 自动转入 **管理群话题（Topics）** 的 webhook 服务。

适用场景：
- 你有一个 Telegram bot
- 外部用户私聊 bot
- 你不想被 bot 私聊轰炸
- 你希望在自己的管理群里，按用户自动建独立话题处理会话
- 你希望在话题里直接回复用户，而不是来回切 bot 对话框

---

# 1. 功能概览

## 已实现

- webhook 模式，不走 `getUpdates` 轮询
- 私聊消息自动进入管理群
- 按用户自动创建 / 复用话题
- 删除旧话题后，收到新消息会自动重建话题
- 新建 / 重建话题时自动发送并 pin 资料卡
- 同一话题后续消息不重复刷名片
- 管理员可直接在话题里回复用户
- 支持标签、拉黑、历史记录、清空记录、刷新资料卡、重命名话题
- 支持群绑定模式 `/bindgroup`
- 支持 systemd 常驻运行

## 当前按钮功能

资料卡支持：
- `🚫 拉黑 / ✅ 解封`
- `🧾 记录`
- `🏷 标签`
- `🧹 清空`
- `👤 刷新`
- `✏️ 改名`

## 当前命令

- `/bindgroup`
- `/unbindgroup`
- `/ban`
- `/unban`
- `/tag 标签名`
- `/untag 标签名`
- `/history`
- `/clear`
- `/profile`
- `/rename`

---

# 2. 工作流程

## 用户侧流程

1. 外部用户私聊 bot
2. bot 收到消息
3. bot 把消息转进管理群里的对应话题
4. 用户不会持续收到“已收到”之类的噪音提示

## 管理员侧流程

1. 你在管理群里查看某个用户对应的话题
2. 第一次会看到一张资料卡，并自动 pin
3. 后续该用户再发消息，只会继续进入这个话题
4. 你直接在这个话题里回复，对方就会收到

## 话题重建流程

如果你手动删掉了某个用户的话题：
1. 该用户再次发消息
2. 旧话题 ID 失效
3. 系统自动新建一个新话题
4. 重新发送并 pin 资料卡
5. 后续继续在新话题处理

---

# 3. 目录结构

```text
telegram-topic-relay/
├── README.md
├── .gitignore
├── config.example.json
├── relay_webhook.py
├── run_webhook.sh
└── telegram-topic-relay.service
```

说明：
- `relay_webhook.py`：主服务
- `run_webhook.sh`：启动脚本
- `config.example.json`：配置模板
- `telegram-topic-relay.service`：systemd 服务文件

运行时文件：
- `config.json`
- `state.json`
- `relay.log`
- `nohup.out`

这些运行时文件默认不入 Git。

---

# 4. 环境要求

- Linux 服务器
- Python 3.10+
- 一个 HTTPS 域名
- Nginx 或其它反向代理
- Telegram bot token
- 一个开启 Topics 的 Telegram supergroup

---

# 5. 配置说明

复制模板：

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

字段说明：

- `bot_token`：BotFather 提供的 token
- `admin_id`：你的 Telegram 数字 ID
- `listen_host`：本地监听地址，默认 `127.0.0.1`
- `listen_port`：本地监听端口，默认 `8780`
- `webhook_secret`：Telegram webhook secret token

---

# 6. Nginx 配置

示例：

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

---

# 7. 设置 Telegram webhook

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/telegram-relay/webhook" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>" \
  -d 'allowed_updates=["message","callback_query"]' \
  -d "drop_pending_updates=true"
```

检查：

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

---

# 8. 启动方式

## 手动启动

```bash
chmod +x run_webhook.sh
./run_webhook.sh
```

## 后台启动

```bash
nohup ./run_webhook.sh >/dev/null 2>&1 &
```

## systemd 启动

```bash
cp telegram-topic-relay.service /etc/systemd/system/telegram-topic-relay.service
systemctl daemon-reload
systemctl enable telegram-topic-relay.service
systemctl restart telegram-topic-relay.service
systemctl status telegram-topic-relay.service
```

---

# 9. 管理群话题模式使用方法

## 第一步：把 bot 拉进群
把 bot 拉进一个 **开启 Topics 的 supergroup**。

## 第二步：关闭 BotFather 隐私模式
在 `@BotFather` 中：
- `/mybots`
- 选择你的 bot
- `Bot Settings`
- `Group Privacy`
- 关闭

不关这步，bot 可能收不到你在群话题里的普通消息。

## 第三步：绑定管理群
管理员在群里发送：

```text
/bindgroup
```

绑定成功后，私聊消息会自动路由到这个群。

## 第四步：开始使用
外部用户私聊 bot 后：
- 自动建话题
- 自动 pin 资料卡
- 后续继续在该话题流转

## 第五步：在话题里直接回复
你直接在话题里发消息，对方就会收到。

---

# 10. 资料卡和按钮说明

资料卡会显示：
- 用户名 / 昵称
- 用户 ID
- 语言
- 标签
- 状态
- 消息数
- 记录数
- 首次时间
- 最近时间
- 最近内容
- 当前话题 ID

按钮含义：

### `🚫 拉黑 / ✅ 解封`
控制该用户是否继续进入正常流程。

### `🧾 记录`
查看这个用户最近的消息记录。

### `🏷 标签`
提示你在当前话题里发送 `/tag 标签名`。

### `🧹 清空`
清空该用户的历史记录。

### `👤 刷新`
刷新资料卡内容。

### `✏️ 改名`
按照当前昵称 / 用户名重新命名话题。

---

# 11. 管理命令说明

## `/bindgroup`
把当前群绑定成管理群。

## `/unbindgroup`
解除管理群绑定。

## `/ban`
拉黑当前话题对应用户。

## `/unban`
解除拉黑。

## `/tag 广告`
给用户打标签。

## `/untag 广告`
移除标签。

## `/history`
查看最近记录。

## `/clear`
清空历史记录。

## `/profile`
刷新资料卡。

## `/rename`
重命名当前话题。

---

# 12. 日志和状态文件

## 日志文件
- `relay.log`
- `nohup.out`

日志包含：
- 服务启动
- incoming 消息
- reply 消息
- callback 按钮点击
- 话题重建
- Telegram API 错误

## 状态文件
- `state.json`

状态里保存：
- 用户信息
- 话题映射
- 历史记录
- 管理群绑定信息

---

# 13. 运维建议

## 检查服务健康

```bash
curl http://127.0.0.1:8780/health
curl https://your-domain.com/telegram-relay/health
```

## 查看 systemd 状态

```bash
systemctl status telegram-topic-relay.service
journalctl -u telegram-topic-relay.service -n 100 --no-pager
```

## 查看 webhook 状态

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

## 遇到“话题删了没反应”
本项目已支持自动重建话题。若仍异常：
- 检查 bot 是否有创建话题权限
- 检查管理群是否仍为 forum supergroup
- 检查 `state.json` 里的 `admin_group_id`

---

# 14. 常见问题

## Q1: 按钮点了没反应
可能原因：
- callback 已超时
- Telegram 客户端点得太晚
- 旧版本回调处理异常

目前已做容错：
- callback 超时不会阻断真实动作
- 真正动作会继续执行

## Q2: 删除旧话题后不再建新话题
当前版本已经支持自动重建。若没出现：
- 检查 bot 是否仍能创建话题
- 检查 webhook 是否正常
- 检查日志里是否有 `created topic` 记录

## Q3: 话题名为什么和资料卡不一致
可以使用：

```text
/rename
```

重新按当前昵称 / 用户名刷新话题名。

---

# 15. 后续可扩展方向

- 管理员备注名
- 自动关闭旧话题
- 标签搜索 / 标签统计
- 黑名单面板
- systemd 安装脚本
- Docker 化
- 更细的 callback 按钮反馈
- 运营面板 / Web UI

---

# 16. 仓库信息

GitHub 仓库：

```text
https://github.com/guyue211/telegram-topic-relay
```

如果你要继续二开，建议：
- 先改 `config.example.json`
- 用独立域名部署
- 用 systemd 托管
- 生产环境不要把真实 token 提交进 Git
