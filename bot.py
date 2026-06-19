import logging
import httpx
from datetime import datetime, timezone, time as dt_time
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

# Mini App manzili (deploy qilganingizdan keyin shu yerga qo'ying)
WEBAPP_URL = "https://example.com"


# ===== Buyruqlar =====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📚 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))]]
    )
    await update.message.reply_text(
        "Salom! Kitob o'qish klubiga xush kelibsiz 📖\n\n"
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


# ===== Rejalashtirilgan kitoblar haqida guruhga e'lon =====
async def check_scheduled_books(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/books",
                headers=SB_HEADERS,
                params={"start_date": "not.is.null", "announced": "eq.false", "select": "*"},
            )
            rows = r.json()
            for b in rows:
                try:
                    text = f"📖 Yangi o'qish boshlanadi!\n\n<b>{b['title']}</b>"
                    if b.get("author"):
                        text += f"\n✍️ {b['author']}"
                    text += f"\n📅 Boshlanish sanasi: {b['start_date']}"
                    if b.get("purchase_link"):
                        text += f"\n🛒 Sotib olish: {b['purchase_link']}"
                    text += "\n\nQo'shilish uchun ilovaga o'ting 👇"
                    await context.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
                    await client.patch(
                        f"{SB_URL}/rest/v1/books",
                        headers=SB_HEADERS,
                        params={"id": f"eq.{b['id']}"},
                        json={"announced": True},
                    )
                except Exception as e:
                    logger.error(f"E'lon yuborilmadi (book_id={b.get('id')}): {e}")
    except Exception as e:
        logger.error(f"check_scheduled_books xato: {e}")


async def check_rank_drops(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            books_r = await client.get(
                f"{SB_URL}/rest/v1/books",
                headers=SB_HEADERS,
                params={"select": "id,title,start_date"},
            )
            books = books_r.json()
            today_str = datetime.now(timezone.utc).date().isoformat()
            for b in books:
                start_date = b.get("start_date")
                if start_date and start_date > today_str:
                    continue
                prog_r = await client.get(
                    f"{SB_URL}/rest/v1/progress",
                    headers=SB_HEADERS,
                    params={
                        "book_id": f"eq.{b['id']}",
                        "select": "user_id,pages_read",
                        "order": "pages_read.desc",
                    },
                )
                progress = prog_r.json()
                if not progress:
                    continue
                tracker_r = await client.get(
                    f"{SB_URL}/rest/v1/rank_tracker",
                    headers=SB_HEADERS,
                    params={"book_id": f"eq.{b['id']}", "select": "user_id,last_rank"},
                )
                tracker_map = {row["user_id"]: row["last_rank"] for row in tracker_r.json()}
                for idx, p in enumerate(progress):
                    current_rank = idx + 1
                    uid = p["user_id"]
                    prev_rank = tracker_map.get(uid)
                    if prev_rank is not None and current_rank > prev_rank:
                        try:
                            await context.bot.send_message(
                                chat_id=uid,
                                text=f"📉 \"{b['title']}\" kitobida darajangiz pastladi: endi {current_rank}-o'rindasiz.",
                            )
                        except Exception as e:
                            logger.error(f"Daraja xabari yuborilmadi (user_id={uid}): {e}")
                    try:
                        await client.post(
                            f"{SB_URL}/rest/v1/rank_tracker?on_conflict=book_id,user_id",
                            headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
                            json={"book_id": b["id"], "user_id": uid, "last_rank": current_rank},
                        )
                    except Exception as e:
                        logger.error(f"rank_tracker yangilanmadi (book_id={b['id']}, user_id={uid}): {e}")
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


async def send_daily_limit_reset(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            user_ids = await get_all_user_ids(client)
            text = (
                "🌅 Yangi kun boshlandi!\n\n"
                "Kunlik o'qish limitlaringiz yangilandi — endi yana kitob o'qishingiz mumkin. Omad!"
            )
            for uid in user_ids:
                try:
                    await context.bot.send_message(chat_id=uid, text=text)
                except Exception as e:
                    logger.error(f"Limit xabari yuborilmadi (user_id={uid}): {e}")
    except Exception as e:
        logger.error(f"send_daily_limit_reset xato: {e}")


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
        application.job_queue.run_repeating(check_scheduled_books, interval=15, first=8)
        application.job_queue.run_repeating(check_rank_drops, interval=30, first=12)
        application.job_queue.run_daily(
            send_daily_limit_reset,
            time=dt_time(19, 0, 1, tzinfo=timezone.utc),
        )
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
