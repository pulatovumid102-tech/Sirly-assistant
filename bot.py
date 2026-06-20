import logging
import calendar
import httpx
from datetime import datetime, timezone, time as dt_time, date as dt_date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ===== Sozlamalar =====
TOKEN = "8935324683:AAFrVn1gszbbU5il0Us5dsMHWLLIHNHlVgw"
CHAT_ID = -1003914304171

SB_URL = "https://ubakgpkcemlchpfejmke.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InViYWtncGtjZW1sY2hwZmVqbWtlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzMjc3NzUsImV4cCI6MjA5NTkwMzc3NX0.wkKSmoTB9RwREFjcJfe0dNBzZDEw2DHxNM3G6erHSJU"
SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# Mini App manzili
WEBAPP_URL = "https://sirly-assistant-production.up.railway.app"


# ===== Buyruqlar =====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📚 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))]]
    )
    await update.message.reply_text(
        "Salom! \"Bir bet\" ilovasiga xush kelibsiz 📖\n\n"
        "Ilovani ochish uchun pastdagi tugmani bosing.",
        reply_markup=keyboard,
    )


# ===== Kontakt so'rovlarini tekshirish (fon vazifasi) =====
async def check_contact_requests(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/contact_requests",
                headers=SB_HEADERS,
                params={"status": "eq.pending", "select": "*"},
            )
            rows = r.json()
            for row in rows:
                try:
                    kb = InlineKeyboardMarkup([[
                        InlineKeyboardButton("✅ Ha", callback_data=f"cr_yes_{row['id']}"),
                        InlineKeyboardButton("❌ Yo'q", callback_data=f"cr_no_{row['id']}"),
                    ]])
                    await context.bot.send_message(
                        chat_id=row["target_id"],
                        text=(
                            f"👤 {row['requester_name']} siz bilan bog'lanishni so'rayapti.\n\n"
                            "Profilingizni unga ulashishga roziman?"
                        ),
                        reply_markup=kb,
                    )
                    await client.patch(
                        f"{SB_URL}/rest/v1/contact_requests",
                        headers=SB_HEADERS,
                        params={"id": f"eq.{row['id']}"},
                        json={"status": "sent"},
                    )
                except Exception as e:
                    logger.error(f"Kontakt so'rovi yuborilmadi (id={row.get('id')}): {e}")
                    await client.patch(
                        f"{SB_URL}/rest/v1/contact_requests",
                        headers=SB_HEADERS,
                        params={"id": f"eq.{row['id']}"},
                        json={"status": "failed"},
                    )
    except Exception as e:
        logger.error(f"check_contact_requests xato: {e}")


async def contact_response_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    if len(parts) != 3:
        return
    _, action, req_id = parts
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{SB_URL}/rest/v1/contact_requests",
            headers=SB_HEADERS,
            params={"id": f"eq.{req_id}", "select": "*"},
        )
        rows = r.json()
        if not rows:
            return
        row = rows[0]
        now_iso = datetime.now(timezone.utc).isoformat()
        if action == "yes":
            await client.patch(
                f"{SB_URL}/rest/v1/contact_requests",
                headers=SB_HEADERS,
                params={"id": f"eq.{req_id}"},
                json={"status": "agreed", "responded_at": now_iso},
            )
            username = query.from_user.username
            contact_line = f"@{username}" if username else f"tg://user?id={row['target_id']}"
            try:
                await query.edit_message_text("✅ Rozilik berdingiz. Profilingiz ulashildi.")
            except Exception:
                pass
            try:
                await context.bot.send_message(
                    chat_id=row["requester_id"],
                    text=f"🎉 {row['target_name']} so'rovingizga rozi bo'ldi!\n\nBog'lanish: {contact_line}",
                )
            except Exception as e:
                logger.error(f"Requesterga xabar yuborilmadi: {e}")
        else:
            await client.patch(
                f"{SB_URL}/rest/v1/contact_requests",
                headers=SB_HEADERS,
                params={"id": f"eq.{req_id}"},
                json={"status": "declined", "responded_at": now_iso},
            )
            try:
                await query.edit_message_text("Rad etdingiz.")
            except Exception:
                pass


# ===== Kogort (guruh) sikli hisoblash =====
COHORT_SIGNUP_DAYS = 5
COHORT_READING_DAYS = 20
COHORT_CLOSING_DAYS = 5


COHORT_SUGGESTED_DAILY_PAGES = 20


