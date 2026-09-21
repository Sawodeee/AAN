"""TON Telegram bot with admin controls and automatic publishing."""
import json
import logging
import os
import threading
import time

import requests
import telebot
from telebot.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup

API_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("ADMIN_USER_ID", "105405258"))
BOT_OWNER_USERNAME = "J_6_K"
DEFAULT_BUTTON = {"text": "📡 قناتنا الرسمية", "url": f"https://t.me/{BOT_OWNER_USERNAME}"}

if not API_TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود")

bot = telebot.TeleBot(API_TOKEN, parse_mode=None)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("TONBot")

FILES = {
    "channels": "database_channels_store.json",
    "admins": "database_admins_store.json",
    "users": "database_users_store.json",
    "blocked": "database_blocked_store.json",
    "timer": "config_timer_interval.txt",
    "auto": "config_auto_publish_state.txt",
    "rights": "config_channel_rights.txt",
    "welcome": "config_welcome_message.txt",
    "mode": "config_operational_mode.txt",
    "notifications": "config_notifications_state.txt",
    "button": "config_custom_button.json",
}
user_state = {}


def load(key, default):
    try:
        path = FILES[key]
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) if path.endswith(".json") else f.read().strip()
    except Exception as exc:
        logger.error("قراءة %s: %s", key, exc)
        return default


def save(key, value):
    try:
        path = FILES[key]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2) if path.endswith(".json") else f.write(str(value))
        return True
    except Exception as exc:
        logger.error("حفظ %s: %s", key, exc)
        return False


def defaults():
    values = {"timer": "3", "auto": "enabled", "rights": "قناتنا الرسمية", "welcome": "أهلاً بك في بوت أسعار TON 💎", "mode": "public", "notifications": "enabled"}
    for key, value in values.items():
        if not os.path.exists(FILES[key]):
            save(key, value)
    if not os.path.exists(FILES["button"]):
        save("button", DEFAULT_BUTTON)
    if not os.path.exists(FILES["channels"]):
        save("channels", [])
    if not os.path.exists(FILES["admins"]):
        save("admins", [])


def is_admin(user):
    if not user:
        return False
    username = (user.username or "").lower().lstrip("@")
    admins = [str(x).lower().lstrip("@") for x in load("admins", [])]
    return user.id == OWNER_ID or username == BOT_OWNER_USERNAME.lower() or username in admins


def interval():
    try:
        return max(1, int(load("timer", "3")))
    except (TypeError, ValueError):
        return 3


def ton_price():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd", timeout=10, headers={"User-Agent": "TONBot/1.0"})
        r.raise_for_status()
        return float(r.json().get("the-open-network", {}).get("usd", 0))
    except Exception as exc:
        logger.error("جلب السعر: %s", exc)
        return 0.0


def price_message():
    price = ton_price()
    if price <= 0:
        return "⚠️ تعذر جلب سعر TON حاليًا."
    return f"💎 تقرير سعر TON\n\n🔹 TON: ${price:.6f}\n\n📌 الحقوق: {load('rights', 'قناتنا الرسمية')}"


def post_keyboard():
    button = load("button", DEFAULT_BUTTON)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("🔄 تحديث السعر", callback_data="refresh"), InlineKeyboardButton(button.get("text", DEFAULT_BUTTON["text"]), url=button.get("url", DEFAULT_BUTTON["url"])))
    return markup


def publish():
    channels = load("channels", [])
    if not channels:
        logger.warning("لا توجد قنوات محفوظة للنشر")
        return
    for channel in channels:
        try:
            bot.send_message(channel, price_message(), reply_markup=post_keyboard())
            logger.info("تم النشر في %s", channel)
        except Exception as exc:
            logger.error("فشل النشر في %s: %s", channel, exc)


def publisher():
    while True:
        try:
            if load("auto", "enabled") == "enabled":
                publish()
            time.sleep(interval() * 60)
        except Exception as exc:
            logger.error("خطأ النشر التلقائي: %s", exc)
            time.sleep(60)


def home_keyboard(user):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("📊 نشر سعر TON الآن"), KeyboardButton("📡 قناتنا الرسمية"), KeyboardButton("📢 نشر منشور جديد لكل القنوات"), KeyboardButton("📊 الإحصائيات السريعة"), KeyboardButton("🆔 آيدي"))
    if is_admin(user):
        markup.add(KeyboardButton("🛠️ لوحة تحكم المشرفين"))
    return markup


