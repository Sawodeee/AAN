import asyncio
import json
import os
import re
from pathlib import Path
from datetime import datetime

import httpx
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


# =========================
# الإعدادات
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "ضع_توكن_البوت_هنا")

# ضع رقم حسابك هنا، وليس اليوزر فقط.
# لمعرفة الرقم أرسل /id للبوت.
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

OWNER_USERNAME = "@J_6_K"
RIGHTS_CHANNEL = "@sn3nn"

DATA_FILE = Path("bot_data.json")
PUBLISH_JOB_NAME = "ton_price_publisher"

DEFAULT_INTERVAL = 180  # 3 دقائق


# =========================
# التخزين
# =========================

def default_data():
    return {
        "channels": [],
        "interval": DEFAULT_INTERVAL,
        "publishing": False,
    }


def load_data():
    if not DATA_FILE.exists():
        return default_data()

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        result = default_data()
        result.update(data)
        return result

    except Exception:
        return default_data()


def save_data(data):
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


DATA = load_data()


# =========================
# التحقق من الإدارة
# =========================

def is_admin(user_id: int) -> bool:
    return ADMIN_USER_ID != 0 and user_id == ADMIN_USER_ID


async def admin_only(update: Update) -> bool:
    user = update.effective_user

    if not user or not is_admin(user.id):
        if update.callback_query:
            await update.callback_query.answer(
                "غير مسموح لك باستخدام لوحة التحكم.",
                show_alert=True,
            )
        elif update.effective_message:
            await update.effective_message.reply_text(
                "هذا البوت مخصص للمالك فقط."
            )
        return False

    return True


# =========================
# جلب سعر TON
# =========================

async def get_ton_price() -> float:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "the-open-network",
        "vs_currencies": "usd",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        result = response.json()

    price = result["the-open-network"]["usd"]
    return float(price)


def format_price(price: float) -> str:
    return f"{price:,.4f}".rstrip("0").rstrip(".")


def build_post(price: float) -> str:
    current_time = datetime.now().strftime("%H:%M:%S")

    return (
        f"💲 سعر TON بالدولار: {format_price(price)} $\n\n"
        f"$$$\n"
        f"____\n"
        f"channel: {RIGHTS_CHANNEL}\n"
        f"Owner: {OWNER_USERNAME}"
    )


# =========================
# تحويل الفاصل الزمني
# =========================

def parse_interval(value: str):
    """
    أمثلة مقبولة:
    30ث = 30 ثانية
    3د  = 3 دقائق
    2س  = ساعتان
    1ي  = يوم واحد
    """

    value = value.strip().lower()
    value = value.replace(" ", "")

    match = re.fullmatch(r"(\d+(?:\.\d+)?)(ث|ثانية|د|دقيقة|س|ساعة|ي|يوم)", value)

    if not match:
        return None

    number = float(match.group(1))
    unit = match.group(2)

    if number <= 0:
        return None

    if unit in ("ث", "ثانية"):
        seconds = number
    elif unit in ("د", "دقيقة"):
        seconds = number * 60
    elif unit in ("س", "ساعة"):
        seconds = number * 60 * 60
    else:
        seconds = number * 60 * 60 * 24

    # حماية من الفواصل الصغيرة جدًا
    if seconds < 10:
        return None

    return int(seconds)


def interval_text(seconds: int) -> str:
    if seconds % 86400 == 0:
        return f"{seconds // 86400}ي"

    if seconds % 3600 == 0:
        return f"{seconds // 3600}س"

    if seconds % 60 == 0:
        return f"{seconds // 60}د"

    return f"{seconds}ث"


# =========================
# لوحة التحكم
# =========================

def main_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("▶️ تشغيل النشر", callback_data="start"),
                InlineKeyboardButton("⏹ إيقاف النشر", callback_data="stop"),
            ],
            [
                InlineKeyboardButton("⏱ تحديد الفاصل", callback_data="interval"),
            ],
            [
                InlineKeyboardButton("➕ إضافة قناة", callback_data="add_channel"),
                InlineKeyboardButton("➖ حذف قناة", callback_data="remove_channel"),
            ],
            [
                InlineKeyboardButton("📋 قنوات النشر", callback_data="list_channels"),
            ],
            [
                InlineKeyboardButton("📊 الحالة", callback_data="status"),
            ],
        ]
    )