def book_reading_days(total_pages):
    if not total_pages or total_pages <= 0:
        return COHORT_READING_DAYS
    return max(1, -(-total_pages // COHORT_SUGGESTED_DAILY_PAGES))


def month_cohort_markers(year: int, month: int):
    days_in_month = calendar.monthrange(year, month)[1]
    days = [5, 10, 15, 20, 25, min(30, days_in_month)]
    return [dt_date(year, month, d) for d in days]


def nearby_cohort_markers(today: dt_date):
    markers = set()
    for offset in range(-2, 2):
        y = today.year
        m = today.month + offset
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        markers.update(month_cohort_markers(y, m))
    return sorted(markers)


def cohort_phase(marker: dt_date, today: dt_date, reading_days: int = None):
    reading_days = reading_days or COHORT_READING_DAYS
    diff = (today - marker).days
    if diff < 0:
        return None
    if diff < COHORT_SIGNUP_DAYS:
        return "signup"
    if diff < COHORT_SIGNUP_DAYS + reading_days:
        return "reading"
    if diff < COHORT_SIGNUP_DAYS + reading_days + COHORT_CLOSING_DAYS:
        return "closing"
    return "ended"


def parse_date_str(s: str) -> dt_date:
    return dt_date.fromisoformat(s)


async def check_rank_drops(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            books_r = await client.get(
                f"{SB_URL}/rest/v1/books",
                headers=SB_HEADERS,
                params={"select": "id,title,total_pages"},
            )
            books = {b["id"]: b for b in books_r.json()}
            today = datetime.now(timezone.utc).date()

            prog_r = await client.get(
                f"{SB_URL}/rest/v1/progress",
                headers=SB_HEADERS,
                params={
                    "select": "book_id,user_id,pages_read,cohort_start_date",
                    "cohort_start_date": "not.is.null",
                    "order": "pages_read.desc",
                },
            )
            all_progress = prog_r.json()

            groups = {}
            for p in all_progress:
                key = (p["book_id"], p["cohort_start_date"])
                groups.setdefault(key, []).append(p)

            for (book_id, cohort_str), members in groups.items():
                marker = parse_date_str(cohort_str)
                book = books.get(book_id)
                if not book:
                    continue
                reading_days = book_reading_days(book.get("total_pages"))
                phase = cohort_phase(marker, today, reading_days)
                if phase not in ("reading", "closing"):
                    continue

                tracker_r = await client.get(
                    f"{SB_URL}/rest/v1/rank_tracker",
                    headers=SB_HEADERS,
                    params={
                        "book_id": f"eq.{book_id}",
                        "cohort_start_date": f"eq.{cohort_str}",
                        "select": "user_id,last_rank",
                    },
                )
                tracker_map = {row["user_id"]: row["last_rank"] for row in tracker_r.json()}

                for idx, p in enumerate(members):
                    current_rank = idx + 1
                    uid = p["user_id"]
                    prev_rank = tracker_map.get(uid)
                    if prev_rank is not None and current_rank > prev_rank:
                        try:
                            await context.bot.send_message(
                                chat_id=uid,
                                text=f"📉 \"{book['title']}\" guruhida darajangiz pastladi: endi {current_rank}-o'rindasiz.",
                            )
                        except Exception as e:
                            logger.error(f"Daraja xabari yuborilmadi (user_id={uid}): {e}")
                    try:
                        await client.post(
                            f"{SB_URL}/rest/v1/rank_tracker?on_conflict=book_id,user_id,cohort_start_date",
                            headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
                            json={
                                "book_id": book_id,
                                "user_id": uid,
                                "cohort_start_date": cohort_str,
                                "last_rank": current_rank,
                            },
                        )
                    except Exception as e:
                        logger.error(f"rank_tracker yangilanmadi (book_id={book_id}, user_id={uid}): {e}")
    except Exception as e:
        logger.error(f"check_rank_drops xato: {e}")


async def get_all_user_ids(client):
    user_ids = set()
    for table in ("progress", "comments", "finishers"):
        r = await client.get(
            f"{SB_URL}/rest/v1/{table}",
            headers=SB_HEADERS,
            params={"select": "user_id"},
        )
        for row in r.json():
            uid = row.get("user_id")
            if uid:
                user_ids.add(uid)
    return user_ids


async def send_daily_motivation(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            user_ids = await get_all_user_ids(client)
            text = (
                "Bugun vaqt topib 1 bet bo'lsa ham kitob o'qing, shoshmasdan tushunib o'qing "
                "va o'qiganingizni boshqaga tushuntirib bera oling.\n\n"
                "O'zingizdan faxrlaning, siz kechagidan kuchliroq, aqlliroq siz."
            )
            for uid in user_ids:
                try:
                    await context.bot.send_message(chat_id=uid, text=text)
                except Exception as e:
                    logger.error(f"Motivatsiya xabari yuborilmadi (user_id={uid}): {e}")
    except Exception as e:
        logger.error(f"send_daily_motivation xato: {e}")


# ===== Asosiy =====
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(contact_response_callback, pattern=r"^cr_(yes|no)_\d+$"))

    if application.job_queue:
        application.job_queue.run_repeating(check_contact_requests, interval=15, first=5)
        application.job_queue.run_repeating(check_rank_drops, interval=30, first=12)
        application.job_queue.run_daily(
            send_daily_motivation,
            time=dt_time(5, 0, 0, tzinfo=timezone.utc),
        )
    else:
        logger.warning(
            "job_queue mavjud emas. Terminalda quyidagini ishga tushiring: "
            'pip install "python-telegram-bot[job-queue]"'
        )

    logger.info("Bot ishga tushdi.")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