def admin_keyboard():
    auto = "مفعل 🟢" if load("auto", "enabled") == "enabled" else "معطل 🔴"
    mode = "مفتوح 🌐" if load("mode", "public") == "public" else "مشرفين فقط 🔒"
    notif = "مفعلة 🟢" if load("notifications", "enabled") == "enabled" else "معطلة 🔴"
    m = InlineKeyboardMarkup(row_width=2)
    m.add(InlineKeyboardButton("📡 إدارة القنوات", callback_data="channels"), InlineKeyboardButton("📈 جلب السعر الفوري", callback_data="status"))
    m.add(InlineKeyboardButton(f"🔄 النشر التلقائي: {auto}", callback_data="toggle_auto"), InlineKeyboardButton(f"⏱ المؤقت: {interval()} د", callback_data="timer"))
    m.add(InlineKeyboardButton("🚫 إدارة الحظر", callback_data="blocks"), InlineKeyboardButton("👑 إدارة المشرفين", callback_data="admins"))
    m.add(InlineKeyboardButton("📢 إذاعة شاملة", callback_data="broadcast"), InlineKeyboardButton("📝 رسالة الترحيب", callback_data="welcome"))
    m.add(InlineKeyboardButton("🎨 تعديل الحقوق", callback_data="rights"), InlineKeyboardButton("🎛 تعديل زر القناة", callback_data="button"))
    m.add(InlineKeyboardButton(f"الوضع: {mode}", callback_data="mode"), InlineKeyboardButton(f"الإشعارات: {notif}", callback_data="notifications"))
    m.add(InlineKeyboardButton("📊 الإحصائيات المتقدمة", callback_data="stats"), InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="home"))
    return m


@bot.message_handler(commands=["start", "ping", "prices", "id", "stats", "help"])
def commands(message: Message):
    command = message.text.split()[0].split("@")[0]
    if command == "/start":
        users = load("users", [])
        if message.from_user.id not in users:
            users.append(message.from_user.id)
            save("users", users)
        bot.send_message(message.chat.id, load("welcome", "أهلاً بك في بوت أسعار TON 💎"), reply_markup=home_keyboard(message.from_user))
    elif command == "/ping":
        bot.reply_to(message, "البوت يعمل ✅")
    elif command == "/prices":
        bot.send_message(message.chat.id, price_message(), reply_markup=post_keyboard())
    elif command == "/id":
        bot.reply_to(message, f"🆔 آيديك: {message.from_user.id}")
    elif command == "/stats":
        bot.reply_to(message, f"المستخدمون: {len(load('users', []))}\nالقنوات: {len(load('channels', []))}")
    else:
        bot.reply_to(message, "استخدم الأزرار أو /prices")


@bot.message_handler(func=lambda m: True, content_types=["text"])
def messages(message: Message):
    user, uid, text = message.from_user, message.from_user.id, message.text.strip()
    state = user_state.get(uid)
    if state == "channel":
        channel = text if text.startswith("@") or text.startswith("-") else "@" + text
        channels = load("channels", [])
        if channel not in channels:
            channels.append(channel)
        save("channels", channels)
        user_state.pop(uid, None)
        bot.send_message(message.chat.id, f"✅ تمت إضافة القناة: {channel}\nعدد القنوات: {len(channels)}", reply_markup=home_keyboard(user))
        return
    if state == "timer":
        try:
            value = int(text)
            if value < 1: raise ValueError
            save("timer", value)
            user_state.pop(uid, None)
            bot.send_message(message.chat.id, f"✅ المؤقت: {value} دقيقة", reply_markup=home_keyboard(user))
        except ValueError:
            bot.reply_to(message, "أرسل رقمًا صحيحًا مثل 3")
        return
    if state == "button":
        parts = [x.strip() for x in text.split("|", 1)]
        if len(parts) != 2 or not parts[1].startswith("https://t.me/"):
            bot.reply_to(message, "الصيغة: اسم الزر | https://t.me/ChannelName")
            return
        save("button", {"text": parts[0], "url": parts[1]})
        user_state.pop(uid, None)
        bot.send_message(message.chat.id, "✅ تم تعديل زر القناة", reply_markup=home_keyboard(user))
        return
    if state == "rights":
        save("rights", text); user_state.pop(uid, None); bot.send_message(message.chat.id, "✅ تم تعديل الحقوق", reply_markup=home_keyboard(user)); return
    if state == "welcome":
        save("welcome", text); user_state.pop(uid, None); bot.send_message(message.chat.id, "✅ تم تعديل الترحيب", reply_markup=home_keyboard(user)); return
    if state == "block":
        try: value = int(text)
        except ValueError: bot.reply_to(message, "أرسل آيدي رقمي"); return
        blocked = load("blocked", [])
        if value in blocked: blocked.remove(value); result = "إلغاء الحظر"
        else: blocked.append(value); result = "تم الحظر"
        save("blocked", blocked); user_state.pop(uid, None); bot.send_message(message.chat.id, f"✅ {result}: {value}", reply_markup=home_keyboard(user)); return
    if state == "admin":
        name = text.lstrip("@"); admins = load("admins", [])
        if name in admins: admins.remove(name); result = "حذف المشرف"
        else: admins.append(name); result = "إضافة المشرف"
        save("admins", admins); user_state.pop(uid, None); bot.send_message(message.chat.id, f"✅ {result}: @{name}", reply_markup=home_keyboard(user)); return
    if state == "broadcast":
        for channel in load("channels", []):
            try: bot.copy_message(channel, message.chat.id, message.message_id, reply_markup=post_keyboard())
            except Exception as exc: logger.error("إذاعة %s: %s", channel, exc)
        user_state.pop(uid, None); bot.send_message(message.chat.id, "✅ تمت الإذاعة", reply_markup=home_keyboard(user)); return
    if text == "📊 نشر سعر TON الآن": bot.send_message(message.chat.id, price_message(), reply_markup=post_keyboard())
    elif text == "📡 قناتنا الرسمية": bot.send_message(message.chat.id, load("button", DEFAULT_BUTTON).get("url", DEFAULT_BUTTON["url"]))
    elif text == "📢 نشر منشور جديد لكل القنوات" and is_admin(user): user_state[uid] = "broadcast"; bot.send_message(message.chat.id, "أرسل المنشور الآن")
    elif text == "📊 الإحصائيات السريعة": bot.send_message(message.chat.id, f"المستخدمون: {len(load('users', []))}\nالقنوات: {len(load('channels', []))}")
    elif text == "🆔 آيدي": bot.send_message(message.chat.id, f"آيديك: {uid}")
    elif text == "🛠️ لوحة تحكم المشرفين" and is_admin(user): bot.send_message(message.chat.id, "🛠️ لوحة التحكم الإدارية:", reply_markup=admin_keyboard())


