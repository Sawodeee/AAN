import json
import logging
import os
import threading
import time

import requests
import telebot
from telebot.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("ADMIN_USER_ID", "105405258"))
DEFAULT_DEVELOPER = "@sn3nn"
FILES = {
    "channels": "database_channels_store.json", "admins": "database_admins_store.json", "users": "database_users_store.json",
    "blocked": "database_blocked_store.json", "timer": "config_timer_interval.txt", "auto": "config_auto_publish_state.txt",
    "developer": "config_developer.txt", "welcome": "config_welcome_message.txt", "mode": "config_operational_mode.txt",
    "notifications": "config_notifications_state.txt", "button": "config_custom_button.json",
}
if not TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود")
bot = telebot.TeleBot(TOKEN, parse_mode=None)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("TONBot")
state = {}


def load(key, default):
    try:
        path = FILES[key]
        if not os.path.exists(path): return default
        with open(path, encoding="utf-8") as f: return json.load(f) if path.endswith(".json") else f.read().strip()
    except Exception as exc:
        log.error("load %s: %s", key, exc); return default


def save(key, value):
    try:
        path = FILES[key]
        with open(path, "w", encoding="utf-8") as f:
            if path.endswith(".json"): json.dump(value, f, ensure_ascii=False, indent=2)
            else: f.write(str(value))
        return True
    except Exception as exc:
        log.error("save %s: %s", key, exc); return False


def defaults():
    values = {"timer": "3", "auto": "enabled", "developer": "المطور", "welcome": "أهلاً بك في بوت أسعار TON 💎", "mode": "public", "notifications": "enabled"}
    for key, value in values.items():
        if not os.path.exists(FILES[key]): save(key, value)
    for key in ("channels", "admins", "users", "blocked"):
        if not os.path.exists(FILES[key]): save(key, [])
    if not os.path.exists(FILES["button"]): save("button", {"text": "👤 المطور", "url": "https://t.me/sn3nn"})


def is_admin(user):
    username = (getattr(user, "username", "") or "").lower().lstrip("@")
    admins = [str(x).lower().lstrip("@") for x in load("admins", [])]
    return bool(user and (user.id == OWNER_ID or username == "j_6_k" or username in admins))


def minutes():
    try: return max(1, int(load("timer", "3")))
    except (TypeError, ValueError): return 3


def channels():
    result = list(load("channels", []))
    for item in os.getenv("PUBLISH_CHANNELS", "").split(","):
        item = item.strip()
        if item and item not in result: result.append(item)
    return result


def ton_price():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd", timeout=10, headers={"User-Agent": "TONBot/1.0"})
        response.raise_for_status()
        return float(response.json().get("the-open-network", {}).get("usd", 0))
    except Exception as exc:
        log.error("price: %s", exc); return 0.0


def price_text():
    value = ton_price()
    if value <= 0: return "⚠️ تعذر جلب سعر TON حاليًا."
    return f"💎 تقرير سعر TON\n\n🔹 TON: ${value:.2f}\n\n📌 المطور: {load('developer', 'المطور')}"


def developer_markup():
    button = load("button", {"text": "👤 المطور", "url": "https://t.me/sn3nn"})
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(button.get("text", "👤 المطور"), url=button.get("url", "https://t.me/sn3nn")))
    return markup


def publish():
    targets = channels()
    if not targets:
        log.warning("لا توجد قنوات للنشر؛ أضف قناة من اللوحة أو PUBLISH_CHANNELS في Secrets")
        return
    for channel in targets:
        try:
            bot.send_message(channel, price_text(), reply_markup=developer_markup())
            log.info("published to %s", channel)
        except Exception as exc: log.error("publish %s: %s", channel, exc)


def publisher():
    while True:
        try:
            if load("auto", "enabled") == "enabled": publish()
            time.sleep(minutes() * 60)
        except Exception as exc:
            log.error("publisher: %s", exc); time.sleep(60)


def home(user):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("📊 نشر سعر TON الآن"), KeyboardButton("📡 قناتنا الرسمية"), KeyboardButton("📢 نشر منشور جديد لكل القنوات"), KeyboardButton("📊 الإحصائيات السريعة"), KeyboardButton("🆔 آيدي"))
    if is_admin(user): markup.add(KeyboardButton("🛠️ لوحة تحكم المشرفين"))
    return markup


