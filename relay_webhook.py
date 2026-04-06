#!/usr/bin/env python3
import html
import json
import signal
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "state.json"
LOG_PATH = BASE_DIR / "relay.log"

DEFAULT_STATE = {
    "routes": {},
    "users": {},
    "history": {},
    "threads": {},
    "admin_group_id": None
}

MAX_HISTORY_PER_USER = 80
PANEL_PAGE_SIZE = 8
running = True
STATE = None
CONFIG = None
TG_CLIENT = None
BOT_INFO = None


def on_signal(signum, frame):
    global running
    running = False


signal.signal(signal.SIGINT, on_signal)
signal.signal(signal.SIGTERM, on_signal)


def now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str):
    line = f"[{now_str()}] {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


class TG:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}/"

    def call(self, method: str, data=None):
        if data is None:
            data = {}
        encoded = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(self.base + method, data=encoded)
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Telegram API error {method}: HTTP {e.code} {body}") from e
        payload = json.loads(raw)
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error {method}: {raw}")
        return payload["result"]


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def ensure_state_shape(state: dict):
    for key, value in DEFAULT_STATE.items():
        if key not in state:
            state[key] = value.copy() if isinstance(value, dict) else value
    return state


def get_message_text(msg: dict):
    if "text" in msg:
        return msg["text"]
    if "caption" in msg:
        return msg["caption"]
    return ""


def message_kind(msg: dict):
    for key in ["text", "photo", "video", "document", "audio", "voice", "sticker", "animation", "contact", "location"]:
        if key in msg:
            return key
    return "message"


def message_preview(msg: dict):
    text = get_message_text(msg).strip()
    if text:
        return text.replace("\n", " ")[:120]
    kind = message_kind(msg)
    mapping = {
        "photo": "[图片]",
        "video": "[视频]",
        "document": "[文件]",
        "audio": "[音频]",
        "voice": "[语音]",
        "sticker": "[贴纸]",
        "animation": "[动图]",
        "contact": "[联系人]",
        "location": "[位置]",
        "text": "[文本]"
    }
    return mapping.get(kind, f"[{kind}]")


def user_label(user: dict):
    name = " ".join(x for x in [user.get("first_name", ""), user.get("last_name", "")] if x).strip() or "(no name)"
    username = f"@{user['username']}" if user.get("username") else "(no username)"
    return f"{name} {username}".strip()


def topic_name_from_user(chat_id: int, record: dict):
    parts = []
    if record.get("first_name"):
        parts.append(record["first_name"])
    if record.get("last_name"):
        parts.append(record["last_name"])
    name = " ".join(parts).strip()
    if not name and record.get("username"):
        name = f"@{record['username']}"
    if not name:
        name = "未命名用户"
    return name[:120]


def send_text(tg: TG, chat_id: int, text: str, reply_to=None, parse_mode=None, reply_markup=None, message_thread_id=None):
    data = {"chat_id": chat_id, "text": text}
    if reply_to:
        data["reply_to_message_id"] = reply_to
    if parse_mode:
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    if message_thread_id:
        data["message_thread_id"] = message_thread_id
    return tg.call("sendMessage", data)


def copy_message(tg: TG, chat_id: int, from_chat_id: int, message_id: int, caption=None, message_thread_id=None):
    data = {
        "chat_id": chat_id,
        "from_chat_id": from_chat_id,
        "message_id": message_id,
    }
    if caption is not None:
        data["caption"] = caption
    if message_thread_id:
        data["message_thread_id"] = message_thread_id
    return tg.call("copyMessage", data)