async def send_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "لوحة التحكم\n\n"
        f"حالة النشر: {'يعمل ✅' if DATA['publishing'] else 'متوقف ⛔'}\n"
        f"الفاصل: {interval_text(DATA['interval'])}\n"
        f"عدد القنوات: {len(DATA['channels'])}\n\n"
        "ملاحظة: @sn3nn حقوق نشر فقط، ولن يتم النشر فيها."
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=main_keyboard(),
        )
    else:
        await update.effective_message.reply_text(
            text,
            reply_markup=main_keyboard(),
        )


# =========================
# أوامر البوت
# =========================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return

    await send_panel(update, context)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    await update.effective_message.reply_text(
        f"رقم حسابك هو:\n{user.id}"
    )


# =========================
# التعامل مع الأزرار
# =========================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await admin_only(update):
        return

    action = query.data

    if action == "start":
        if not DATA["channels"]:
            await query.edit_message_text(
                "لا توجد قنوات للنشر.\n"
                "أضف قناة أولًا، ثم اجعل البوت مشرفًا فيها.",
                reply_markup=main_keyboard(),
            )
            return

        DATA["publishing"] = True
        save_data(DATA)

        await restart_publisher(context)

        await query.edit_message_text(
            "✅ تم تشغيل النشر التلقائي.",
            reply_markup=main_keyboard(),
        )

    elif action == "stop":
        DATA["publishing"] = False
        save_data(DATA)

        stop_publisher(context)

        await query.edit_message_text(
            "⛔ تم إيقاف النشر التلقائي.",
            reply_markup=main_keyboard(),
        )

    elif action == "interval":
        context.user_data["awaiting"] = "interval"

        await query.edit_message_text(
            "أرسل الفاصل الزمني، مثل:\n\n"
            "3د = كل 3 دقائق\n"
            "30ث = كل 30 ثانية\n"
            "2س = كل ساعتين\n"
            "1ي = كل يوم",
            reply_markup=main_keyboard(),
        )

    elif action == "add_channel":
        context.user_data["awaiting"] = "add_channel"

        await query.edit_message_text(
            "أرسل معرف القناة المراد النشر فيها.\n\n"
            "مثال:\n"
            "@my_channel\n\n"
            "أو أرسل رقم القناة الخاصة مثل:\n"
            "-1001234567890\n\n"
            "لا ترسل @sn3nn لأنها حقوق نشر فقط.",
            reply_markup=main_keyboard(),
        )

    elif action == "remove_channel":
        context.user_data["awaiting"] = "remove_channel"

        await query.edit_message_text(
            "أرسل معرف القناة المراد حذفها من قائمة النشر.",
            reply_markup=main_keyboard(),
        )

    elif action == "list_channels":
        channels = DATA["channels"]

        if not channels:
            text = "لا توجد قنوات مضافة حاليًا."
        else:
            lines = ["📋 قنوات النشر:\n"]

            for index, channel in enumerate(channels, start=1):
                lines.append(f"{index}. {channel}")

            text = "\n".join(lines)

        await query.edit_message_text(
            text,
            reply_markup=main_keyboard(),
        )

    elif action == "status":
        status = "يعمل ✅" if DATA["publishing"] else "متوقف ⛔"

        text = (
            "📊 حالة البوت\n\n"
            f"النشر: {status}\n"
            f"الفاصل: {interval_text(DATA['interval'])}\n"
            f"عدد القنوات: {len(DATA['channels'])}\n"
            f"القناة المستثناة: {RIGHTS_CHANNEL}\n"
        )

        await query.edit_message_text(
            text,
            reply_markup=main_keyboard(),
        )