def panel():
    auto = "مفعل 🟢" if load("auto", "enabled") == "enabled" else "معطل 🔴"
    mode = "مفتوح 🌐" if load("mode", "public") == "public" else "مشرفين فقط 🔒"
    note = "مفعلة 🟢" if load("notifications", "enabled") == "enabled" else "معطلة 🔴"
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("📡 إدارة القنوات", callback_data="channels"), InlineKeyboardButton("📈 جلب السعر الفوري", callback_data="status"))
    markup.add(InlineKeyboardButton(f"🔄 النشر التلقائي: {auto}", callback_data="auto"), InlineKeyboardButton(f"⏱ المؤقت: {minutes()} د", callback_data="timer"))
    markup.add(InlineKeyboardButton("🚫 إدارة الحظر", callback_data="block"), InlineKeyboardButton("👑 إدارة المشرفين", callback_data="admins"))
    markup.add(InlineKeyboardButton("📢 إذاعة شاملة", callback_data="broadcast"), InlineKeyboardButton("📝 رسالة الترحيب", callback_data="welcome"))
    markup.add(InlineKeyboardButton("🎨 تعديل المطور", callback_data="developer"), InlineKeyboardButton("👤 تعديل زر المطور", callback_data="button"))
    markup.add(InlineKeyboardButton(f"الوضع: {mode}", callback_data="mode"), InlineKeyboardButton(f"الإشعارات: {note}", callback_data="notifications"))
    markup.add(InlineKeyboardButton("📊 الإحصائيات المتقدمة", callback_data="stats"), InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="home"))
    return markup


@bot.message_handler(commands=["start", "ping", "prices", "id", "stats", "help"])
def commands(message):
    command = message.text.split()[0].split("@")[0]
    if command == "/start":
        users = load("users", [])
        if message.from_user.id not in users: users.append(message.from_user.id); save("users", users)
        bot.send_message(message.chat.id, load("welcome", "أهلاً بك في بوت أسعار TON 💎"), reply_markup=home(message.from_user))
    elif command == "/ping": bot.reply_to(message, "البوت يعمل ✅")
    elif command == "/prices": bot.send_message(message.chat.id, price_text(), reply_markup=developer_markup())
    elif command == "/id": bot.reply_to(message, f"🆔 آيديك: {message.from_user.id}")
    elif command == "/stats": bot.reply_to(message, f"المستخدمون: {len(load('users', []))}\nالقنوات: {len(channels())}")
    else: bot.reply_to(message, "استخدم الأزرار أو /prices")


@bot.message_handler(func=lambda m: True, content_types=["text"])
def messages(message):
    user, uid, text = message.from_user, message.from_user.id, message.text.strip()
    current = state.get(uid)
    if current == "channel":
        value = text if text.startswith(("@", "-")) else "@" + text
        items = load("channels", [])
        if value not in items: items.append(value)
        save("channels", items); state.pop(uid, None)
        bot.send_message(message.chat.id, f"✅ تمت إضافة القناة: {value}", reply_markup=home(user)); return
    if current == "timer":
        try:
            value = int(text)
            if value < 1: raise ValueError
            save("timer", value); state.pop(uid, None); bot.send_message(message.chat.id, f"✅ المؤقت: {value} دقيقة", reply_markup=home(user))
        except ValueError: bot.reply_to(message, "أرسل رقمًا صحيحًا مثل 3")
        return
    if current == "button":
        parts = [x.strip() for x in text.split("|", 1)]
        if len(parts) != 2:
            bot.reply_to(message, "أرسل اسم الزر والمعرف بهذا الشكل:\n👤 المطور | @sn3nn")
            return
        target = parts[1].strip()
        if target.startswith("https://t.me/"): url = target
        else:
            username = target.lstrip("@").strip()
            if not username: bot.reply_to(message, "اكتب معرف الحساب مثل @sn3nn"); return
            url = f"https://t.me/{username}"
        save("button", {"text": parts[0], "url": url}); state.pop(uid, None)
        bot.send_message(message.chat.id, "✅ تم تعديل زر المطور", reply_markup=home(user)); return
    if current in ("developer", "welcome"):
        save(current, text); state.pop(uid, None); bot.send_message(message.chat.id, "✅ تم الحفظ", reply_markup=home(user)); return
    if current == "block":
        try: value = int(text)
        except ValueError: bot.reply_to(message, "أرسل آيدي رقمي"); return
        blocked = load("blocked", [])
        if value in blocked: blocked.remove(value); result = "إلغاء الحظر"
        else: blocked.append(value); result = "تم الحظر"
        save("blocked", blocked); state.pop(uid, None); bot.send_message(message.chat.id, f"✅ {result}: {value}", reply_markup=home(user)); return
    if current == "admins":
        name = text.lstrip("@"); admins = load("admins", [])
        if name in admins: admins.remove(name); result = "حذف المشرف"
        else: admins.append(name); result = "إضافة المشرف"
        save("admins", admins); state.pop(uid, None); bot.send_message(message.chat.id, f"✅ {result}: @{name}", reply_markup=home(user)); return
    if current == "broadcast":
        for channel in channels():
            try: bot.copy_message(channel, message.chat.id, message.message_id)
            except Exception as exc: log.error("broadcast %s: %s", channel, exc)
        state.pop(uid, None); bot.send_message(message.chat.id, "✅ تمت الإذاعة", reply_markup=home(user)); return
    if text == "📊 نشر سعر TON الآن": bot.send_message(message.chat.id, price_text(), reply_markup=developer_markup())
    elif text == "📡 قناتنا الرسمية": bot.send_message(message.chat.id, load("button", {"url": "https://t.me/sn3nn"}).get("url", "https://t.me/sn3nn"))
    elif text == "📢 نشر منشور جديد لكل القنوات" and is_admin(user): state[uid] = "broadcast"; bot.send_message(message.chat.id, "أرسل المنشور الآن")
    elif text == "📊 الإحصائيات السريعة": bot.send_message(message.chat.id, f"المستخدمون: {len(load('users', []))}\nالقنوات: {len(channels())}")
    elif text == "🆔 آيدي": bot.send_message(message.chat.id, f"آيديك: {uid}")
    elif text == "🛠️ لوحة تحكم المشرفين" and is_admin(user): bot.send_message(message.chat.id, "🛠️ لوحة التحكم الإدارية:", reply_markup=panel())


