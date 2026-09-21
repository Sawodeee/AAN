import asyncio
import logging
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


# =========================================================
# الإعدادات
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

# هذه القناة حقوق فقط، ولن تتم الإضافة إليها أو النشر فيها
RIGHTS_CHANNEL = "@sn3nn"
OWNER_USERNAME = "@J_6_K"

DATABASE_FILE = Path("bot.sqlite3")
LOG_FILE = Path("bot.log")
JOB_NAME = "ton_price_publisher"

# أقل مدة مسموحة بين المنشورات
MIN_INTERVAL_SECONDS = 10

# CoinGecko وBinance كمصدرين احتياطيين
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
BINANCE_URL = "https://api.binance.com/api/v3/ticker/price?symbol=TONUSDT"


# =========================================================
# التسجيل في السجل
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("ton_bot")


# =========================================================
# قاعدة البيانات
# =========================================================

def db_connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def init_database() -> None:
    with closing(db_connect()) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS channels (
                chat_id TEXT PRIMARY KEY,
                title TEXT,
                added_at TEXT NOT NULL,
                last_success TEXT,
                last_error TEXT
            );
            """
        )

        defaults = {
            "interval": "180",
            "publishing": "0",
        }

        for key, value in defaults.items():
            connection.execute(
                """
                INSERT OR IGNORE INTO settings(key, value)
                VALUES (?, ?)
                """,
                (key, value),
            )

        connection.commit()


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with closing(db_connect()) as connection:
        row = connection.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()

    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with closing(db_connect()) as connection:
        connection.execute(
            """
            INSERT INTO settings(key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        connection.commit()


def get_interval() -> int:
    try:
        return max(int(get_setting("interval", "180")), MIN_INTERVAL_SECONDS)
    except ValueError:
        return 180


def is_publishing() -> bool:
    return get_setting("publishing", "0") == "1"


def get_channels() -> list[sqlite3.Row]:
    with closing(db_connect()) as connection:
        return connection.execute(
            """
            SELECT chat_id, title, added_at, last_success, last_error
            FROM channels
            ORDER BY added_at ASC
            """
        ).fetchall()


def get_channel(chat_id: str) -> Optional[sqlite3.Row]:
    with closing(db_connect()) as connection:
        return connection.execute(
            "SELECT * FROM channels WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()


def add_channel(chat_id: str, title: str) -> None:
    with closing(db_connect()) as connection:
        connection.execute(
            """
            INSERT INTO channels(chat_id, title, added_at)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title = excluded.title
            """,
            (
                chat_id,
                title,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        connection.commit()


def remove_channel(chat_id: str) -> None:
    with closing(db_connect()) as connection:
        connection.execute(
            "DELETE FROM channels WHERE chat_id = ?",
            (chat_id,),
        )
        connection.commit()


def update_channel_success(chat_id: str) -> None:
    with closing(db_connect()) as connection:
        connection.execute(
            """
            UPDATE channels
            SET last_success = ?, last_error = NULL
            WHERE chat_id = ?
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                chat_id,
            ),
        )
        connection.commit()


def update_channel_error(chat_id: str, error: str) -> None:
    with closing(db_connect()) as connection:
        connection.execute(
            """
            UPDATE channels
            SET last_error = ?
            WHERE chat_id = ?
            """,
            (error[:1000], chat_id),
        )
        connection.commit()


# =========================================================
# التحقق من المالك
# =========================================================

def is_admin(user_id: Optional[int]) -> bool:
    return bool(user_id and ADMIN_USER_ID and user_id == ADMIN_USER_ID)


async def require_admin(update: Update) -> bool:
    user = update.effective_user

    if is_admin(user.id if user else None):
        return True

    if update.callback_query:
        await update.callback_query.answer(
            "هذا الخيار متاح للمالك فقط.",
            show_alert=True,
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            "هذا البوت مخصص للمالك فقط."
        )

    return False


# =========================================================
# السعر
# =========================================================

async def get_ton_price_from_coingecko() -> float:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            COINGECKO_URL,
            params={
                "ids": "the-open-network",
                "vs_currencies": "usd",
            },
        )
        response.raise_for_status()
        data = response.json()

    price = data["the-open-network"]["usd"]
    return float(price)


async def get_ton_price_from_binance() -> float:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(BINANCE_URL)
        response.raise_for_status()
        data = response.json()

    return float(data["price"])


async def get_ton_price() -> float:
    errors = []

    for source in (
        get_ton_price_from_coingecko,
        get_ton_price_from_binance,
    ):
        try:
            price = await source()

            if price > 0:
                return price

        except Exception as error:
            errors.append(str(error))

    raise RuntimeError(
        "تعذر جلب سعر TON من جميع المصادر: "
        + " | ".join(errors)
    )


def format_price(price: float) -> str:
    return f"{price:,.4f}".rstrip("0").rstrip(".")


def build_post(price: float) -> str:
    return (
        f"💲 سعر TON بالدولار: {format_price(price)} $\n\n"
        f"$$$\n"
        f"____\n"
        f"channel: {RIGHTS_CHANNEL}\n"
        f"Owner: {OWNER_USERNAME}"
    )


# =========================================================
# الفاصل الزمني
# =========================================================

def parse_interval(value: str) -> Optional[int]:
    """
    الصيغ المدعومة:
    30ث
    3د
    2س
    1ي
    """

    value = value.strip().lower().replace(" ", "")

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)(ث|ثانية|ثواني|د|دقيقة|دقائق|س|ساعة|ساعات|ي|يوم|أيام)",
        value,
    )

    if not match:
        return None

    number = float(match.group(1))
    unit = match.group(2)

    if number <= 0:
        return None

    if unit in ("ث", "ثانية", "ثواني"):
        seconds = number
    elif unit in ("د", "دقيقة", "دقائق"):
        seconds = number * 60
    elif unit in ("س", "ساعة", "ساعات"):
        seconds = number * 60 * 60
    else:
        seconds = number * 60 * 60 * 24

    seconds = int(seconds)

    if seconds < MIN_INTERVAL_SECONDS:
        return None

    return seconds


def format_interval(seconds: int) -> str:
    if seconds % 86400 == 0:
        return f"{seconds // 86400}ي"

    if seconds % 3600 == 0:
        return f"{seconds // 3600}س"

    if seconds % 60 == 0:
        return f"{seconds // 60}د"

    return f"{seconds}ث"


# =========================================================
# لوحة التحكم
# =========================================================

def control_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "▶️ تشغيل النشر",
                    callback_data="publisher_start",
                ),
                InlineKeyboardButton(
                    "⏹ إيقاف النشر",
                    callback_data="publisher_stop",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⏱ تحديد الفاصل",
                    callback_data="set_interval",
                ),
            ],
            [
                InlineKeyboardButton(
                    "➕ إضافة قناة",
                    callback_data="add_channel",
                ),
                InlineKeyboardButton(
                    "➖ حذف قناة",
                    callback_data="remove_channel",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📋 قنوات النشر",
                    callback_data="list_channels",
                ),
                InlineKeyboardButton(
                    "📊 الحالة",
                    callback_data="status",
                ),
            ],
        ]
    )


def panel_text() -> str:
    channels = get_channels()
    state = "يعمل ✅" if is_publishing() else "متوقف ⛔"

    return (
        "🎛 لوحة التحكم\n\n"
        f"حالة النشر: {state}\n"
        f"الفاصل: {format_interval(get_interval())}\n"
        f"عدد قنوات النشر: {len(channels)}\n\n"
        f"ملاحظة: {RIGHTS_CHANNEL} حقوق فقط، "
        "ولن يتم النشر فيها."
    )


async def show_panel(update: Update) -> None:
    text = panel_text()

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=control_keyboard(),
        )
    else:
        await update.effective_message.reply_text(
            text,
            reply_markup=control_keyboard(),
        )


# =========================================================
# التحقق من القناة
# =========================================================

def normalize_channel(value: str) -> Optional[str]:
    value = value.strip()

    if value == RIGHTS_CHANNEL:
        return None

    if value.startswith("@") and len(value) > 1:
        return value

    if re.fullmatch(r"-100\d+", value):
        return value

    return None


async def verify_bot_can_publish(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: str,
) -> tuple[bool, str, str]:
    try:
        chat = await context.bot.get_chat(chat_id)

        member = await context.bot.get_chat_member(
            chat.id,
            context.bot.id,
        )

        if member.status not in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            return (
                False,
                "",
                "البوت ليس مشرفًا في القناة.",
            )

        if member.status == ChatMemberStatus.ADMINISTRATOR:
            can_post = getattr(member, "can_post_messages", True)

            if can_post is False:
                return (
                    False,
                    "",
                    "البوت مشرف، لكن لا يملك صلاحية نشر الرسائل.",
                )

        title = chat.title or str(chat.id)
        return True, title, ""

    except TelegramError as error:
        return False, "", str(error)


# =========================================================
# النشر
# =========================================================

def remove_publisher_jobs(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.job_queue:
        return

    for job in context.job_queue.get_jobs_by_name(JOB_NAME):
        job.schedule_removal()


def start_publisher_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    remove_publisher_jobs(context)

    if not is_publishing() or not get_channels():
        return

    context.job_queue.run_repeating(
        publish_job,
        interval=get_interval(),
        first=0,
        name=JOB_NAME,
    )


async def publish_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_publishing():
        return

    channels = get_channels()

    if not channels:
        logger.warning("لا توجد قنوات للنشر.")
        return

    try:
        price = await get_ton_price()
        message = build_post(price)

    except Exception as error:
        logger.exception("فشل جلب سعر TON: %s", error)
        return

    for channel in channels:
        chat_id = channel["chat_id"]

        if chat_id == RIGHTS_CHANNEL:
            continue

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                disable_web_page_preview=True,
            )

            update_channel_success(chat_id)
            logger.info("تم النشر في %s", chat_id)

        except TelegramError as error:
            update_channel_error(chat_id, str(error))
            logger.error(
                "فشل النشر في %s: %s",
                chat_id,
                error,
            )

        # تأخير بسيط حتى لا ترسل الطلبات كلها في اللحظة نفسها
        await asyncio.sleep(0.5)


# =========================================================
# الأوامر
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await require_admin(update):
        return

    await show_panel(update)


async def id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.effective_user:
        return

    await update.effective_message.reply_text(
        f"رقم حسابك هو:\n{update.effective_user.id}"
    )


# =========================================================
# الأزرار
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    await query.answer()

    if not await require_admin(update):
        return

    action = query.data

    if action == "publisher_start":
        if not get_channels():
            await query.edit_message_text(
                "❌ لا توجد قنوات للنشر.\n"
                "أضف قناة أولًا، واجعل البوت مشرفًا فيها.",
                reply_markup=control_keyboard(),
            )
            return

        set_setting("publishing", "1")
        start_publisher_job(context)

        await query.edit_message_text(
            "✅ تم تشغيل النشر التلقائي.\n"
            f"الفاصل الحالي: {format_interval(get_interval())}",
            reply_markup=control_keyboard(),
        )

    elif action == "publisher_stop":
        set_setting("publishing", "0")
        remove_publisher_jobs(context)

        await query.edit_message_text(
            "⛔ تم إيقاف النشر التلقائي.",
            reply_markup=control_keyboard(),
        )

    elif action == "set_interval":
        context.user_data["waiting_for"] = "interval"

        await query.edit_message_text(
            "أرسل الفاصل الزمني فقط، مثل:\n\n"
            "30ث = كل 30 ثانية\n"
            "3د = كل 3 دقائق\n"
            "2س = كل ساعتين\n"
            "1ي = كل يوم\n\n"
            f"أقل مدة مسموحة: {MIN_INTERVAL_SECONDS} ثوانٍ.",
            reply_markup=control_keyboard(),
        )

    elif action == "add_channel":
        context.user_data["waiting_for"] = "add_channel"

        await query.edit_message_text(
            "أرسل معرف القناة المراد النشر فيها.\n\n"
            "مثال لقناة عامة:\n"
            "@my_channel\n\n"
            "أو رقم قناة خاصة:\n"
            "-1001234567890\n\n"
            f"ممنوع إضافة {RIGHTS_CHANNEL}؛ "
            "لأنها حقوق فقط.",
            reply_markup=control_keyboard(),
        )

    elif action == "remove_channel":
        context.user_data["waiting_for"] = "remove_channel"

        await query.edit_message_text(
            "أرسل معرف القناة التي تريد حذفها من قائمة النشر.",
            reply_markup=control_keyboard(),
        )

    elif action == "list_channels":
        channels = get_channels()

        if not channels:
            text = "📋 لا توجد قنوات مضافة."
        else:
            lines = ["📋 قنوات النشر:\n"]

            for index, channel in enumerate(channels, start=1):
                title = channel["title"] or "بدون اسم"
                lines.append(
                    f"{index}. {title}\n"
                    f"   المعرف: {channel['chat_id']}"
                )

            text = "\n".join(lines)

        await query.edit_message_text(
            text,
            reply_markup=control_keyboard(),
        )

    elif action == "status":
        channels = get_channels()
        state = "يعمل ✅" if is_publishing() else "متوقف ⛔"

        lines = [
            "📊 حالة البوت\n",
            f"النشر: {state}",
            f"الفاصل: {format_interval(get_interval())}",
            f"عدد القنوات: {len(channels)}",
            f"حقوق النشر: {RIGHTS_CHANNEL}",
        ]

        for channel in channels:
            if channel["last_error"]:
                lines.append(
                    f"\n⚠️ {channel['chat_id']}\n"
                    f"آخر خطأ: {channel['last_error'][:300]}"
                )

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=control_keyboard(),
        )


# =========================================================
# استقبال رسائل المالك
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await require_admin(update):
        return

    waiting_for = context.user_data.get("waiting_for")

    if not waiting_for:
        return

    value = update.effective_message.text.strip()
    context.user_data.pop("waiting_for", None)

    if waiting_for == "interval":
        seconds = parse_interval(value)

        if seconds is None:
            await update.effective_message.reply_text(
                "❌ الصيغة غير صحيحة.\n\n"
                "أمثلة صحيحة:\n"
                "30ث\n"
                "3د\n"
                "2س\n"
                "1ي"
            )
            return

        set_setting("interval", str(seconds))

        if is_publishing():
            start_publisher_job(context)

        await update.effective_message.reply_text(
            f"✅ تم ضبط النشر كل {format_interval(seconds)}.",
            reply_markup=control_keyboard(),
        )

    elif waiting_for == "add_channel":
        chat_id = normalize_channel(value)

        if not chat_id:
            await update.effective_message.reply_text(
                f"❌ معرف القناة غير صحيح أو أنها {RIGHTS_CHANNEL}.\n\n"
                "استخدم:\n"
                "@channel_username\n"
                "أو:\n"
                "-1001234567890"
            )
            return

        if get_channel(chat_id):
            await update.effective_message.reply_text(
                "⚠️ هذه القناة مضافة مسبقًا.",
                reply_markup=control_keyboard(),
            )
            return

        valid, title, error = await verify_bot_can_publish(
            context,
            chat_id,
        )

        if not valid:
            await update.effective_message.reply_text(
                "❌ تعذر إضافة القناة.\n\n"
                f"السبب: {error}\n\n"
                "تأكد من أن البوت موجود في القناة "
                "ومشرف ويملك صلاحية نشر الرسائل."
            )
            return

        add_channel(chat_id, title)

        await update.effective_message.reply_text(
            f"✅ تمت إضافة القناة بنجاح:\n"
            f"{title}\n"
            f"{chat_id}",
            reply_markup=control_keyboard(),
        )

    elif waiting_for == "remove_channel":
        chat_id = normalize_channel(value)

        if not chat_id or not get_channel(chat_id):
            await update.effective_message.reply_text(
                "❌ هذه القناة غير موجودة في قائمة النشر."
            )
            return

        remove_channel(chat_id)

        if not get_channels():
            set_setting("publishing", "0")
            remove_publisher_jobs(context)

        await update.effective_message.reply_text(
            f"✅ تم حذف القناة:\n{chat_id}",
            reply_markup=control_keyboard(),
        )


# =========================================================
# بدء التطبيق
# =========================================================

async def post_init(application: Application) -> None:
    init_database()

    if is_publishing() and get_channels():
        start_publisher_job(application)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "ضع توكن البوت في المتغير BOT_TOKEN."
        )

    if ADMIN_USER_ID <= 0:
        raise RuntimeError(
            "ضع رقم حسابك في المتغير ADMIN_USER_ID."
        )

    init_database()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start_command)
    )
    application.add_handler(
        CommandHandler("id", id_command)
    )
    application.add_handler(
        CallbackQueryHandler(button_handler)
    )
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    logger.info("تم تشغيل البوت.")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
