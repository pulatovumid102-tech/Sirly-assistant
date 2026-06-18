import logging
import httpx
from datetime import datetime, timezone
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


# ===== Asosiy =====
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(contact_response_callback, pattern=r"^cr_(yes|no)_\d+$"))

    if application.job_queue:
        application.job_queue.run_repeating(check_contact_requests, interval=15, first=5)
        application.job_queue.run_repeating(check_scheduled_books, interval=15, first=8)
    else:
        logger.warning(
            "job_queue mavjud emas. Terminalda quyidagini ishga tushiring: "
            'pip install "python-telegram-bot[job-queue]"'
        )

    logger.info("Bot ishga tushdi.")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
