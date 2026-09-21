"""Telegram TON price bot."""
import json
import logging
import os
import threading
import time

import requests
import telebot
from telebot.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

API_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("ADMIN_USER_ID", "105405258"))
BOT_OWNER_USERNAME = "J_6_K"
DEFAULT_CHANNEL_BUTTON_TEXT = "📡 قناتنا الرسمية"
DEFAULT_CHANNEL_BUTTON_URL = f"https://t.me/{BOT_OWNER_USERNAME}"

if not API_TOKEN:
    raise RuntimeError("ضع توكن البوت في المتغير BOT_TOKEN.")

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
    "button": "config_custom_button.json",
}
user_state = {}


def load_data(key, default):
    path = FILES[key]
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file) if path.endswith(".json") else file.read().strip()
    except Exception as exc:
        logger.error("Failed reading %s: %s", path, exc)
        return default


def save_data(key, value):
    path = FILES[key]
    try:
        with open(path, "w", encoding="utf-8") as file:
            if path.endswith(".json"):
                json.dump(value, file, ensure_ascii=False, indent=2)
            else:
                file.write(str(value))
        return True
    except Exception as exc:
        logger.error("Failed writing %s: %s", path, exc)
        return False


def defaults():
    if not os.path.exists(FILES["timer"]):
        save_data("timer", "3")
    if not os.path.exists(FILES["auto"]):
        save_data("auto", "enabled")
    if not os.path.exists(FILES["button"]):
        save_data("button", {"text": DEFAULT_CHANNEL_BUTTON_TEXT, "url": DEFAULT_CHANNEL_BUTTON_URL})
    if not os.path.exists(FILES["rights"]):
        save_data("rights", "قناتنا الرسمية")


def is_admin(user):
    if not user:
        return False
    if user.id == OWNER_ID:
        return True
    username = (user.username or "").lower().lstrip("@")
    admins = [str(item).lower().lstrip("@") for item in load_data("admins", [])]
    return username == BOT_OWNER_USERNAME.lower().lstrip("@") or username in admins


def minutes():
    try:
        return max(1, int(load_data("timer", "3")))
    except (TypeError, ValueError):
        return 3


def get_ton_price():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd"
    try:
        response = requests.get(url, headers={"User-Agent": "TONBot/1.0"}, timeout=10)
        response.raise_for_status()
        return float(response.json().get("the-open-network", {}).get("usd", 0))
    except Exception as exc:
        logger.error("Price request failed: %s", exc)
        return 0.0


def price_text():
    price = get_ton_price()
    if price <= 0:
        return "⚠️ تعذر جلب سعر TON حاليًا."
    rights = load_data("rights", "قناتنا الرسمية")
    return f"💎 تقرير سعر TON\n\n🔹 TON: ${price:.6f}\n\n📌 الحقوق: {rights}"


def post_keyboard():
    button = load_data("button", {"text": DEFAULT_CHANNEL_BUTTON_TEXT, "url": DEFAULT_CHANNEL_BUTTON_URL})
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔄 تحديث السعر", callback_data="refresh_ton"),
        InlineKeyboardButton(button.get("text", DEFAULT_CHANNEL_BUTTON_TEXT), url=button.get("url", DEFAULT_CHANNEL_BUTTON_URL)),
    )
    return markup


def publish_to_channels():
    channels = load_data("channels", [])
    if not channels:
        logger.warning("لا توجد قنوات محفوظة للنشر.")
        return
    text = price_text()
    for channel in channels:
        try:
            bot.send_message(channel, text, reply_markup=post_keyboard())
            logger.info("Published TON price to %s", channel)
        except Exception as exc:
            logger.error("Could not publish to %s: %s", channel, exc)


def publisher():
    # يعمل طوال مدة تشغيل GitHub Actions: ينشر فورًا ثم كل 3 دقائق افتراضيًا.
    while True:
        try:
            if load_data("auto", "enabled") == "enabled":
                publish_to_channels()
            time.sleep(minutes() * 60)
        except Exception as exc:
            logger.error("Publisher error: %s", exc)
            time.sleep(60)


def home_keyboard(user):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("💎 سعر TON الآن"), KeyboardButton("📡 قناتنا الرسمية"))
    if is_admin(user):
        markup.add(KeyboardButton("🛠️ لوحة المشرف"))
    return markup


def admin_keyboard():
    status = "مفعل 🟢" if load_data("auto", "enabled") == "enabled" else "معطل 🔴"
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("📡 إدارة القنوات", callback_data="channels"))
    markup.add(InlineKeyboardButton(f"🔄 النشر التلقائي: {status}", callback_data="toggle_auto"), InlineKeyboardButton(f"⏱ المؤقت: {minutes()} د", callback_data="timer"))
    markup.add(InlineKeyboardButton("🎛 تعديل زر القناة", callback_data="edit_button"), InlineKeyboardButton("🎨 تعديل الحقوق", callback_data="edit_rights"))
    markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="home"))
    return markup