def edit_message_text(tg: TG, chat_id: int, message_id: int, text: str, parse_mode=None, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if parse_mode:
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return tg.call("editMessageText", data)


def answer_callback_query(tg: TG, callback_query_id: str, text: str = "", alert: bool = False):
    data = {"callback_query_id": callback_query_id}
    if text:
        data["text"] = text[:180]
    if alert:
        data["show_alert"] = "true"
    return tg.call("answerCallbackQuery", data)

def safe_answer_callback_query(tg: TG, callback_query_id: str, text: str = "", alert: bool = False):
    try:
        return answer_callback_query(tg, callback_query_id, text, alert)
    except Exception as e:
        log(f"answerCallbackQuery ignored: {e}")
        return None

def pin_chat_message(tg: TG, chat_id: int, message_id: int):
    return tg.call("pinChatMessage", {"chat_id": chat_id, "message_id": message_id, "disable_notification": "true"})


def create_forum_topic(tg: TG, chat_id: int, name: str):
    return tg.call("createForumTopic", {"chat_id": chat_id, "name": name})

def edit_forum_topic(tg: TG, chat_id: int, message_thread_id: int, name: str):
    return tg.call("editForumTopic", {"chat_id": chat_id, "message_thread_id": message_thread_id, "name": name})


def ensure_user_record(state: dict, chat_id: int, user=None):
    key = str(chat_id)
    existing = state["users"].get(key, {
        "chat_id": chat_id,
        "label": f"User {chat_id}",
        "username": "",
        "first_name": "",
        "last_name": "",
        "language_code": "",
        "first_seen": now_str(),
        "last_seen": now_str(),
        "last_preview": "",
        "message_count": 0,
        "banned": False,
        "tags": [],
        "topic_id": None
    })
    if user:
        existing["label"] = user_label(user)
        existing["username"] = user.get("username", existing.get("username", ""))
        existing["first_name"] = user.get("first_name", existing.get("first_name", ""))
        existing["last_name"] = user.get("last_name", existing.get("last_name", ""))
        existing["language_code"] = user.get("language_code", existing.get("language_code", ""))
    existing.setdefault("tags", [])
    existing.setdefault("banned", False)
    existing.setdefault("message_count", 0)
    existing.setdefault("first_seen", now_str())
    existing.setdefault("topic_id", None)
    existing["last_seen"] = now_str()
    state["users"][key] = existing
    state["history"].setdefault(key, [])
    return existing


def append_history(state: dict, chat_id: int, direction: str, msg: dict, note: str = ""):
    key = str(chat_id)
    items = state["history"].setdefault(key, [])
    items.append({
        "ts": now_str(),
        "direction": direction,
        "type": message_kind(msg),
        "preview": message_preview(msg),
        "note": note
    })
    if len(items) > MAX_HISTORY_PER_USER:
        del items[:-MAX_HISTORY_PER_USER]


def tags_text(tags):
    if not tags:
        return "无"
    return "、".join(html.escape(str(tag)) for tag in tags)


def profile_keyboard(chat_id: int, banned: bool):
    return {
        "inline_keyboard": [
            [
                {"text": "✅ 解封" if banned else "🚫 拉黑", "callback_data": f"{'unban' if banned else 'ban'}:{chat_id}"},
                {"text": "🧾 记录", "callback_data": f"history:{chat_id}"}
            ],
            [
                {"text": "🏷 标签", "callback_data": f"taghint:{chat_id}"},
                {"text": "🧹 清空", "callback_data": f"clear:{chat_id}"}
            ],
            [
                {"text": "🏷 面板", "callback_data": f"tagpanel:{chat_id}"},
                {"text": "🚫 黑名单", "callback_data": f"blacklist:0"}
            ],
            [
                {"text": "👤 刷新", "callback_data": f"profile:{chat_id}"},
                {"text": "✏️ 改名", "callback_data": f"rename:{chat_id}"}
            ]
        ]
    }


def format_profile_card(state: dict, chat_id: int):
    record = ensure_user_record(state, chat_id)
    history_count = len(state["history"].get(str(chat_id), []))
    label = html.escape(record.get("label", f"User {chat_id}"))
    username = html.escape("@" + record["username"] if record.get("username") else "无")
    lang = html.escape(record.get("language_code") or "未知")
    status = "已拉黑" if record.get("banned") else "正常"
    last_preview = html.escape(record.get("last_preview") or "无")
    topic_id = record.get("topic_id") or "未建"
    return (
        f"👤 <b>{label}</b>\n"
        f"🆔 <code>{chat_id}</code>\n"
        f"👤 用户名: {username}\n"
        f"🌐 语言: {lang}\n"
        f"🧵 话题: <code>{topic_id}</code>\n"
        f"🏷 标签: {tags_text(record.get('tags', []))}\n"
        f"🚦 状态: {status}\n"
        f"📨 消息数: {record.get('message_count', 0)}\n"
        f"🧾 记录数: {history_count}\n"
        f"🕒 首次: {html.escape(record.get('first_seen', ''))}\n"
        f"🕘 最近: {html.escape(record.get('last_seen', ''))}\n"
        f"📝 最近内容: {last_preview}\n\n"
        f"可用命令：/ban /unban /tag 标签 /untag 标签 /history /clear /profile"
    )


def send_profile_card(tg: TG, admin_chat_id: int, state: dict, chat_id: int, reply_to=None, edit_message_id=None, message_thread_id=None):
    text = format_profile_card(state, chat_id)
    markup = profile_keyboard(chat_id, ensure_user_record(state, chat_id).get("banned", False))
    if edit_message_id:
        return edit_message_text(tg, admin_chat_id, edit_message_id, text, parse_mode="HTML", reply_markup=markup)
    return send_text(tg, admin_chat_id, text, reply_to=reply_to, parse_mode="HTML", reply_markup=markup, message_thread_id=message_thread_id)


def render_history(state: dict, chat_id: int):
    items = state["history"].get(str(chat_id), [])
    if not items:
        return f"🧾 <code>{chat_id}</code> 暂无历史记录。"
    lines = [f"🧾 <code>{chat_id}</code> 最近 {min(len(items), 15)} 条记录："]
    for item in items[-15:]:
        arrow = "⬅️" if item["direction"] == "in" else "➡️"
        preview = html.escape(item.get("preview") or "")
        lines.append(f"{arrow} {html.escape(item['ts'])} [{html.escape(item['type'])}] {preview}")
    return "\n".join(lines)

def render_blacklist_panel(state: dict):
    users = state.get("users", {})
    banned = []
    for chat_id, record in users.items():
        if record.get("banned"):
            label = html.escape(record.get("label") or f"User {chat_id}")
            banned.append(f"• <code>{chat_id}</code> {label}")
    if not banned:
        return "🚫 当前黑名单为空。"
    return "🚫 黑名单列表：\n" + "\n".join(banned)


def extract_target_chat_id(state: dict, msg: dict):
    reply_msg = msg.get("reply_to_message")
    if reply_msg:
        target = state["routes"].get(str(reply_msg.get("message_id")))
        if target:
            return int(target)
    thread_id = msg.get("message_thread_id")
    chat_id = msg.get("chat", {}).get("id")
    if chat_id == state.get("admin_group_id") and thread_id:
        mapped = state["threads"].get(str(thread_id))
        if mapped:
            return int(mapped)
    return None


def parse_command(text: str):
    if not text.startswith("/"):
        return None, ""
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].split("@", 1)[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    return cmd, arg


def ensure_topic_for_user(tg: TG, state: dict, record: dict, chat_id: int, force_new: bool = False):
    admin_group_id = state.get("admin_group_id")
    if not admin_group_id:
        return None
    topic_id = record.get("topic_id")
    if topic_id and not force_new:
        state["threads"][str(topic_id)] = chat_id
        return topic_id
    if topic_id and force_new:
        state["threads"].pop(str(topic_id), None)
    topic = create_forum_topic(tg, int(admin_group_id), topic_name_from_user(chat_id, record))
    topic_id = topic.get("message_thread_id")
    record["topic_id"] = topic_id
    state["threads"][str(topic_id)] = chat_id
    save_json(STATE_PATH, state)
    log(f"created topic {topic_id} for {chat_id}")
    return topic_id


def forward_user_into_admin_group(tg: TG, state: dict, chat_id: int, message_id: int, record: dict):
    admin_group_id = state.get("admin_group_id")
    existing_topic_id = record.get("topic_id")
    created_new_topic = existing_topic_id is None
    topic_id = ensure_topic_for_user(tg, state, record, chat_id)
    try:
        copied = copy_message(tg, int(admin_group_id), chat_id, message_id, message_thread_id=topic_id)
        info_card = None
        if created_new_topic:
            info_card = send_profile_card(tg, int(admin_group_id), state, chat_id, reply_to=copied["message_id"], message_thread_id=topic_id)
            if info_card:
                try:
                    pin_chat_message(tg, int(admin_group_id), int(info_card["message_id"]))
                except Exception as e:
                    log(f"pin profile card failed: {e}")
        return copied, info_card
    except Exception as e:
        log(f"forward to topic failed for {chat_id}, topic={topic_id}, error={e}")
        try:
            topic_id = ensure_topic_for_user(tg, state, record, chat_id, force_new=True)
            send_text(tg, int(admin_group_id), f"🔁 已为 {topic_name_from_user(chat_id, record)} 重建话题", parse_mode=None)
            copied = copy_message(tg, int(admin_group_id), chat_id, message_id, message_thread_id=topic_id)
            info_card = send_profile_card(tg, int(admin_group_id), state, chat_id, reply_to=copied["message_id"], message_thread_id=topic_id)
            if info_card:
                try:
                    pin_chat_message(tg, int(admin_group_id), int(info_card["message_id"]))
                except Exception as e:
                    log(f"pin rebuilt profile card failed: {e}")
            return copied, info_card
        except Exception as e2:
            log(f"recreate topic failed for {chat_id}, fallback to group root, error={e2}")
            copied = copy_message(tg, int(admin_group_id), chat_id, message_id)
            info_card = None
            if created_new_topic:
                info_card = send_profile_card(tg, int(admin_group_id), state, chat_id, reply_to=copied["message_id"])
            return copied, info_card


def handle_user_message(tg: TG, config: dict, state: dict, msg: dict):
    admin_private_id = config["admin_id"]
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    message_id = msg["message_id"]
    text = get_message_text(msg)

    record = ensure_user_record(state, chat_id, user)
    record["last_preview"] = message_preview(msg)

    if text.startswith("/start"):
        send_text(tg, chat_id, "已连接成功，直接给我发消息即可，我会转给管理员。")
        return
    if text.startswith("/help"):
        send_text(tg, chat_id, "直接发送文字、图片、文件、语音都行，管理员回复后会原路回给你。")
        return

    record["message_count"] = int(record.get("message_count", 0)) + 1
    append_history(state, chat_id, "in", msg)
    log(f"incoming from {chat_id} ({record.get('label','')}) : {record['last_preview']}")

    if record.get("banned"):
        save_json(STATE_PATH, state)
        return

    admin_group_id = state.get("admin_group_id")
    if admin_group_id:
        copied, info_card = forward_user_into_admin_group(tg, state, chat_id, message_id, record)
        state["routes"][str(copied["message_id"])] = chat_id
        if info_card:
            state["routes"][str(info_card["message_id"])] = chat_id
    else:
        copied = copy_message(tg, admin_private_id, chat_id, message_id)
        state["routes"][str(copied["message_id"])] = chat_id
        info_card = send_profile_card(tg, admin_private_id, state, chat_id, reply_to=copied["message_id"])
        state["routes"][str(info_card["message_id"])] = chat_id

    save_json(STATE_PATH, state)


def handle_admin_command(tg: TG, config: dict, state: dict, msg: dict, target_chat: int, cmd: str, arg: str, admin_chat_id: int):
    record = ensure_user_record(state, target_chat)
    key = str(target_chat)
    thread_id = record.get("topic_id") if admin_chat_id == state.get("admin_group_id") else None

    if cmd == "/ban":
        record["banned"] = True
        send_text(tg, admin_chat_id, f"🚫 已拉黑 <code>{target_chat}</code>", reply_to=msg.get("message_id"), parse_mode="HTML", message_thread_id=thread_id)
        send_profile_card(tg, admin_chat_id, state, target_chat, reply_to=msg.get("message_id"), message_thread_id=thread_id)
        return True
    if cmd in ("/unban", "/allow"):
        record["banned"] = False
        send_text(tg, admin_chat_id, f"✅ 已解除拉黑 <code>{target_chat}</code>", reply_to=msg.get("message_id"), parse_mode="HTML", message_thread_id=thread_id)
        send_profile_card(tg, admin_chat_id, state, target_chat, reply_to=msg.get("message_id"), message_thread_id=thread_id)
        return True
    if cmd == "/tag":
        if not arg:
            send_text(tg, admin_chat_id, "用法：/tag 标签名", reply_to=msg.get("message_id"), message_thread_id=thread_id)
            return True
        if arg not in record["tags"]:
            record["tags"].append(arg)
        send_text(tg, admin_chat_id, f"🏷 已添加标签：{arg}", reply_to=msg.get("message_id"), message_thread_id=thread_id)
        send_profile_card(tg, admin_chat_id, state, target_chat, reply_to=msg.get("message_id"), message_thread_id=thread_id)
        return True
    if cmd == "/untag":
        if not arg:
            send_text(tg, admin_chat_id, "用法：/untag 标签名", reply_to=msg.get("message_id"), message_thread_id=thread_id)
            return True
        record["tags"] = [x for x in record.get("tags", []) if x != arg]
        send_text(tg, admin_chat_id, f"🗑 已移除标签：{arg}", reply_to=msg.get("message_id"), message_thread_id=thread_id)
        send_profile_card(tg, admin_chat_id, state, target_chat, reply_to=msg.get("message_id"), message_thread_id=thread_id)
        return True
    if cmd == "/history":
        send_text(tg, admin_chat_id, render_history(state, target_chat), reply_to=msg.get("message_id"), parse_mode="HTML", message_thread_id=thread_id)
        return True
    if cmd in ("/clear", "/clearhistory"):
        state["history"][key] = []
        send_text(tg, admin_chat_id, f"🧹 已清空 <code>{target_chat}</code> 的历史记录", reply_to=msg.get("message_id"), parse_mode="HTML", message_thread_id=thread_id)
        send_profile_card(tg, admin_chat_id, state, target_chat, reply_to=msg.get("message_id"), message_thread_id=thread_id)
        return True
    if cmd == "/profile":
        send_profile_card(tg, admin_chat_id, state, target_chat, reply_to=msg.get("message_id"), message_thread_id=thread_id)
        return True
    if cmd == "/rename":
        topic_id = record.get("topic_id")
        if admin_chat_id == state.get("admin_group_id") and topic_id:
            edit_forum_topic(tg, int(admin_chat_id), int(topic_id), topic_name_from_user(target_chat, record))
            send_text(tg, admin_chat_id, "✅ 已按用户名重命名当前话题", reply_to=msg.get("message_id"), message_thread_id=thread_id)
        else:
            send_text(tg, admin_chat_id, "当前没有可改名的话题", reply_to=msg.get("message_id"), message_thread_id=thread_id)
        return True
    return False


def handle_admin_message(tg: TG, config: dict, state: dict, msg: dict):
    text = get_message_text(msg)
    cmd, arg = parse_command(text) if text else (None, "")
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    from_id = msg.get("from", {}).get("id")

    if chat.get("type") in ("group", "supergroup"):
        if from_id != config["admin_id"]:
            return
        if cmd == "/bindgroup":
            state["admin_group_id"] = chat_id
            save_json(STATE_PATH, state)
            send_text(tg, chat_id, f"✅ 已绑定当前群为管理群\n群ID: <code>{chat_id}</code>\n后续私聊消息会自动按用户建话题。\n注意：去 BotFather 把 /setprivacy 关掉，不然你在话题里直接发消息，bot 收不到。", reply_to=msg.get("message_id"), parse_mode="HTML")
            return
        if cmd == "/unbindgroup":
            state["admin_group_id"] = None
            save_json(STATE_PATH, state)
            send_text(tg, chat_id, "✅ 已解除当前管理群绑定。", reply_to=msg.get("message_id"))
            return
        if state.get("admin_group_id") != chat_id:
            return
    else:
        if chat_id != config["admin_id"]:
            return

    if cmd == "/start":
        send_text(tg, chat_id, "管理员在线。私聊模式下回复转发消息即可；群话题模式下先在群里发送 /bindgroup 绑定。", reply_to=msg.get("message_id"))
        return
    if cmd == "/blacklist":
        send_text(tg, chat_id, render_blacklist_panel(state, 0), reply_to=msg.get("message_id"), parse_mode="HTML", reply_markup=build_blacklist_keyboard(state, 0))
        return
    if cmd == "/tags":
        send_text(tg, chat_id, render_tags_panel(state, 0), reply_to=msg.get("message_id"), parse_mode="HTML", reply_markup=build_tags_keyboard(state, 0))
        return
    if cmd == "/tagsearch":
        send_text(tg, chat_id, render_tag_search_result(state, arg), reply_to=msg.get("message_id"), parse_mode="HTML", reply_markup=build_tag_search_keyboard(state, arg))
        return
    if cmd == "/menu":
        send_text(tg, chat_id, render_main_menu(), reply_to=msg.get("message_id"), reply_markup=build_main_menu_keyboard())
        return
    if cmd == "/help":
        help_text = (
            "管理员命令：\n"
            "/bindgroup  在已开启话题的群里绑定管理群\n"
            "/unbindgroup  解绑管理群\n"
            "/ban /unban /tag 标签 /untag 标签 /history /clear /profile\n\n"
            "私聊模式：回复用户转发消息即可。\n"
            "群话题模式：建议先去 BotFather 关闭 /setprivacy，然后你在对应话题里直接回复或发消息都行。"
        )
        send_text(tg, chat_id, help_text, reply_to=msg.get("message_id"))
        return

    target_chat = extract_target_chat_id(state, msg)
    if cmd and target_chat:
        handled = handle_admin_command(tg, config, state, msg, int(target_chat), cmd, arg, chat_id)
        if handled:
            save_json(STATE_PATH, state)
            return

    if not target_chat:
        send_text(tg, chat_id, "这条消息没有绑定到具体用户。\n如果你想走群话题模式，请把 bot 拉进已开启话题的群，然后发送 /bindgroup。", reply_to=msg.get("message_id"))
        return

    thread_id = msg.get("message_thread_id") if chat_id == state.get("admin_group_id") else None
    copy_message(tg, int(target_chat), chat_id, msg["message_id"])
    append_history(state, int(target_chat), "out", msg)
    ensure_user_record(state, int(target_chat))["last_seen"] = now_str()
    log(f"reply to {target_chat} in thread {thread_id}: {message_preview(msg)}")
    save_json(STATE_PATH, state)


def handle_callback_query(tg: TG, config: dict, state: dict, query: dict):
    from_id = query.get("from", {}).get("id")
    data = query.get("data", "")
    log(f"callback from={from_id} data={data} msg_id={query.get('message',{}).get('message_id')}")
    if from_id != config["admin_id"]:
        safe_answer_callback_query(tg, query["id"], "无权限")
        return

    # 先尽快 ack，提升体感速度；后续动作失败不影响按钮点击本身
    if data.startswith('ban:'):
        safe_answer_callback_query(tg, query["id"], "处理中")
    elif data.startswith('unban:'):
        safe_answer_callback_query(tg, query["id"], "处理中")
    elif data.startswith('history:'):
        safe_answer_callback_query(tg, query["id"], "正在获取记录")
    elif data.startswith('clear:'):
        safe_answer_callback_query(tg, query["id"], "正在清空")
    elif data.startswith('profile:'):
        safe_answer_callback_query(tg, query["id"], "正在刷新")
    elif data.startswith('rename:'):
        safe_answer_callback_query(tg, query["id"], "正在改名")
    elif data.startswith('taghint:'):
        safe_answer_callback_query(tg, query["id"], "在当前话题发送 /tag 标签名，删除用 /untag 标签名", alert=True)

    if ":" not in data:
        safe_answer_callback_query(tg, query["id"], "无效操作")
        return

    parts = data.split(":")
    action = parts[0]
    raw_chat_id = parts[1] if len(parts) > 1 else "0"
    try:
        chat_id = int(raw_chat_id)
    except ValueError:
        safe_answer_callback_query(tg, query["id"], "无效用户")
        return

    record = ensure_user_record(state, chat_id)
    message = query.get("message", {})
    admin_chat_id = message.get("chat", {}).get("id", config["admin_id"])
    message_id = message.get("message_id")
    thread_id = record.get("topic_id") if admin_chat_id == state.get("admin_group_id") else None

    if action == "ban":
        record["banned"] = True
        safe_answer_callback_query(tg, query["id"], "已拉黑")
        if message_id:
            send_profile_card(tg, admin_chat_id, state, chat_id, edit_message_id=message_id)
    elif action == "unban":
        record["banned"] = False
        safe_answer_callback_query(tg, query["id"], "已解除拉黑")
        if message_id:
            send_profile_card(tg, admin_chat_id, state, chat_id, edit_message_id=message_id)
    elif action == "history":
        safe_answer_callback_query(tg, query["id"], "已发送记录")
        send_text(tg, admin_chat_id, render_history(state, chat_id), reply_to=message_id, parse_mode="HTML", message_thread_id=thread_id)
    elif action == "clear":
        state["history"][str(chat_id)] = []
        safe_answer_callback_query(tg, query["id"], "已清空记录")
        if message_id:
            send_profile_card(tg, admin_chat_id, state, chat_id, edit_message_id=message_id)
    elif action == "profile":
        safe_answer_callback_query(tg, query["id"], "已刷新")
        if message_id:
            send_profile_card(tg, admin_chat_id, state, chat_id, edit_message_id=message_id)
    elif action == "rename":
        topic_id = record.get("topic_id")
        if admin_chat_id == state.get("admin_group_id") and topic_id:
            try:
                edit_forum_topic(tg, int(admin_chat_id), int(topic_id), topic_name_from_user(chat_id, record))
            except Exception as e:
                if "TOPIC_NOT_MODIFIED" in str(e):
                    safe_answer_callback_query(tg, query["id"], "话题名没变化")
                else:
                    raise
        else:
            safe_answer_callback_query(tg, query["id"], "当前没有可改名的话题")
    elif action == "taghint":
        safe_answer_callback_query(tg, query["id"], "在当前话题发送 /tag 标签名，删除用 /untag 标签名", alert=True)
    elif action == "tagpanel":
        safe_answer_callback_query(tg, query["id"], "打开标签面板")
        if message_id:
            edit_message_text(tg, admin_chat_id, message_id, render_tags_panel(state, 0), parse_mode="HTML", reply_markup=build_tags_keyboard(state, 0))
    elif action == "tags":
        page = int(raw_chat_id or 0)
        safe_answer_callback_query(tg, query["id"], "返回标签面板")
        if message_id:
            edit_message_text(tg, admin_chat_id, message_id, render_tags_panel(state, page), parse_mode="HTML", reply_markup=build_tags_keyboard(state, page))
    elif action == "taglist":
        tag = parts[1] if len(parts) > 1 else ""
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        safe_answer_callback_query(tg, query["id"], "查看标签用户")
        if message_id:
            edit_message_text(tg, admin_chat_id, message_id, render_tag_users(state, tag, page), parse_mode="HTML", reply_markup=build_tag_users_keyboard(state, tag, page))
    elif action == "openprofile":
        safe_answer_callback_query(tg, query["id"], "打开用户资料")
        if message_id:
            send_profile_card(tg, admin_chat_id, state, chat_id, reply_to=message_id)
    elif action == "blacklist":
        page = int(raw_chat_id or 0)
        safe_answer_callback_query(tg, query["id"], "打开黑名单面板")
        if message_id:
            edit_message_text(tg, admin_chat_id, message_id, render_blacklist_panel(state, page), parse_mode="HTML", reply_markup=build_blacklist_keyboard(state, page))
    elif action == "tagsearch":
        safe_answer_callback_query(tg, query["id"], "请发送 /tagsearch 关键词")
        if message_id:
            edit_message_text(tg, admin_chat_id, message_id, "🔎 标签搜索\n\n请发送：/tagsearch 关键词", reply_markup={"inline_keyboard":[[{"text":"⬅️ 返回主菜单","callback_data":"menu:0"}]]})
    elif action == "menu":
        safe_answer_callback_query(tg, query["id"], "打开主菜单")
        if message_id:
            edit_message_text(tg, admin_chat_id, message_id, render_main_menu(), reply_markup=build_main_menu_keyboard())
    elif action == "menuhelp":
        safe_answer_callback_query(tg, query["id"], "查看帮助")
        if message_id:
            edit_message_text(tg, admin_chat_id, message_id, "ℹ️ 面板说明\n\n- 标签面板：看所有标签\n- 黑名单面板：看并解封黑名单\n- 标签搜索：搜索标签\n\n你也可以直接发送命令：/tags /blacklist /tagsearch 关键词", reply_markup={"inline_keyboard":[[{"text":"⬅️ 返回主菜单","callback_data":"menu:0"}]]})
    elif action == "noop":
        safe_answer_callback_query(tg, query["id"], "当前没有内容")
    else:
        safe_answer_callback_query(tg, query["id"], "未知操作")
        return

    save_json(STATE_PATH, state)


def process_update(update: dict):
    global STATE, CONFIG, TG_CLIENT
    if "callback_query" in update:
        handle_callback_query(TG_CLIENT, CONFIG, STATE, update["callback_query"])
        save_json(STATE_PATH, STATE)
        return

    msg = update.get("message")
    if not msg:
        return

    chat_type = msg.get("chat", {}).get("type")
    if chat_type in ("group", "supergroup"):
        handle_admin_message(TG_CLIENT, CONFIG, STATE, msg)
    else:
        chat_id = msg["chat"]["id"]
        if chat_id == CONFIG["admin_id"]:
            handle_admin_message(TG_CLIENT, CONFIG, STATE, msg)
        else:
            handle_user_message(TG_CLIENT, CONFIG, STATE, msg)
    save_json(STATE_PATH, STATE)


class RelayHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "service": "telegram-relay-webhook", "admin_group_id": STATE.get("admin_group_id") if STATE else None}).encode())
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        expected = CONFIG.get("webhook_secret", "")
        if expected and secret != expected:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"forbidden")
            log("forbidden webhook request: bad secret")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            update = json.loads(raw.decode("utf-8")) if raw else {}
            process_update(update)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except Exception as e:
            log(f"webhook error: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"ok":false}')

    def log_message(self, format, *args):
        return


def main():
    global STATE, CONFIG, TG_CLIENT, BOT_INFO
    if not CONFIG_PATH.exists():
        print(f"Missing config: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    CONFIG = load_json(CONFIG_PATH, {})
    token = CONFIG.get("bot_token", "").strip()
    admin_id = CONFIG.get("admin_id")
    if not token or not admin_id:
        print("config.json needs bot_token and admin_id", file=sys.stderr)
        sys.exit(1)

    TG_CLIENT = TG(token)
    STATE = ensure_state_shape(load_json(STATE_PATH, DEFAULT_STATE))
    try:
        BOT_INFO = TG_CLIENT.call("getMe")
        log(f"webhook relay started for @{BOT_INFO.get('username', 'unknown')} admin={admin_id}")
    except Exception as e:
        log(f"startup failed: {e}")
        raise

    host = CONFIG.get("listen_host", "127.0.0.1")
    port = int(CONFIG.get("listen_port", 8780))
    server = ReusableThreadingHTTPServer((host, port), RelayHandler)
    server.timeout = 1
    log(f"listening on {host}:{port}")
    try:
        while running:
            server.handle_request()
    finally:
        server.server_close()
        save_json(STATE_PATH, STATE)
        log("relay stopped")


if __name__ == "__main__":
    main()