# =========================
# استقبال إدخالات الإدارة
# =========================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return

    awaiting = context.user_data.get("awaiting")

    if not awaiting:
        return

    value = update.effective_message.text.strip()
    context.user_data.pop("awaiting", None)

    if awaiting == "interval":
        seconds = parse_interval(value)

        if seconds is None:
            await update.effective_message.reply_text(
                "صيغة غير صحيحة.\n\n"
                "استخدم مثلًا:\n"
                "3د أو 30ث أو 2س أو 1ي\n"
                "وأقل مدة مسموحة 10 ثوانٍ."
            )
            return

        DATA["interval"] = seconds
        save_data(DATA)

        if DATA["publishing"]:
            await restart_publisher(context)

        await update.effective_message.reply_text(
            f"✅ تم ضبط النشر كل {interval_text(seconds)}.",
            reply_markup=main_keyboard(),
        )

    elif awaiting == "add_channel":
        channel = value

        if channel == RIGHTS_CHANNEL or channel.lstrip("-").isdigit() and channel == RIGHTS_CHANNEL:
            await update.effective_message.reply_text(
                "❌ لا يمكن إضافة @sn3nn للنشر؛ هذه القناة مخصصة للحقوق فقط."
            )
            return

        if not channel.startswith("@") and not channel.lstrip("-").isdigit():
            await update.effective_message.reply_text(
                "❌ معرف القناة غير صحيح.\n"
                "استخدم @channel أو رقم يبدأ بـ -100."
            )
            return

        if channel in DATA["channels"]:
            await update.effective_message.reply_text(
                "القناة مضافة مسبقًا."
            )
            return

        DATA["channels"].append(channel)
        save_data(DATA)

        await update.effective_message.reply_text(
            f"✅ تمت إضافة القناة:\n{channel}\n\n"
            "تأكد من إضافة البوت مشرفًا مع صلاحية نشر الرسائل.",
            reply_markup=main_keyboard(),
        )

    elif awaiting == "remove_channel":
        channel = value

        if channel not in DATA["channels"]:
            await update.effective_message.reply_text(
                "القناة غير موجودة في قائمة النشر."
            )
            return

        DATA["channels"].remove(channel)
        save_data(DATA)

        await update.effective_message.reply_text(
            f"✅ تم حذف القناة:\n{channel}",
            reply_markup=main_keyboard(),
        )


# =========================
# النشر
# =========================

async def publish_to_channels(context: ContextTypes.DEFAULT_TYPE):
    if not DATA["publishing"]:
        return

    if not DATA["channels"]:
        return

    try:
        price = await get_ton_price()
        message = build_post(price)
    except Exception as error:
        print(f"خطأ في جلب سعر TON: {error}")
        return

    failed_channels = []

    for channel in list(DATA["channels"]):
        # حماية إضافية حتى لا يتم النشر في قناة الحقوق
        if channel == RIGHTS_CHANNEL:
            continue

        try:
            await context.bot.send_message(
                chat_id=channel,
                text=message,
            )

            print(f"تم النشر في {channel}")

        except Exception as error:
            print(f"فشل النشر في {channel}: {error}")
            failed_channels.append(channel)

    if failed_channels:
        print(
            "تأكد من أن البوت مشرف في القنوات التالية "
            "ولديه صلاحية نشر الرسائل:"
        )
        print(failed_channels)


def stop_publisher(context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name(PUBLISH_JOB_NAME)

    for job in jobs:
        job.schedule_removal()


async def restart_publisher(context: ContextTypes.DEFAULT_TYPE):
    stop_publisher(context)

    if not DATA["publishing"]:
        return

    context.job_queue.run_repeating(
        publish_to_channels,
        interval=DATA["interval"],
        first=0,
        name=PUBLISH_JOB_NAME,
    )


async def post_init(application: Application):
    if DATA["publishing"] and DATA["channels"]:
        await restart_publisher(application)


# =========================
# التشغيل
# =========================

def main():
    if BOT_TOKEN == "ضع_توكن_البوت_هنا":
        raise RuntimeError(
            "ضع توكن البوت داخل متغير BOT_TOKEN قبل التشغيل."
        )

    if ADMIN_USER_ID == 0:
        raise RuntimeError(
            "ضع رقم حسابك داخل ADMIN_USER_ID قبل التشغيل."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    print("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()
