# Telegram Topic Relay

[中文](./README.zh-CN.md) | [English](./README.en.md)

一个把 **Telegram 私聊消息** 自动转入 **管理群话题（Topics）** 的 webhook 服务。

适合：
- 私聊客服场景
- 私域引流承接
- 广告线索收集
- 个人号 / 团队号统一在群话题处理消息

---

# 1. 项目目标

你不需要再被 bot 私聊窗口轰炸。

这个项目做的事很直接：

1. 用户私聊 bot
2. bot 自动把消息转进你的管理群
3. 每个用户单独对应一个话题
4. 你直接在话题里回复
5. bot 再把回复原路发回给用户

也就是说，它把 **“私聊收消息”** 变成了 **“群话题处理工单”**。

---

# 2. 功能特性

## 已实现

- webhook 模式，不走 `getUpdates` 轮询
- 用户私聊消息自动转进管理群
- 按用户自动创建 / 复用话题
- 删除旧话题后，收到新消息可自动重建话题
- 新建 / 重建话题时自动发送并 pin 资料卡
- 后续消息不重复刷名片
- 直接在话题里回复用户
- 标签、拉黑、解封、历史记录、清空记录、刷新资料卡、重命名话题
- 可用 systemd 托管
- 可 Docker 化部署

## 当前资料卡按钮

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

# 3. 目录结构

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

说明：
- `relay_webhook.py`：主服务
- `run_webhook.sh`：启动脚本
- `telegram-topic-relay.service`：systemd 服务文件
- `Dockerfile` / `docker-compose.yml`：Docker 部署

运行时文件：
- `config.json`
- `state.json`
- `relay.log`
- `nohup.out`

---

# 4. 环境要求

- Linux 服务器
- Python 3.10+
- 一个 HTTPS 域名
- 一个 Telegram bot token
- 一个开启 Topics 的 supergroup
- Nginx 或其它反向代理

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
- `listen_host`：本地监听地址
- `listen_port`：本地监听端口
- `webhook_secret`：Telegram webhook secret token

---

# 6. Nginx 配置示例

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

# 9. 群话题模式使用方法

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
- 自动建 / 复用话题
- 首次发送并 pin 资料卡
- 后续消息继续进入该话题

## 第五步：在话题里直接回复
你直接在对应话题里发消息，对方就会收到。

---

# 10. 黑名单面板（当前版本）

当前已经具备 **基础黑名单面板能力**，入口是资料卡：

- 按钮：`🚫 拉黑 / ✅ 解封`
- 命令：`/ban`、`/unban`

逻辑：
- 用户被拉黑后，后续新消息不再按正常流程推送
- 用户解除拉黑后恢复正常

## 当前黑名单面板形态
严格说现在还是“资料卡驱动的黑名单面板”，不是独立 Web UI。

也就是：
- 在资料卡里看状态
- 点按钮拉黑/解封
- 用命令批量控制

## 后续可继续扩展的黑名单面板
下一版可以加：
- `/blacklist` 命令
- 统一列出所有黑名单用户
- 分页按钮翻页
- 搜索某个用户是否被拉黑
- 一键从黑名单恢复

---

# 11. 资料卡说明

资料卡包含：
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

行为：
- 新建话题时发送并 pin
- 重建话题时重新发送并 pin
- 普通消息不重复刷

---

# 12. 管理命令说明

## `/bindgroup`
绑定当前群为管理群。

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
查看该用户最近记录。

## `/clear`
清空该用户历史记录。

## `/profile`
刷新资料卡。

## `/rename`
按当前昵称 / 用户名重命名话题。

---

# 13. Docker 部署

## Dockerfile 构建

```bash
docker build -t telegram-topic-relay .
```

## docker-compose 启动

```bash
docker compose up -d
```

当前 `docker-compose.yml` 默认：
- 映射 `127.0.0.1:8780`
- 挂载 `config.json`
- 挂载 `state.json`
- 挂载日志文件

你仍然需要在宿主机 Nginx 层做 HTTPS 反代。

---

# 14. 日志和状态文件

## 日志
- `relay.log`
- `nohup.out`

日志会记录：
- 服务启动
- incoming 消息
- reply 消息
- callback 点击
- 话题重建
- Telegram API error

## 状态文件
- `state.json`

状态里记录：
- 用户信息
- 话题映射
- 历史记录
- 管理群绑定信息
- 拉黑状态

---

# 15. 运维命令

## 查看健康检查

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

---

# 16. 常见问题

## Q1: 删除话题后为什么没马上看到新话题
系统会在下次收到该用户消息时自动重建。

## Q2: 按钮点了没反应
当前版本已经对 callback 超时做了容错。
如果按钮点得太晚，弹窗可能不稳定，但真实动作会尽量继续执行。

## Q3: 话题名为什么不更新
在话题里发送：

```text
/rename
```

或者点资料卡里的 `✏️ 改名`。

## Q4: 为什么 bot 在群里收不到我的普通消息
大概率是没有关闭 BotFather 的隐私模式。

---

# 17. 后续优化方向

- 独立 `/blacklist` 面板
- 标签面板
- 管理员备注名
- 自动关闭旧话题
- 话题归档
- Docker 镜像发布
- Web 管理台

---

# 18. 仓库地址

GitHub：

```text
https://github.com/guyue211/telegram-topic-relay
```


# 19. Telegram 机器人命令菜单

服务启动时会自动调用 `setMyCommands` 注册原生命令菜单，因此 Telegram 输入框中可以直接看到：

- `/menu`
- `/tags`
- `/tagsearch`
- `/blacklist`
- `/stats`
- `/help`