@bot.callback_query_handler(func=lambda c: True)
def callbacks(call):
    data, user, uid = call.data, call.from_user, call.from_user.id
    if not is_admin(user): bot.answer_callback_query(call.id, "غير مسموح", show_alert=True); return
    bot.answer_callback_query(call.id)
    if data == "home": bot.send_message(call.message.chat.id, "القائمة الرئيسية", reply_markup=home(user))
    elif data == "channels": state[uid] = "channel"; bot.send_message(call.message.chat.id, "أرسل معرف القناة مثل @sn3nn")
    elif data == "auto": save("auto", "disabled" if load("auto", "enabled") == "enabled" else "enabled"); bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=panel())
    elif data == "timer": state[uid] = "timer"; bot.send_message(call.message.chat.id, "أرسل عدد الدقائق، مثال: 3")
    elif data == "button": state[uid] = "button"; bot.send_message(call.message.chat.id, "أرسل اسم الزر والمعرف بهذا الشكل:\n👤 المطور | @sn3nn")
    elif data == "developer": state[uid] = "developer"; bot.send_message(call.message.chat.id, "أرسل اسم المطور")
    elif data == "welcome": state[uid] = "welcome"; bot.send_message(call.message.chat.id, "أرسل رسالة الترحيب الجديدة")
    elif data == "block": state[uid] = "block"; bot.send_message(call.message.chat.id, "أرسل آيدي المستخدم")
    elif data == "admins": state[uid] = "admins"; bot.send_message(call.message.chat.id, "أرسل username المشرف بدون @")
    elif data == "broadcast": state[uid] = "broadcast"; bot.send_message(call.message.chat.id, "أرسل المنشور للقنوات")
    elif data == "status": bot.answer_callback_query(call.id, f"TON: ${ton_price():.2f}", show_alert=True)
    elif data == "mode": save("mode", "admin_only" if load("mode", "public") == "public" else "public"); bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=panel())
    elif data == "notifications": save("notifications", "disabled" if load("notifications", "enabled") == "enabled" else "enabled"); bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=panel())
    elif data == "stats": bot.send_message(call.message.chat.id, f"المستخدمون: {len(load('users', []))}\nالقنوات: {len(channels())}\nالمحظورون: {len(load('blocked', []))}")


def main():
    defaults(); threading.Thread(target=publisher, daemon=True).start()
    bot.set_my_commands([BotCommand("start", "تشغيل"), BotCommand("prices", "سعر TON"), BotCommand("ping", "فحص")])
    bot.infinity_polling(skip_pending=True)


if __name__ == "__main__": main()