@bot.callback_query_handler(func=lambda c: True)
def callbacks(call):
    data, user, uid = call.data, call.from_user, call.from_user.id
    if data == "refresh":
        bot.answer_callback_query(call.id, "تم التحديث ✅")
        try: bot.edit_message_text(price_message(), call.message.chat.id, call.message.message_id, reply_markup=post_keyboard())
        except Exception as exc: logger.error("تحديث الرسالة: %s", exc)
        return
    if not is_admin(user): bot.answer_callback_query(call.id, "غير مسموح", show_alert=True); return
    bot.answer_callback_query(call.id)
    if data == "home": bot.send_message(call.message.chat.id, "القائمة الرئيسية", reply_markup=home_keyboard(user))
    elif data == "channels": user_state[uid] = "channel"; bot.send_message(call.message.chat.id, "أرسل معرف القناة مثل @ChannelName. يجب أن يكون البوت مشرفًا بصلاحية النشر.")
    elif data == "toggle_auto": save("auto", "disabled" if load("auto", "enabled") == "enabled" else "enabled"); bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())
    elif data == "timer": user_state[uid] = "timer"; bot.send_message(call.message.chat.id, "أرسل عدد الدقائق، مثال: 3")
    elif data == "button": user_state[uid] = "button"; bot.send_message(call.message.chat.id, "أرسل: اسم الزر | https://t.me/ChannelName")
    elif data == "rights": user_state[uid] = "rights"; bot.send_message(call.message.chat.id, "أرسل نص الحقوق الجديد")
    elif data == "welcome": user_state[uid] = "welcome"; bot.send_message(call.message.chat.id, "أرسل رسالة الترحيب الجديدة")
    elif data == "blocks": user_state[uid] = "block"; bot.send_message(call.message.chat.id, "أرسل آيدي المستخدم لإضافة/إزالة الحظر")
    elif data == "admins": user_state[uid] = "admin"; bot.send_message(call.message.chat.id, "أرسل username المشرف بدون @ لإضافة/إزالة")
    elif data == "broadcast": user_state[uid] = "broadcast"; bot.send_message(call.message.chat.id, "أرسل المنشور ليتم إرساله للقنوات")
    elif data == "status": bot.answer_callback_query(call.id, f"TON: ${ton_price():.6f}", show_alert=True)
    elif data == "mode": save("mode", "admin_only" if load("mode", "public") == "public" else "public"); bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())
    elif data == "notifications": save("notifications", "disabled" if load("notifications", "enabled") == "enabled" else "enabled"); bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())
    elif data == "stats": bot.send_message(call.message.chat.id, f"المستخدمون: {len(load('users', []))}\nالقنوات: {len(load('channels', []))}\nالمحظورون: {len(load('blocked', []))}")


def main():
    defaults()
    threading.Thread(target=publisher, daemon=True).start()
    bot.set_my_commands([BotCommand("start", "تشغيل"), BotCommand("prices", "سعر TON"), BotCommand("ping", "فحص")])
    logger.info("TON bot يعمل، النشر كل %s دقائق", interval())
    bot.infinity_polling(skip_pending=True)


if __name__ == "__main__":
    main()
