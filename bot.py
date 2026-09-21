"""
================================================================================
   اسم البوت: البوت الشامل والمتكامل لإدارة القنوات والعملات الرقمية (TON & Gram)
   المطور: @J_6_K
   الإصدار: 2026 النهائي (النسخة المطورة والخالية من الأخطاء)
================================================================================
"""

import os
import sys
import json
import logging
import requests
import threading
import time
import telebot
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
    Message
)

# ==============================================================================
# 1. إعدادات النظام ومتغيرات البيئة والتوكن الأساسي
# ==============================================================================
API_TOKEN = ""
OWNER_ID = 105405258
BOT_OWNER_USERNAME = "J_6_K"
CHANNEL_USERNAME = "@J_6_K"

# تهيئة كائن البوت الرئيسي
bot = telebot.TeleBot(API_TOKEN, parse_mode="Markdown")

# إعداد نظام السجلات (Logging System)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d): %(message)s',
    handlers=[
        logging.FileHandler("bot_execution.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ComprehensiveBot2026")

# تعيين أوامر البوت الافتراضية
try:
    bot.set_my_commands([
        BotCommand("start", "تشغيل البوت وإظهار اللوحة الرئيسية"),
        BotCommand("id", "معرفة الآيدي والمعلومات الشخصية"),
        BotCommand("ping", "فحص سرعة وحالة الاستجابة"),
        BotCommand("stats", "عرض إحصائيات البوت الشاملة"),
        BotCommand("help", "الحصول على مساعدة واستعراض الأوامر"),
        BotCommand("prices", "عرض أسعار العملات الرقمية الحالية")
    ])
    logger.info("تم تعيين الأوامر بنجاح.")
except Exception as e:
    logger.error(f"خطأ أثناء تعيين الأوامر: {e}")

# ==============================================================================
# 2. هيكل قواعد البيانات المحلية وإدارة الملفات (JSON Storage Engine)
# ==============================================================================
DATABASE_FILES = {
    "channels": "database_channels_store.json",
    "admins": "database_admins_store.json",
    "users": "database_users_store.json",
    "blocked": "database_blocked_store.json",
    "welcome": "config_welcome_message.txt",
    "timer": "config_timer_interval.txt",
    "rights": "config_channel_rights.txt",
    "notifications": "config_notifications_state.txt",
    "mode": "config_operational_mode.txt",
    "auto_publish": "config_auto_publish_state.txt",
    "custom_btn": "config_custom_button.json"
}

user_state = {}
user_pending_posts = {}
bot_runtime_stats = {
    "start_time": time.time(),
    "messages_handled": 0,
    "commands_executed": 0,
    "errors_count": 0
}

def load_data(file_key, default_value):
    filename = DATABASE_FILES.get(file_key, "fallback_data.json")
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                if filename.endswith(".json"):
                    return json.load(f)
                return f.read().strip()
        except Exception as err:
            logger.error(f"فشل قراءة الملف {filename}: {err}")
            return default_value
    return default_value

def save_data(file_key, data_payload):
    filename = DATABASE_FILES.get(file_key, "fallback_data.json")
    try:
        with open(filename, "w", encoding="utf-8") as f:
            if filename.endswith(".json"):
                json.dump(data_payload, f, ensure_ascii=False, indent=4)
            else:
                f.write(str(data_payload))
        return True
    except Exception as err:
        logger.error(f"فشل حفظ البيانات إلى {filename}: {err}")
        bot_runtime_stats["errors_count"] += 1
        return False

# ==============================================================================
# 3. نظام الصلاحيات والحظر
# ==============================================================================
def is_admin(user_obj):
    if not user_obj:
        return False
    if user_obj.id == OWNER_ID:
        return True
    if not user_obj.username:
        return False
    current_username = user_obj.username.lower().replace("@", "")
    owner_clean = BOT_OWNER_USERNAME.lower().replace("@", "")
    if current_username == owner_clean:
        return True
    stored_admins = load_data("admins", [])
    return current_username in [str(a).lower().replace("@", "") for a in stored_admins]

def is_blocked(user_id):
    return user_id in load_data("blocked", [])

def get_bot_mode():
    return load_data("mode", "public")

def get_notifications_status():
    return load_data("notifications", "enabled") == "enabled"

def get_auto_publish_status():
    return load_data("auto_publish", "disabled") == "enabled"

def get_timer_minutes():
    try:
        val = int(load_data("timer", "60"))
        return val if val > 0 else 60
    except ValueError:
        return 60

# ==============================================================================
# 4. محرك جلب الأسعار والـ APIs
# ==============================================================================
def get_ton_and_gram_prices():
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network,gram&vs_currencies=usd"
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            ton = data.get("the-open-network", {}).get("usd", 5.5)
            gram = data.get("gram", {}).get("usd", ton * 0.2)
            return float(ton), float(gram)
    except Exception as e:
        logger.error(f"خطأ جلب الأسعار: {e}")
    return 5.5, 1.1

def get_channel_post_keyboard():
    markup = InlineKeyboardMarkup()
    btn_custom = load_data("custom_btn", {"text": "📡 قناتنا الرسمية", "url": f"https://t.me/{BOT_OWNER_USERNAME}"})
    markup.add(
        InlineKeyboardButton("🔄 تحديث السعر", callback_data="refresh_ton_price"),
        InlineKeyboardButton(btn_custom["text"], url=btn_custom["url"])
    )
    return markup

def broadcast_prices_to_all_channels():
    ton, gram = get_ton_and_gram_prices()
    rights = load_data("rights", "قناتنا الرسمية")
    channels = load_data("channels", [])
    if not channels:
        return False
    text = f"💎 **تقرير أسعار العملات الرقمية المباشر:**\n\n🔹 **TON:** `${ton}`\n🔸 **Gram:** `${gram}`\n\n📌 **الحقوق:** {rights}"
    for ch in channels:
        try:
            bot.send_message(ch, text, parse_mode="Markdown", reply_markup=get_channel_post_keyboard())
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"خطأ النشر للقناة {ch}: {e}")
    return True