@bot.message_handler(commands=["start", "ping", "prices"])
def commands(message: Message):
    if message.text.startswith("/start"):
        bot.send_message(message.chat.id, "أهلاً بك في بوت أسعار TON 💎", reply_markup=home_keyboard(message.from_user))
    elif message.text.startswith("/ping"):
        bot.reply_to(message, "البوت يعمل ✅")
    else:
        bot.send_message(message.chat.id, price_text(), reply_markup=post_keyboard())


@bot.message_handler(func=lambda message: True, content_types=["text"])
def messages(message: Message):
    user = message.from_user
    uid = user.id
    text = message.text.strip()
    state = user_state.get(uid)

    if state == "channel":
        channels = load_data("channels", [])
        channel = text if text.startswith("@") or text.startswith("-") else f"@{text}"
        if channel not in channels:
            channels.append(channel)
            save_data("channels", channels)
        user_state.pop(uid, None)
        bot.send_message(message.chat.id, f"✅ تمت إضافة القناة: {channel}", reply_markup=home_keyboard(user))
        return
    if state == "timer":
        try:
            value = int(text)
            if value < 1:
                raise ValueError
            save_data("timer", value)
            user_state.pop(uid, None)
            bot.send_message(message.chat.id, f"✅ المؤقت أصبح {value} دقيقة.", reply_markup=home_keyboard(user))
        except ValueError:
            bot.reply_to(message, "أرسل رقمًا صحيحًا، مثل 3.")
        return
    if state == "button":
        parts = [part.strip() for part in text.split("|", 1)]
        if len(parts) != 2 or not parts[1].startswith("https://t.me/"):
            bot.reply_to(message, "أرسلها بهذا الشكل:\nاسم الزر | https://t.me/ChannelName")
            return
        save_data("button", {"text": parts[0], "url": parts[1]})
        user_state.pop(uid, None)
        bot.send_message(message.chat.id, "✅ تم تعديل اسم ورابط زر القناة.", reply_markup=home_keyboard(user))
        return
    if state == "rights":
        save_data("rights", text)
        user_state.pop(uid, None)
        bot.send_message(message.chat.id, "✅ تم تعديل الحقوق.", reply_markup=home_keyboard(user))
        return

    if text == "💎 سعر TON الآن":
        bot.send_message(message.chat.id, price_text(), reply_markup=post_keyboard())
    elif text == "📡 قناتنا الرسمية":
        button = load_data("button", {"text": DEFAULT_CHANNEL_BUTTON_TEXT, "url": DEFAULT_CHANNEL_BUTTON_URL})
        bot.send_message(message.chat.id, f"قناتنا الرسمية: {button.get('url', DEFAULT_CHANNEL_BUTTON_URL)}")
    elif text == "🛠️ لوحة المشرف" and is_admin(user):
        bot.send_message(message.chat.id, "🛠️ لوحة المشرف", reply_markup=admin_keyboard())


@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if call.data == "refresh_ton":
        bot.answer_callback_query(call.id, "تم تحديث سعر TON ✅")
        try:
            bot.edit_message_text(price_text(), call.message.chat.id, call.message.message_id, reply_markup=post_keyboard())
        except Exception as exc:
            logger.error("Could not edit price message: %s", exc)
        return
    if not is_admin(call.from_user):
        bot.answer_callback_query(call.id, "غير مسموح.", show_alert=True)
        return
    if call.data == "home":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "القائمة الرئيسية", reply_markup=home_keyboard(call.from_user))
    elif call.data == "channels":
        user_state[call.from_user.id] = "channel"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "أرسل معرف القناة، مثل @ChannelName، بعد إضافة البوت مشرفًا.")
    elif call.data == "toggle_auto":
        new_value = "disabled" if load_data("auto", "enabled") == "enabled" else "enabled"
        save_data("auto", new_value)
        bot.answer_callback_query(call.id, "تم تغيير حالة النشر التلقائي ✅")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())
    elif call.data == "timer":
        user_state[call.from_user.id] = "timer"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "أرسل عدد الدقائق بين المنشورات. الافتراضي 3 دقائق.")
    elif call.data == "edit_button":
        user_state[call.from_user.id] = "button"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "أرسل اسم الزر والرابط بهذا الشكل:\nاسم الزر | https://t.me/ChannelName")
    elif call.data == "edit_rights":
        user_state[call.from_user.id] = "rights"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "أرسل نص الحقوق الجديد.")


def main():
    defaults()
    threading.Thread(target=publisher, daemon=True).start()
    bot.set_my_commands([BotCommand("start", "تشغيل البوت"), BotCommand("prices", "سعر TON"), BotCommand("ping", "فحص البوت")])
    logger.info("TON bot يعمل 24/7، النشر كل %s دقائق.", minutes())
    bot.infinity_polling(skip_pending=True)


if __name__ == "__main__":
    main()