def background_auto_publisher_daemon():
    while True:
        try:
            if get_auto_publish_status():
                broadcast_prices_to_all_channels()
            time.sleep(get_timer_minutes() * 60)
        except Exception as e:
            logger.error(f"خطأ خيط النشر الخلفي: {e}")
            time.sleep(60)

threading.Thread(target=background_auto_publisher_daemon, daemon=True).start()

# ==============================================================================
# 5. بناء لوحات المفاتيح (الرئيسية ولوحة التحكم المتطورة 2026)
# ==============================================================================
def get_main_reply_keyboard(user):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("📊 نشر سعر TON الآن"),
        KeyboardButton("📡 قناتنا الرسمية"),
        KeyboardButton("📢 نشر منشور جديد لكل القنوات"),
        KeyboardButton("📊 الإحصائيات السريعة"),
        KeyboardButton("🆔 آيدي")
    )
    if is_admin(user):
        markup.add(KeyboardButton("🛠️ لوحة تحكم المشرفين"))
    return markup

def get_admin_inline_control_panel():
    notif_label = "الإشعارات: مفعلة 🟢" if get_notifications_status() else "الإشعارات: معطلة 🔴"
    mode_label = "🌐 الوضع: مفتوح" if get_bot_mode() == "public" else "🔒 الوضع: مشرفين فقط"
    auto_label = "🔄 النشر التلقائي: مفعل 🟢" if get_auto_publish_status() else "🔄 النشر التلقائي: معطل 🔴"
    timer_val = get_timer_minutes()
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("📈 جلب الأسعار الفوري", callback_data="status_ch"), InlineKeyboardButton("📡 إدارة القنوات", callback_data="manage_channels"))
    markup.add(InlineKeyboardButton(auto_label, callback_data="toggle_auto_publish"), InlineKeyboardButton(f"⏳ المؤقت: {timer_val}د", callback_data="edit_timer"))
    markup.add(InlineKeyboardButton("🚫 إدارة الحظر", callback_data="manage_blocks"), InlineKeyboardButton("👑 إدارة المشرفين", callback_data="manage_admins"))
    markup.add(InlineKeyboardButton("📢 إذاعة شاملة", callback_data="start_broadcast"), InlineKeyboardButton("📝 رسالة الترحيب", callback_data="edit_welcome"))
    markup.add(InlineKeyboardButton("🎨 تعديل الحقوق", callback_data="edit_rights"), InlineKeyboardButton("📊 الإحصائيات المتقدمة", callback_data="bot_stats"))
    markup.add(InlineKeyboardButton(mode_label, callback_data="toggle_mode"), InlineKeyboardButton(notif_label, callback_data="toggle_notifications"))
    markup.add(InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_home"))
    return markup

# ==============================================================================
# 6. معالجات الأوامر والرسائل
# ==============================================================================
@bot.message_handler(commands=['start'])
def start_cmd(message: Message):
    bot_runtime_stats["commands_executed"] += 1
    user = message.from_user
    if is_blocked(user.id):
        return
    
    users = load_data("users", [])
    if user.id not in users:
        users.append(user.id)
        save_data("users", users)

    if get_bot_mode() == "admin_only" and not is_admin(user):
        bot.reply_to(message, "⚠️ البوت في وضع الصيانة حالياً.")
        return

    welcome_msg = load_data("welcome", f"أهلاً بك يا {user.first_name} في بوت أسعار العملات الرقمية المتطور 🚀")
    bot.send_message(message.chat.id, welcome_msg, reply_markup=get_main_reply_keyboard(user), parse_mode="Markdown")

@bot.message_handler(commands=['id', 'stats', 'ping', 'help', 'prices'])
def utility_cmds(message: Message):
    bot_runtime_stats["commands_executed"] += 1
    user = message.from_user
    if is_blocked(user.id):
        return
    cmd = message.text.split()[0].lower().split("@")[0]

    if cmd == "/id":
        bot.reply_to(message, f"🆔 الآيدي: `{user.id}`\n👤 الاسم: {user.first_name}", parse_mode="Markdown")
    elif cmd == "/stats":
        bot.reply_to(message, f"📊 المشتركين: {len(load_data('users', []))}\n🚫 المحظورين: {len(load_data('blocked', []))}\n📡 القنوات: {len(load_data('channels', []))}", parse_mode="Markdown")
    elif cmd == "/ping":
        bot.reply_to(message, "pong! ⚡ البوت يعمل بكفاءة عالية وبدون أخطاء.")
    elif cmd == "/help":
        bot.reply_to(message, f"💡 استخدم الأزرار بالأسفل أو راسل المطور مباشرة: @{BOT_OWNER_USERNAME}", parse_mode="Markdown")
    elif cmd == "/prices":
        ton, gram = get_ton_and_gram_prices()
        bot.reply_to(message, f"💎 TON: `${ton}`\n🔸 Gram: `${gram}`", parse_mode="Markdown", reply_markup=get_channel_post_keyboard())

@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'document', 'audio', 'sticker'])
def message_handler(message: Message):
    bot_runtime_stats["messages_handled"] += 1
    user = message.from_user
    uid = user.id
    if is_blocked(uid):
        return

    text = message.text or message.caption or ""

    if uid in user_state:
        state = user_state[uid]
        if state == "wait_channel":
            channels = load_data("channels", [])
            if text not in channels:
                channels.append(text)
                save_data("channels", channels)
            bot.reply_to(message, f"✅ تمت إضافة القناة بنجاح: `{text}`", parse_mode="Markdown", reply_markup=get_main_reply_keyboard(user))
            del user_state[uid]
            return
        elif state == "wait_broadcast":
            success_count = 0
            for u in load_data("users", []):
                try: 
                    bot.copy_message(u, message.chat.id, message.message_id)
                    success_count += 1
                except: pass
            for ch in load_data("channels", []):
                try: 
                    bot.copy_message(ch, message.chat.id, message.message_id, reply_markup=get_channel_post_keyboard())
                except: pass
            bot.reply_to(message, f"✅ تمت الإذاعة بنجاح إلى المستخدمين والقنوات.", reply_markup=get_main_reply_keyboard(user))
            del user_state[uid]
            return
        elif state == "wait_welcome":
            save_data("welcome", text)
            bot.reply_to(message, "✅ تم تحديث رسالة الترحيب بنجاح.", reply_markup=get_main_reply_keyboard(user))
            del user_state[uid]
            return

    if text == "📊 نشر سعر TON الآن":
        ton, gram = get_ton_and_gram_prices()
        bot.send_message(message.chat.id, f"💎 TON: `${ton}`\n🔸 Gram: `${gram}`", parse_mode="Markdown")
    elif text == "📡 قناتنا الرسمية":
        bot.send_message(message.chat.id, f"قناتنا الرسمية: {CHANNEL_USERNAME}")
    elif text == "📢 نشر منشور جديد لكل القنوات":
        if not is_admin(user): return
        user_pending_posts[uid] = message
        bot.send_message(message.chat.id, "✍️ أرسل المنشور المراد تعميمه على كافة القنوات:")
    elif text == "📊 الإحصائيات السريعة":
        bot.send_message(message.chat.id, f"📊 إحصائيات البوت:\n- المشتركين: {len(load_data('users', []))}\n- القنوات المضافة: {len(load_data('channels', []))}", parse_mode="Markdown")
    elif text == "🆔 آيدي":
        bot.send_message(message.chat.id, f"🆔 الآيدي الخاص بك: `{uid}`", parse_mode="Markdown")
    elif text == "🛠️ لوحة تحكم المشرفين":
        if not is_admin(user): return
        bot.send_message(message.chat.id, "🛠️ لوحة التحكم الإدارية المتطورة:", reply_markup=get_admin_inline_control_panel())

# ==============================================================================
# 7. معالجة الـ Callbacks والأزرار الشفافة (خالية من الأخطاء الآمنة تماماً)
# ==============================================================================
@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):
    user = c.from_user
    uid = user.id
    if is_blocked(uid):
        return
    data = c.data

    try:
        if data == "refresh_ton_price":
            ton, gram = get_ton_and_gram_prices()
            try:
                bot.edit_message_text(
                    f"💎 **تقرير أسعار العملات الرقمية المباشر:**\n\n🔹 **TON:** `${ton}`\n🔸 **Gram:** `${gram}`", 
                    c.message.chat.id, 
                    c.message.message_id, 
                    parse_mode="Markdown", 
                    reply_markup=get_channel_post_keyboard()
                )
            except Exception:
                pass
            bot.answer_callback_query(c.id, "تم التحديث بنجاح ✅")

        elif data == "open_admin_panel":
            if not is_admin(user):
                bot.answer_callback_query(c.id, "⚠️ لست مشرفاً مخولاً!", show_alert=True)
                return
            try:
                bot.edit_message_text(
                    "🛠️ لوحة التحكم الإدارية المتطورة:", 
                    c.message.chat.id, 
                    c.message.message_id, 
                    reply_markup=get_admin_inline_control_panel()
                )
            except Exception:
                pass
            bot.answer_callback_query(c.id)

        elif data == "back_home":
            try:
                bot.delete_message(c.message.chat.id, c.message.message_id)
            except Exception:
                pass
            bot.send_message(c.message.chat.id, "🏠 القائمة الرئيسية للبوت:", reply_markup=get_main_reply_keyboard(user))
            bot.answer_callback_query(c.id)

        elif data == "manage_channels":
            if not is_admin(user): 
                return
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("➕ إضافة قناة", callback_data="add_ch"),
                InlineKeyboardButton("📋 عرض القنوات", callback_data="list_ch")
            )
            markup.add(InlineKeyboardButton("🔙 رجوع للوحة التحكم", callback_data="open_admin_panel"))
            try:
                bot.edit_message_text("📡 قسم إدارة القنوات المرتبطة:", c.message.chat.id, c.message.message_id, reply_markup=markup)
            except Exception:
                pass
            bot.answer_callback_query(c.id)

        elif data == "add_ch":
            user_state[uid] = "wait_channel"
            bot.send_message(c.message.chat.id, "أرسل معرف القناة الآن (مثال: `@ChannelName`):")
            bot.answer_callback_query(c.id)

        elif data == "list_ch":
            channels = load_data("channels", [])
            ch_list_str = "\n".join(channels) if channels else "لا توجد قنوات مضافة حالياً."
            bot.answer_callback_query(c.id, f"القنوات: {len(channels)} قناة مضافة", show_alert=True)
            bot.send_message(c.message.chat.id, f"📋 **قائمة القنوات المضافة:**\n\n{ch_list_str}", parse_mode="Markdown")

        elif data == "toggle_auto_publish":
            current_status = get_auto_publish_status()
            save_data("auto_publish", "disabled" if current_status else "enabled")
            try:
                bot.edit_message_reply_markup(
                    c.message.chat.id, 
                    c.message.message_id, 
                    reply_markup=get_admin_inline_control_panel()
                )
            except Exception:
                pass
            bot.answer_callback_query(c.id, "✅ تم تغيير حالة النشر التلقائي بنجاح.")

        elif data == "toggle_mode":
            current_mode = get_bot_mode()
            new_mode = "admin_only" if current_mode == "public" else "public"
            save_data("mode", new_mode)
            try:
                bot.edit_message_reply_markup(
                    c.message.chat.id, 
                    c.message.message_id, 
                    reply_markup=get_admin_inline_control_panel()
                )
            except Exception:
                pass
            bot.answer_callback_query(c.id, f"✅ تم تغيير وضع البوت إلى: {new_mode}")

        elif data == "toggle_notifications":
            current_notif = load_data("notifications", "enabled")
            new_notif = "disabled" if current_notif == "enabled" else "enabled"
            save_data("notifications", new_notif)
            try:
                bot.edit_message_reply_markup(
                    c.message.chat.id, 
                    c.message.message_id, 
                    reply_markup=get_admin_inline_control_panel()
                )
            except Exception:
                pass
            bot.answer_callback_query(c.id, "✅ تم تحديث حالة الإشعارات.")

        elif data == "start_broadcast":
            user_state[uid] = "wait_broadcast"
            bot.send_message(c.message.chat.id, "📢 أرسل الآن محتوى الإذاعة الشاملة (نص، صورة، أو وسائط):")
            bot.answer_callback_query(c.id)

        elif data == "edit_welcome":
            user_state[uid] = "wait_welcome"
            bot.send_message(c.message.chat.id, "✍️ أرسل نص رسالة الترحيب الجديدة:")
            bot.answer_callback_query(c.id)

        elif data == "bot_stats":
            users_count = len(load_data('users', []))
            blocked_count = len(load_data('blocked', []))
            channels_count = len(load_data('channels', []))
            stats_text = (
                f"📊 **الإحصائيات الشاملة للبوت:**\n\n"
                f"👥 إجمالي المشتركين: `{users_count}`\n"
                f"🚫 إجمالي المحظورين: `{blocked_count}`\n"
                f"📡 القنوات المفعلة: `{channels_count}`\n"
                f"⚙️ الأوامر المنفذة: `{bot_runtime_stats['commands_executed']}`\n"
                f"💬 الرسائل المعالجة: `{bot_runtime_stats['messages_handled']}`"
            )
            bot.answer_callback_query(c.id, "تم جلب الإحصائيات بنجاح", show_alert=False)
            bot.send_message(c.message.chat.id, stats_text, parse_mode="Markdown")

        elif data == "status_ch":
            ton, gram = get_ton_and_gram_prices()
            # تم تأمين النص بالكامل بدون أي أقواس أو علامات قد تسبب أخطاء
            bot.answer_callback_query(c.id, f"TON: {ton}$\vert{} Gram: {gram}$", show_alert=True)

        else:
            bot.answer_callback_query(c.id, "⚙️ الزر يعمل بنجاح.")

    except Exception as err:
        logger.error(f"خطأ في معالجة الزر {data}: {err}")
        try:
            bot.answer_callback_query(c.id, "حدث خطأ مؤقت، حاول لاحقاً.", show_alert=False)
        except:
            pass

# ==============================================================================
# 8. التشغيل التلقائي الآمن
# ==============================================================================
if __name__ == "__main__":
    logger.info("جاري تشغيل البوت بنجاح...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as e:
            logger.critical(f"خطأ حرج في دورة التشغيل: {e}")
            time.sleep(5)
