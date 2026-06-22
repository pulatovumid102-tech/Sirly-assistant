import logging
import calendar
import os
import threading
import http.server
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
import httpx

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ===== Sozlamalar =====
TOKEN = "8500527121:AAF_Z3rqt9ZxbrygkI_DQMgitoO3WzTj5Ss"
CHAT_ID = -1003914304171
CHANNEL_IDS = [-1004451061109, -1001644206432]

SB_URL = "https://ubakgpkcemlchpfejmke.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InViYWtncGtjZW1sY2hwZmVqbWtlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzMjc3NzUsImV4cCI6MjA5NTkwMzc3NX0.wkKSmoTB9RwREFjcJfe0dNBzZDEw2DHxNM3G6erHSJU"
SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# Mini App manzili
WEBAPP_URL = "https://pulatovumid102-tech.github.io/Sirly-assistant/"
BOT_USERNAME = "atigabirbet_bot"


# ===== Buyruqlar =====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! \"Neyra\" ilovasiga xush kelibsiz 📖\n\n"
        "Ilovani ochish uchun Menu tugmasini bosing."
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
    days = [1, 5, 10, 15, 20, 25]
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


def previous_cohort_marker(marker: dt_date):
    all_markers = []
    for offset in (-1, 0):
        y = marker.year
        m = marker.month + offset
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        all_markers.extend(month_cohort_markers(y, m))
    all_markers.sort()
    idx = all_markers.index(marker) if marker in all_markers else -1
    return all_markers[idx - 1] if idx > 0 else None


def cohort_phase(marker: dt_date, today: dt_date, reading_days: int = None):
    reading_days = reading_days or COHORT_READING_DAYS
    diff = (today - marker).days
    prev_marker = previous_cohort_marker(marker)
    signup_days = (marker - prev_marker).days if prev_marker else COHORT_SIGNUP_DAYS
    if diff < -signup_days:
        return None
    if diff < 0:
        return "signup"
    if diff < reading_days:
        return "reading"
    if diff < reading_days + COHORT_CLOSING_DAYS:
        return "closing"
    return "ended"


def parse_date_str(s: str) -> dt_date:
    return dt_date.fromisoformat(s)


async def check_rank_drops(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            today = datetime.now(timezone.utc).date()

            # ===== KITOB REYTINGI =====
            books_r = await client.get(
                f"{SB_URL}/rest/v1/books",
                headers=SB_HEADERS,
                params={"select": "id,title,total_pages"},
            )
            books = {b["id"]: b for b in books_r.json()}

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
                key = (p["book_id"], str(p["cohort_start_date"])[:10])
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
                    if prev_rank is not None and current_rank != prev_rank:
                        arrow = "📈" if current_rank < prev_rank else "📉"
                        direction = "ko'tarildingiz" if current_rank < prev_rank else "tushdingiz"
                        try:
                            await context.bot.send_message(
                                chat_id=uid,
                                text=f"{arrow} \"{book['title']}\" guruhida o'riningiz o'zgardi: endi {current_rank}-o'rindasiz.",
                            )
                        except Exception as e:
                            logger.error(f"Kitob rank xabari yuborilmadi (user_id={uid}): {e}")
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

            # ===== SPORT REYTINGI =====
            sdl_r = await client.get(
                f"{SB_URL}/rest/v1/sport_daily_logs",
                headers=SB_HEADERS,
                params={"select": "challenge_id,user_id,count_done,cohort_start_date"},
            )
            sport_logs = sdl_r.json()
            sport_groups = {}
            for l in sport_logs:
                key = (l["challenge_id"], str(l["cohort_start_date"])[:10])
                sport_groups.setdefault(key, {})
                uid = l["user_id"]
                sport_groups[key][uid] = sport_groups[key].get(uid, 0) + l["count_done"]

            ch_r = await client.get(
                f"{SB_URL}/rest/v1/sport_challenges",
                headers=SB_HEADERS,
                params={"select": "id,title,duration_days"},
            )
            challenges = {c["id"]: c for c in ch_r.json()}

            for (ch_id, cohort_str), user_totals in sport_groups.items():
                marker = parse_date_str(cohort_str)
                ch = challenges.get(ch_id)
                if not ch:
                    continue
                phase = cohort_phase(marker, today, ch.get("duration_days", 5))
                if phase not in ("reading", "closing"):
                    continue

                sorted_users = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)

                sport_tracker_r = await client.get(
                    f"{SB_URL}/rest/v1/rank_tracker",
                    headers=SB_HEADERS,
                    params={
                        "challenge_id": f"eq.{ch_id}",
                        "cohort_start_date": f"eq.{cohort_str}",
                        "select": "user_id,last_rank",
                    },
                )
                sport_tracker_map = {row["user_id"]: row["last_rank"] for row in sport_tracker_r.json()}

                for idx, (uid, total) in enumerate(sorted_users):
                    current_rank = idx + 1
                    prev_rank = sport_tracker_map.get(uid)
                    if prev_rank is not None and current_rank != prev_rank:
                        arrow = "📈" if current_rank < prev_rank else "📉"
                        try:
                            await context.bot.send_message(
                                chat_id=uid,
                                text=f"{arrow} \"{ch['title']}\" sport guruhida o'riningiz o'zgardi: endi {current_rank}-o'rindasiz.",
                            )
                        except Exception as e:
                            logger.error(f"Sport rank xabari yuborilmadi (user_id={uid}): {e}")
                    try:
                        await client.post(
                            f"{SB_URL}/rest/v1/rank_tracker?on_conflict=challenge_id,user_id,cohort_start_date",
                            headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
                            json={
                                "challenge_id": ch_id,
                                "user_id": uid,
                                "cohort_start_date": cohort_str,
                                "last_rank": current_rank,
                            },
                        )
                    except Exception as e:
                        logger.error(f"sport rank_tracker yangilanmadi (ch_id={ch_id}, user_id={uid}): {e}")

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


async def check_join_notifications(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/join_notifications",
                headers=SB_HEADERS,
                params={"sent": "eq.false", "select": "*", "order": "created_at.asc"},
            )
            rows = r.json()
            for row in rows:
                try:
                    book_r = await client.get(
                        f"{SB_URL}/rest/v1/books",
                        headers=SB_HEADERS,
                        params={"id": f"eq.{row['book_id']}", "select": "title"},
                    )
                    book_rows = book_r.json()
                    title = book_rows[0]["title"] if book_rows else "Kitob"

                    count_r = await client.get(
                        f"{SB_URL}/rest/v1/progress",
                        headers=SB_HEADERS,
                        params={
                            "book_id": f"eq.{row['book_id']}",
                            "cohort_start_date": f"eq.{row['cohort_start_date']}",
                            "select": "user_id",
                        },
                    )
                    total = len(count_r.json())

                    text = (
                        f"📈 {row['cohort_start_date']}da boshlanadigan \"{title}\" o'qish "
                        f"challenjiga yana 1 kishi qo'shildi, jami {total} kishi."
                    )
                    await context.bot.send_message(chat_id=row["creator_id"], text=text)
                except Exception as e:
                    logger.error(f"Qo'shilish xabari yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/join_notifications",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"sent": True},
                        )
                    except Exception as e:
                        logger.error(f"join_notifications belgilanmadi (id={row.get('id')}): {e}")
    except Exception as e:
        logger.error(f"check_join_notifications xato: {e}")


async def check_join_confirmations(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/join_confirmations",
                headers=SB_HEADERS,
                params={"sent": "eq.false", "select": "*", "order": "created_at.asc"},
            )
            for row in r.json():
                try:
                    share_link = f"https://t.me/{BOT_USERNAME}/app?startapp=book_{row['book_id']}"
                    text = (
                        f"✅ {row['cohort_start_date']}da boshlanadigan \"{row['book_title']}\" "
                        f"challenjiga qo'shildingiz!\n\n"
                        f"Do'stlaringizni ham taklif qiling, ulashish uchun havola:\n{share_link}"
                    )
                    await context.bot.send_message(chat_id=row["user_id"], text=text)
                except Exception as e:
                    logger.error(f"Qo'shilish tasdiqlash xabari yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/join_confirmations",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"sent": True},
                        )
                    except Exception as e:
                        logger.error(f"join_confirmations belgilanmadi (id={row.get('id')}): {e}")
    except Exception as e:
        logger.error(f"check_join_confirmations xato: {e}")


async def check_payment_notifications(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            pr = await client.get(
                f"{SB_URL}/rest/v1/qovun_purchase_requests",
                headers=SB_HEADERS,
                params={"status": "neq.pending", "notified": "eq.false", "select": "*"},
            )
            for row in pr.json():
                try:
                    if row["status"] == "approved":
                        text = f"✅ {row['qovun_amount']} ta qovun sotib olish so'rovingiz tasdiqlandi va hisobingizga qo'shildi."
                    else:
                        reason = row.get("reject_reason") or "sabab ko'rsatilmagan"
                        text = f"❌ {row['qovun_amount']} ta qovun sotib olish so'rovingiz rad etildi. Sabab: {reason}"
                    await context.bot.send_message(chat_id=row["user_id"], text=text)
                except Exception as e:
                    logger.error(f"To'lov xabari yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/qovun_purchase_requests",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"notified": True},
                        )
                    except Exception as e:
                        logger.error(f"notified belgilanmadi (purchase id={row.get('id')}): {e}")

            wr = await client.get(
                f"{SB_URL}/rest/v1/withdrawal_requests",
                headers=SB_HEADERS,
                params={"status": "neq.pending", "notified": "eq.false", "select": "*"},
            )
            for row in wr.json():
                try:
                    if row["status"] == "paid":
                        text = (
                            f"✅ {row['amount']} ta {row['currency']} ({row['money_amount']} so'm) "
                            f"pulga aylantirish so'rovingiz to'landi."
                        )
                    else:
                        reason = row.get("reject_reason") or "sabab ko'rsatilmagan"
                        text = f"❌ Pulga aylantirish so'rovingiz rad etildi. Sabab: {reason}"
                    await context.bot.send_message(chat_id=row["user_id"], text=text)
                except Exception as e:
                    logger.error(f"Pul chiqarish xabari yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/withdrawal_requests",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"notified": True},
                        )
                    except Exception as e:
                        logger.error(f"notified belgilanmadi (withdrawal id={row.get('id')}): {e}")
    except Exception as e:
        logger.error(f"check_payment_notifications xato: {e}")


async def check_book_approval_notifications(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/book_approval_notifications",
                headers=SB_HEADERS,
                params={"sent": "eq.false", "select": "*", "order": "created_at.asc"},
            )
            for row in r.json():
                try:
                    text = f"✅ \"{row['book_title']}\" kitobingiz admin tomonidan tasdiqlandi va endi ilovada hammaga ko'rinadi!"
                    await context.bot.send_message(chat_id=row["creator_id"], text=text)
                except Exception as e:
                    logger.error(f"Tasdiqlash xabari yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/book_approval_notifications",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"sent": True},
                        )
                    except Exception as e:
                        logger.error(f"notified belgilanmadi (book_approval id={row.get('id')}): {e}")
    except Exception as e:
        logger.error(f"check_book_approval_notifications xato: {e}")


async def check_sport_approval_notifications(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/sport_approval_notifications",
                headers=SB_HEADERS,
                params={"sent": "eq.false", "select": "*", "order": "created_at.asc"},
            )
            for row in r.json():
                try:
                    share_link = f"https://t.me/{BOT_USERNAME}/app?startapp=sport_{row['challenge_id']}"
                    text = (
                        f"✅ \"{row['challenge_title']}\" sport challenjingiz admin tomonidan tasdiqlandi va endi ilovada hammaga ko'rinadi!\n\n"
                        f"Do'stlaringizni taklif qiling:\n{share_link}"
                    )
                    await context.bot.send_message(chat_id=row["creator_id"], text=text)
                except Exception as e:
                    logger.error(f"Sport approval xabari yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/sport_approval_notifications",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"sent": True},
                        )
                    except Exception as e:
                        logger.error(f"sport_approval belgilanmadi (id={row.get('id')}): {e}")
    except Exception as e:
        logger.error(f"check_sport_approval_notifications xato: {e}")


async def check_sport_join_notifications(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/sport_join_notifications",
                headers=SB_HEADERS,
                params={"sent": "eq.false", "select": "*", "order": "created_at.asc"},
            )
            for row in r.json():
                try:
                    total_r = await client.get(
                        f"{SB_URL}/rest/v1/sport_progress",
                        headers=SB_HEADERS,
                        params={"challenge_id": f"eq.{row['challenge_id']}", "cohort_start_date": f"eq.{row['cohort_start_date']}", "select": "user_id"},
                    )
                    total = len(total_r.json())
                    ch_r = await client.get(
                        f"{SB_URL}/rest/v1/sport_challenges",
                        headers=SB_HEADERS,
                        params={"id": f"eq.{row['challenge_id']}", "select": "title"},
                    )
                    ch_list = ch_r.json()
                    title = ch_list[0]["title"] if ch_list else "Challenj"
                    text = (
                        f"📈 {row['cohort_start_date']}da boshlanadigan \"{title}\" sport "
                        f"challenjiga yana 1 kishi qo'shildi, jami {total} kishi."
                    )
                    await context.bot.send_message(chat_id=row["creator_id"], text=text)
                except Exception as e:
                    logger.error(f"Sport join notification yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/sport_join_notifications",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"sent": True},
                        )
                    except Exception as e:
                        logger.error(f"sport_join_notifications belgilanmadi (id={row.get('id')}): {e}")
    except Exception as e:
        logger.error(f"check_sport_join_notifications xato: {e}")


async def check_challenge_start(context: ContextTypes.DEFAULT_TYPE):
    """Bugun boshlanayotgan challenj guruhlariga xabar yuborish."""
    try:
        today = dt_date.today()
        months_uz = ['yanvar','fevral','mart','aprel','may','iyun','iyul','avgust','sentabr','oktabr','noyabr','dekabr']
        today_str = f"{today.day}-{months_uz[today.month-1]}, {today.year}"
        async with httpx.AsyncClient(timeout=30) as client:
            # Kitob challenjlari
            prog_r = await client.get(
                f"{SB_URL}/rest/v1/progress",
                headers=SB_HEADERS,
                params={"cohort_start_date": f"eq.{today}", "select": "user_id,book_id,cohort_start_date"},
            )
            book_progs = prog_r.json()
            book_ids = list(set(p["book_id"] for p in book_progs))
            for book_id in book_ids:
                book_r = await client.get(
                    f"{SB_URL}/rest/v1/books",
                    headers=SB_HEADERS,
                    params={"id": f"eq.{book_id}", "select": "title,total_pages"},
                )
                books = book_r.json()
                if not books:
                    continue
                book = books[0]
                reading_days = -(-book.get("total_pages", 200) // 20)
                members = [p for p in book_progs if p["book_id"] == book_id]
                pm_text = (
                    f"📖 \"{book['title']}\" kitob challenjingiz bugun boshlandi!\n\n"
                    f"Challenj davomiyligi: {reading_days} kun\n"
                    f"Kunlik me'yor: 20 bet\n\n"
                    f"Muvaffaqiyat! 🌱"
                )
                for member in members:
                    try:
                        await context.bot.send_message(chat_id=member["user_id"], text=pm_text)
                    except Exception as e:
                        logger.error(f"Kitob start xabari yuborilmadi (user_id={member['user_id']}): {e}")
                # Kanalga xabar
                channel_text = (
                    f"📚 Kitob challenjи boshlandi!\n"
                    f"📅 {today_str}\n"
                    f"📖 \"{book['title']}\"\n\n"
                    f"👥 {len(members)} kishi bugun challenjni boshladi!\n\n"
                    f"🌱 Neyra — o'zingni rivojlantir\n"
                    f"t.me/{BOT_USERNAME}/app"
                )
                for channel_id in CHANNEL_IDS:
                    try:
                        await context.bot.send_message(chat_id=channel_id, text=channel_text)
                    except Exception as e:
                        logger.error(f"Kanalga kitob start xabari yuborilmadi (id={channel_id}): {e}")

            # Sport challenjlari
            sp_r = await client.get(
                f"{SB_URL}/rest/v1/sport_progress",
                headers=SB_HEADERS,
                params={"cohort_start_date": f"eq.{today}", "select": "user_id,challenge_id"},
            )
            sport_progs = sp_r.json()
            ch_ids = list(set(p["challenge_id"] for p in sport_progs))
            for ch_id in ch_ids:
                ch_r = await client.get(
                    f"{SB_URL}/rest/v1/sport_challenges",
                    headers=SB_HEADERS,
                    params={"id": f"eq.{ch_id}", "select": "title,duration_days"},
                )
                chs = ch_r.json()
                if not chs:
                    continue
                ch = chs[0]
                ex_r = await client.get(
                    f"{SB_URL}/rest/v1/sport_exercises",
                    headers=SB_HEADERS,
                    params={"challenge_id": f"eq.{ch_id}", "select": "name,daily_count", "order": "sort_order.asc"},
                )
                exercises = ex_r.json()
                ex_lines = "\n".join([f"💪 {e['name']}: kuniga {e['daily_count']} ta" for e in exercises])
                members = [p for p in sport_progs if p["challenge_id"] == ch_id]
                pm_text = (
                    f"🏃 \"{ch['title']}\" sport challenjingiz bugun boshlandi!\n\n"
                    f"Challenj davomiyligi: {ch['duration_days']} kun\n\n"
                    f"{ex_lines}\n\n"
                    f"Muvaffaqiyat! 🌱"
                )
                for member in members:
                    try:
                        await context.bot.send_message(chat_id=member["user_id"], text=pm_text)
                    except Exception as e:
                        logger.error(f"Sport start xabari yuborilmadi (user_id={member['user_id']}): {e}")
                # Kanalga xabar
                channel_text = (
                    f"🏃 Sport challenjи boshlandi!\n"
                    f"📅 {today_str}\n"
                    f"💪 \"{ch['title']}\"\n\n"
                    f"👥 {len(members)} kishi bugun challenjni boshladi!\n\n"
                    f"🌱 Neyra — o'zingni rivojlantir\n"
                    f"t.me/{BOT_USERNAME}/app"
                )
                for channel_id in CHANNEL_IDS:
                    try:
                        await context.bot.send_message(chat_id=channel_id, text=channel_text)
                    except Exception as e:
                        logger.error(f"Kanalga sport start xabari yuborilmadi (id={channel_id}): {e}")
    except Exception as e:
        logger.error(f"check_challenge_start xato: {e}")


async def send_daily_top(context: ContextTypes.DEFAULT_TYPE):
    """Har kuni 22:00 UZT (17:00 UTC) da kanalga TOP 3 yuborish."""
    try:
        today = dt_date.today()
        today_str = today.strftime("%d-%B, %Y").replace("January", "yanvar").replace("February", "fevral").replace("March", "mart").replace("April", "aprel").replace("May", "may").replace("June", "iyun").replace("July", "iyul").replace("August", "avgust").replace("September", "sentabr").replace("October", "oktabr").replace("November", "noyabr").replace("December", "dekabr")
        medals = ["🥇", "🥈", "🥉"]
        async with httpx.AsyncClient(timeout=30) as client:
            # ===== KITOB TOP 3 =====
            book_lines = []
            prog_r = await client.get(
                f"{SB_URL}/rest/v1/progress",
                headers=SB_HEADERS,
                params={"select": "user_id,user_name,pages_read,book_id,cohort_start_date", "order": "pages_read.desc"},
            )
            progs = prog_r.json()
            # Faqat bugun "reading" holatidagi guruhlar
            active_progs = []
            for p in progs:
                if not p.get("cohort_start_date"):
                    continue
                cohort_date = dt_date.fromisoformat(p["cohort_start_date"])
                diff = (today - cohort_date).days
                if 0 <= diff < 60:
                    active_progs.append(p)

            if active_progs:
                top_book = active_progs[:3]
                book_r = await client.get(
                    f"{SB_URL}/rest/v1/books",
                    headers=SB_HEADERS,
                    params={"id": f"eq.{active_progs[0]['book_id']}", "select": "title,total_pages"},
                )
                book_info = book_r.json()
                book_title = book_info[0]["title"] if book_info else "Kitob"
                total_pages = book_info[0]["total_pages"] if book_info else 0
                cohort_date_str = active_progs[0]["cohort_start_date"]
                cohort_dt = dt_date.fromisoformat(cohort_date_str)
                cohort_str = f"{cohort_dt.day}-{['yanvar','fevral','mart','aprel','may','iyun','iyul','avgust','sentabr','oktabr','noyabr','dekabr'][cohort_dt.month-1]} guruhi"
                daily_limit = 20
                for i, p in enumerate(top_book):
                    book_lines.append(f"{medals[i]} {p['user_name']} — {p['pages_read']}/{daily_limit} bet")

            # ===== SPORT TOP 3 =====
            sport_lines = []
            sdl_r = await client.get(
                f"{SB_URL}/rest/v1/sport_daily_logs",
                headers=SB_HEADERS,
                params={"log_date": f"eq.{today}", "select": "user_id,user_name,count_done,challenge_id,cohort_start_date"},
            )
            sport_logs = sdl_r.json()
            user_totals = {}
            ch_id_day = None
            cohort_start_day = None
            for l in sport_logs:
                uid = l["user_id"]
                if uid not in user_totals:
                    user_totals[uid] = {"name": l["user_name"], "total": 0, "ex_count": 0, "challenge_id": l["challenge_id"], "cohort_start_date": l["cohort_start_date"]}
                user_totals[uid]["total"] += l["count_done"]
                user_totals[uid]["ex_count"] += 1
                ch_id_day = l["challenge_id"]
                cohort_start_day = l["cohort_start_date"]

            top_sport = sorted(user_totals.values(), key=lambda x: x["total"], reverse=True)[:3]
            ch_title = "Challenj"
            ch_cohort_str = ""
            if ch_id_day:
                ch_r = await client.get(
                    f"{SB_URL}/rest/v1/sport_challenges",
                    headers=SB_HEADERS,
                    params={"id": f"eq.{ch_id_day}", "select": "title"},
                )
                ch_list = ch_r.json()
                if ch_list:
                    ch_title = ch_list[0]["title"]
                if cohort_start_day:
                    cdt = dt_date.fromisoformat(cohort_start_day)
                    ch_cohort_str = f"{cdt.day}-{['yanvar','fevral','mart','aprel','may','iyun','iyul','avgust','sentabr','oktabr','noyabr','dekabr'][cdt.month-1]} guruhi"
                ex_r = await client.get(
                    f"{SB_URL}/rest/v1/sport_exercises",
                    headers=SB_HEADERS,
                    params={"challenge_id": f"eq.{ch_id_day}", "select": "id"},
                )
                total_ex_count = len(ex_r.json())
                for i, u in enumerate(top_sport):
                    unique_ex = min(u["ex_count"], total_ex_count)
                    sport_lines.append(f"{medals[i]} {u['name']} — {unique_ex}/{total_ex_count} mashq · jami {u['total']} ta")

            # ===== XABAR YARATISH =====
            if not book_lines and not sport_lines:
                return

            msg_parts = [f"📅 {today_str}\n"]
            if book_lines:
                msg_parts.append(f"📚 Kitob challenjida bugungi TOP 3")
                if active_progs:
                    msg_parts.append(f"📖 \"{book_title}\" — {cohort_str}")
                msg_parts.extend(book_lines)
                msg_parts.append("")
            if sport_lines:
                msg_parts.append(f"🏃 Sport challenjida bugungi TOP 3")
                if ch_id_day:
                    msg_parts.append(f"💪 \"{ch_title}\" — {ch_cohort_str}")
                msg_parts.extend(sport_lines)
                msg_parts.append("")
            msg_parts.append("🌱 Neyra — o'zingni rivojlantir")
            msg_parts.append(f"t.me/{BOT_USERNAME}/app")

            text = "\n".join(msg_parts)
            for channel_id in CHANNEL_IDS:
                try:
                    await context.bot.send_message(chat_id=channel_id, text=text)
                except Exception as e:
                    logger.error(f"Kanalga xabar yuborilmadi (id={channel_id}): {e}")
    except Exception as e:
        logger.error(f"send_daily_top xato: {e}")


async def check_sport_join_confirmations(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{SB_URL}/rest/v1/sport_join_confirmations",
                headers=SB_HEADERS,
                params={"sent": "eq.false", "select": "*", "order": "created_at.asc"},
            )
            for row in r.json():
                try:
                    share_link = f"https://t.me/{BOT_USERNAME}/app?startapp=sport_{row['challenge_id']}"
                    text = (
                        f"✅ {row['cohort_start_date']}da boshlanadigan \"{row['challenge_title']}\" "
                        f"sport challenjiga qo'shildingiz!\n\n"
                        f"Do'stlaringizni ham taklif qiling, ulashish uchun havola:\n{share_link}"
                    )
                    await context.bot.send_message(chat_id=row["user_id"], text=text)
                except Exception as e:
                    logger.error(f"Sport join confirmation yuborilmadi (id={row.get('id')}): {e}")
                finally:
                    try:
                        await client.patch(
                            f"{SB_URL}/rest/v1/sport_join_confirmations",
                            headers=SB_HEADERS,
                            params={"id": f"eq.{row['id']}"},
                            json={"sent": True},
                        )
                    except Exception as e:
                        logger.error(f"sport_join_confirmations belgilanmadi (id={row.get('id')}): {e}")
    except Exception as e:
        logger.error(f"check_sport_join_confirmations xato: {e}")


# ===== Asosiy =====
# ===== Ilova faylini (index.html) servisga chiqarish =====
def run_web_server():
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Veb-server {port}-portda ishga tushirilmoqda...")
    try:
        handler = http.server.SimpleHTTPRequestHandler
        http.server.ThreadingHTTPServer.allow_reuse_address = True
        httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)
        logger.info(f"Veb-server {port}-portda muvaffaqiyatli ishga tushdi (index.html shu yerdan ko'rinadi).")
        httpd.serve_forever()
    except Exception:
        logger.exception("Veb-server ishga tushmadi (xatolik yuqorida):")


def main():
    threading.Thread(target=run_web_server, daemon=True).start()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(contact_response_callback, pattern=r"^cr_(yes|no)_\d+$"))

    if application.job_queue:
        application.job_queue.run_repeating(check_contact_requests, interval=15, first=5)
        application.job_queue.run_repeating(check_rank_drops, interval=30, first=12)
        application.job_queue.run_repeating(check_join_notifications, interval=15, first=10)
        application.job_queue.run_repeating(check_join_confirmations, interval=15, first=11)
        application.job_queue.run_repeating(check_payment_notifications, interval=15, first=13)
        application.job_queue.run_repeating(check_book_approval_notifications, interval=15, first=16)
        application.job_queue.run_repeating(check_sport_approval_notifications, interval=15, first=17)
        application.job_queue.run_repeating(check_sport_join_confirmations, interval=15, first=18)
        application.job_queue.run_repeating(check_sport_join_notifications, interval=15, first=19)
        application.job_queue.run_daily(
            check_challenge_start,
            time=dt_time(23, 0, 0, tzinfo=timezone.utc),  # 04:00 UZT
        )
        application.job_queue.run_daily(
            send_daily_top,
            time=dt_time(17, 0, 0, tzinfo=timezone.utc),  # 22:00 UZT
        )
    else:
        logger.warning(
            "job_queue mavjud emas. Terminalda quyidagini ishga tushiring: "
            'pip install "python-telegram-bot[job-queue]"'
        )

    logger.info("Bot ishga tushdi.")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main().streak-fire{ font-size:22px; }
.streak-num{ font-size:16px; font-weight:800; }
.streak-label{ font-size:11px; color:var(--text-muted); }
.streak-daraja{ font-size:12px; font-weight:700; color:var(--accent-1); text-align:right; }
.streak-days-row{ display:flex; justify-content:space-between; gap:6px; }
.streak-day{ flex:1; display:flex; flex-direction:column; align-items:center; gap:4px; }
.streak-day-icon{ font-size:19px; filter:grayscale(1) opacity(0.35); }
.streak-day-icon.lit{ filter:none; }
.streak-day-num{ font-size:9px; color:var(--text-muted); font-weight:700; }

.loading,.empty{ text-align:center; color:var(--text-muted); font-size:13px; padding:40px 16px; line-height:1.6; }

.fab{ position:fixed; right:18px; bottom:118px; width:58px; height:58px; border-radius:50%; border:none; background:linear-gradient(135deg,var(--accent-1),var(--accent-2)); color:var(--bg); font-size:28px; font-weight:700; box-shadow:8px 8px 16px var(--shadow-dark), -6px -6px 14px var(--shadow-light); z-index:5; }

.tabbar{ position:fixed; left:0; right:0; bottom:0; display:flex; justify-content:center; gap:8px; padding:14px 10px calc(14px + env(safe-area-inset-bottom)); }
.tab{ flex:1; max-width:80px; height:64px; border:none; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; border-radius:var(--radius-md); background:var(--surface); box-shadow:6px 6px 14px var(--shadow-dark), -5px -5px 12px var(--shadow-light); color:var(--text-muted); font-family:inherit; }
.tab.active{ color:var(--bg); background:linear-gradient(135deg,var(--accent-1),var(--accent-2)); }
.tab-icon{ font-size:20px; }
.tab-label{ font-size:10px; font-weight:600; }

.form{ display:flex; flex-direction:column; gap:12px; }
.input{ width:100%; background:var(--surface-alt); border:none; color:var(--text); border-radius:var(--radius-sm); padding:13px 14px; font-size:14px; font-family:inherit; box-shadow:inset 4px 4px 8px var(--shadow-dark), inset -3px -3px 6px var(--shadow-light); }
.input::placeholder{ color:var(--text-muted); }
.hint{ font-size:12px; color:var(--accent-1); background:rgba(183,229,186,0.1); border-radius:var(--radius-sm); padding:10px 12px; line-height:1.5; }
.btn-primary{ background:linear-gradient(135deg,var(--accent-1),var(--accent-2)); color:var(--bg); border:none; border-radius:var(--radius-sm); padding:13px 18px; font-weight:700; font-size:14px; font-family:inherit; box-shadow:6px 6px 14px var(--shadow-dark), -4px -4px 10px var(--shadow-light); }
.btn-primary.full{ width:100%; margin-top:6px; }
.btn-primary:disabled{ opacity:.6; }
.result-card{ cursor:pointer; margin-bottom:8px; }

.file-btn{ display:block; text-align:center; background:var(--surface-alt); color:var(--text-muted); border-radius:var(--radius-sm); padding:13px 14px; font-size:13px; font-weight:600; box-shadow:inset 4px 4px 8px var(--shadow-dark), inset -3px -3px 6px var(--shadow-light); cursor:pointer; }
.cover-preview-img{ width:84px; height:118px; object-fit:cover; border-radius:var(--radius-sm); margin-top:4px; box-shadow:5px 5px 12px var(--shadow-dark); }

.hero-row{ display:flex; gap:16px; margin-bottom:18px; }
.cover-hero{ width:84px; height:118px; object-fit:cover; border-radius:var(--radius-sm); flex-shrink:0; box-shadow:6px 6px 14px var(--shadow-dark); }
.cover-hero-placeholder{ width:84px; height:118px; border-radius:var(--radius-sm); flex-shrink:0; background:var(--surface-alt); display:flex; align-items:center; justify-content:center; font-size:32px; }
.hero-info{ flex:1; min-width:0; padding-top:2px; }
.book-hero-title{ font-size:20px; font-weight:800; margin-bottom:4px; }
.book-hero-author{ font-size:13px; color:var(--text-muted); margin-bottom:8px; }
.book-hero-sub{ font-size:12px; color:var(--text-muted); margin-top:4px; }



.readers{ display:flex; flex-direction:column; gap:8px; }
.reader-row{ display:flex; align-items:center; gap:10px; background:var(--surface); border-radius:var(--radius-sm); padding:12px 14px; box-shadow:5px 5px 12px var(--shadow-dark), -4px -4px 10px var(--shadow-light); cursor:pointer; }
.reader-row.me{ box-shadow:5px 5px 12px var(--shadow-dark), -4px -4px 10px var(--shadow-light), 0 0 0 2px var(--accent-1) inset; }
.reader-rank{ width:26px; text-align:center; font-size:14px; font-weight:700; color:var(--text-muted); flex-shrink:0; }
.reader-info{ flex:1; min-width:0; }
.reader-name{ font-size:14px; font-weight:600; }
.reader-note{ font-size:11px; color:var(--text-muted); margin-top:2px; }
.reader-pages{ font-size:12px; color:var(--accent-1); font-weight:700; white-space:nowrap; }

.comment-form{ display:flex; align-items:flex-end; gap:8px; margin-bottom:16px; }
.comment-form textarea{ resize:none; font-family:inherit; }
.comments{ display:flex; flex-direction:column; gap:0; }
.comment-block{ padding:10px 0; border-bottom:1px solid rgba(255,255,255,0.06); }
.comment-block.reply{ margin-left:22px; border-bottom:none; padding:8px 0 2px; }
.comment-text{ font-size:13px; line-height:1.6; color:var(--text-muted); white-space:pre-wrap; }
.comment-name{ font-weight:700; color:var(--text); }
.edited-tag{ font-size:11px; color:var(--text-muted); font-style:italic; }
.comment-actions{ display:flex; gap:16px; margin-top:5px; }
.notes-list{ display:flex; flex-direction:column; gap:0; }
.note-entry{ padding:10px 0; border-bottom:1px solid rgba(255,255,255,0.06); }
.note-meta{ font-size:11px; color:var(--accent-1); margin-bottom:4px; }
.note-text{ font-size:13px; line-height:1.6; color:var(--text-muted); white-space:pre-wrap; }
.note-photo-img{ width:100%; max-width:220px; border-radius:var(--radius-sm); margin-bottom:8px; display:block; box-shadow:5px 5px 12px var(--shadow-dark); }
.cohort-schedule{ display:flex; flex-direction:column; gap:6px; }
.cohort-sched-row{ display:flex; justify-content:space-between; align-items:center; background:var(--surface); border-radius:var(--radius-sm); padding:10px 12px; box-shadow:4px 4px 10px var(--shadow-dark), -3px -3px 8px var(--shadow-light); font-size:12px; }
.cohort-sched-row.nearest{ box-shadow:0 0 0 2px var(--accent-1), 4px 4px 10px var(--shadow-dark); }
.cohort-sched-row.mine{ background:var(--surface-alt); }
.cohort-sched-date{ font-weight:700; }
.cohort-sched-meta{ color:var(--text-muted); text-align:right; }
.comment-action-btn{ background:none; border:none; color:var(--text-muted); font-size:11px; font-family:inherit; display:flex; align-items:center; gap:4px; padding:2px 0; }
.comment-action-btn.liked{ color:var(--accent-1); font-weight:700; }
.reply-banner{ display:flex; align-items:center; justify-content:space-between; background:var(--surface-alt); border-radius:var(--radius-sm); padding:9px 12px; margin-bottom:10px; font-size:12px; color:var(--accent-1); }
.reply-banner button{ font-family:inherit; }

.remove-link{ display:block; text-align:center; color:var(--text-muted); font-size:12px; margin-top:20px; text-decoration:underline; background:none; border:none; font-family:inherit; width:100%; padding:8px; }

.profile-header{ display:flex; flex-direction:column; align-items:center; gap:12px; margin-bottom:20px; }
.profile-header-name{ font-size:18px; font-weight:700; }
.avatar-img{ border-radius:50%; object-fit:cover; box-shadow:6px 6px 14px var(--shadow-dark), -5px -5px 12px var(--shadow-light); }
.avatar-placeholder{ border-radius:50%; background:var(--surface-alt); display:flex; align-items:center; justify-content:center; box-shadow:6px 6px 14px var(--shadow-dark), -5px -5px 12px var(--shadow-light); }
.profile-stats{ display:flex; gap:12px; margin-bottom:18px; }
.profile-stat-box{ flex:1; background:var(--surface); border-radius:var(--radius-md); padding:16px; text-align:center; box-shadow:8px 8px 18px var(--shadow-dark), -6px -6px 14px var(--shadow-light); }
.profile-stat-num{ font-size:24px; font-weight:800; color:var(--accent-1); }
.profile-stat-label{ font-size:11px; color:var(--text-muted); margin-top:4px; }
.section-label{ font-size:13px; font-weight:700; color:var(--text-muted); margin-bottom:10px; text-transform:uppercase; letter-spacing:.4px; }
.medal-slots-row{ display:flex; gap:10px; margin-bottom:8px; }
.medal-slot-icon{ font-size:26px; filter:grayscale(1) opacity(0.35); }
.medal-slot-icon.lit{ filter:none; }
.medal-count-label{ font-size:12px; color:var(--text-muted); font-weight:600; }

.btn-small{ background:var(--surface-alt); color:var(--text); border:none; border-radius:var(--radius-sm); padding:9px 14px; font-size:12px; font-weight:600; font-family:inherit; box-shadow:inset 3px 3px 6px var(--shadow-dark), inset -2px -2px 5px var(--shadow-light); }
.btn-small.danger{ color:var(--danger); }
.admin-row{ display:flex; align-items:center; justify-content:space-between; gap:10px; background:var(--surface); border-radius:var(--radius-sm); padding:12px 14px; margin-bottom:8px; box-shadow:5px 5px 12px var(--shadow-dark), -4px -4px 10px var(--shadow-light); }
.admin-row-info{ min-width:0; flex:1; }

.coming-soon{ display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:65vh; text-align:center; }
.cs-icon{ font-size:52px; margin-bottom:14px; }
.cs-title{ font-size:20px; font-weight:700; margin-bottom:6px; }
.cs-sub{ font-size:14px; color:var(--text-muted); }
</style>
</head>
<body>
<div id="app"></div>
<script>
// ===== Supabase sozlamalari =====
var SB_URL = 'https://ubakgpkcemlchpfejmke.supabase.co';
var SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InViYWtncGtjZW1sY2hwZmVqbWtlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzMjc3NzUsImV4cCI6MjA5NTkwMzc3NX0.wkKSmoTB9RwREFjcJfe0dNBzZDEw2DHxNM3G6erHSJU';
var SB_H = { apikey: SB_KEY, Authorization: 'Bearer ' + SB_KEY, 'Content-Type': 'application/json' };
var HUJJATLAR_BUCKET = 'hujjatlar';
var JOIN_COST_QOVUN = 10000;
var QOVUN_PER_SOM = 1;
var PROTEINCHA_PER_SOM = 10000;
var FURA_SIZE = 5000;
var PAYMENT_CARD = "UMIDJON PULATOV 9860 1701 0633 3009";
var COHORT_SIGNUP_DAYS = 5;
var COHORT_READING_DAYS = 20;
var COHORT_CLOSING_DAYS = 5;
var COHORT_SUGGESTED_DAILY_PAGES = 20;
var ADMIN_ID = 1645167548;

// ===== Telegram WebApp init =====
var tg = window.Telegram ? window.Telegram.WebApp : null;
if (tg) {
  try {
    tg.ready();
    tg.expand();
    tg.setHeaderColor('#1A5140');
    tg.setBackgroundColor('#1A5140');
  } catch (e) {}
}

function vibrate(style) {
  try { if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred(style || 'light'); } catch (e) {}
}
function showAlert(msg, callback) {
  try { if (tg && tg.showAlert) { tg.showAlert(msg, callback); return; } } catch (e) {}
  alert(msg);
  if (callback) callback();
}
function confirmAction(msg, onYes) {
  try {
    if (tg && tg.showConfirm) { tg.showConfirm(msg, function (ok) { if (ok) onYes(); }); return; }
  } catch (e) {}
  if (window.confirm(msg)) onYes();
}
function customPrompt(message, callback) {
  var overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.55);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px;';
  var box = document.createElement('div');
  box.style.cssText = 'background:var(--surface);border-radius:var(--radius,16px);padding:20px;width:100%;max-width:320px;box-shadow:0 8px 24px rgba(0,0,0,0.3);';
  box.innerHTML =
    '<div style="margin-bottom:12px;font-size:14px;color:var(--text-main,#fff)">' + escapeHtml(message) + '</div>' +
    '<input id="customPromptInput" class="input" style="margin-bottom:14px;width:100%;box-sizing:border-box" />' +
    '<div style="display:flex;gap:8px">' +
    '<button id="customPromptCancel" class="btn-small" style="flex:1">Bekor qilish</button>' +
    '<button id="customPromptOk" class="btn-primary" style="flex:1">OK</button>' +
    '</div>';
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  var input = box.querySelector('#customPromptInput');
  setTimeout(function () { input.focus(); }, 50);
  function cleanup(value) {
    document.body.removeChild(overlay);
    callback(value);
  }
  box.querySelector('#customPromptCancel').addEventListener('click', function () { cleanup(null); });
  box.querySelector('#customPromptOk').addEventListener('click', function () { cleanup(input.value); });
  input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); cleanup(input.value); } });
}

// ===== Foydalanuvchi =====
var ME = (function () {
  try {
    var u = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
    if (u) return { id: u.id, name: [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username || ('Foydalanuvchi ' + u.id), photoUrl: u.photo_url || null, username: u.username || null };
  } catch (e) {}
  return { id: 0, name: 'Mehmon', photoUrl: null, username: null };
})();

var iAmBlocked = false;
(function () {
  sbGet('blocked_users?select=user_id&user_id=eq.' + ME.id).then(function (rows) {
    iAmBlocked = rows.length > 0;
  }).catch(function () {});
})();

// Foydalanuvchini darhol saqlash (hamyon yaratish orqali)
(function () {
  if (ME.id) {
    getOrCreateWallet(ME.id, ME.name, ME.username).catch(function () {});
  }
})();

// ===== Yordamchi: sana formatlash =====
var UZ_MONTHS = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'];
function formatDate(iso) {
  if (!iso) return '';
  var d = new Date(iso);
  return d.getDate() + '-' + UZ_MONTHS[d.getMonth()] + ', ' + d.getFullYear();
}
function formatDateTime(iso) {
  if (!iso) return '';
  var d = new Date(iso);
  var hh = String(d.getHours()).padStart(2, '0');
  var mi = String(d.getMinutes()).padStart(2, '0');
  return formatDate(iso) + ' ' + hh + ':' + mi;
}

// ===== Supabase yordamchi funksiyalar =====
async function sbGet(path) {
  var res = await fetch(SB_URL + '/rest/v1/' + path, { headers: SB_H });
  if (!res.ok) throw new Error('SB GET xato: ' + res.status);
  return res.json();
}
async function sbPost(path, body, prefer) {
  var res = await fetch(SB_URL + '/rest/v1/' + path, {
    method: 'POST',
    headers: Object.assign({}, SB_H, { Prefer: prefer || 'return=representation' }),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('SB POST xato: ' + res.status + ' ' + (await res.text()));
  var txt = await res.text();
  return txt ? JSON.parse(txt) : null;
}
async function sbPatch(path, body) {
  var res = await fetch(SB_URL + '/rest/v1/' + path, {
    method: 'PATCH',
    headers: Object.assign({}, SB_H, { Prefer: 'return=representation' }),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('SB PATCH xato: ' + res.status + ' ' + (await res.text()));
  var txt = await res.text();
  return txt ? JSON.parse(txt) : null;
}
async function sbDelete(path) {
  var res = await fetch(SB_URL + '/rest/v1/' + path, { method: 'DELETE', headers: SB_H });
  if (!res.ok) throw new Error('SB DELETE xato: ' + res.status);
}
async function sbUploadFile(bucket, path, file) {
  var res = await fetch(SB_URL + '/storage/v1/object/' + bucket + '/' + path, {
    method: 'POST',
    headers: { apikey: SB_KEY, Authorization: 'Bearer ' + SB_KEY, 'Content-Type': file.type || 'application/octet-stream' },
    body: file,
  });
  if (!res.ok) throw new Error('Yuklash xatosi: ' + res.status);
  return SB_URL + '/storage/v1/object/public/' + bucket + '/' + path;
}

// ===== Hamyon (qovuncha/proteincha) =====
async function getOrCreateWallet(userId, userName, username) {
  var rows = await sbGet('wallets?select=*&user_id=eq.' + userId);
  if (rows[0]) return rows[0];
  var inserted = await sbPost('wallets?on_conflict=user_id', { user_id: userId, user_name: userName || '', username: username || null, qovun_balance: 10000, proteincha_balance: 1 }, 'resolution=merge-duplicates,return=representation');
  return (inserted && inserted[0]) || { user_id: userId, user_name: userName || '', qovun_balance: 10000, proteincha_balance: 1 };
}
async function adjustWallet(userId, qovunDelta, proteinchaDelta) {
  var w = await getOrCreateWallet(userId);
  var newQovun = (w.qovun_balance || 0) + (qovunDelta || 0);
  var newProteincha = (w.proteincha_balance || 0) + (proteinchaDelta || 0);
  await sbPost('wallets?on_conflict=user_id', { user_id: userId, qovun_balance: newQovun, proteincha_balance: newProteincha }, 'resolution=merge-duplicates,return=representation');
  return { qovun_balance: newQovun, proteincha_balance: newProteincha };
}
async function addToTreasury(qovunDelta) {
  var rows = await sbGet('treasury?select=*&id=eq.1');
  var current = (rows[0] && rows[0].qovun_balance) || 0;
  await sbPatch('treasury?id=eq.1', { qovun_balance: current + qovunDelta });
}
function formatSom(n) {
  n = Math.round(n || 0);
  return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + " so'm";
}
function formatNumber(n) {
  n = Math.round(n || 0);
  return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}
function qovunLabel(qovun) {
  return formatNumber(qovun) + ' ta qovuncha';
}
async function joinCohortFlow(book, marker, progress) {
  var isCreator = String(book.created_by_id) === String(ME.id);
  if (!isCreator) {
    var wallet = await getOrCreateWallet(ME.id, ME.name, ME.username);
    if ((wallet.qovun_balance || 0) < JOIN_COST_QOVUN) {
      showAlert("Qovunchangiz yetarli emas. Challenjga qo'shilish uchun " + formatNumber(JOIN_COST_QOVUN) + " ta qovuncha kerak.");
      return false;
    }
  }
  var nowIso = new Date().toISOString();
  var inserted = await sbPost('progress?on_conflict=book_id,user_id', {
    book_id: book.id, user_id: ME.id, user_name: ME.name, pages_read: 0, updated_at: nowIso, started_at: nowIso, cohort_start_date: marker,
  }, 'resolution=merge-duplicates,return=representation');
  if (inserted && inserted[0]) {
    progress.push(inserted[0]);
    progress.sort(function (a, b) { return b.pages_read - a.pages_read; });
  }
  if (!isCreator) {
    await adjustWallet(ME.id, -JOIN_COST_QOVUN, 0);
    await addToTreasury(JOIN_COST_QOVUN);
  }
  try {
    await sbPost('join_notifications', { book_id: book.id, creator_id: book.created_by_id, cohort_start_date: marker });
  } catch (e) { console.error(e); }
  try {
    await sbPost('join_confirmations', { book_id: book.id, user_id: ME.id, book_title: book.title, cohort_start_date: marker });
  } catch (e) { console.error(e); }
  return true;
}

// ===== Kogort (guruh) sikli hisoblash =====
function monthCohortMarkers(year, month) {
  var days = [1, 5, 10, 15, 20, 25];
  return days.map(function (d) {
    return year + '-' + String(month + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
  });
}
function nearbyCohortMarkers(todayStr) {
  var today = new Date(todayStr + 'T00:00:00');
  var set = {};
  for (var offset = -2; offset <= 1; offset++) {
    var d = new Date(today.getFullYear(), today.getMonth() + offset, 1);
    monthCohortMarkers(d.getFullYear(), d.getMonth()).forEach(function (m) { set[m] = true; });
  }
  return Object.keys(set).sort();
}
function cohortDiffDays(markerStr, todayStr) {
  var marker = new Date(markerStr + 'T00:00:00');
  var today = new Date(todayStr + 'T00:00:00');
  return Math.round((today - marker) / 86400000);
}
function bookReadingDays(book) {
  var pages = book && book.total_pages;
  if (!pages || pages <= 0) return COHORT_READING_DAYS;
  return Math.max(1, Math.ceil(pages / COHORT_SUGGESTED_DAILY_PAGES));
}
function previousCohortMarker(markerStr) {
  var d = new Date(markerStr + 'T00:00:00');
  var all = [];
  for (var offset = -1; offset <= 0; offset++) {
    var dm = new Date(d.getFullYear(), d.getMonth() + offset, 1);
    all = all.concat(monthCohortMarkers(dm.getFullYear(), dm.getMonth()));
  }
  all.sort();
  var idx = all.indexOf(markerStr);
  return idx > 0 ? all[idx - 1] : null;
}
function cohortPhase(markerStr, todayStr, readingDays) {
  readingDays = readingDays || COHORT_READING_DAYS;
  var diff = cohortDiffDays(markerStr, todayStr);
  var prevMarker = previousCohortMarker(markerStr);
  var signupDays = prevMarker ? cohortDiffDays(markerStr, prevMarker) * -1 : COHORT_SIGNUP_DAYS;
  if (diff < -signupDays) return null;
  if (diff < 0) return 'signup';
  if (diff < readingDays) return 'reading';
  if (diff < readingDays + COHORT_CLOSING_DAYS) return 'closing';
  return 'ended';
}
function currentSignupCohortMarker(todayStr) {
  var markers = nearbyCohortMarkers(todayStr);
  for (var i = 0; i < markers.length; i++) {
    if (cohortPhase(markers[i], todayStr) === 'signup') return markers[i];
  }
  return null;
}
function nextUpcomingCohortMarker(todayStr) {
  var markers = nearbyCohortMarkers(todayStr);
  var signupMarker = currentSignupCohortMarker(todayStr);
  if (!signupMarker) return null;
  var idx = markers.indexOf(signupMarker);
  return idx >= 0 && idx + 1 < markers.length ? markers[idx + 1] : null;
}
function addDaysToDateStr(markerStr, days) {
  var d = new Date(markerStr + 'T00:00:00');
  d.setDate(d.getDate() + days);
  return formatDate(localDateStr(d));
}
function cohortPhaseLabel(phase, diff, markerStr, readingDays) {
  readingDays = readingDays || COHORT_READING_DAYS;
  if (phase === null || phase === undefined) return "Hali ochilmagan — start sanasi " + formatDate(markerStr);
  if (phase === 'signup') return "Guruh shakillanmoqda — o'qish " + formatDate(markerStr) + " da boshlanadi";
  if (phase === 'reading') return (diff + 1) + '-kun / ' + readingDays + ' kunlik challenge';
  if (phase === 'closing') return "Challenge tugadi — guruh yana " + (readingDays + COHORT_CLOSING_DAYS - diff) + " kun ko'rinadi";
  return 'Guruh yopilgan';
}

// ===== Kunlik odat (streak) =====
function localDateStr(d) {
  d = d || new Date();
  var y = d.getFullYear();
  var m = String(d.getMonth() + 1).padStart(2, '0');
  var day = String(d.getDate()).padStart(2, '0');
  return y + '-' + m + '-' + day;
}
function cohortTodayStr(d) {
  d = d || new Date();
  return localDateStr(new Date(d.getTime() - 4 * 60 * 60 * 1000));
}

async function recordReadingActivity() {
  var today = localDateStr();
  try {
    var rows = await sbGet('streaks?select=*&user_id=eq.' + ME.id);
    var row = rows[0];
    var current = 1, longest = 1;
    if (row) {
      if (row.last_active_date === today) {
        current = row.current_streak;
        longest = row.longest_streak;
      } else {
        var yesterday = localDateStr(new Date(Date.now() - 86400000));
        current = (row.last_active_date === yesterday) ? row.current_streak + 1 : 1;
        longest = Math.max(row.longest_streak, current);
      }
    }
    await sbPost('streaks?on_conflict=user_id', {
      user_id: ME.id, current_streak: current, longest_streak: longest, last_active_date: today,
    }, 'resolution=merge-duplicates,return=representation');
  } catch (e) { console.error(e); }
}

async function recordSportActivity() {
  var today = localDateStr();
  try {
    var rows = await sbGet('sport_streaks?select=*&user_id=eq.' + ME.id);
    var row = rows[0];
    var current = 1, longest = 1;
    if (row) {
      if (row.last_active_date === today) {
        current = row.current_streak;
        longest = row.longest_streak;
      } else {
        var yesterday = localDateStr(new Date(Date.now() - 86400000));
        current = (row.last_active_date === yesterday) ? row.current_streak + 1 : 1;
        longest = Math.max(row.longest_streak, current);
      }
    }
    await sbPost('sport_streaks?on_conflict=user_id', {
      user_id: ME.id, current_streak: current, longest_streak: longest, last_active_date: today,
    }, 'resolution=merge-duplicates,return=representation');
  } catch (e) { console.error(e); }
}

// ===== Kitobni tugatganlik (medal) =====
async function tryRecordFinish(book) {
  try {
    var existing = await sbGet('finishers?select=id&book_id=eq.' + book.id + '&user_id=eq.' + ME.id);
    if (existing.length) return null;
    var allFinishers = await sbGet('finishers?select=user_id&book_id=eq.' + book.id);
    var medal = allFinishers.length === 0 ? 1 : allFinishers.length === 1 ? 2 : 0;
    await sbPost('finishers', { book_id: book.id, book_title: book.title, user_id: ME.id, user_name: ME.name, medal: medal });
    if (medal === 1) return "🥇 Tabriklaymiz! Bu kitobni BIRINCHI bo'lib tugatdingiz!";
    if (medal === 2) return "🥈 Tabriklaymiz! Bu kitobni IKKINCHI bo'lib tugatdingiz!";
    return "🎉 Kitobni tugatdingiz!";
  } catch (e) { console.error(e); return null; }
}

// ===== Holat =====
var state = { view: 'modeSelect', tab: 'top', bookId: null, detailTab: 'readers', listData: [], viewUserId: null, viewUserName: null, adminTab: 'dashboard', sportTab: 'top', sportId: null, sportDetailTab: 'participants' };
var replyTarget = null;
var editTarget = null;
var expandedReplies = {};
var isAdminMode = false;
var _bdCache = null;
var noteEditTarget = null;
var _cohortCountdownInterval = null;
var selectedCohortMarker = null;
var _adminUsersCache = [];
var _adminBadgeInterval = null;
var _adminTxHistoryCache = [];
var _adminWdHistoryCache = [];
function txCurrencyLabel(r) { return r.currency === 'proteincha' ? 'proteincha' : 'qovuncha'; }
var _adminBlockedSet = {};
var _adminBooksCache = [];
var app = document.getElementById('app');
var _backHandler = null;

function setBackButton(show, handler) {
  if (!tg || !tg.BackButton) return;
  try {
    if (show) {
      if (_backHandler) { try { tg.BackButton.offClick(_backHandler); } catch (e2) {} }
      _backHandler = handler;
      tg.BackButton.show();
      tg.BackButton.onClick(_backHandler);
    } else {
      if (_backHandler) { try { tg.BackButton.offClick(_backHandler); } catch (e2) {} _backHandler = null; }
      tg.BackButton.hide();
    }
  } catch (e) {}
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}

function avatarHtml(photoUrl, size) {
  size = size || 72;
  if (photoUrl) {
    return '<img src="' + photoUrl + '" class="avatar-img" style="width:' + size + 'px;height:' + size + 'px" />';
  }
  return '<div class="avatar-placeholder" style="width:' + size + 'px;height:' + size + 'px;font-size:' + Math.round(size * 0.45) + 'px">👤</div>';
}

// ===== Router =====
function render() {
  if (state.view === 'modeSelect') renderModeSelect();
  else if (state.view === 'adminLogin') renderAdminLogin();
  else if (state.view === 'home') renderHome();
  else if (state.view === 'addBook') renderAddBook();
  else if (state.view === 'bookDetail') renderBookDetail();
  else if (state.view === 'userBooks') renderUserBooks();
  else if (state.view === 'profile') renderMyProfile();
  else if (state.view === 'wallet') renderWallet();
  else if (state.view === 'admin') renderAdmin();
  else if (state.view === 'sport') renderSportHome();
  else if (state.view === 'sportDetail') renderSportDetail();
  else if (state.view === 'addSport') renderAddSport();
}

function currentSection() {
  if (state.view === 'sport' || state.view === 'sportDetail' || state.view === 'addSport') return 'sport';
  if (state.view === 'profile' || state.view === 'wallet') return 'profile';
  return 'home';
}

function tabBtn(view, icon, label) {
  var active = currentSection() === view ? ' active' : '';
  return '<button class="tab' + active + '" data-go="' + view + '"><span class="tab-icon">' + icon + '</span><span class="tab-label">' + label + '</span></button>';
}

function renderShell(innerHtml, opts) {
  opts = opts || {};
  var tabs = tabBtn('home', '📚', 'Kitoblar') + tabBtn('sport', '🏃', 'Sport') + tabBtn('profile', '👤', 'Profil');
  var fabTarget = opts.fabAction === 'addSport' ? 'addSport' : 'addBook';
  app.innerHTML =
    '<div class="screen">' + innerHtml + '</div>' +
    (opts.fab ? '<button class="fab" data-go="' + fabTarget + '">+</button>' : '') +
    '<nav class="tabbar">' + tabs + '</nav>';
}

// ===== Rejim tanlash va admin kirish =====
function renderModeSelect() {
  setBackButton(false);
  app.innerHTML =
    '<div class="screen" style="display:flex;flex-direction:column;justify-content:center;min-height:80vh;gap:14px">' +
    '<div style="text-align:center;margin-bottom:24px"><div style="font-size:24px;font-weight:700">Neyra</div></div>' +
    '<button class="btn-primary full" data-go="home" style="padding:18px 16px;font-size:15px">🌱 Shaxsiy rivojlanish</button>' +
    '<button class="btn-primary full" data-go="adminLogin" style="padding:18px 16px;font-size:15px;background:var(--surface);color:var(--text);box-shadow:6px 6px 14px var(--shadow-dark), -4px -4px 10px var(--shadow-light)">🔐 Admin rejimi</button>' +
    '</div>';
}

function renderAdminLogin() {
  setBackButton(true, function () { state.view = 'modeSelect'; render(); });
  app.innerHTML =
    '<div class="screen">' +
    '<div class="header"><button class="back" data-go="modeSelect">←</button><div class="h-title">Admin kirish</div></div>' +
    '<div class="form">' +
    '<input id="adminLoginInput" class="input" placeholder="Login" autocomplete="off" />' +
    '<input id="adminPassInput" class="input" type="password" placeholder="Parol" autocomplete="off" />' +
    '<button id="adminLoginBtn" class="btn-primary full">Kirish</button>' +
    '</div>' +
    '</div>';
  document.getElementById('adminLoginBtn').addEventListener('click', function () {
    var login = document.getElementById('adminLoginInput').value.trim();
    var pass = document.getElementById('adminPassInput').value.trim();
    if (login === 'testadmin' && pass === 'testadmin') {
      isAdminMode = true;
      state.adminTab = 'dashboard';
      state.view = 'admin';
      render();
    } else {
      showAlert('Login yoki parol xato.');
    }
  });
}

// ===== Bosh sahifa =====
async function renderHome() {
  setBackButton(false);
  var isTop = state.tab === 'top';
  var bodyHtml = isTop
    ? '<div id="topLists"><div class="loading">Yuklanmoqda...</div></div>'
    : '<input id="bookListSearch" class="input" placeholder="Kitob yoki muallif bo\'yicha qidirish..." style="margin-bottom:14px" />' +
      '<div id="bookList" class="book-list"><div class="loading">Yuklanmoqda...</div></div>';
  renderShell(
    '<div class="header"><div class="h-title">Kitoblar</div></div>' +
    '<div class="segment">' +
    '<button class="seg-btn' + (state.tab === 'top' ? ' active' : '') + '" data-tab="top">🏆 TOP</button>' +
    '<button class="seg-btn' + (state.tab === 'all' ? ' active' : '') + '" data-tab="all">Barcha challenjlar</button>' +
    '</div>' +
    bodyHtml,
    { fab: true }
  );
  if (isTop) {
    await loadTopLists();
  } else {
    document.getElementById('bookListSearch').addEventListener('input', renderFilteredList);
    await loadAndRenderBookList();
  }
}

async function loadTopLists() {
  var el = document.getElementById('topLists');
  try {
    var results = await Promise.all([
      sbGet('finishers?select=user_id,user_name'),
      sbGet('progress?select=book_id,user_id,user_name,pages_read'),
      sbGet('books?select=*&approved=eq.true'),
    ]);
    var finishers = results[0];
    var progressRows = results[1];
    var books = results[2];

    var usingPagesFallback = finishers.length === 0;
    var topReaders;
    if (!usingPagesFallback) {
      var readerCounts = {}, readerNames = {};
      finishers.forEach(function (f) {
        readerCounts[f.user_id] = (readerCounts[f.user_id] || 0) + 1;
        readerNames[f.user_id] = f.user_name;
      });
      topReaders = Object.keys(readerCounts).map(function (uid) {
        return { id: parseInt(uid, 10), name: readerNames[uid], count: readerCounts[uid], unit: ' ta kitob' };
      }).sort(function (a, b) { return b.count - a.count; }).slice(0, 5);
    } else {
      var pageSums = {}, pageNames = {};
      progressRows.forEach(function (p) {
        pageSums[p.user_id] = (pageSums[p.user_id] || 0) + (p.pages_read || 0);
        pageNames[p.user_id] = p.user_name;
      });
      topReaders = Object.keys(pageSums).map(function (uid) {
        return { id: parseInt(uid, 10), name: pageNames[uid], count: pageSums[uid], unit: ' bet' };
      }).filter(function (r) { return r.count > 0; })
        .sort(function (a, b) { return b.count - a.count; }).slice(0, 5);
    }

    var bookCounts = {};
    progressRows.forEach(function (p) { bookCounts[p.book_id] = (bookCounts[p.book_id] || 0) + 1; });
    var topBooks = books.map(function (b) {
      return { book: b, count: bookCounts[b.id] || 0 };
    }).filter(function (x) { return x.count > 0; })
      .sort(function (a, b) { return b.count - a.count; }).slice(0, 5);

    var medalMark = function (i) { return i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : (i + 1); };

    var readersHtml = topReaders.length ? topReaders.map(function (r, i) {
      var isMe = r.id === ME.id;
      return '<div class="reader-row' + (isMe ? ' me' : '') + '" data-go="' + (isMe ? 'profile' : 'userBooks') + '" data-userid="' + r.id + '" data-username="' + escapeHtml(r.name) + '">' +
        '<div class="reader-rank">' + medalMark(i) + '</div>' +
        '<div class="reader-info"><div class="reader-name">' + escapeHtml(r.name) + '</div></div>' +
        '<div class="reader-pages">' + r.count + r.unit + '</div>' +
        '</div>';
    }).join('') : '<div class="empty">Hali hech kim kitob o\'qishni boshlamagan.</div>';

    var booksHtml = topBooks.length ? topBooks.map(function (x, i) {
      var b = x.book;
      var thumb = b.cover_url ? '<img src="' + b.cover_url + '" class="cover-thumb" />' : '<div class="cover-thumb-placeholder">📖</div>';
      return '<div class="card book-card" data-go="bookDetail" data-id="' + b.id + '">' +
        '<div class="book-card-row">' + thumb +
        '<div class="book-card-info"><div class="card-title">' + medalMark(i) + ' ' + escapeHtml(b.title) + '</div>' +
        (b.author ? '<div class="card-author">' + escapeHtml(b.author) + '</div>' : '') +
        '<div class="card-meta">👥 ' + x.count + ' kishi o\'qiyapti' + (b.total_pages ? ' · ' + b.total_pages + ' bet' : '') + '</div>' +
        '</div></div></div>';
    }).join('') : '<div class="empty">Hozircha hech kim kitob o\'qimayapti.</div>';

    el.innerHTML =
      '<div class="h-title" style="font-size:16px;margin-bottom:4px">Top 5 kitobxon</div>' +
      (usingPagesFallback ? '<div class="hint" style="margin-bottom:10px">Hali hech kim kitob tugatmagan — hozircha umumiy o\'qilgan betlar bo\'yicha.</div>' : '<div style="margin-bottom:10px"></div>') +
      '<div class="readers" style="margin-bottom:24px">' + readersHtml + '</div>' +
      '<div class="h-title" style="font-size:16px;margin-bottom:10px">Top 5 kitob</div>' +
      '<div class="book-list">' + booksHtml + '</div>';
  } catch (e) {
    el.innerHTML = '<div class="empty">Ma\'lumot yuklanmadi.</div>';
    console.error(e);
  }
}

var DARAJA_TITLES = [
  "Molodets",
  "VAOO",
  "Aqltoy",
  "Miyyasi ikkita",
  "Qoyil",
  "O'zga sayyoralik",
  "Bu ketishingizda sizga kitob yetqazib bo'lmay qoladi",
  "Vahshiy",
  "O'zingizni bosing",
  "Kamroq o'qing, miyangiz portlab ketadi",
  "Faylasuf",
  "Sizniyam ona tuqqanmi",
  "Marslik",
  "Boshingiz 400 kg bo'lib ketdi",
  "Ko'p o'qisham zarar",
  "Buncha o'qib nimaga tayyorlanyapsiz bilmadim-u, lekin tayyorsiz",
  "Boshingizda qasdingiz bormi",
];
function darajaTitle(n) {
  var idx = Math.min(n, DARAJA_TITLES.length) - 1;
  return DARAJA_TITLES[idx];
}

async function loadStreakBadge(targetId) {
  var el = document.getElementById(targetId || 'streakBadge');
  if (!el) return;
  try {
    var results = await Promise.all([
      sbGet('streaks?select=*&user_id=eq.' + ME.id),
      sbGet('sport_streaks?select=*&user_id=eq.' + ME.id),
    ]);
    var s = results[0][0];
    var ss = results[1][0];
    var today = localDateStr();
    var yesterday = localDateStr(new Date(Date.now() - 86400000));
    var n = (s && (s.last_active_date === today || s.last_active_date === yesterday)) ? s.current_streak : 0;
    var ns = (ss && (ss.last_active_date === today || ss.last_active_date === yesterday)) ? ss.current_streak : 0;

    function streakHtml(count, label, streakLabel) {
      if (count <= 0) return '';
      var cycleIndex = Math.floor((count - 1) / 5);
      var lit = ((count - 1) % 5) + 1;
      var daysRow = '';
      for (var i = 1; i <= 5; i++) {
        var dayLabel = cycleIndex * 5 + i;
        daysRow += '<div class="streak-day"><div class="streak-day-icon' + (i <= lit ? ' lit' : '') + '">' + (label === 'sport' ? '⚡' : '🔥') + '</div><div class="streak-day-num">' + dayLabel + '</div></div>';
      }
      return '<div class="streak-badge">' +
        '<div class="streak-top-row"><div><div class="streak-num">' + count + ' kun</div><div class="streak-label">' + streakLabel + '</div></div>' +
        '<div class="streak-daraja">🏅 ' + escapeHtml(darajaTitle(count)) + '</div></div>' +
        '<div class="streak-days-row">' + daysRow + '</div>' +
        '</div>';
    }

    el.innerHTML = streakHtml(n, 'kitob', 'ketma-ket o\'qiyapsiz') + streakHtml(ns, 'sport', 'ketma-ket mashq qilyapsiz');
  } catch (e) { el.innerHTML = ''; console.error(e); }
}

async function loadAndRenderBookList() {
  var listEl = document.getElementById('bookList');
  try {
    if (state.tab === 'mine') {
      var rows = await sbGet('progress?select=*,books(*)&user_id=eq.' + ME.id + '&order=updated_at.desc');
      state.listData = rows.map(function (r) {
        var b = r.books;
        var pct = b.total_pages ? Math.min(100, Math.round((r.pages_read / b.total_pages) * 100)) : Math.min(100, r.pages_read);
        return { book: b, pct: pct, pagesRead: r.pages_read, readerCount: null };
      });
    } else {
      var bookResults = await Promise.all([
        sbGet('books?select=*&order=title.asc&approved=eq.true'),
        sbGet('progress?select=book_id'),
      ]);
      var books = bookResults[0];
      var progress = bookResults[1];
      var counts = {};
      progress.forEach(function (p) { counts[p.book_id] = (counts[p.book_id] || 0) + 1; });
      state.listData = books.map(function (b) {
        return { book: b, pct: null, pagesRead: null, readerCount: counts[b.id] || 0 };
      });
    }
    renderFilteredList();
  } catch (e) {
    listEl.innerHTML = '<div class="empty">Ma\'lumot yuklanmadi. Internetni tekshiring.</div>';
    console.error(e);
  }
}

function renderFilteredList() {
  var listEl = document.getElementById('bookList');
  var searchEl = document.getElementById('bookListSearch');
  var q = searchEl ? searchEl.value.trim().toLowerCase() : '';
  var items = state.listData || [];
  if (q) {
    items = items.filter(function (it) {
      var t = (it.book.title || '').toLowerCase();
      var a = (it.book.author || '').toLowerCase();
      return t.indexOf(q) !== -1 || a.indexOf(q) !== -1;
    });
  }
  if (!items.length) {
    if (!(state.listData || []).length) {
      listEl.innerHTML = state.tab === 'mine'
        ? '<div class="empty">Hali kitob boshlamadingiz.<br>Pastdagi + tugmasi bilan qo\'shing.</div>'
        : '<div class="empty">Hozircha kitob yo\'q.<br>Birinchi bo\'lib siz qo\'shing!</div>';
    } else {
      listEl.innerHTML = '<div class="empty">Hech narsa topilmadi.</div>';
    }
    return;
  }
  listEl.innerHTML = items.map(function (it) {
    return bookCard(it.book, it.pct, it.pagesRead, it.readerCount);
  }).join('');
}

function bookCard(b, pct, pagesRead, readerCount) {
  var inner;
  if (pct !== null) {
    var metaText = b.total_pages ? (pagesRead + ' bet - ' + pct + '%') : (pagesRead + ' bet');
    inner = '<div class="progress-track"><div class="progress-fill" style="width:' + pct + '%"></div></div>' +
      '<div class="card-meta">' + metaText + '</div>';
  } else {
    inner = '';
  }
  var thumb = b.cover_url ? '<img src="' + b.cover_url + '" class="cover-thumb" />' : '<div class="cover-thumb-placeholder">📖</div>';
  return '<div class="card book-card" data-go="bookDetail" data-id="' + b.id + '">' +
    '<div class="book-card-row">' + thumb +
    '<div class="book-card-info"><div class="card-title">' + escapeHtml(b.title) + '</div>' +
    (b.approved === false ? '<div class="card-meta" style="color:var(--accent-1)">⏳ Tasdiq kutilmoqda</div>' : '') +
    (b.author ? '<div class="card-author">' + escapeHtml(b.author) + '</div>' : '') +
    inner + '</div></div>' +
    '</div>';
}

// ===== Profil (o'zim va boshqalar uchun umumiy) =====
function profileBodyHtml(isOwn, finishedCount, medals, books, finishedSportCount, dailyTargetInfo, sportProgRows) {
  var medalCount = medals.length;
  var litSlots = Math.min(medalCount, 5);
  var bookMedalHtml = '<div class="section-label">📚 Kitob medallari</div><div class="medal-slots-row">';
  for (var i = 1; i <= 5; i++) {
    bookMedalHtml += '<div class="medal-slot-icon' + (i <= litSlots ? ' lit' : '') + '">🏅</div>';
  }
  bookMedalHtml += '</div><div class="medal-count-label">' + medalCount + ' medal</div>';
  var sportMedalHtml = '<div class="section-label" style="margin-top:16px">🏃 Sport medallari</div>' +
    '<div class="medal-slots-row">';
  for (var j = 1; j <= 5; j++) {
    sportMedalHtml += '<div class="medal-slot-icon">🏅</div>';
  }
  sportMedalHtml += '</div><div class="medal-count-label">0 medal (tez orada)</div>';
  var booksHtml = books.length
    ? '<div class="book-list">' + books.map(function (it) { return bookCard(it.book, it.pct, it.pagesRead); }).join('') + '</div>'
    : '<div class="empty">Hali kitob yo\'q.</div>';
  var dailyTargetHtml = '';
  if (isOwn && dailyTargetInfo) {
    if (dailyTargetInfo.phase === 'signup') {
      dailyTargetHtml = '<div class="hint" style="margin-bottom:14px">⏳ "' + escapeHtml(dailyTargetInfo.bookTitle) + '" — hali boshlanmagan. Kunlik me\'yor: <b>' + dailyTargetInfo.dailyLimit + ' bet</b></div>';
    } else {
      var doneToday = dailyTargetInfo.todayRead >= dailyTargetInfo.dailyLimit;
      dailyTargetHtml = '<div class="hint" style="margin-bottom:14px' + (doneToday ? ';color:var(--accent-1)' : '') + '">' +
        (doneToday ? '✅ ' : '📖 ') + '"' + escapeHtml(dailyTargetInfo.bookTitle) + '" — bugungi: <b>' + dailyTargetInfo.todayRead + '/' + dailyTargetInfo.dailyLimit + ' bet</b></div>';
    }
  }
  var sportBooksHtml = sportProgRows.length
    ? '<div class="book-list">' + sportProgRows.map(function (p) {
        var c = p.sport_challenges;
        if (!c) return '';
        return sportCard(c);
      }).join('') + '</div>'
    : '<div class="empty">Hali sport challenj yo\'q.</div>';
  return '<div class="profile-stats">' +
    '<div class="profile-stat-box"><div class="profile-stat-num">' + finishedCount + '</div><div class="profile-stat-label">tugatilgan kitob</div></div>' +
    '<div class="profile-stat-box"><div class="profile-stat-num">' + (finishedSportCount || 0) + '</div><div class="profile-stat-label">tugatilgan sport</div></div>' +
    '</div>' +
    dailyTargetHtml +
    (isOwn ? '<button id="goWalletBtn" class="btn-primary full" style="margin-bottom:18px">🏦 Hamyon</button>' : '') +
    (isOwn ? '' : '<button id="contactBtn" class="btn-primary full" style="margin-bottom:18px">✉️ Yozish</button>') +
    bookMedalHtml + sportMedalHtml +
    '<div class="section-label" style="margin-top:20px">Kitoblari</div>' + booksHtml +
    '<div class="section-label" style="margin-top:20px">Sport challenjlari</div>' + sportBooksHtml;
}

async function loadProfileInto(elId, userId, userName, isOwn) {
  var el = document.getElementById(elId);
  try {
    var profileResults = await Promise.all([
      sbGet('finishers?select=*&user_id=eq.' + userId + '&order=finished_at.desc'),
      sbGet('progress?select=*,books(*)&user_id=eq.' + userId + '&order=updated_at.desc'),
      sbGet('sport_progress?select=*,sport_challenges(*)&user_id=eq.' + userId),
    ]);
    var finishers = profileResults[0];
    var medals = finishers.filter(function (f) { return f.medal === 1 || f.medal === 2; });
    var progRows = profileResults[1];
    var sportProgRows = profileResults[2];
    var todayStr = cohortTodayStr();
    var finishedSportCount = sportProgRows.filter(function (p) {
      if (!p.sport_challenges) return false;
      var ph = sportCohortPhase(p.cohort_start_date, todayStr, p.sport_challenges.duration_days);
      return ph === 'ended';
    }).length;
    var seenBookIds = {};
    var books = progRows.map(function (r) {
      var b = r.books;
      seenBookIds[b.id] = true;
      var pct = b.total_pages ? Math.min(100, Math.round((r.pages_read / b.total_pages) * 100)) : Math.min(100, r.pages_read);
      return { book: b, pct: pct, pagesRead: r.pages_read };
    });
    var missingFinisherBookIds = finishers.map(function (f) { return f.book_id; }).filter(function (id) { return !seenBookIds[id]; });
    if (missingFinisherBookIds.length) {
      try {
        var extraBooks = await sbGet('books?select=*&id=in.(' + missingFinisherBookIds.join(',') + ')');
        extraBooks.forEach(function (b) {
          books.push({ book: b, pct: 100, pagesRead: b.total_pages || 0 });
        });
      } catch (e) { console.error(e); }
    }
    var dailyTargetInfo = null;
    if (isOwn) {
      var todayStr = cohortTodayStr();
      for (var i = 0; i < progRows.length; i++) {
        var pr = progRows[i];
        if (!pr.cohort_start_date || !pr.books) continue;
        var rd = bookReadingDays(pr.books);
        var ph = cohortPhase(pr.cohort_start_date, todayStr, rd);
        if (ph !== 'reading' && ph !== 'signup' && ph !== 'closing') continue;
        var todayRead = 0;
        if (ph === 'reading') {
          var todayNotes = await sbGet('reading_notes?select=pages_from,pages_read,created_at&book_id=eq.' + pr.book_id + '&user_id=eq.' + ME.id);
          todayNotes.forEach(function (n) {
            var noteDay = localDateStr(new Date(new Date(n.created_at).getTime() - 4 * 3600000));
            if (noteDay === todayStr) todayRead += Math.max(0, (n.pages_read || 0) - (n.pages_from || 0));
          });
        }
        dailyTargetInfo = { bookTitle: pr.books.title, todayRead: todayRead, dailyLimit: COHORT_SUGGESTED_DAILY_PAGES, phase: ph };
        break;
      }
    }
    el.innerHTML = profileBodyHtml(isOwn, finishers.length, medals, books, finishedSportCount, dailyTargetInfo, sportProgRows);
    if (isOwn) {
      document.getElementById('goWalletBtn').addEventListener('click', function () {
        state.view = 'wallet';
        render();
      });
    }
    if (!isOwn) {
      document.getElementById('contactBtn').addEventListener('click', async function () {
        var btn = this;
        if (iAmBlocked) { showAlert('Siz blok qilingansiz.'); return; }
        btn.disabled = true;
        try {
          await sbPost('contact_requests', { requester_id: ME.id, requester_name: ME.name, target_id: userId, target_name: userName });
          vibrate('light');
          showAlert("So'rov yuborildi. " + userName + " rozi bo'lsa, bot orqali xabar olasiz.");
        } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); btn.disabled = false; }
      });
    }
  } catch (e) {
    el.innerHTML = '<div class="empty">Ma\'lumot yuklanmadi.</div>';
    console.error(e);
  }
}

async function renderMyProfile() {
  setBackButton(false);
  renderShell(
    '<div class="profile-header">' + avatarHtml(ME.photoUrl, 76) + '<div class="profile-header-name">' + escapeHtml(ME.name) + '</div></div>' +
    '<div id="profileStreakBadge"></div>' +
    '<div id="profileBody"><div class="loading">Yuklanmoqda...</div></div>'
  );
  loadStreakBadge('profileStreakBadge');
  await loadProfileInto('profileBody', ME.id, ME.name, true);
}

// ===== Hamyon sahifasi =====
async function renderWallet() {
  setBackButton(true, function () { state.view = 'profile'; render(); });
  renderShell(
    '<div class="header"><button class="back" data-go="profile">←</button><div class="h-title">🏦 Hamyon</div></div>' +
    '<div id="walletBody"><div class="loading">Yuklanmoqda...</div></div>',
    { fab: false }
  );
  await loadWalletBody();
}

async function loadWalletBody() {
  var el = document.getElementById('walletBody');
  try {
    var results = await Promise.all([
      getOrCreateWallet(ME.id, ME.name, ME.username),
      sbGet('qovun_purchase_requests?select=*&user_id=eq.' + ME.id + '&order=created_at.desc&limit=30'),
      sbGet('withdrawal_requests?select=*&user_id=eq.' + ME.id + '&order=created_at.desc&limit=30'),
    ]);
    var wallet = results[0];
    var purchases = results[1].map(function (r) { r._type = 'purchase'; return r; });
    var withdrawals = results[2].map(function (r) { r._type = 'withdrawal'; return r; });
    var history = purchases.concat(withdrawals).sort(function (a, b) { return new Date(b.created_at) - new Date(a.created_at); });

    var historyHtml = history.length ? history.map(function (r) {
      var statusEmoji = r.status === 'pending' ? '⏳' : (r.status === 'approved' || r.status === 'paid') ? '✅' : '❌';
      var statusText = r.status === 'pending' ? 'Kutilmoqda' : r.status === 'approved' ? 'Tasdiqlandi' : r.status === 'paid' ? "To'landi" : ('Rad etildi' + (r.reject_reason ? ' (' + escapeHtml(r.reject_reason) + ')' : ''));
      var currencyLabel = r.currency === 'proteincha' ? 'proteincha' : 'qovuncha';
      var line = r._type === 'purchase'
        ? (currencyLabel.charAt(0).toUpperCase() + currencyLabel.slice(1)) + ' sotib olish: ' + r.qovun_amount + ' ta'
        : "Pulga aylantirish: " + r.amount + ' ta ' + currencyLabel + ' → ' + r.money_amount + " so'm";
      return '<div class="admin-row"><div class="admin-row-info"><div class="reader-name">' + line + '</div>' +
        '<div class="reader-note">' + statusEmoji + ' ' + statusText + '</div>' +
        '<div class="reader-note">' + formatDate(r.created_at) + '</div></div></div>';
    }).join('') : '<div class="empty">Tarix yo\'q.</div>';

    el.innerHTML =
      '<div class="profile-stats">' +
      '<div class="profile-stat-box"><div class="profile-stat-num" style="font-size:18px">' + formatNumber(wallet.qovun_balance) + '</div><div class="profile-stat-label">qovuncha</div></div>' +
      '<div class="profile-stat-box"><div class="profile-stat-num">' + (wallet.proteincha_balance || 0) + '</div><div class="profile-stat-label">proteincha</div></div>' +
      '</div>' +
      '<div style="display:flex;gap:8px;margin-top:10px">' +
      '<button id="buyBtn" class="btn-small" style="flex:1">💰 Sotib olish</button>' +
      '<button id="withdrawBtn" class="btn-small" style="flex:1">💸 Pulga aylantirish</button>' +
      '</div>' +
      '<div id="buyForm" style="display:none;margin-top:10px"></div>' +
      '<div id="withdrawForm" style="display:none;margin-top:10px"></div>' +
      '<div class="section-label" style="margin-top:20px">Tarix</div>' + historyHtml;

    var buyBtn = document.getElementById('buyBtn');
    var buyForm = document.getElementById('buyForm');
    var withdrawFormEl = document.getElementById('withdrawForm');
    buyBtn.addEventListener('click', function () {
      var showing = buyForm.style.display !== 'none';
      buyForm.style.display = showing ? 'none' : 'block';
      withdrawFormEl.style.display = 'none';
      if (!showing) {
        buyForm.innerHTML =
          '<select id="buyCurrency" class="input">' +
          '<option value="qovun">Qovuncha</option><option value="proteincha">Proteincha</option>' +
          '</select>' +
          '<input id="buyAmount" class="input" type="number" min="1" placeholder="Nechta sotib olmoqchisiz?" style="margin-top:8px" />' +
          '<div id="buyAmountSom" style="font-size:12px;color:var(--accent-1);margin-top:4px;font-weight:600"></div>' +
          '<div class="hint" style="margin-top:8px">To\'lov uchun karta:<br><div style="display:flex;align-items:center;gap:8px;margin-top:4px"><b id="paymentCardText">' + PAYMENT_CARD + '</b><button type="button" id="copyCardBtn" class="btn-small" style="flex-shrink:0">📋 Nusxalash</button></div><div style="margin-top:6px">To\'lov qilib, kvitansiya rasmini yuklang. Kvitansiyada SANA, SOAT va SUMMA aniq ko\'rinib turishi shart.</div></div>' +
          '<label class="file-btn" for="buyReceiptInput" style="margin-top:8px">🧾 Kvitansiya yuklash</label>' +
          '<input type="file" id="buyReceiptInput" accept="image/*" style="display:none" />' +
          '<div id="buyReceiptPreview"></div>' +
          '<button id="submitBuyBtn" class="btn-primary full" style="margin-top:8px">Yuborish</button>';
        var updateBuySom = function () {
          var amt = parseInt(document.getElementById('buyAmount').value, 10) || 0;
          var cur = document.getElementById('buyCurrency').value;
          var som = cur === 'proteincha' ? amt * PROTEINCHA_PER_SOM : amt * QOVUN_PER_SOM;
          document.getElementById('buyAmountSom').textContent = amt > 0 ? ('= ' + formatSom(som)) : '';
        };
        document.getElementById('buyAmount').addEventListener('input', updateBuySom);
        document.getElementById('buyCurrency').addEventListener('change', updateBuySom);
        document.getElementById('copyCardBtn').addEventListener('click', function () {
          var text = PAYMENT_CARD;
          var btnEl = this;
          function done() { vibrate('light'); var old = btnEl.textContent; btnEl.textContent = '✅ Nusxalandi'; setTimeout(function () { btnEl.textContent = old; }, 1500); }
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done).catch(function () { showAlert("Nusxalab bo'lmadi. Qo'lda yozib oling: " + text); });
          } else { showAlert("Nusxalab bo'lmadi. Qo'lda yozib oling: " + text); }
        });
        document.getElementById('buyReceiptInput').addEventListener('change', function () {
          var f = this.files[0];
          var prevEl = document.getElementById('buyReceiptPreview');
          if (!f) { prevEl.innerHTML = ''; return; }
          prevEl.innerHTML = '<img src="' + URL.createObjectURL(f) + '" class="note-photo-img" />';
        });
        document.getElementById('submitBuyBtn').addEventListener('click', async function () {
          var currency = document.getElementById('buyCurrency').value;
          var amt = parseInt(document.getElementById('buyAmount').value, 10);
          if (!amt || amt <= 0) { showAlert("Miqdorni to'g'ri kiriting."); return; }
          var receiptFile = document.getElementById('buyReceiptInput').files[0];
          if (!receiptFile) { showAlert('Kvitansiya rasmini yuklang.'); return; }
          var sBtn = this; sBtn.disabled = true; sBtn.textContent = 'Yuborilmoqda...';
          try {
            var ext = (receiptFile.name.split('.').pop() || 'jpg').toLowerCase();
            var receiptUrl = await sbUploadFile(HUJJATLAR_BUCKET, 'receipts/' + Date.now() + '_' + Math.random().toString(36).slice(2) + '.' + ext, receiptFile);
            await sbPost('qovun_purchase_requests', { user_id: ME.id, user_name: ME.name, username: ME.username, qovun_amount: amt, currency: currency, receipt_url: receiptUrl });
            vibrate('light');
            showAlert("So'rovingiz yuborildi. Admin tekshirib tasdiqlagach, hisobingizga qo'shiladi.");
            renderWallet();
          } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); sBtn.disabled = false; sBtn.textContent = 'Yuborish'; }
        });
      }
    });

    var withdrawBtn = document.getElementById('withdrawBtn');
    withdrawBtn.addEventListener('click', function () {
      var showing = withdrawFormEl.style.display !== 'none';
      withdrawFormEl.style.display = showing ? 'none' : 'block';
      buyForm.style.display = 'none';
      if (!showing) {
        withdrawFormEl.innerHTML =
          '<div class="hint">Kurs: 1 qovuncha = ' + QOVUN_PER_SOM + " so'm, 1 proteincha = " + PROTEINCHA_PER_SOM + " so'm</div>" +
          '<select id="withdrawCurrency" class="input" style="margin-top:8px">' +
          '<option value="qovun">Qovuncha</option><option value="proteincha">Proteincha</option>' +
          '</select>' +
          '<input id="withdrawAmount" class="input" type="number" min="1" placeholder="Miqdor" />' +
          '<div id="withdrawAmountSom" style="font-size:12px;color:var(--accent-1);margin-top:4px;font-weight:600"></div>' +
          '<input id="withdrawCardHolder" class="input" placeholder="Karta egasining F.I.Sh" />' +
          '<input id="withdrawCard" class="input" placeholder="Karta raqamingiz" />' +
          '<button id="submitWithdrawBtn" class="btn-primary full" style="margin-top:8px">So\'rov yuborish</button>';
        var updateWithdrawSom = function () {
          var amt = parseInt(document.getElementById('withdrawAmount').value, 10) || 0;
          var cur = document.getElementById('withdrawCurrency').value;
          var som = cur === 'proteincha' ? amt * PROTEINCHA_PER_SOM : amt * QOVUN_PER_SOM;
          document.getElementById('withdrawAmountSom').textContent = amt > 0 ? ('= ' + formatSom(som)) : '';
        };
        document.getElementById('withdrawAmount').addEventListener('input', updateWithdrawSom);
        document.getElementById('withdrawCurrency').addEventListener('change', updateWithdrawSom);
        document.getElementById('submitWithdrawBtn').addEventListener('click', async function () {
          var currency = document.getElementById('withdrawCurrency').value;
          var amt = parseInt(document.getElementById('withdrawAmount').value, 10);
          var holder = document.getElementById('withdrawCardHolder').value.trim();
          var card = document.getElementById('withdrawCard').value.trim();
          if (!amt || amt <= 0) { showAlert("Miqdorni to'g'ri kiriting."); return; }
          if (!holder) { showAlert('Karta egasining ismini kiriting.'); return; }
          if (!card) { showAlert('Karta raqamingizni kiriting.'); return; }
          var bal = currency === 'qovun' ? wallet.qovun_balance : wallet.proteincha_balance;
          if (amt > bal) { showAlert('Balansingizda yetarli mablag\' yo\'q.'); return; }
          var moneyAmount = currency === 'qovun' ? amt * QOVUN_PER_SOM : amt * PROTEINCHA_PER_SOM;
          var sBtn = this; sBtn.disabled = true; sBtn.textContent = 'Yuborilmoqda...';
          try {
            await sbPost('withdrawal_requests', { user_id: ME.id, user_name: ME.name, username: ME.username, currency: currency, amount: amt, money_amount: moneyAmount, card_number: card, card_holder_name: holder });
            vibrate('light');
            showAlert("So'rovingiz yuborildi. Admin to'lab, tasdiqlagach mablag' hisobingizdan yechiladi.");
            renderWallet();
          } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); sBtn.disabled = false; sBtn.textContent = "So'rov yuborish"; }
        });
      }
    });
  } catch (e) { el.innerHTML = '<div class="empty">Yuklanmadi.</div>'; console.error(e); }
}

async function renderUserBooks() {
  setBackButton(true, function () { state.view = 'bookDetail'; state.detailTab = 'readers'; render(); });
  renderShell(
    '<div class="header"><button class="back" data-go="bookDetail" data-id="' + state.bookId + '">←</button></div>' +
    '<div class="profile-header">' + avatarHtml(null, 76) + '<div class="profile-header-name">' + escapeHtml(state.viewUserName) + '</div></div>' +
    '<div id="profileBody"><div class="loading">Yuklanmoqda...</div></div>'
  );
  await loadProfileInto('profileBody', state.viewUserId, state.viewUserName, false);
}

// ===== Admin panel =====
async function renderAdmin() {
  setBackButton(true, function () { isAdminMode = false; state.view = 'modeSelect'; render(); });
  app.innerHTML =
    '<div class="screen">' +
    '<div class="header"><div class="h-title">Admin</div><button class="back" id="adminExitBtn" style="margin-left:auto">✕</button></div>' +
    '<div class="segment" style="flex-wrap:wrap">' +
    '<button class="seg-btn' + (state.adminTab === 'dashboard' ? ' active' : '') + '" data-admintab="dashboard">Dashboard</button>' +
    '<button class="seg-btn' + (state.adminTab === 'users' ? ' active' : '') + '" data-admintab="users">Foydalanuvchilar<span id="badgeUsers"></span></button>' +
    '<button class="seg-btn' + (state.adminTab === 'books' ? ' active' : '') + '" data-admintab="books">Kitoblar<span id="badgeBooks"></span></button>' +
    '<button class="seg-btn' + (state.adminTab === 'sport' ? ' active' : '') + '" data-admintab="sport">Sport<span id="badgeSport"></span></button>' +
    '<button class="seg-btn' + (state.adminTab === 'transactions' ? ' active' : '') + '" data-admintab="transactions">Tranzaksiyalar<span id="badgeTx"></span></button>' +
    '<button class="seg-btn' + (state.adminTab === 'withdrawals' ? ' active' : '') + '" data-admintab="withdrawals">Pul chiqarish<span id="badgeWd"></span></button>' +
    '</div>' +
    '<div id="adminBody"><div class="loading">Yuklanmoqda...</div></div>' +
    '</div>';
  document.getElementById('adminExitBtn').addEventListener('click', function () { isAdminMode = false; if (_adminBadgeInterval) { clearInterval(_adminBadgeInterval); _adminBadgeInterval = null; } state.view = 'modeSelect'; render(); });
  document.querySelectorAll('[data-admintab]').forEach(function (b) {
    b.addEventListener('click', function () { state.adminTab = b.dataset.admintab; renderAdmin(); });
  });
  loadAdminBadgeCounts();
  if (_adminBadgeInterval) clearInterval(_adminBadgeInterval);
  _adminBadgeInterval = setInterval(loadAdminBadgeCounts, 5000);
  if (state.adminTab === 'books') await loadAdminBooks();
  else if (state.adminTab === 'sport') await loadAdminSport();
  else if (state.adminTab === 'transactions') await loadAdminTransactions();
  else if (state.adminTab === 'withdrawals') await loadAdminWithdrawals();
  else if (state.adminTab === 'dashboard') await loadAdminDashboard();
  else await loadAdminUsers();
}

async function loadAdminBadgeCounts() {
  try {
    var stateRows = await sbGet('admin_state?select=*&id=eq.1');
    var lastSeen = (stateRows[0] && stateRows[0].users_last_seen_at) || '1970-01-01T00:00:00Z';
    var results = await Promise.all([
      sbGet('books?select=id&approved=eq.false'),
      sbGet('qovun_purchase_requests?select=id&status=eq.pending'),
      sbGet('withdrawal_requests?select=id&status=eq.pending'),
      sbGet('wallets?select=id&created_at=gt.' + encodeURIComponent(lastSeen)),
      sbGet('sport_challenges?select=id&approved=eq.false'),
    ]);
    function badgeHtml(n) { return n > 0 ? ' <span style="background:var(--danger);color:#fff;border-radius:10px;padding:1px 7px;font-size:11px;margin-left:4px">' + n + '</span>' : ''; }
    var bB = document.getElementById('badgeBooks');
    var bT = document.getElementById('badgeTx');
    var bW = document.getElementById('badgeWd');
    var bU = document.getElementById('badgeUsers');
    var bS = document.getElementById('badgeSport');
    if (bB) bB.innerHTML = badgeHtml(results[0].length);
    if (bT) bT.innerHTML = badgeHtml(results[1].length);
    if (bW) bW.innerHTML = badgeHtml(results[2].length);
    if (bU) bU.innerHTML = badgeHtml(results[3].length);
    if (bS) bS.innerHTML = badgeHtml(results[4].length);
  } catch (e) { console.error(e); }
}

async function loadAllUsersMerged() {
  var map = {};
  function consider(id, name, date) {
    if (id == null) return;
    if (!map[id]) map[id] = { id: id, name: name || ('Foydalanuvchi ' + id), firstSeen: date };
    else {
      if (name) map[id].name = name;
      if (date && new Date(date) < new Date(map[id].firstSeen)) map[id].firstSeen = date;
    }
  }
  var results = await Promise.all([
    sbGet('progress?select=user_id,user_name,started_at'),
    sbGet('comments?select=user_id,user_name,created_at'),
    sbGet('books?select=created_by_id,created_by_name,created_at'),
    sbGet('wallets?select=user_id,user_name,created_at'),
  ]);
  results[0].forEach(function (p) { consider(p.user_id, p.user_name, p.started_at); });
  results[1].forEach(function (c) { consider(c.user_id, c.user_name, c.created_at); });
  results[2].forEach(function (b) { consider(b.created_by_id, b.created_by_name, b.created_at); });
  results[3].forEach(function (w) { consider(w.user_id, w.user_name, w.created_at); });
  return Object.keys(map).map(function (k) { return map[k]; }).sort(function (a, b) { return new Date(b.firstSeen) - new Date(a.firstSeen); });
}

async function loadAdminUsers() {
  var el = document.getElementById('adminBody');
  try {
    sbPost('admin_state?on_conflict=id', { id: 1, users_last_seen_at: new Date().toISOString() }, 'resolution=merge-duplicates').catch(function (e) { console.error(e); });
    var badgeUsersEl = document.getElementById('badgeUsers');
    if (badgeUsersEl) badgeUsersEl.innerHTML = '';
    var usersAndBlocked = await Promise.all([loadAllUsersMerged(), sbGet('blocked_users?select=user_id')]);
    _adminUsersCache = usersAndBlocked[0];
    var blockedRows = usersAndBlocked[1];
    _adminBlockedSet = {};
    blockedRows.forEach(function (b) { _adminBlockedSet[b.user_id] = true; });
    el.innerHTML = '<input id="adminUserSearch" class="input" placeholder="Foydalanuvchi qidirish (ism yoki ID)..." style="margin-bottom:10px" />' +
      '<div class="hint" style="margin-bottom:6px">Qo\'shilgan sana oralig\'i</div>' +
      '<div style="display:flex;gap:8px;margin-bottom:14px"><input id="adminUserDateFrom" class="input" type="date" style="flex:1" /><input id="adminUserDateTo" class="input" type="date" style="flex:1" /></div>' +
      '<div id="adminUsersList"></div>';
    document.getElementById('adminUserSearch').addEventListener('input', renderAdminUsersList);
    document.getElementById('adminUserDateFrom').addEventListener('change', renderAdminUsersList);
    document.getElementById('adminUserDateTo').addEventListener('change', renderAdminUsersList);
    renderAdminUsersList();
  } catch (e) { el.innerHTML = '<div class="empty">Yuklanmadi.</div>'; console.error(e); }
}

function renderAdminUsersList() {
  var listEl = document.getElementById('adminUsersList');
  var searchEl = document.getElementById('adminUserSearch');
  var fromEl = document.getElementById('adminUserDateFrom');
  var toEl = document.getElementById('adminUserDateTo');
  var q = searchEl ? searchEl.value.trim().toLowerCase() : '';
  var fromVal = fromEl ? fromEl.value : '';
  var toVal = toEl ? toEl.value : '';
  var users = _adminUsersCache;
  if (q) {
    users = users.filter(function (u) {
      return (u.name || '').toLowerCase().indexOf(q) !== -1 || String(u.id).indexOf(q) !== -1;
    });
  }
  if (fromVal) users = users.filter(function (u) { return u.firstSeen && u.firstSeen.slice(0, 10) >= fromVal; });
  if (toVal) users = users.filter(function (u) { return u.firstSeen && u.firstSeen.slice(0, 10) <= toVal; });
  listEl.innerHTML = users.length ? users.map(function (u) {
    var isBlocked = !!_adminBlockedSet[u.id];
    return '<div class="admin-row"><div class="admin-row-info"><div class="reader-name">' + escapeHtml(u.name) + '</div>' +
      '<div class="reader-note">ID: ' + u.id + ' · 📅 ' + formatDateTime(u.firstSeen) + '</div></div>' +
      '<div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end">' +
      '<button class="btn-small' + (isBlocked ? ' danger' : '') + '" data-block-id="' + u.id + '" data-blocked="' + (isBlocked ? '1' : '0') + '">' + (isBlocked ? "Blokdan chiqar" : "Blokla") + '</button>' +
      '<button class="btn-small" data-add-qovun="' + u.id + '" data-name="' + escapeHtml(u.name) + '">💰 Qovuncha qo\'shish</button>' +
      '</div></div>';
  }).join('') : '<div class="empty">Foydalanuvchi topilmadi.</div>';
  document.querySelectorAll('[data-add-qovun]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var id = parseInt(btn.dataset.addQovun, 10);
      customPrompt(btn.dataset.name + " uchun nechta qovuncha qo'shamiz? (ayirish uchun manfiy son kiriting)", async function (raw) {
        if (raw === null) return;
        var amt = parseInt(raw, 10);
        if (isNaN(amt)) { showAlert("Noto'g'ri son."); return; }
        try {
          await adjustWallet(id, amt, 0);
          vibrate('light');
          showAlert('Bajarildi.');
        } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
      });
    });
  });
  document.querySelectorAll('[data-block-id]').forEach(function (btn) {
    btn.addEventListener('click', async function () {
      var id = parseInt(btn.dataset.blockId, 10);
      var wasBlocked = btn.dataset.blocked === '1';
      try {
        if (wasBlocked) { await sbDelete('blocked_users?user_id=eq.' + id); delete _adminBlockedSet[id]; }
        else { await sbPost('blocked_users?on_conflict=user_id', { user_id: id }, 'resolution=merge-duplicates,return=representation'); _adminBlockedSet[id] = true; }
        vibrate('light');
        renderAdminUsersList();
      } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
    });
  });
}

async function loadAdminSport() {
  var el = document.getElementById('adminBody');
  try {
    var challenges = await sbGet('sport_challenges?select=*&order=created_at.desc');
    challenges = challenges.slice().sort(function (a, b) {
      if (a.approved === b.approved) return (a.title || '').localeCompare(b.title || '');
      return a.approved ? 1 : -1;
    });
    el.innerHTML = challenges.length ? challenges.map(function (c) {
      return '<div class="card" style="margin-bottom:10px"><div class="book-card-row">' +
        (c.cover_url ? '<img src="' + c.cover_url + '" class="cover-thumb" />' : '<div class="cover-thumb-placeholder">🏃</div>') +
        '<div class="book-card-info"><div class="card-title">' + escapeHtml(c.title) + '</div>' +
        (c.approved === false ? '<div class="reader-note" style="color:var(--danger);font-weight:600">⏳ Tasdiq kutilmoqda</div>' : '') +
        '<div class="reader-note">👤 ' + escapeHtml(c.created_by_name || 'Noma\'lum') + '</div>' +
        '<div class="reader-note">⏱ ' + c.duration_days + ' kun</div>' +
        '<div class="reader-note">📅 ' + formatDateTime(c.created_at) + '</div>' +
        '<div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">' +
        (c.approved === false ? '<button class="btn-small" data-approve-sport="' + c.id + '" data-creator="' + c.created_by_id + '" data-title="' + escapeHtml(c.title) + '">✅ Tasdiqlash</button>' : '') +
        '<button class="btn-small" data-edit-sport="' + c.id + '">Tahrirlash</button>' +
        '<button class="btn-small danger" data-delete-sport="' + c.id + '">O\'chirish</button>' +
        '</div></div></div></div>';
    }).join('') : '<div class="empty">Sport challenj yo\'q.</div>';

    document.querySelectorAll('[data-approve-sport]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        confirmAction("Bu sport challenjni tasdiqlaysizmi?", async function () {
          try {
            var id = btn.dataset.approveSport;
            await sbPatch('sport_challenges?id=eq.' + id, { approved: true });
            await sbPost('sport_approval_notifications', { challenge_id: id, creator_id: btn.dataset.creator, challenge_title: btn.dataset.title });
            vibrate('light');
            loadAdminSport();
            loadAdminBadgeCounts();
          } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
        });
      });
    });

    document.querySelectorAll('[data-edit-sport]').forEach(function (btn) {
      btn.addEventListener('click', async function (e) {
        e.stopPropagation();
        var id = btn.dataset.editSport;
        var c = challenges.find(function (x) { return String(x.id) === String(id); });
        if (!c) return;
        var exercises = await sbGet('sport_exercises?select=*&challenge_id=eq.' + id + '&order=sort_order.asc');
        var hasMembers = (await sbGet('sport_progress?select=id&challenge_id=eq.' + id)).length > 0;
        renderAdminSportEdit(c, exercises, hasMembers);
      });
    });

    document.querySelectorAll('[data-delete-sport]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        confirmAction("Bu sport challenjni o'chirasizmi?", async function () {
          try {
            await sbDelete('sport_challenges?id=eq.' + btn.dataset.deleteSport);
            vibrate('medium');
            loadAdminSport();
            loadAdminBadgeCounts();
          } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
        });
      });
    });
  } catch (e) { el.innerHTML = '<div class="empty">Yuklanmadi.</div>'; console.error(e); }
}

function renderAdminSportEdit(c, exercises, hasMembers) {
  var el = document.getElementById('adminBody');
  var exList = exercises.map(function (e) { return { id: e.id, name: e.name, total: e.total_count, daily: e.daily_count }; });

  function renderExList() {
    var listEl = document.getElementById('adminSportExList');
    if (!listEl) return;
    listEl.innerHTML = exList.map(function (e, i) {
      return '<div style="background:var(--bg);border-radius:10px;padding:10px;margin-bottom:8px">' +
        '<input class="input adex-name" type="text" placeholder="Mashq nomi" value="' + escapeHtml(e.name) + '" data-idx="' + i + '" />' +
        '<div style="display:flex;gap:8px">' +
        '<input class="input adex-total" type="number" min="1" placeholder="Jami soni" value="' + (e.total || '') + '" data-idx="' + i + '" style="flex:1" />' +
        '<input class="input adex-daily" type="number" min="1" placeholder="Kuniga" value="' + (e.daily || '') + '" data-idx="' + i + '" style="flex:1" />' +
        '</div>' +
        '<button class="remove-link adex-remove" data-idx="' + i + '">O\'chirish</button>' +
        '</div>';
    }).join('') || '<div class="empty" style="font-size:13px">Hali mashq yo\'q</div>';
    listEl.querySelectorAll('.adex-name').forEach(function (inp) { inp.addEventListener('input', function () { exList[inp.dataset.idx].name = inp.value; }); });
    listEl.querySelectorAll('.adex-total').forEach(function (inp) { inp.addEventListener('input', function () { exList[inp.dataset.idx].total = parseInt(inp.value, 10) || 0; }); });
    listEl.querySelectorAll('.adex-daily').forEach(function (inp) { inp.addEventListener('input', function () { exList[inp.dataset.idx].daily = parseInt(inp.value, 10) || 0; }); });
    listEl.querySelectorAll('.adex-remove').forEach(function (btn) { btn.addEventListener('click', function () { exList.splice(parseInt(btn.dataset.idx, 10), 1); renderExList(); }); });
  }

  el.innerHTML =
    '<div class="form" style="padding:0">' +
    '<div class="section-label">Asosiy ma\'lumotlar</div>' +
    '<input id="adminSportTitle" class="input" value="' + escapeHtml(c.title) + '" placeholder="Sarlavha" />' +
    '<textarea id="adminSportDesc" class="input" rows="2" placeholder="Tavsif">' + escapeHtml(c.description || '') + '</textarea>' +
    '<label class="file-btn" for="adminSportCoverInput">📷 Yangi rasm (ixtiyoriy)</label>' +
    '<input type="file" id="adminSportCoverInput" accept="image/*" style="display:none" />' +
    '<div id="adminSportCoverPreview">' + (c.cover_url ? '<img src="' + c.cover_url + '" class="note-photo-img" />' : '') + '</div>' +
    '<input id="adminSportDuration" class="input" type="number" min="1" max="30" value="' + c.duration_days + '" placeholder="Necha kun?" ' + (hasMembers ? 'disabled title="Qatnashuvchisi bor — kun sonini o\'zgartirish mumkin emas"' : '') + ' />' +
    (hasMembers ? '<div class="hint" style="color:var(--danger)">⚠️ Qatnashuvchisi bor — kun sonini o\'zgartirish bloklanган.</div>' : '') +
    '<div class="section-label" style="margin-top:16px">Mashqlar</div>' +
    '<div id="adminSportExList"></div>' +
    '<button id="adminAddExBtn" class="btn-small" style="margin-top:8px">+ Mashq qo\'shish</button>' +
    '<div style="display:flex;gap:8px;margin-top:16px">' +
    '<button id="adminSportSaveBtn" class="btn-primary" style="flex:1">Saqlash</button>' +
    '<button id="adminSportCancelBtn" class="btn-small" style="flex:1">Bekor</button>' +
    '</div></div>';

  renderExList();

  document.getElementById('adminSportCoverInput').addEventListener('change', function () {
    var f = this.files[0];
    if (!f) return;
    document.getElementById('adminSportCoverPreview').innerHTML = '<img src="' + URL.createObjectURL(f) + '" class="note-photo-img" />';
  });
  document.getElementById('adminAddExBtn').addEventListener('click', function () {
    exList.push({ id: null, name: '', total: 0, daily: 0 });
    renderExList();
  });
  document.getElementById('adminSportCancelBtn').addEventListener('click', function () { loadAdminSport(); });
  document.getElementById('adminSportSaveBtn').addEventListener('click', async function () {
    var title = document.getElementById('adminSportTitle').value.trim();
    if (!title) { showAlert("Sarlavha kiriting."); return; }
    var duration = hasMembers ? c.duration_days : parseInt(document.getElementById('adminSportDuration').value, 10);
    if (!duration || duration < 1) { showAlert("Kun sonini kiriting."); return; }
    for (var e of exList) {
      if (!e.name || !e.total || !e.daily) { showAlert("Barcha mashqlar uchun nom, jami va kunlik son kiriting."); return; }
    }
    var btn = this; btn.disabled = true; btn.textContent = 'Saqlanmoqda...';
    try {
      var coverUrl = c.cover_url;
      var coverFile = document.getElementById('adminSportCoverInput').files[0];
      if (coverFile) {
        var ext = (coverFile.name.split('.').pop() || 'jpg').toLowerCase();
        coverUrl = await sbUploadFile(HUJJATLAR_BUCKET, 'sport/covers/' + Date.now() + '.' + ext, coverFile);
      }
      await sbPatch('sport_challenges?id=eq.' + c.id, { title: title, description: document.getElementById('adminSportDesc').value.trim() || null, cover_url: coverUrl, duration_days: duration });
      await sbDelete('sport_exercises?challenge_id=eq.' + c.id);
      for (var i = 0; i < exList.length; i++) {
        await sbPost('sport_exercises', { challenge_id: c.id, name: exList[i].name, total_count: exList[i].total, daily_count: exList[i].daily, sort_order: i });
      }
      vibrate('light');
      showAlert("Saqlandi!");
      loadAdminSport();
    } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); btn.disabled = false; btn.textContent = 'Saqlash'; }
  });
}

async function loadAdminDashboard() {
  var el = document.getElementById('adminBody');
  el.innerHTML =
    '<div class="segment" style="margin-bottom:14px">' +
    '<button class="seg-btn active" data-period="today">Bugun</button>' +
    '<button class="seg-btn" data-period="week">Hafta</button>' +
    '<button class="seg-btn" data-period="month">Oy</button>' +
    '</div>' +
    '<div id="dashboardBody"><div class="loading">Yuklanmoqda...</div></div>';
  document.querySelectorAll('[data-period]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('[data-period]').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      renderDashboardBody(btn.dataset.period);
    });
  });
  renderDashboardBody('today');
}

async function renderDashboardBody(period) {
  var bodyEl = document.getElementById('dashboardBody');
  bodyEl.innerHTML = '<div class="loading">Yuklanmoqda...</div>';
  try {
    var since = new Date();
    if (period === 'today') since.setHours(0, 0, 0, 0);
    else if (period === 'week') since.setDate(since.getDate() - 7);
    else since.setMonth(since.getMonth() - 1);
    var sinceIso = since.toISOString();

    var results = await Promise.all([
      sbGet('books?select=id,title,created_by_name&created_at=gte.' + sinceIso),
      sbGet('progress?select=user_id,user_name,started_at&started_at=gte.' + sinceIso + '&order=started_at.desc'),
      sbGet('treasury?select=*&id=eq.1'),
    ]);
    var newBooks = results[0];
    var newJoinsRaw = results[1];
    var treasury = results[2][0] || { qovun_balance: 0 };
    var seenUsers = {};
    var newUsers = [];
    newJoinsRaw.forEach(function (p) {
      if (!seenUsers[p.user_id]) { seenUsers[p.user_id] = true; newUsers.push(p); }
    });

    bodyEl.innerHTML =
      '<div class="profile-stats">' +
      '<div class="profile-stat-box"><div class="profile-stat-num">' + newBooks.length + '</div><div class="profile-stat-label">yangi challenj</div></div>' +
      '<div class="profile-stat-box"><div class="profile-stat-num">' + newUsers.length + '</div><div class="profile-stat-label">yangi qatnashuvchi</div></div>' +
      '</div>' +
      '<div class="profile-stats" style="margin-top:8px">' +
      '<div class="profile-stat-box"><div class="profile-stat-num" style="font-size:18px">' + qovunLabel(treasury.qovun_balance) + '</div><div class="profile-stat-label">ilova xazinasi</div></div>' +
      '</div>' +
      '<div class="section-label" style="margin-top:18px">Yangi challenjlar</div>' +
      (newBooks.length ? newBooks.map(function (b) {
        return '<div class="admin-row"><div class="admin-row-info"><div class="reader-name">' + escapeHtml(b.title) + '</div><div class="reader-note">Yaratuvchi: ' + escapeHtml(b.created_by_name || '') + '</div></div></div>';
      }).join('') : '<div class="empty">Yo\'q.</div>') +
      '<div class="section-label" style="margin-top:18px">Yangi qatnashuvchilar</div>' +
      (newUsers.length ? newUsers.map(function (u) {
        return '<div class="admin-row"><div class="admin-row-info"><div class="reader-name">' + escapeHtml(u.user_name) + '</div><div class="reader-note">' + formatDate(u.started_at) + '</div></div></div>';
      }).join('') : '<div class="empty">Yo\'q.</div>');
  } catch (e) { bodyEl.innerHTML = '<div class="empty">Yuklanmadi.</div>'; console.error(e); }
}

async function loadAdminTransactions() {
  var el = document.getElementById('adminBody');
  try {
    var results = await Promise.all([
      sbGet('qovun_purchase_requests?select=*&status=eq.pending&order=created_at.desc'),
      sbGet('qovun_purchase_requests?select=*&status=neq.pending&order=resolved_at.desc&limit=200'),
    ]);
    var pending = results[0];
    _adminTxHistoryCache = results[1];
    var pendingHtml = pending.length ? pending.map(function (r) {
      return '<div class="admin-row" style="flex-direction:column;align-items:stretch">' +
        '<div class="admin-row-info" style="margin-bottom:8px"><div class="reader-name">' + escapeHtml(r.user_name) + (r.username ? ' (@' + escapeHtml(r.username) + ')' : '') + '</div>' +
        '<div class="reader-note">' + r.qovun_amount + ' ta ' + txCurrencyLabel(r) + ' uchun to\'lov bo\'ldi — tekshirib tasdiqlang</div>' +
        '<div class="reader-note">' + formatDateTime(r.created_at) + '</div></div>' +
        '<img src="' + r.receipt_url + '" class="note-photo-img" style="max-width:100%" />' +
        '<div style="display:flex;gap:8px;margin-top:8px">' +
        '<button class="btn-small" data-approve-purchase="' + r.id + '" data-amount="' + r.qovun_amount + '" data-uid="' + r.user_id + '" data-currency="' + r.currency + '">Tasdiqlash</button>' +
        '<button class="btn-small danger" data-reject-purchase="' + r.id + '">Rad etish</button>' +
        '</div></div>';
    }).join('') : '<div class="empty">Hozircha kutilayotgan tranzaksiya yo\'q.</div>';
    el.innerHTML =
      '<div class="section-label">Kutilayotgan</div>' + pendingHtml +
      '<div class="section-label" style="margin-top:20px">Tarix</div>' +
      '<div style="display:flex;gap:8px;margin-bottom:10px"><input id="adminTxDateFrom" class="input" type="date" style="flex:1" /><input id="adminTxDateTo" class="input" type="date" style="flex:1" /></div>' +
      '<div id="adminTxHistoryList"></div>';
    document.getElementById('adminTxDateFrom').addEventListener('change', renderAdminTxHistory);
    document.getElementById('adminTxDateTo').addEventListener('change', renderAdminTxHistory);
    renderAdminTxHistory();
    document.querySelectorAll('[data-approve-purchase]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        confirmAction("To'lovni tasdiqlaysizmi?", async function () {
          try {
            var id = btn.dataset.approvePurchase;
            var amt = parseInt(btn.dataset.amount, 10);
            var uid = parseInt(btn.dataset.uid, 10);
            var currency = btn.dataset.currency;
            if (currency === 'proteincha') await adjustWallet(uid, 0, amt);
            else await adjustWallet(uid, amt, 0);
            await sbPatch('qovun_purchase_requests?id=eq.' + id, { status: 'approved', resolved_at: new Date().toISOString() });
            vibrate('light');
            loadAdminTransactions();
          } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
        });
      });
    });
    document.querySelectorAll('[data-reject-purchase]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        customPrompt("Rad etish sababi:", function (reason) {
          var id = btn.dataset.rejectPurchase;
          sbPatch('qovun_purchase_requests?id=eq.' + id, { status: 'rejected', reject_reason: reason || '', resolved_at: new Date().toISOString() })
            .then(function () { vibrate('light'); loadAdminTransactions(); })
            .catch(function (e) { console.error(e); showAlert('Xatolik yuz berdi.'); });
        });
      });
    });
  } catch (e) { el.innerHTML = '<div class="empty">Yuklanmadi.</div>'; console.error(e); }
}

function renderAdminTxHistory() {
  var listEl = document.getElementById('adminTxHistoryList');
  var fromVal = document.getElementById('adminTxDateFrom').value;
  var toVal = document.getElementById('adminTxDateTo').value;
  var history = _adminTxHistoryCache;
  if (fromVal) history = history.filter(function (r) { return (r.resolved_at || r.created_at).slice(0, 10) >= fromVal; });
  if (toVal) history = history.filter(function (r) { return (r.resolved_at || r.created_at).slice(0, 10) <= toVal; });
  listEl.innerHTML = history.length ? history.map(function (r) {
    var statusLabel = r.status === 'approved' ? '✅ Tasdiqlandi' : ('❌ Rad etildi' + (r.reject_reason ? ' (' + escapeHtml(r.reject_reason) + ')' : ''));
    return '<div class="admin-row"><div class="admin-row-info"><div class="reader-name">' + escapeHtml(r.user_name) + (r.username ? ' (@' + escapeHtml(r.username) + ')' : '') + '</div>' +
      '<div class="reader-note">' + r.qovun_amount + ' ta ' + txCurrencyLabel(r) + ' · ' + statusLabel + '</div>' +
      '<div class="reader-note">' + formatDateTime(r.resolved_at || r.created_at) + '</div></div></div>';
  }).join('') : '<div class="empty">Tarix yo\'q.</div>';
}

async function loadAdminWithdrawals() {
  var el = document.getElementById('adminBody');
  try {
    var results = await Promise.all([
      sbGet('withdrawal_requests?select=*&status=eq.pending&order=created_at.desc'),
      sbGet('withdrawal_requests?select=*&status=neq.pending&order=resolved_at.desc&limit=200'),
    ]);
    var rows = results[0];
    _adminWdHistoryCache = results[1];
    var pendingHtml = rows.length ? rows.map(function (r) {
      return '<div class="admin-row" style="flex-direction:column;align-items:stretch">' +
        '<div class="admin-row-info"><div class="reader-name">' + escapeHtml(r.user_name) + (r.username ? ' (@' + escapeHtml(r.username) + ')' : '') + '</div>' +
        '<div class="reader-note">' + r.amount + ' ta ' + txCurrencyLabel(r) + ' → ' + r.money_amount + " so'm</div>" +
        '<div class="reader-note">Karta egasi: ' + escapeHtml(r.card_holder_name || '—') + '</div>' +
        '<div class="reader-note">Karta: ' + escapeHtml(r.card_number) + '</div>' +
        '<div class="reader-note">' + formatDateTime(r.created_at) + '</div></div>' +
        '<div style="display:flex;gap:8px;margin-top:8px">' +
        '<button class="btn-small" data-approve-withdrawal="' + r.id + '" data-currency="' + r.currency + '" data-amount="' + r.amount + '" data-uid="' + r.user_id + '">To\'landi</button>' +
        '<button class="btn-small danger" data-reject-withdrawal="' + r.id + '">Rad etish</button>' +
        '</div></div>';
    }).join('') : '<div class="empty">Hozircha so\'rov yo\'q.</div>';
    el.innerHTML =
      '<div class="section-label">Kutilayotgan</div>' + pendingHtml +
      '<div class="section-label" style="margin-top:20px">Tarix</div>' +
      '<div style="display:flex;gap:8px;margin-bottom:10px"><input id="adminWdDateFrom" class="input" type="date" style="flex:1" /><input id="adminWdDateTo" class="input" type="date" style="flex:1" /></div>' +
      '<div id="adminWdHistoryList"></div>';
    document.getElementById('adminWdDateFrom').addEventListener('change', renderAdminWdHistory);
    document.getElementById('adminWdDateTo').addEventListener('change', renderAdminWdHistory);
    renderAdminWdHistory();
    document.querySelectorAll('[data-approve-withdrawal]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        confirmAction("To'lov qildingizmi? Tasdiqlasangiz balansdan yechiladi.", async function () {
          try {
            var id = btn.dataset.approveWithdrawal;
            var currency = btn.dataset.currency;
            var amt = parseInt(btn.dataset.amount, 10);
            var uid = parseInt(btn.dataset.uid, 10);
            if (currency === 'qovun') await adjustWallet(uid, -amt, 0);
            else await adjustWallet(uid, 0, -amt);
            await sbPatch('withdrawal_requests?id=eq.' + id, { status: 'paid', resolved_at: new Date().toISOString() });
            vibrate('light');
            loadAdminWithdrawals();
          } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
        });
      });
    });
    document.querySelectorAll('[data-reject-withdrawal]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        customPrompt("Rad etish sababi:", function (reason) {
          var id = btn.dataset.rejectWithdrawal;
          sbPatch('withdrawal_requests?id=eq.' + id, { status: 'rejected', reject_reason: reason || '', resolved_at: new Date().toISOString() })
            .then(function () { vibrate('light'); loadAdminWithdrawals(); })
            .catch(function (e) { console.error(e); showAlert('Xatolik yuz berdi.'); });
        });
      });
    });
  } catch (e) { el.innerHTML = '<div class="empty">Yuklanmadi.</div>'; console.error(e); }
}

function renderAdminWdHistory() {
  var listEl = document.getElementById('adminWdHistoryList');
  var fromVal = document.getElementById('adminWdDateFrom').value;
  var toVal = document.getElementById('adminWdDateTo').value;
  var history = _adminWdHistoryCache;
  if (fromVal) history = history.filter(function (r) { return (r.resolved_at || r.created_at).slice(0, 10) >= fromVal; });
  if (toVal) history = history.filter(function (r) { return (r.resolved_at || r.created_at).slice(0, 10) <= toVal; });
  listEl.innerHTML = history.length ? history.map(function (r) {
    var statusLabel = r.status === 'paid' ? "✅ To'landi" : ('❌ Rad etildi' + (r.reject_reason ? ' (' + escapeHtml(r.reject_reason) + ')' : ''));
    return '<div class="admin-row"><div class="admin-row-info"><div class="reader-name">' + escapeHtml(r.user_name) + (r.username ? ' (@' + escapeHtml(r.username) + ')' : '') + '</div>' +
      '<div class="reader-note">' + r.amount + ' ta ' + txCurrencyLabel(r) + ' → ' + r.money_amount + " so'm · " + statusLabel + '</div>' +
      '<div class="reader-note">' + formatDateTime(r.resolved_at || r.created_at) + '</div></div></div>';
  }).join('') : '<div class="empty">Tarix yo\'q.</div>';
}

async function loadAdminBooks() {
  var el = document.getElementById('adminBody');
  try {
    _adminBooksCache = await sbGet('books?select=*&order=title.asc');
    el.innerHTML = '<input id="adminBookSearch" class="input" placeholder="Kitob nomi yoki muallif bo\'yicha qidirish..." style="margin-bottom:10px" />' +
      '<div class="hint" style="margin-bottom:6px">Qo\'shilgan sana oralig\'i</div>' +
      '<div style="display:flex;gap:8px;margin-bottom:14px"><input id="adminBookDateFrom" class="input" type="date" style="flex:1" /><input id="adminBookDateTo" class="input" type="date" style="flex:1" /></div>' +
      '<div id="adminBooksList"></div>';
    document.getElementById('adminBookSearch').addEventListener('input', renderAdminBooksList);
    document.getElementById('adminBookDateFrom').addEventListener('change', renderAdminBooksList);
    document.getElementById('adminBookDateTo').addEventListener('change', renderAdminBooksList);
    renderAdminBooksList();
  } catch (e) { el.innerHTML = '<div class="empty">Yuklanmadi.</div>'; console.error(e); }
}

function renderAdminBooksList() {
  var listEl = document.getElementById('adminBooksList');
  var searchEl = document.getElementById('adminBookSearch');
  var fromEl = document.getElementById('adminBookDateFrom');
  var toEl = document.getElementById('adminBookDateTo');
  var q = searchEl ? searchEl.value.trim().toLowerCase() : '';
  var fromVal = fromEl ? fromEl.value : '';
  var toVal = toEl ? toEl.value : '';
  var books = _adminBooksCache;
  if (q) {
    books = books.filter(function (b) {
      return (b.title || '').toLowerCase().indexOf(q) !== -1 || (b.author || '').toLowerCase().indexOf(q) !== -1;
    });
  }
  if (fromVal) books = books.filter(function (b) { return b.created_at && b.created_at.slice(0, 10) >= fromVal; });
  if (toVal) books = books.filter(function (b) { return b.created_at && b.created_at.slice(0, 10) <= toVal; });
  books = books.slice().sort(function (a, b) {
    if (a.approved === b.approved) return (a.title || '').localeCompare(b.title || '');
    return a.approved ? 1 : -1;
  });
  listEl.innerHTML = books.length ? books.map(function (b) {
    return '<div class="card" style="margin-bottom:10px" data-go="bookDetail" data-id="' + b.id + '"><div class="book-card-row">' +
      (b.cover_url ? '<img src="' + b.cover_url + '" class="cover-thumb" />' : '<div class="cover-thumb-placeholder">📖</div>') +
      '<div class="book-card-info"><div class="card-title">' + escapeHtml(b.title) + '</div>' +
      (b.approved === false ? '<div class="reader-note" style="color:var(--danger);font-weight:600">⏳ Tasdiq kutilmoqda</div>' : '') +
      (b.author ? '<div class="card-author">' + escapeHtml(b.author) + '</div>' : '') +
      '<div class="reader-note">👤 ' + escapeHtml(b.created_by_name || 'Noma\'lum') + '</div>' +
      '<div class="reader-note">📅 ' + formatDateTime(b.created_at) + '</div>' +
      '<div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">' +
      (b.approved === false ? '<button class="btn-small" data-approve-book="' + b.id + '" data-creator="' + b.created_by_id + '" data-title="' + escapeHtml(b.title) + '">✅ Tasdiqlash</button>' : '') +
      '<button class="btn-small" data-edit-book="' + b.id + '">Tahrirlash</button>' +
      '<button class="btn-small danger" data-delete-book="' + b.id + '">O\'chirish</button>' +
      '</div></div></div></div>';
  }).join('') : '<div class="empty">Kitob topilmadi.</div>';

  document.querySelectorAll('[data-approve-book]').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      confirmAction("Bu kitobni tasdiqlaysizmi? Hammaga ko'rinadigan bo'ladi.", async function () {
        try {
          var id = btn.dataset.approveBook;
          var creatorId = btn.dataset.creator;
          var title = btn.dataset.title;
          await sbPatch('books?id=eq.' + id, { approved: true });
          await sbPost('book_approval_notifications', { book_id: id, creator_id: creatorId, book_title: title });
          var bk = _adminBooksCache.find(function (b) { return String(b.id) === String(id); });
          if (bk) bk.approved = true;
          vibrate('light');
          renderAdminBooksList();
          loadAdminBadgeCounts();
        } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
      });
    });
  });
  document.querySelectorAll('[data-delete-book]').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var id = btn.dataset.deleteBook;
      confirmAction("Kitobni butunlay o'chirish? Bu amalni qaytarib bo'lmaydi.", async function () {
        try {
          await sbDelete('books?id=eq.' + id);
          _adminBooksCache = _adminBooksCache.filter(function (b) { return String(b.id) !== id; });
          vibrate('medium');
          renderAdminBooksList();
          loadAdminBadgeCounts();
        } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
      });
    });
  });
  document.querySelectorAll('[data-edit-book]').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var book = _adminBooksCache.find(function (b) { return String(b.id) === btn.dataset.editBook; });
      openEditBookForm(book);
    });
  });
}

function openEditBookForm(book) {
  var el = document.getElementById('adminBody');
  el.innerHTML =
    '<button class="remove-link" id="adminBackToList">← Ro\'yxatga qaytish</button>' +
    '<div class="form">' +
    '<input id="editTitle" class="input" placeholder="Nomi" value="' + escapeHtml(book.title) + '" />' +
    '<input id="editAuthor" class="input" placeholder="Muallif" value="' + escapeHtml(book.author || '') + '" />' +
    '<input id="editTotalPages" class="input" type="number" min="1" placeholder="Jami bet" value="' + (book.total_pages || '') + '" />' +
    (book.cover_url ? '<img src="' + book.cover_url + '" class="cover-preview-img" />' : '') +
    '<label class="file-btn" for="editCoverInput">🖼️ Rasmni almashtirish</label>' +
    '<input type="file" id="editCoverInput" accept="image/*" style="display:none" />' +
    '<input id="editPurchaseLink" class="input" placeholder="Sotib olish linki" value="' + escapeHtml(book.purchase_link || '') + '" />' +
    '<button id="saveEditBookBtn" class="btn-primary full">Saqlash</button>' +
    '</div>';
  document.getElementById('adminBackToList').addEventListener('click', loadAdminBooks);
  document.getElementById('saveEditBookBtn').addEventListener('click', async function () {
    var btn = this; btn.disabled = true; btn.textContent = 'Saqlanmoqda...';
    try {
      var coverFile = document.getElementById('editCoverInput').files[0];
      var tpVal = document.getElementById('editTotalPages').value.trim();
      var patch = {
        title: document.getElementById('editTitle').value.trim(),
        author: document.getElementById('editAuthor').value.trim() || null,
        total_pages: tpVal ? parseInt(tpVal, 10) : null,
        purchase_link: document.getElementById('editPurchaseLink').value.trim() || null,
      };
      if (coverFile) {
        var ext = (coverFile.name.split('.').pop() || 'jpg').toLowerCase();
        patch.cover_url = await sbUploadFile(HUJJATLAR_BUCKET, 'covers/' + Date.now() + '_' + Math.random().toString(36).slice(2) + '.' + ext, coverFile);
      }
      await sbPatch('books?id=eq.' + book.id, patch);
      vibrate('medium');
      showAlert('Saqlandi.');
      loadAdminBooks();
    } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); btn.disabled = false; btn.textContent = 'Saqlash'; }
  });
}

// ===== Kitob qo'shish =====
function renderAddBook() {
  setBackButton(true, function () { state.view = 'home'; render(); });
  renderShell(
    '<div class="header"><button class="back" data-go="home">←</button><div class="h-title">Kitob qo\'shish</div></div>' +
    '<div class="form">' +
    '<input id="bookSearch" class="input" placeholder="Kitob nomini yozing..." />' +
    '<div id="searchResults"></div>' +
    '<div id="newBookForm" style="display:none">' +
    '<div class="hint">Bu kitob topilmadi — yangi sifatida qo\'shamiz. Siz birinchi o\'quvchi bo\'lasiz 🎉</div>' +
    '<input id="bookAuthor" class="input" placeholder="Muallif nomi" />' +
    '<input id="totalPages" class="input" type="number" min="1" placeholder="Jami bet soni" />' +
    '<label class="file-btn" for="coverInput">🖼️ Kitob rasmini tanlash (majburiy)</label>' +
    '<input type="file" id="coverInput" accept="image/*" style="display:none" />' +
    '<div id="coverPreview"></div>' +
    '<button id="createBookBtn" class="btn-primary full">Kitobni qo\'shish</button>' +
    '</div>' +
    '</div>'
  );

  var searchEl = document.getElementById('bookSearch');
  var resultsEl = document.getElementById('searchResults');
  var newFormEl = document.getElementById('newBookForm');
  var timer = null;

  searchEl.addEventListener('input', function () {
    clearTimeout(timer);
    var q = searchEl.value.trim();
    newFormEl.style.display = 'none';
    if (!q) { resultsEl.innerHTML = ''; return; }
    timer = setTimeout(async function () {
      try {
        var matches = await sbGet('books?select=*&title=ilike.*' + encodeURIComponent(q) + '*&approved=eq.true&limit=5');
        if (matches.length) {
          resultsEl.innerHTML = matches.map(function (b) {
            return '<div class="card result-card" data-go="bookDetail" data-id="' + b.id + '">' + escapeHtml(b.title) +
              (b.author ? ' <span style="color:var(--text-muted)">— ' + escapeHtml(b.author) + '</span>' : '') + '</div>';
          }).join('');
        } else {
          resultsEl.innerHTML = '';
          newFormEl.style.display = 'block';
          newFormEl.dataset.title = q;
        }
      } catch (e) { console.error(e); }
    }, 400);
  });

  document.getElementById('coverInput').addEventListener('change', function () {
    var f = this.files[0];
    var prevEl = document.getElementById('coverPreview');
    if (!f) { prevEl.innerHTML = ''; return; }
    if (f.size > 8 * 1024 * 1024) { showAlert('Rasm hajmi katta (8MB dan oshmasin).'); this.value = ''; prevEl.innerHTML = ''; return; }
    prevEl.innerHTML = '<div style="position:relative;display:inline-block">' +
      '<img src="' + URL.createObjectURL(f) + '" class="cover-preview-img" />' +
      '<button type="button" id="removeCoverBtn" style="position:absolute;top:-8px;right:-8px;width:26px;height:26px;border-radius:50%;border:none;background:var(--danger);color:#fff;font-size:14px;font-weight:700;line-height:1;cursor:pointer">✕</button>' +
      '</div>';
    document.getElementById('removeCoverBtn').addEventListener('click', function () {
      document.getElementById('coverInput').value = '';
      prevEl.innerHTML = '';
    });
  });

  document.getElementById('createBookBtn').addEventListener('click', async function () {
    if (iAmBlocked) { showAlert('Siz blok qilingansiz.'); return; }
    var title = newFormEl.dataset.title || searchEl.value.trim();
    if (!title) return;
    var coverFile = document.getElementById('coverInput').files[0];
    if (!coverFile) { showAlert("Kitob rasmini tanlang — rasmsiz kitob qo'shib bo'lmaydi."); return; }
    var author = document.getElementById('bookAuthor').value.trim();
    if (!author) { showAlert('Muallif nomini kiriting.'); return; }
    var tpVal = document.getElementById('totalPages').value.trim();
    var totalPages = tpVal ? parseInt(tpVal, 10) : null;
    if (!totalPages || totalPages <= 0) { showAlert('Jami bet sonini kiriting.'); return; }
    try {
      var myBooks = await sbGet('books?select=id,title,total_pages&created_by_id=eq.' + ME.id);
      if (myBooks.length) {
        var today = cohortTodayStr();
        for (var bi = 0; bi < myBooks.length; bi++) {
          var mb = myBooks[bi];
          var mbProgress = await sbGet('progress?select=cohort_start_date&book_id=eq.' + mb.id);
          var mbReadingDays = bookReadingDays(mb);
          var mbActive = mbProgress.some(function (p) {
            if (!p.cohort_start_date) return false;
            var ph = cohortPhase(p.cohort_start_date, today, mbReadingDays);
            return ph && ph !== 'ended';
          });
          if (mbActive) {
            showAlert('Sizning "' + mb.title + '" challenjingiz hali tugamagan. Yangi challenj yaratish uchun avvalgisi tugashini kuting.');
            return;
          }
        }
      }
    } catch (e) { console.error(e); }
    var btn = this;
    confirmAction("Hammasini to'g'ri kiritdingizmi? Kitob hammaga ko'rinadi.", async function () {
      btn.disabled = true; btn.textContent = 'Yuklanmoqda...';
      try {
        var ext = (coverFile.name.split('.').pop() || 'jpg').toLowerCase();
        var coverUrl = await sbUploadFile(HUJJATLAR_BUCKET, 'covers/' + Date.now() + '_' + Math.random().toString(36).slice(2) + '.' + ext, coverFile);
        var created = await sbPost('books', {
          title: title, author: author, total_pages: totalPages,
          cover_url: coverUrl, created_by_id: ME.id, created_by_name: ME.name, approved: false,
        });
        var book = created[0];
        var marker = currentSignupCohortMarker(cohortTodayStr());
        await sbPost('progress', { book_id: book.id, user_id: ME.id, user_name: ME.name, pages_read: 0, cohort_start_date: marker });
        vibrate('medium');
        replyTarget = null;
        editTarget = null;
        state.view = 'bookDetail'; state.bookId = book.id; state.detailTab = 'readers'; render();
      } catch (e) {
        console.error(e); showAlert('Rasm yuklashda yoki saqlashda xatolik. Qaytadan urinib ko\'ring.');
        btn.disabled = false; btn.textContent = "Kitobni qo'shish";
      }
    });
  });
}

// ===== Kitob sahifasi =====
async function renderBookDetail() {
  var backView = isAdminMode ? 'admin' : 'home';
  setBackButton(true, function () { state.view = backView; render(); });
  var sameBookCached = _bdCache && _bdCache.bookId === state.bookId;
  var headerHtml = '<div class="header"><button class="back" data-go="' + backView + '">←</button><div class="h-title">Kitob</div></div>' +
    '<div id="bookDetailBody">' + (sameBookCached ? '' : '<div class="loading">Yuklanmoqda...</div>') + '</div>';
  if (isAdminMode) app.innerHTML = '<div class="screen">' + headerHtml + '</div>';
  else renderShell(headerHtml);

  if (sameBookCached) {
    renderBookDetailBody();
    return;
  }

  var body = document.getElementById('bookDetailBody');
  try {
    var today = cohortTodayStr();
    var results = await Promise.all([
      sbGet('books?select=*&id=eq.' + state.bookId),
      sbGet('progress?select=*&book_id=eq.' + state.bookId + '&order=pages_read.desc'),
      sbGet('comments?select=*&book_id=eq.' + state.bookId + '&order=created_at.asc&limit=100'),
      sbGet('progress?select=book_id,cohort_start_date&user_id=eq.' + ME.id),
      sbGet('reading_notes?select=*&book_id=eq.' + state.bookId + '&order=created_at.asc&limit=200'),
    ]);
    var book = results[0][0];
    if (!book) {
      body.innerHTML = '<div class="empty">Kitob topilmadi.</div>';
      return;
    }
    if (book.approved === false && String(book.created_by_id) !== String(ME.id) && !isAdminMode) {
      body.innerHTML = '<div class="empty">⏳ Bu kitob hali admin tomonidan tasdiqlanmagan.</div>';
      return;
    }
    var progress = results[1];
    var comments = results[2];
    var myAllProgress = results[3];
    var allNotes = results[4];

    var likeCounts = {}, myLiked = {};
    if (comments.length) {
      var likeRows = await sbGet('comment_likes?select=comment_id,user_id&comment_id=in.(' + comments.map(function (c) { return c.id; }).join(',') + ')');
      likeRows.forEach(function (l) { likeCounts[l.comment_id] = (likeCounts[l.comment_id] || 0) + 1; if (l.user_id === ME.id) myLiked[l.comment_id] = true; });
    }
    _bdCache = {
      bookId: state.bookId, today: today, book: book, progress: progress, comments: comments,
      likeCounts: likeCounts, myLiked: myLiked, allNotes: allNotes, myAllProgress: myAllProgress,
    };
    renderBookDetailBody();
  } catch (e) {
    body.innerHTML = '<div class="empty">Xatolik: kitob topilmadi.</div>';
    console.error(e);
  }
}

function renderBookDetailBody() {
  var body = document.getElementById('bookDetailBody');
  var today = _bdCache.today;
  var book = _bdCache.book;
  var progress = _bdCache.progress;
  var comments = _bdCache.comments;
  var likeCounts = _bdCache.likeCounts;
  var myLiked = _bdCache.myLiked;
  var allNotes = _bdCache.allNotes;
  var myAllProgress = _bdCache.myAllProgress;
  try {
    var mine = progress.find(function (p) { return p.user_id === ME.id; });
    var myPages = mine ? mine.pages_read : 0;
    var totalPages = book.total_pages;
    var readingDays = bookReadingDays(book);
    var myCohortMarker = mine ? String(mine.cohort_start_date).slice(0, 10) : null;
    var myCohortPhase = myCohortMarker ? cohortPhase(myCohortMarker, today, readingDays) : null;
    var signupMarker = currentSignupCohortMarker(today);
    var otherActive = myAllProgress.find(function (p) {
      if (String(p.book_id) === String(book.id)) return false;
      if (!p.cohort_start_date) return false;
      var ph = cohortPhase(p.cohort_start_date, today);
      return ph !== 'ended';
    });
    var coverHtml = book.cover_url ? '<img src="' + book.cover_url + '" class="cover-hero" />' : '<div class="cover-hero-placeholder">📖</div>';

    var membersByMarker = {};
    progress.forEach(function (p) {
      if (p.cohort_start_date) {
        var d = String(p.cohort_start_date).slice(0, 10);
        membersByMarker[d] = (membersByMarker[d] || 0) + 1;
      }
    });
    var allMarkers = nearbyCohortMarkers(today);
    var nextMarker = nextUpcomingCohortMarker(today);
    var activeMarkers = [], endedMarkers = [];
    allMarkers.forEach(function (m) {
      var ph = cohortPhase(m, today, readingDays);
      if (ph === null) { if (m === nextMarker) activeMarkers.push(m); return; }
      if (ph === 'ended') { if (membersByMarker[m]) endedMarkers.push(m); return; }
      if (membersByMarker[m] || ph === 'signup') activeMarkers.push(m);
    });
    activeMarkers.sort();
    endedMarkers.sort();

    var viewMarker = (selectedCohortMarker || myCohortMarker || signupMarker || '').slice(0, 10) || null;

    function schedRowHtml(m) {
      var count = membersByMarker[m] || 0;
      var isMine = m === myCohortMarker;
      var isSelected = m === viewMarker;
      return '<div class="cohort-sched-row' + (isSelected ? ' mine' : '') + '" data-view-cohort="' + m + '" style="cursor:pointer;display:flex;justify-content:space-between;align-items:center">' +
        '<div class="cohort-sched-date">Start sanasi: ' + formatDate(m) + (isMine ? ' <span style="color:var(--accent-1);font-weight:600">(siz qatnashayotgan)</span>' : '') + '</div>' +
        '<div class="cohort-sched-meta">' + count + ' kishi</div>' +
        '</div>';
    }
    var scheduleHtml = '<div class="cohort-schedule">' + activeMarkers.map(schedRowHtml).join('') + '</div>' +
      (endedMarkers.length
        ? '<button id="archiveToggleBtn" class="btn-small" style="margin-top:10px">📦 Arxiv (' + endedMarkers.length + ')</button>' +
          '<div id="archiveList" class="cohort-schedule" style="display:none;margin-top:8px">' + endedMarkers.map(schedRowHtml).join('') + '</div>'
        : '');

    var viewParticipants = viewMarker ? progress.filter(function (p) { return String(p.cohort_start_date).slice(0, 10) === viewMarker; }) : [];
    var viewMarkerPhase = viewMarker ? cohortPhase(viewMarker, today, readingDays) : null;
    var canJoinViewMarker = !mine && !otherActive && viewMarker && (viewMarkerPhase === 'signup' || viewMarker === nextMarker);
    var joinTopBtnHtml = canJoinViewMarker ? '<button id="joinCohortBtnTop" class="btn-primary full" data-marker="' + viewMarker + '" style="margin-bottom:14px">✅ Ro\'yxatga qo\'shilish (' + formatDate(viewMarker) + ')</button>' : '';
    var sectionTitle = viewMarker === myCohortMarker ? 'Sizning guruhingiz' : (formatDate(viewMarker || '') + ' guruhi');
    var readersTabHtml = scheduleHtml + joinTopBtnHtml + '<div class="section-label" style="margin-top:18px">' + sectionTitle + '</div>' +
      (!viewParticipants.length
      ? '<div class="empty">Hozircha hech kim qo\'shilmagan.</div>'
      : '<div class="readers">' + viewParticipants.map(function (p, i) {
          var pPct = totalPages ? Math.min(100, Math.round((p.pages_read / totalPages) * 100)) : Math.min(100, p.pages_read);
          var rankMark = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : (i + 1);
          var isMe = p.user_id === ME.id;
          return '<div class="reader-row' + (isMe ? ' me' : '') + '" data-go="' + (isMe ? 'profile' : 'userBooks') + '" data-userid="' + p.user_id + '" data-username="' + escapeHtml(p.user_name) + '">' +
            '<div class="reader-rank">' + rankMark + '</div>' +
            '<div class="reader-info"><div class="reader-name">' + escapeHtml(p.user_name) + '</div>' +
            '<div class="reader-note">📅 ' + formatDate(p.started_at) + ' ' + new Date(p.started_at).getHours().toString().padStart(2, '0') + ':' + new Date(p.started_at).getMinutes().toString().padStart(2, '0') + '</div></div>' +
            '<div class="reader-pages">' + p.pages_read + ' bet - ' + pPct + '%</div>' +
            '</div>';
        }).join('') + '</div>');

    var purchaseLinkHtml = book.purchase_link ? '<a href="#" data-open-link="' + escapeHtml(book.purchase_link) + '" class="btn-primary full" style="display:block;text-align:center;text-decoration:none;margin-top:10px">🛒 Kitobni sotib olish</a>' : '';

    var progressTabHtml;
    if (otherActive) {
      progressTabHtml = '<div class="empty">Siz hozir boshqa kitob guruhidasiz. Bir vaqtda faqat bitta guruhda ishtirok etish mumkin. Avval o\'sha kitobdan chiqing.</div>';
    } else if (!mine) {
      progressTabHtml = '<div class="empty">Siz hali bu kitob guruhiga qo\'shilmagansiz. Qo\'shilish uchun "Qatnashuvchilar" tabiga o\'ting.</div>' + purchaseLinkHtml;
    } else {
      var cohortLocked = myCohortPhase === 'ended';
      var cohortWaiting = myCohortPhase === 'signup' || myCohortPhase === null;
      var disabledAttr = (cohortLocked || cohortWaiting) ? ' disabled' : '';
      var readingStartMs = new Date(myCohortMarker + 'T00:00:00').getTime() + (4 * 3600000);
      var phaseHintHtml = cohortLocked
        ? '<div class="hint" style="margin-bottom:14px;color:var(--danger)">⛔ Guruh yopilgan, endi bet qo\'sha olmaysiz.</div>'
        : (cohortWaiting ? '<div class="hint cohort-countdown" id="cohortCountdown" data-target="' + readingStartMs + '" style="margin-bottom:14px"></div>' : '');

      progressTabHtml =
        phaseHintHtml +
        '<div class="form">' +
        '<input id="pagesInput" class="input" type="number" min="0" max="' + (totalPages || '') + '" placeholder="Oxirgi o\'qilgan bet raqamini kiriting (masalan: 45)" value="' + (myPages > 0 ? myPages : '') + '"' + disabledAttr + ' />' +
        '<textarea id="noteInput" class="input" rows="3" maxlength="200" placeholder="O\'qigan betlaringiz haqida fikr yozing — bu sizni rostdan o\'qiganingizning bir isboti (shart)..."' + disabledAttr + '></textarea>' +
        '<div style="text-align:right;font-size:11px;color:var(--text-muted);margin-top:-8px"><span id="noteCharCount">0</span>/200</div>' +
        '<label class="file-btn" for="noteCoverInput" style="' + ((cohortLocked || cohortWaiting) ? 'opacity:0.5;pointer-events:none;' : '') + '">📷 Rasm yuklash (majburiy)</label>' +
        '<input type="file" id="noteCoverInput" accept="image/*" style="display:none"' + disabledAttr + ' />' +
        '<div id="noteCoverPreview"></div>' +
        '<button id="updateProgressBtn" class="btn-primary full"' + disabledAttr + '>Izohlar bo\'limiga yuborish</button>' +
        '</div>' +
        '<button id="removeFromListBtn" class="remove-link">Guruhdan chiqish</button>' +
        purchaseLinkHtml +
        '<div class="hint" style="margin-top:14px">Yozgan fikringizni "Izohlar" bo\'limidan ko\'rishingiz mumkin.</div>';
    }

    var displayCohortMarker = viewMarker;
    var displayCohortComments = displayCohortMarker ? comments.filter(function (c) { return c.cohort_start_date === displayCohortMarker; }) : [];
    var displayCohortNotes = displayCohortMarker ? allNotes.filter(function (n) { return n.cohort_start_date === displayCohortMarker; }) : [];
    var unifiedItems = displayCohortComments.filter(function (c) { return !c.reply_to_id; }).map(function (c) { return { type: 'comment', data: c, ts: c.created_at }; })
      .concat(displayCohortNotes.map(function (n) { return { type: 'note', data: n, ts: n.created_at }; }))
      .sort(function (a, b) { return new Date(b.ts) - new Date(a.ts); });
    var repliesByParent = {};
    displayCohortComments.forEach(function (c) { if (c.reply_to_id) { (repliesByParent[c.reply_to_id] = repliesByParent[c.reply_to_id] || []).push(c); } });

    function commentRow(c, isReply) {
      var liked = !!myLiked[c.id];
      var count = likeCounts[c.id] || 0;
      var replyCount = isReply ? 0 : (repliesByParent[c.id] || []).length;
      var isMine = c.user_id === ME.id;
      return '<div class="comment-block' + (isReply ? ' reply' : '') + '">' +
        '<div class="comment-text"><span class="comment-name">' + escapeHtml(c.user_name) + ':</span> ' + escapeHtml(c.text) + (c.edited ? ' <span class="edited-tag">(tahrirlangan)</span>' : '') + '</div>' +
        '<div class="comment-actions">' +
        '<button class="comment-action-btn' + (liked ? ' liked' : '') + '" data-like-comment="' + c.id + '">' + (liked ? '❤️' : '🤍') + (count ? ' ' + count : '') + '</button>' +
        (!isReply ? '<button class="comment-action-btn" data-reply-comment="' + c.id + '" data-reply-name="' + escapeHtml(c.user_name) + '">↩ Javob</button>' : '') +
        (replyCount > 0 ? '<button class="comment-action-btn" data-toggle-replies="' + c.id + '">' + (expandedReplies[c.id] ? '▴ Javoblarni yashirish' : '▾ Javoblar (' + replyCount + ')') + '</button>' : '') +
        (!isAdminMode && isMine && c.user_name !== 'Admin' ? '<button class="comment-action-btn" data-edit-comment="' + c.id + '" data-edit-text="' + escapeHtml(c.text) + '">✏ Tahrirlash</button>' : '') +
        (isAdminMode ? '<button class="comment-action-btn" data-del-comment="' + c.id + '">🗑 O\'chir</button>' : '') +
        '</div></div>';
    }

    function noteRow(n) {
      var isMine = n.user_id === ME.id;
      var fromPage = (n.pages_from !== null && n.pages_from !== undefined) ? n.pages_from : 0;
      var rangeLabel = fromPage + '-' + n.pages_read;
      if (noteEditTarget && String(noteEditTarget) === String(n.id)) {
        return '<div class="note-entry">' +
          '<div class="note-meta"><span class="comment-name">' + escapeHtml(n.user_name) + '</span> · 📅 ' + formatDate(n.created_at) + ' — ' + rangeLabel + ' bet uchun fikr:</div>' +
          '<img src="' + n.photo_url + '" class="note-photo-img" id="noteEditPhotoPreview" />' +
          '<label class="file-btn" for="noteEditPhotoInput">📷 Rasmni almashtirish</label>' +
          '<input type="file" id="noteEditPhotoInput" accept="image/*" style="display:none" />' +
          '<textarea class="input" id="noteEditInput" rows="3" maxlength="200">' + escapeHtml(n.note) + '</textarea>' +
          '<div style="display:flex;gap:8px;margin-top:8px">' +
          '<button class="btn-small" data-save-note-edit="' + n.id + '">Saqlash</button>' +
          '<button class="btn-small" data-cancel-note-edit>Bekor qilish</button>' +
          '</div></div>';
      }
      return '<div class="note-entry">' +
        '<div class="note-meta"><span class="comment-name">' + escapeHtml(n.user_name) + '</span> · 📅 ' + formatDate(n.created_at) + ' — ' + rangeLabel + ' bet uchun fikr:' + (n.edited ? ' <span class="edited-tag">(tahrirlangan)</span>' : '') + '</div>' +
        '<img src="' + n.photo_url + '" class="note-photo-img" />' +
        '<div class="note-text">' + escapeHtml(n.note) + '</div>' +
        '<div class="comment-actions">' +
        (!isAdminMode && isMine ? '<button class="comment-action-btn" data-edit-note="' + n.id + '">✏ Tahrirlash</button>' : '') +
        (isAdminMode ? '<button class="comment-action-btn" data-del-note="' + n.id + '">🗑 O\'chir</button>' : '') +
        '</div></div>';
    }

    var commentsListHtml = unifiedItems.map(function (item) {
      if (item.type === 'note') return noteRow(item.data);
      var c = item.data;
      var repliesHtml = expandedReplies[c.id] ? (repliesByParent[c.id] || []).map(function (r) { return commentRow(r, true); }).join('') : '';
      return commentRow(c, false) + repliesHtml;
    }).join('');

    var isViewingOwnCohort = displayCohortMarker === myCohortMarker;
    var canComment = !!mine && isViewingOwnCohort && myCohortPhase !== 'signup' && myCohortPhase !== null;
    var canViewComments = !!mine;
    var commentFormHtml;
    if (canComment) {
      commentFormHtml = (editTarget ? '<div class="reply-banner"><span>✏ Komentariyani tahrirlamoqdasiz</span><button data-cancel-edit style="background:none;border:none;color:var(--accent-1);font-size:14px">✕</button></div>' :
         replyTarget ? '<div class="reply-banner"><span>↩ ' + escapeHtml(replyTarget.name) + ' ga javob yozyapsiz</span><button data-cancel-reply style="background:none;border:none;color:var(--accent-1);font-size:14px">✕</button></div>' : '') +
        '<div class="comment-form"><textarea id="commentInput" class="input" rows="2" placeholder="' + (replyTarget ? 'Javobingiz...' : "Fikringizni yozing...") + '">' + (editTarget ? escapeHtml(editTarget.text) : '') + '</textarea>' +
        '<button id="sendCommentBtn" class="btn-primary">' + (editTarget ? 'Saqlash' : 'Yubor') + '</button></div>';
    } else if (!mine) {
      commentFormHtml = '<div class="hint" style="margin-bottom:10px">Izohlarni ko\'rish va yozish uchun avval guruhga qo\'shiling.</div>';
    } else if (isViewingOwnCohort) {
      commentFormHtml = '<div class="hint" style="margin-bottom:10px">⏳ Guruhingiz hali boshlanmagan — izoh yozish challenj boshlangach ochiladi.</div>';
    } else {
      commentFormHtml = '<div class="hint" style="margin-bottom:10px">👀 Boshqa guruh izohlarini ko\'ryapsiz (faqat o\'qish mumkin).</div>';
    }

    var commentsTabHtml = commentFormHtml +
      (canViewComments ? '<div class="comments">' + (commentsListHtml || '<div class="empty">Hali izoh yo\'q.</div>') + '</div>' : '');

    var activeTabHtml = (state.detailTab === 'progress' && !isAdminMode) ? progressTabHtml : state.detailTab === 'comments' ? commentsTabHtml : readersTabHtml;

    body.innerHTML =
      '<div class="hero-row">' + coverHtml +
      '<div class="hero-info"><div class="book-hero-title">' + escapeHtml(book.title) + '</div>' +
      (book.author ? '<div class="book-hero-author">' + escapeHtml(book.author) + '</div>' : '') +
      (totalPages ? '<div class="book-hero-sub">' + totalPages + ' bet · Challenge: ' + readingDays + ' kun · Kunlik o\'qish me\'yori: ' + COHORT_SUGGESTED_DAILY_PAGES + ' bet</div>' : '') +
      (book.purchase_link ? '<div class="book-hero-sub"><a href="#" data-open-link="' + escapeHtml(book.purchase_link) + '" style="color:var(--accent-1);text-decoration:underline">🛒 Sotib olish</a></div>' : '') +
      '</div></div>' +
      '<div class="segment">' +
      '<button class="seg-btn' + (state.detailTab === 'readers' ? ' active' : '') + '" data-detailtab="readers">Qatnashuvchilar</button>' +
      '<button class="seg-btn' + (state.detailTab === 'comments' ? ' active' : '') + '" data-detailtab="comments">Izohlar</button>' +
      (isAdminMode ? '' : '<button class="seg-btn' + (state.detailTab === 'progress' ? ' active' : '') + '" data-detailtab="progress">O\'qish jarayonim</button>') +
      '</div>' +
      activeTabHtml;

    document.querySelectorAll('[data-detailtab]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.detailTab = btn.dataset.detailtab;
        renderBookDetail();
      });
    });
    document.querySelectorAll('[data-open-link]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        var url = a.dataset.openLink;
        try { if (tg && tg.openLink) { tg.openLink(url); return; } } catch (e2) {}
        window.open(url, '_blank');
      });
    });

    if (state.detailTab === 'readers') {
      document.querySelectorAll('[data-view-cohort]').forEach(function (row) {
        row.addEventListener('click', function () {
          selectedCohortMarker = row.dataset.viewCohort;
          renderBookDetail();
        });
      });
      var archiveToggleBtn = document.getElementById('archiveToggleBtn');
      if (archiveToggleBtn) {
        archiveToggleBtn.addEventListener('click', function () {
          var listEl = document.getElementById('archiveList');
          listEl.style.display = listEl.style.display === 'none' ? 'block' : 'none';
        });
      }
      var joinBtnTop = document.getElementById('joinCohortBtnTop');
      if (joinBtnTop) {
        joinBtnTop.addEventListener('click', function () {
          if (iAmBlocked) { showAlert('Siz blok qilingansiz.'); return; }
          var marker = joinBtnTop.dataset.marker;
          var isCreatorJoin = String(book.created_by_id) === String(ME.id);
          var confirmMsg = isCreatorJoin ? "Guruhga qo'shilasizmi?" : ("Qo'shilish narxi " + formatNumber(JOIN_COST_QOVUN) + " ta qovuncha. Tasdiqlaysizmi?");
          confirmAction(confirmMsg, async function () {
            try {
              var ok = await joinCohortFlow(book, marker, progress);
              if (!ok) return;
              selectedCohortMarker = null;
              vibrate('light');
              showAlert('Guruhga qo\'shildingiz!');
              renderBookDetail();
            } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
          });
        });
      }
    }

    if (state.detailTab === 'comments') {
      document.querySelectorAll('[data-like-comment]').forEach(function (btn) {
        btn.addEventListener('click', async function () {
          var cid = btn.dataset.likeComment;
          var alreadyLiked = btn.classList.contains('liked');
          var oldCountMatch = btn.textContent.match(/\d+/);
          var oldCount = oldCountMatch ? parseInt(oldCountMatch[0], 10) : 0;
          var newLiked = !alreadyLiked;
          var newCount = newLiked ? oldCount + 1 : Math.max(0, oldCount - 1);
          btn.classList.toggle('liked', newLiked);
          btn.textContent = (newLiked ? '❤️' : '🤍') + (newCount ? ' ' + newCount : '');
          vibrate('light');
          likeCounts[cid] = newCount;
          if (newLiked) myLiked[cid] = true; else delete myLiked[cid];
          try {
            if (alreadyLiked) await sbDelete('comment_likes?comment_id=eq.' + cid + '&user_id=eq.' + ME.id);
            else await sbPost('comment_likes', { comment_id: cid, user_id: ME.id });
          } catch (e) {
            console.error(e);
            btn.classList.toggle('liked', alreadyLiked);
            btn.textContent = (alreadyLiked ? '❤️' : '🤍') + (oldCount ? ' ' + oldCount : '');
            likeCounts[cid] = oldCount;
            if (alreadyLiked) myLiked[cid] = true; else delete myLiked[cid];
            showAlert('Xatolik yuz berdi.');
          }
        });
      });
      document.querySelectorAll('[data-reply-comment]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          editTarget = null;
          replyTarget = { id: btn.dataset.replyComment, name: btn.dataset.replyName };
          renderBookDetail();
        });
      });
      document.querySelectorAll('[data-edit-comment]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          replyTarget = null;
          editTarget = { id: btn.dataset.editComment, text: btn.dataset.editText };
          renderBookDetail();
        });
      });
      document.querySelectorAll('[data-toggle-replies]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var cid = btn.dataset.toggleReplies;
          expandedReplies[cid] = !expandedReplies[cid];
          renderBookDetail();
        });
      });
      var cancelReplyBtn = document.querySelector('[data-cancel-reply]');
      if (cancelReplyBtn) cancelReplyBtn.addEventListener('click', function () { replyTarget = null; renderBookDetail(); });
      var cancelEditBtn = document.querySelector('[data-cancel-edit]');
      if (cancelEditBtn) cancelEditBtn.addEventListener('click', function () { editTarget = null; renderBookDetail(); });
      document.querySelectorAll('[data-del-comment]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var cid = btn.dataset.delComment;
          confirmAction("Komentariyani o'chirish?", async function () {
            try {
              await sbDelete('comments?id=eq.' + cid);
              _bdCache.comments = comments.filter(function (c) { return String(c.id) !== String(cid) && String(c.reply_to_id) !== String(cid); });
              vibrate('medium');
              renderBookDetail();
            }
            catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
          });
        });
      });
      document.querySelectorAll('[data-edit-note]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          noteEditTarget = btn.dataset.editNote;
          renderBookDetail();
        });
      });
      var cancelNoteEditBtn = document.querySelector('[data-cancel-note-edit]');
      if (cancelNoteEditBtn) {
        cancelNoteEditBtn.addEventListener('click', function () {
          noteEditTarget = null;
          renderBookDetail();
        });
      }
      var noteEditPhotoInputEl = document.getElementById('noteEditPhotoInput');
      if (noteEditPhotoInputEl) {
        noteEditPhotoInputEl.addEventListener('change', function () {
          var f = this.files[0];
          if (!f) return;
          document.getElementById('noteEditPhotoPreview').src = URL.createObjectURL(f);
        });
      }
      document.querySelectorAll('[data-save-note-edit]').forEach(function (btn) {
        btn.addEventListener('click', async function () {
          var noteId = btn.dataset.saveNoteEdit;
          var editInputEl = document.getElementById('noteEditInput');
          var newText = editInputEl.value.trim();
          if (!newText) { showAlert('Fikr matni bo\'sh bo\'lishi mumkin emas.'); return; }
          var sBtn = this; sBtn.disabled = true;
          try {
            var patch = { note: newText, edited: true };
            var newPhotoFile = document.getElementById('noteEditPhotoInput') ? document.getElementById('noteEditPhotoInput').files[0] : null;
            if (newPhotoFile) {
              var ext = (newPhotoFile.name.split('.').pop() || 'jpg').toLowerCase();
              patch.photo_url = await sbUploadFile(HUJJATLAR_BUCKET, 'notes/' + Date.now() + '_' + Math.random().toString(36).slice(2) + '.' + ext, newPhotoFile);
            }
            await sbPatch('reading_notes?id=eq.' + noteId, patch);
            var editedNote = allNotes.find(function (nn) { return String(nn.id) === String(noteId); });
            if (editedNote) { editedNote.note = newText; editedNote.edited = true; if (patch.photo_url) editedNote.photo_url = patch.photo_url; }
            noteEditTarget = null;
            vibrate('light');
            renderBookDetail();
          } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); sBtn.disabled = false; }
        });
      });
      document.querySelectorAll('[data-del-note]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var noteId = btn.dataset.delNote;
          confirmAction("Bu yozuvni o'chirasizmi?", async function () {
            try {
              await sbDelete('reading_notes?id=eq.' + noteId);
              _bdCache.allNotes = allNotes.filter(function (nn) { return String(nn.id) !== String(noteId); });
              vibrate('medium');
              renderBookDetail();
            } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
          });
        });
      });
      var sendCommentBtnEl = document.getElementById('sendCommentBtn');
      if (sendCommentBtnEl) sendCommentBtnEl.addEventListener('click', function () {
        if (iAmBlocked) { showAlert('Siz blok qilingansiz.'); return; }
        var input = document.getElementById('commentInput');
        var text = input.value.trim();
        if (!text) return;
        if (editTarget) {
          var editId = editTarget.id;
          showAlert("Bu xabaringiz boshqa o'qiyotganlarga ko'rinadi.", async function () {
            try {
              await sbPatch('comments?id=eq.' + editId, { text: text, edited: true });
              var editedC = comments.find(function (cc) { return String(cc.id) === String(editId); });
              if (editedC) { editedC.text = text; editedC.edited = true; }
              input.value = '';
              editTarget = null;
              vibrate('light');
              renderBookDetail();
            } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
          });
          return;
        }
        showAlert("Bu xabaringiz boshqa o'qiyotganlarga ko'rinadi.", async function () {
          try {
            var inserted = await sbPost('comments', { book_id: book.id, user_id: ME.id, user_name: isAdminMode ? 'Admin' : ME.name, text: text, reply_to_id: replyTarget ? replyTarget.id : null, cohort_start_date: myCohortMarker || null });
            if (inserted && inserted[0]) comments.push(inserted[0]);
            input.value = '';
            if (replyTarget) expandedReplies[replyTarget.id] = true;
            replyTarget = null;
            vibrate('light');
            renderBookDetail();
          } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
        });
      });
    } else if (state.detailTab === 'progress') {
      if (_cohortCountdownInterval) { clearInterval(_cohortCountdownInterval); _cohortCountdownInterval = null; }
      var countdownEl = document.getElementById('cohortCountdown');
      if (countdownEl) {
        var targetMs = parseInt(countdownEl.dataset.target, 10);
        var updateCountdown = function () {
          var diffMs = targetMs - Date.now();
          if (diffMs <= 0) { countdownEl.textContent = "O'qish boshlandi, sahifani yangilang."; clearInterval(_cohortCountdownInterval); return; }
          var totalSec = Math.floor(diffMs / 1000);
          var days = Math.floor(totalSec / 86400);
          var hours = Math.floor((totalSec % 86400) / 3600);
          var mins = Math.floor((totalSec % 3600) / 60);
          countdownEl.textContent = '⏳ Boshlanishiga: ' + days + ' kun ' + hours + ' soat ' + mins + ' daqiqa qoldi';
        };
        updateCountdown();
        _cohortCountdownInterval = setInterval(updateCountdown, 1000);
      }
      var noteInputEl = document.getElementById('noteInput');
      var noteCharCountEl = document.getElementById('noteCharCount');
      if (noteInputEl) {
        noteInputEl.addEventListener('input', function () {
          noteCharCountEl.textContent = noteInputEl.value.length;
        });
      }
      var noteCoverInputEl = document.getElementById('noteCoverInput');
      if (noteCoverInputEl) {
        noteCoverInputEl.addEventListener('change', function () {
          var f = this.files[0];
          var prevEl = document.getElementById('noteCoverPreview');
          if (!f) { prevEl.innerHTML = ''; return; }
          if (f.size > 8 * 1024 * 1024) { showAlert('Rasm hajmi katta (8MB dan oshmasin).'); this.value = ''; prevEl.innerHTML = ''; return; }
          prevEl.innerHTML = '<div style="position:relative;display:inline-block">' +
            '<img src="' + URL.createObjectURL(f) + '" class="note-photo-img" />' +
            '<button type="button" id="removeNoteCoverBtn" style="position:absolute;top:-8px;right:-8px;width:26px;height:26px;border-radius:50%;border:none;background:var(--danger);color:#fff;font-size:14px;font-weight:700;line-height:1;cursor:pointer">✕</button>' +
            '</div>';
          document.getElementById('removeNoteCoverBtn').addEventListener('click', function () {
            document.getElementById('noteCoverInput').value = '';
            prevEl.innerHTML = '';
          });
        });
      }
      var updateBtnEl = document.getElementById('updateProgressBtn');
      if (updateBtnEl) {
        updateBtnEl.addEventListener('click', async function () {
          if (iAmBlocked) { showAlert('Siz blok qilingansiz.'); return; }
          var pagesInputEl = document.getElementById('pagesInput');
          var requestedPages = parseInt(pagesInputEl.value, 10);
          if (isNaN(requestedPages) || requestedPages < 0) { showAlert("Oxirgi o'qilgan bet sonini to'g'ri kiriting."); return; }
          var noteText = noteInputEl.value.trim();
          if (!noteText) { showAlert("O'qigan betlaringiz haqida fikr yozish shart."); return; }
          var photoFile = document.getElementById('noteCoverInput').files[0];
          if (!photoFile) { showAlert("Rasm yuklang — rasmsiz saqlab bo'lmaydi."); return; }
          if (totalPages && requestedPages > totalPages) requestedPages = totalPages;
          var oldPages = mine ? mine.pages_read : 0;
          var delta = requestedPages - oldPages;
          if (delta <= 0) { showAlert("Yangi bet soni avvalgisidan ko'p bo'lishi kerak."); return; }
          var todayStr2 = cohortTodayStr();
          var alreadyToday = 0;
          try {
            var todayNotesCheck = await sbGet('reading_notes?select=pages_from,pages_read,created_at&book_id=eq.' + book.id + '&user_id=eq.' + ME.id);
            todayNotesCheck.forEach(function (n) {
              var noteDay = localDateStr(new Date(new Date(n.created_at).getTime() - 4 * 3600000));
              if (noteDay === todayStr2) alreadyToday += Math.max(0, (n.pages_read || 0) - (n.pages_from || 0));
            });
          } catch (e) { console.error(e); }
          if (alreadyToday + delta > COHORT_SUGGESTED_DAILY_PAGES) {
            var canStillAdd = Math.max(0, COHORT_SUGGESTED_DAILY_PAGES - alreadyToday);
            showAlert("Kunlik limit " + COHORT_SUGGESTED_DAILY_PAGES + " bet. Bugun allaqachon " + alreadyToday + " bet kiritgansiz, yana faqat " + canStillAdd + " bet kiritishingiz mumkin.");
            return;
          }
          var saveBtn = document.getElementById('updateProgressBtn');
          confirmAction("Hammasini to'g'ri yozdingizmi?", async function () {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Yuklanmoqda...';
            var photoUrl = null;
            try {
              var ext = (photoFile.name.split('.').pop() || 'jpg').toLowerCase();
              photoUrl = await sbUploadFile(HUJJATLAR_BUCKET, 'notes/' + Date.now() + '_' + Math.random().toString(36).slice(2) + '.' + ext, photoFile);
            } catch (e) {
              console.error(e);
              saveBtn.disabled = false;
              saveBtn.textContent = 'Saqlash';
              showAlert("Rasm yuklanmadi. Internetni tekshirib qayta urinib ko'ring.");
              return;
            }
            try {
        await recordReadingActivity();
        await recordSportActivity();
              var finalPages = requestedPages;
              await sbPost('progress?on_conflict=book_id,user_id', {
                book_id: book.id, user_id: ME.id, user_name: ME.name, pages_read: finalPages, updated_at: new Date().toISOString(), cohort_start_date: myCohortMarker,
              }, 'resolution=merge-duplicates,return=representation');
              var insertedNote = await sbPost('reading_notes', {
                book_id: book.id, user_id: ME.id, user_name: ME.name, pages_read: finalPages, pages_from: oldPages, note: noteText, photo_url: photoUrl, cohort_start_date: myCohortMarker,
              });
              if (insertedNote && insertedNote[0]) allNotes.push(insertedNote[0]);
              vibrate('light');
              var nowIso = new Date().toISOString();
              mine.pages_read = finalPages;
              mine.updated_at = nowIso;
              progress.sort(function (a, b) { return b.pages_read - a.pages_read; });
              var finishedPct = totalPages ? Math.min(100, Math.round((finalPages / totalPages) * 100)) : Math.min(100, finalPages);
              var medalMsg = finishedPct >= 100 ? await tryRecordFinish(book) : null;
              if (medalMsg) showAlert(medalMsg);
              else showAlert('Saqlandi.');
              renderBookDetail();
            } catch (e) {
              console.error(e);
              saveBtn.disabled = false;
              saveBtn.textContent = 'Saqlash';
              showAlert('Xatolik yuz berdi.');
            }
          });
        });
      }

      var removeBtn = document.getElementById('removeFromListBtn');
      if (removeBtn) {
        removeBtn.addEventListener('click', function () {
          var isCreatorLeaving = String(book.created_by_id) === String(ME.id);
          var willRefund = !isCreatorLeaving && (myCohortPhase === 'signup' || myCohortPhase === null);
          var confirmText = willRefund
            ? "Guruhdan chiqasizmi? Hali challenj boshlanmaganligi sababli " + formatNumber(JOIN_COST_QOVUN) + " ta qovunchangiz qaytariladi."
            : "Guruhdan chiqasizmi? Progressingiz o'chib ketadi. To'langan qovuncha qaytarilmaydi.";
          confirmAction(confirmText, async function () {
            try {
              await sbDelete('progress?book_id=eq.' + book.id + '&user_id=eq.' + ME.id);
              if (willRefund) {
                await adjustWallet(ME.id, JOIN_COST_QOVUN, 0);
                await addToTreasury(-JOIN_COST_QOVUN);
              }
              vibrate('medium');
              _bdCache = null;
              state.view = 'home'; state.detailTab = 'readers'; render();
            } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
          });
        });
      }
    }
  } catch (e) {
    body.innerHTML = '<div class="empty">Xatolik: kitob topilmadi.</div>';
    console.error(e);
  }
}


// ===== SPORT MODULI =====

var _sportCache = null;
var selectedSportCohortMarker = null;

function sportCohortPhase(markerStr, todayStr, durationDays) {
  return cohortPhase(markerStr, todayStr, durationDays);
}

function sportBookReadingDays(challenge) {
  return challenge.duration_days || 5;
}

async function renderSportHome() {
  setBackButton(false);
  var isTop = state.sportTab === 'top';
  var bodyHtml = isTop
    ? '<div id="sportTopLists"><div class="loading">Yuklanmoqda...</div></div>'
    : '<input id="sportListSearch" class="input" placeholder="Challenj qidirish..." style="margin-bottom:12px"><div id="sportList"><div class="loading">Yuklanmoqda...</div></div>';
  renderShell(
    '<div class="header"><div class="h-title">Sport</div></div>' +
    '<div class="segment">' +
    '<button class="seg-btn' + (state.sportTab === 'top' ? ' active' : '') + '" data-sport-tab="top">🏆 TOP</button>' +
    '<button class="seg-btn' + (state.sportTab === 'all' ? ' active' : '') + '" data-sport-tab="all">Barcha challenjlar</button>' +
    '</div>' + bodyHtml,
    { fab: true, fabAction: 'addSport' }
  );
  if (isTop) {
    await loadSportTopLists();
  } else {
    document.getElementById('sportListSearch').addEventListener('input', renderFilteredSportList);
    await loadSportList();
  }
  document.querySelectorAll('[data-sport-tab]').forEach(function (btn) {
    btn.addEventListener('click', function () { state.sportTab = btn.dataset.sportTab; renderSportHome(); });
  });
}

var _sportListCache = [];
async function loadSportList() {
  _sportListCache = await sbGet('sport_challenges?select=*&approved=eq.true&order=created_at.desc');
  renderFilteredSportList();
}
function renderFilteredSportList() {
  var listEl = document.getElementById('sportList');
  var q = (document.getElementById('sportListSearch') ? document.getElementById('sportListSearch').value.trim().toLowerCase() : '');
  var items = _sportListCache.filter(function (c) { return !q || c.title.toLowerCase().indexOf(q) !== -1; });
  listEl.innerHTML = items.length ? items.map(function (c) { return sportCard(c); }).join('') : '<div class="empty">Challenj topilmadi.</div>';
}
function sportCard(c) {
  return sportCardWithCount(c, null);
}
function sportCardWithCount(c, count) {
  var thumb = c.cover_url ? '<img src="' + c.cover_url + '" class="cover-thumb" />' : '<div class="cover-thumb-placeholder">🏃</div>';
  var meta = count !== null
    ? '<div class="card-meta">👥 ' + count + ' kishi qatnashyapti · ' + c.duration_days + ' kun</div>'
    : '<div class="card-meta">' + c.duration_days + ' kunlik challenj</div>';
  return '<div class="card book-card" data-go="sportDetail" data-sport-id="' + c.id + '">' +
    '<div class="book-card-row">' + thumb +
    '<div class="book-card-info"><div class="card-title">' + escapeHtml(c.title) + '</div>' +
    (c.approved === false ? '<div class="card-meta" style="color:var(--danger)">⏳ Tasdiq kutilmoqda</div>' : '') +
    meta +
    '</div></div></div>';
}

async function loadSportTopLists() {
  var el = document.getElementById('sportTopLists');
  try {
    var results = await Promise.all([
      sbGet('sport_daily_logs?select=user_id,user_name,count_done&order=count_done.desc'),
      sbGet('sport_challenges?select=*&approved=eq.true&order=created_at.desc'),
      sbGet('sport_progress?select=challenge_id,user_id'),
    ]);
    var logs = results[0]; var challenges = results[1]; var allProgress = results[2];
    var memberCounts = {};
    allProgress.forEach(function (p) { memberCounts[p.challenge_id] = (memberCounts[p.challenge_id] || 0) + 1; });
    var userTotals = {};
    logs.forEach(function (l) {
      userTotals[l.user_id] = userTotals[l.user_id] || { name: l.user_name, total: 0 };
      userTotals[l.user_id].total += l.count_done;
    });
    var topSportsmen = Object.keys(userTotals).map(function (id) { return { id: id, name: userTotals[id].name, total: userTotals[id].total }; })
      .sort(function (a, b) { return b.total - a.total; }).slice(0, 5);
    var medalMark = function (i) { return i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : (i + 1); };
    var topSportsmenHtml = topSportsmen.length ? '<div class="readers">' + topSportsmen.map(function (u, i) {
      var isMe = String(u.id) === String(ME.id);
      return '<div class="reader-row' + (isMe ? ' me' : '') + '" data-go="' + (isMe ? 'profile' : 'userBooks') + '" data-userid="' + u.id + '" data-username="' + escapeHtml(u.name) + '">' +
        '<div class="reader-rank">' + medalMark(i) + '</div>' +
        '<div class="reader-info"><div class="reader-name">' + escapeHtml(u.name) + '</div></div>' +
        '<div class="reader-pages">' + formatNumber(u.total) + ' ta</div>' +
        '</div>';
    }).join('') + '</div>' : '<div class="empty">Hali hech kim mashq qilmagan.</div>';
    var topChallengesHtml = challenges.filter(function (c) { return (memberCounts[c.id] || 0) > 0; }).slice(0, 5).map(function (c) {
      var count = memberCounts[c.id] || 0;
      return sportCardWithCount(c, count);
    });
    var topChallengesHtmlStr = topChallengesHtml.length
      ? '<div class="book-list">' + topChallengesHtml.join('') + '</div>'
      : '<div class="empty">Hali qatnashuvchisi bor challenj yo\'q.</div>';
    el.innerHTML =
      '<div class="h-title" style="font-size:16px;margin-bottom:4px">Top 5 sportchi</div>' + topSportsmenHtml +
      '<div class="h-title" style="font-size:16px;margin-top:20px;margin-bottom:10px">Top 5 challenj</div>' + topChallengesHtmlStr;
  } catch (e) { el.innerHTML = '<div class="empty">Yuklanmadi.</div>'; console.error(e); }
}

async function renderSportDetail() {
  setBackButton(true, function () { state.view = 'sport'; render(); });
  var body = document.getElementById('sportDetailBody') || (function () {
    renderShell(
      '<div class="header"><button class="back" data-go="sport">←</button><div class="h-title">Challenj</div></div>' +
      '<div id="sportDetailBody"><div class="loading">Yuklanmoqda...</div></div>'
    );
    return document.getElementById('sportDetailBody');
  })();
  renderShell(
    '<div class="header"><button class="back" data-go="sport">←</button><div class="h-title">Challenj</div></div>' +
    '<div id="sportDetailBody"><div class="loading">Yuklanmoqda...</div></div>'
  );
  await loadSportDetailBody();
}

async function loadSportDetailBody() {
  var body = document.getElementById('sportDetailBody');
  try {
    var today = cohortTodayStr();
    var results = await Promise.all([
      sbGet('sport_challenges?select=*&id=eq.' + state.sportId),
      sbGet('sport_exercises?select=*&challenge_id=eq.' + state.sportId + '&order=sort_order.asc'),
      sbGet('sport_progress?select=*&challenge_id=eq.' + state.sportId + '&order=started_at.asc'),
      sbGet('sport_progress?select=challenge_id,cohort_start_date&user_id=eq.' + ME.id),
    ]);
    var challenge = results[0][0];
    if (!challenge) { body.innerHTML = '<div class="empty">Challenj topilmadi.</div>'; return; }
    if (challenge.approved === false && String(challenge.created_by_id) !== String(ME.id) && !isAdminMode) {
      body.innerHTML = '<div class="empty">⏳ Bu challenj hali admin tomonidan tasdiqlanmagan.</div>'; return;
    }
    var exercises = results[1];
    var progress = results[2];
    var myAllSportProgress = results[3];
    var durationDays = sportBookReadingDays(challenge);
    var signupMarker = currentSignupCohortMarker(today);
    var nextMarker = nextUpcomingCohortMarker(today);
    var mine = progress.find(function (p) { return String(p.user_id) === String(ME.id); });
    var myCohortMarker = mine ? mine.cohort_start_date : null;
    var myCohortPhase = myCohortMarker ? sportCohortPhase(myCohortMarker, today, durationDays) : null;
    var otherActive = myAllSportProgress.find(function (p) {
      if (String(p.challenge_id) === String(state.sportId)) return false;
      if (!p.cohort_start_date) return false;
      var ph = sportCohortPhase(p.cohort_start_date, today, durationDays);
      return ph !== 'ended';
    });
    var membersByMarker = {};
    progress.forEach(function (p) { if (p.cohort_start_date) membersByMarker[p.cohort_start_date] = (membersByMarker[p.cohort_start_date] || 0) + 1; });
    var allMarkers = nearbyCohortMarkers(today);
    var activeMarkers = [], endedMarkers = [];
    allMarkers.forEach(function (m) {
      var ph = sportCohortPhase(m, today, durationDays);
      if (ph === null) { if (m === nextMarker) activeMarkers.push(m); return; }
      if (ph === 'ended') { if (membersByMarker[m]) endedMarkers.push(m); return; }
      if (membersByMarker[m] || ph === 'signup') activeMarkers.push(m);
    });
    activeMarkers.sort(); endedMarkers.sort();
    var selectedSportMarker = state.selectedSportCohortMarker || myCohortMarker || signupMarker;
    var viewParticipants = selectedSportMarker ? progress.filter(function (p) { return p.cohort_start_date === selectedSportMarker; }) : [];
    var viewMarkerPhase = selectedSportMarker ? sportCohortPhase(selectedSportMarker, today, durationDays) : null;
    var canJoin = !mine && !otherActive && selectedSportMarker && (viewMarkerPhase === 'signup' || selectedSportMarker === nextMarker);

    var userTotalsMap = {};
    if (viewParticipants.length && selectedSportMarker) {
      var cohortLogs = await sbGet('sport_daily_logs?select=user_id,count_done&challenge_id=eq.' + state.sportId + '&cohort_start_date=eq.' + selectedSportMarker);
      cohortLogs.forEach(function (l) { userTotalsMap[l.user_id] = (userTotalsMap[l.user_id] || 0) + l.count_done; });
    }
    viewParticipants = viewParticipants.slice().sort(function (a, b) {
      return (userTotalsMap[b.user_id] || 0) - (userTotalsMap[a.user_id] || 0);
    });

    function schedRowHtml(m) {
      var count = membersByMarker[m] || 0;
      var isMine = m === myCohortMarker;
      var isSel = m === selectedSportMarker;
      return '<div class="cohort-sched-row' + (isSel ? ' mine' : '') + '" data-sport-view-cohort="' + m + '" style="cursor:pointer;display:flex;justify-content:space-between;align-items:center">' +
        '<div class="cohort-sched-date">Start sanasi: ' + formatDate(m) + (isMine ? ' <span style="color:var(--accent-1);font-weight:600">(siz qatnashayotgan)</span>' : '') + '</div>' +
        '<div class="cohort-sched-meta">' + count + ' kishi</div>' +
        '</div>';
    }
    var schedHtml = '<div class="cohort-schedule">' + activeMarkers.map(schedRowHtml).join('') + '</div>' +
      (endedMarkers.length ? '<button id="sportArchiveBtn" class="btn-small" style="margin-top:10px">📦 Arxiv (' + endedMarkers.length + ')</button><div id="sportArchiveList" class="cohort-schedule" style="display:none;margin-top:8px">' + endedMarkers.map(schedRowHtml).join('') + '</div>' : '');

    var exercisesHtml = exercises.map(function (e) {
      return '<div class="hint" style="margin-bottom:6px"><b>' + escapeHtml(e.name) + '</b>: jami ' + formatNumber(e.total_count) + ' ta · kuniga ' + formatNumber(e.daily_count) + ' ta</div>';
    }).join('');

    var participantsHtml = viewParticipants.length
      ? '<div class="readers">' + viewParticipants.map(function (p, i) {
        var rankMark = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : (i + 1);
        var isMe = String(p.user_id) === String(ME.id);
        var total = userTotalsMap[p.user_id] || 0;
        return '<div class="reader-row' + (isMe ? ' me' : '') + '" data-go="' + (isMe ? 'profile' : 'userBooks') + '" data-userid="' + p.user_id + '" data-username="' + escapeHtml(p.user_name) + '">' +
          '<div class="reader-rank">' + rankMark + '</div>' +
          '<div class="reader-info"><div class="reader-name">' + escapeHtml(p.user_name) + '</div>' +
          '<div class="reader-note">📅 ' + formatDate(p.started_at) + '</div></div>' +
          '<div class="reader-pages">' + formatNumber(total) + ' ta</div>' +
          '</div>';
      }).join('') + '</div>'
      : '<div class="empty">Hali hech kim qo\'shilmagan.</div>';

    var participantsTab = schedHtml +
      (canJoin ? '<button id="joinSportBtn" class="btn-primary full" data-marker="' + selectedSportMarker + '" style="margin:10px 0">✅ Qo\'shilish (1 proteincha)</button>' : '') +
      '<div class="section-label" style="margin-top:12px">' + (selectedSportMarker ? formatDate(selectedSportMarker) + ' guruhi' : 'Qatnashuvchilar') + '</div>' +
      participantsHtml;

    var myProgressTab = '';
    if (!mine) {
      myProgressTab = '<div class="empty">Qo\'shilish uchun "Qatnashuvchilar" bo\'limiga o\'ting.</div>';
    } else if (myCohortPhase === 'signup' || myCohortPhase === null) {
      var readingStart = new Date(myCohortMarker + 'T04:00:00').getTime();
      var msLeft = readingStart - Date.now();
      var dDays = Math.floor(msLeft / 86400000);
      var dHours = Math.floor((msLeft % 86400000) / 3600000);
      var dMins = Math.floor((msLeft % 3600000) / 60000);
      myProgressTab = '<div class="hint">⏳ Boshlanishiga: ' + dDays + ' kun ' + dHours + ' soat ' + dMins + ' daqiqa qoldi</div>' +
        '<button id="sportLeaveBtn" class="remove-link" style="margin-top:16px">Guruhdan chiqish</button>';
    } else if (myCohortPhase === 'reading') {
      var todayLogs = await sbGet('sport_daily_logs?select=*&challenge_id=eq.' + state.sportId + '&user_id=eq.' + ME.id + '&log_date=eq.' + today);
      var logsByExercise = {};
      todayLogs.forEach(function (l) { logsByExercise[l.exercise_id] = l.count_done; });
      var exerciseInputs = exercises.map(function (e) {
        return '<div style="margin-bottom:10px"><label style="font-size:13px;color:var(--text-muted)">' + escapeHtml(e.name) + ' (kuniga ' + e.daily_count + ' ta)</label>' +
          '<input class="input sport-exercise-input" type="number" min="0" max="' + e.daily_count + '" placeholder="Bugun nechta qildingiz?" data-exercise-id="' + e.id + '" data-exercise-name="' + escapeHtml(e.name) + '" value="' + (logsByExercise[e.id] || '') + '" /></div>';
      }).join('');
      myProgressTab =
        '<div class="section-label">Bugungi natijalar</div>' +
        '<div class="form">' + exerciseInputs +
        '<label class="file-btn" for="sportPhotoBeforeInput">📷 Before rasm (majburiy)</label>' +
        '<input type="file" id="sportPhotoBeforeInput" accept="image/*" style="display:none" />' +
        '<div id="sportPhotoBeforePreview"></div>' +
        '<label class="file-btn" for="sportPhotoAfterInput" style="margin-top:8px">📷 After rasm (majburiy)</label>' +
        '<input type="file" id="sportPhotoAfterInput" accept="image/*" style="display:none" />' +
        '<div id="sportPhotoAfterPreview"></div>' +
        '<button id="saveSportLogBtn" class="btn-primary full" style="margin-top:12px">Izohlar bo\'limiga yuborish</button>' +
        '</div>' +
        '<button id="sportLeaveBtn" class="remove-link" style="margin-top:16px">Guruhdan chiqish</button>';
    } else {
      myProgressTab = '<div class="hint">⛔ Challenj yakunlandi.</div>' +
        '<button id="sportLeaveBtn" class="remove-link" style="margin-top:16px">Guruhdan chiqish</button>';
    }

    var tabsHtml = '<div class="segment">' +
      '<button class="seg-btn' + (state.sportDetailTab === 'participants' ? ' active' : '') + '" data-sport-detail-tab="participants">Qatnashuvchilar</button>' +
      '<button class="seg-btn' + (state.sportDetailTab === 'comments' ? ' active' : '') + '" data-sport-detail-tab="comments">Izohlar</button>' +
      '<button class="seg-btn' + (state.sportDetailTab === 'progress' ? ' active' : '') + '" data-sport-detail-tab="progress">Mening jarayonim</button>' +
      '</div>';

    var sportLogsTab = '';
    if (myCohortMarker) {
      var allLogs = await sbGet('sport_daily_logs?select=*&challenge_id=eq.' + state.sportId + '&cohort_start_date=eq.' + myCohortMarker + '&order=created_at.desc');
      var logsByUserDay = {};
      allLogs.forEach(function (l) {
        var key = l.user_id + '_' + l.log_date;
        if (!logsByUserDay[key]) logsByUserDay[key] = { user_name: l.user_name, log_date: l.log_date, photo_before_url: l.photo_before_url, photo_after_url: l.photo_after_url, created_at: l.created_at, exercises: [] };
        logsByUserDay[key].exercises.push({ name: l.exercise_name, done: l.count_done });
      });
      var logCards = Object.values(logsByUserDay).sort(function (a, b) { return new Date(b.created_at) - new Date(a.created_at); });
      sportLogsTab = logCards.length ? '<div class="comments">' + logCards.map(function (entry) {
        var exLines = entry.exercises.map(function (e) {
          var ex = exercises.find(function (x) { return x.name === e.name; });
          var daily = ex ? ex.daily_count : '?';
          return '<div style="font-size:13px">💪 ' + escapeHtml(e.name) + ': <b>' + e.done + '/' + daily + '</b></div>';
        }).join('');
        return '<div class="comment-card" style="margin-bottom:14px;background:var(--surface);border-radius:14px;padding:14px">' +
          '<div style="display:flex;justify-content:space-between;margin-bottom:8px">' +
          '<div class="reader-name">' + escapeHtml(entry.user_name) + '</div>' +
          '<div class="reader-note">' + formatDateTime(entry.created_at) + '</div>' +
          '</div>' +
          exLines +
          '<div style="display:flex;gap:8px;margin-top:10px">' +
          (entry.photo_before_url ? '<img src="' + entry.photo_before_url + '" class="note-photo-img" style="flex:1;max-width:48%" />' : '') +
          (entry.photo_after_url ? '<img src="' + entry.photo_after_url + '" class="note-photo-img" style="flex:1;max-width:48%" />' : '') +
          '</div></div>';
      }).join('') + '</div>' : '<div class="empty">Hali hech kim natija kirmagan.</div>';
    } else {
      sportLogsTab = '<div class="empty">Guruhga qo\'shilsangiz izohlarni ko\'rasiz.</div>';
    }

    body.innerHTML =
      '<div class="book-card-row" style="margin-bottom:12px">' +
      (challenge.cover_url ? '<img src="' + challenge.cover_url + '" class="cover-hero" style="width:100px;height:100px;object-fit:cover;border-radius:12px;flex-shrink:0" />' : '<div class="cover-hero-placeholder" style="width:100px;height:100px;font-size:40px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:var(--surface);flex-shrink:0">🏃</div>') +
      '<div class="book-hero-info" style="padding-left:12px">' +
      '<div class="book-hero-title">' + escapeHtml(challenge.title) + '</div>' +
      '<div class="book-hero-sub">' + durationDays + ' kun · ' + exercises.length + ' mashq</div>' +
      '</div></div>' +
      (challenge.description ? '<div class="hint">' + escapeHtml(challenge.description) + '</div>' : '') +
      exercisesHtml +
      tabsHtml +
      '<div id="sportDetailContent">' + (state.sportDetailTab === 'participants' ? participantsTab : state.sportDetailTab === 'comments' ? sportLogsTab : myProgressTab) + '</div>';

    document.querySelectorAll('[data-sport-detail-tab]').forEach(function (btn) {
      btn.addEventListener('click', function () { state.sportDetailTab = btn.dataset.sportDetailTab; loadSportDetailBody(); });
    });
    document.querySelectorAll('[data-sport-view-cohort]').forEach(function (row) {
      row.addEventListener('click', function () { state.selectedSportCohortMarker = row.dataset.sportViewCohort; loadSportDetailBody(); });
    });
    var archiveBtn = document.getElementById('sportArchiveBtn');
    if (archiveBtn) archiveBtn.addEventListener('click', function () { var l = document.getElementById('sportArchiveList'); l.style.display = l.style.display === 'none' ? 'block' : 'none'; });

    var joinBtn = document.getElementById('joinSportBtn');
    if (joinBtn) joinBtn.addEventListener('click', function () {
      if (iAmBlocked) { showAlert('Siz blok qilingansiz.'); return; }
      var marker = joinBtn.dataset.marker;
      var isCreator = String(challenge.created_by_id) === String(ME.id);
      var msg = isCreator ? "Guruhga qo'shilasizmi?" : ("Qo'shilish narxi 1 ta proteincha. Tasdiqlaysizmi?");
      confirmAction(msg, async function () {
        try {
          var wallet = await getOrCreateWallet(ME.id, ME.name, ME.username);
          if (!isCreator && (wallet.proteincha_balance || 0) < 1) { showAlert("Proteinchangiz yetarli emas. Qo'shilish uchun 1 ta proteincha kerak."); return; }
          var nowIso = new Date().toISOString();
          await sbPost('sport_progress?on_conflict=challenge_id,user_id', { challenge_id: state.sportId, user_id: ME.id, user_name: ME.name, cohort_start_date: marker, started_at: nowIso }, 'resolution=merge-duplicates,return=representation');
          if (!isCreator) {
            await adjustWallet(ME.id, 0, -1);
            await addToTreasury(0);
          }
          try { await sbPost('sport_join_confirmations', { challenge_id: state.sportId, user_id: ME.id, challenge_title: challenge.title, cohort_start_date: marker }); } catch (e) { console.error(e); }
          if (!isCreator) {
            try { await sbPost('sport_join_notifications', { challenge_id: state.sportId, creator_id: challenge.created_by_id, cohort_start_date: marker }); } catch (e) { console.error(e); }
          }
          state.selectedSportCohortMarker = null;
          vibrate('light');
          showAlert("Guruhga qo'shildingiz!");
          loadSportDetailBody();
        } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
      });
    });

    var leaveBtn = document.getElementById('sportLeaveBtn');
    if (leaveBtn) leaveBtn.addEventListener('click', function () {
      var willRefund = myCohortPhase === 'signup' || myCohortPhase === null;
      var isCreator = String(challenge.created_by_id) === String(ME.id);
      var txt = (willRefund && !isCreator) ? "Guruhdan chiqasizmi? Challenj boshlanmaganligi uchun 1 ta proteinchangiz qaytariladi." : "Guruhdan chiqasizmi? Progressingiz o'chib ketadi.";
      confirmAction(txt, async function () {
        try {
          await sbDelete('sport_progress?challenge_id=eq.' + state.sportId + '&user_id=eq.' + ME.id);
          if (willRefund && !isCreator) await adjustWallet(ME.id, 0, 1);
          vibrate('medium');
          state.view = 'sport'; render();
        } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); }
      });
    });

    var saveSportLogBtn = document.getElementById('saveSportLogBtn');
    if (saveSportLogBtn) saveSportLogBtn.addEventListener('click', async function () {
      var beforeFile = document.getElementById('sportPhotoBeforeInput').files[0];
      var afterFile = document.getElementById('sportPhotoAfterInput').files[0];
      if (!beforeFile) { showAlert("Before rasm yuklang."); return; }
      if (!afterFile) { showAlert("After rasm yuklang."); return; }
      var inputs = document.querySelectorAll('.sport-exercise-input');
      var hasData = false;
      inputs.forEach(function (inp) { if (parseInt(inp.value, 10) > 0) hasData = true; });
      if (!hasData) { showAlert("Kamida bitta mashq uchun son kiriting."); return; }
      saveSportLogBtn.disabled = true; saveSportLogBtn.textContent = 'Yuklanmoqda...';
      try {
        var ext1 = (beforeFile.name.split('.').pop() || 'jpg').toLowerCase();
        var ext2 = (afterFile.name.split('.').pop() || 'jpg').toLowerCase();
        var beforeUrl = await sbUploadFile(HUJJATLAR_BUCKET, 'sport/before_' + Date.now() + '_' + Math.random().toString(36).slice(2) + '.' + ext1, beforeFile);
        var afterUrl = await sbUploadFile(HUJJATLAR_BUCKET, 'sport/after_' + Date.now() + '_' + Math.random().toString(36).slice(2) + '.' + ext2, afterFile);
        for (var inp of inputs) {
          var val = parseInt(inp.value, 10);
          if (isNaN(val) || val < 0) continue;
          var exId = inp.dataset.exerciseId;
          var exName = inp.dataset.exerciseName;
          var dailyMax = exercises.find(function (e) { return String(e.id) === String(exId); });
          var capped = dailyMax ? Math.min(val, dailyMax.daily_count) : val;
          await sbPost('sport_daily_logs', { challenge_id: state.sportId, user_id: ME.id, user_name: ME.name, cohort_start_date: myCohortMarker, log_date: today, exercise_id: exId, exercise_name: exName, count_done: capped, photo_before_url: beforeUrl, photo_after_url: afterUrl });
        }
        await recordReadingActivity();
        vibrate('light');
        showAlert("Saqlandi!");
        loadSportDetailBody();
      } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); saveSportLogBtn.disabled = false; saveSportLogBtn.textContent = 'Izohlar bo\'limiga yuborish'; }
    });

    ['sportPhotoBeforeInput', 'sportPhotoAfterInput'].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      var previewId = id === 'sportPhotoBeforeInput' ? 'sportPhotoBeforePreview' : 'sportPhotoAfterPreview';
      el.addEventListener('change', function () {
        var f = this.files[0];
        var prev = document.getElementById(previewId);
        if (!f || !prev) return;
        prev.innerHTML = '<img src="' + URL.createObjectURL(f) + '" class="note-photo-img" />';
      });
    });
  } catch (e) { body.innerHTML = '<div class="empty">Xatolik yuz berdi.</div>'; console.error(e); }
}

async function renderAddSport() {
  setBackButton(true, function () { state.view = 'sport'; render(); });
  renderShell(
    '<div class="header"><button class="back" data-go="sport">←</button><div class="h-title">Yangi sport challenj</div></div>' +
    '<div class="form" style="padding:16px">' +
    '<input id="sportTitle" class="input" placeholder="Challenj nomi (shart)" />' +
    '<textarea id="sportDesc" class="input" rows="2" placeholder="Tavsif (ixtiyoriy)"></textarea>' +
    '<label class="file-btn" for="sportCoverInput">📷 Rasm yuklash</label>' +
    '<input type="file" id="sportCoverInput" accept="image/*" style="display:none" />' +
    '<div id="sportCoverPreview"></div>' +
    '<input id="sportDuration" class="input" type="number" min="1" max="30" placeholder="Necha kunlik challenj? (masalan: 5)" />' +
    '<div class="section-label" style="margin-top:16px">Mashqlar</div>' +
    '<div id="sportExercisesList"></div>' +
    '<button id="addExerciseBtn" class="btn-small" style="margin-top:8px">+ Mashq qo\'shish</button>' +
    '<button id="createSportBtn" class="btn-primary full" style="margin-top:16px">Yaratish</button>' +
    '</div>'
  );
  var exercises = [];
  function renderExercises() {
    var el = document.getElementById('sportExercisesList');
    el.innerHTML = exercises.map(function (e, i) {
      return '<div style="background:var(--surface);border-radius:10px;padding:10px;margin-bottom:8px">' +
        '<input class="input ex-name" type="text" placeholder="Mashq nomi (masalan: Otjimani)" value="' + escapeHtml(e.name) + '" data-idx="' + i + '" />' +
        '<div style="display:flex;gap:8px">' +
        '<input class="input ex-total" type="number" min="1" placeholder="Jami soni" value="' + (e.total || '') + '" data-idx="' + i + '" style="flex:1" />' +
        '<input class="input ex-daily" type="number" min="1" placeholder="Kuniga" value="' + (e.daily || '') + '" data-idx="' + i + '" style="flex:1" />' +
        '</div>' +
        '<button class="remove-link" data-remove-ex="' + i + '">O\'chirish</button>' +
        '</div>';
    }).join('') || '<div class="empty" style="font-size:13px">Hali mashq yo\'q</div>';
    el.querySelectorAll('.ex-name').forEach(function (inp) { inp.addEventListener('input', function () { exercises[inp.dataset.idx].name = inp.value; }); });
    el.querySelectorAll('.ex-total').forEach(function (inp) { inp.addEventListener('input', function () { exercises[inp.dataset.idx].total = parseInt(inp.value, 10) || 0; }); });
    el.querySelectorAll('.ex-daily').forEach(function (inp) { inp.addEventListener('input', function () { exercises[inp.dataset.idx].daily = parseInt(inp.value, 10) || 0; }); });
    el.querySelectorAll('[data-remove-ex]').forEach(function (btn) { btn.addEventListener('click', function () { exercises.splice(parseInt(btn.dataset.removeEx, 10), 1); renderExercises(); }); });
  }
  renderExercises();
  document.getElementById('addExerciseBtn').addEventListener('click', function () { exercises.push({ name: '', total: 0, daily: 0 }); renderExercises(); });
  document.getElementById('sportCoverInput').addEventListener('change', function () {
    var f = this.files[0];
    if (!f) return;
    document.getElementById('sportCoverPreview').innerHTML = '<img src="' + URL.createObjectURL(f) + '" class="note-photo-img" />';
  });
  document.getElementById('createSportBtn').addEventListener('click', async function () {
    var title = document.getElementById('sportTitle').value.trim();
    if (!title) { showAlert("Challenj nomini kiriting."); return; }
    var duration = parseInt(document.getElementById('sportDuration').value, 10);
    if (!duration || duration < 1) { showAlert("Kunlik muddat kiriting."); return; }
    if (!exercises.length) { showAlert("Kamida bitta mashq qo'shing."); return; }
    for (var e of exercises) {
      if (!e.name || !e.total || !e.daily) { showAlert("Barcha mashqlar uchun nom, jami va kunlik sonni kiriting."); return; }
    }
    var myActive = await sbGet('sport_progress?select=challenge_id,cohort_start_date&user_id=eq.' + ME.id);
    var todayStr = cohortTodayStr();
    for (var p of myActive) {
      var ch = await sbGet('sport_challenges?select=duration_days&id=eq.' + p.challenge_id);
      if (!ch[0]) continue;
      var ph = sportCohortPhase(p.cohort_start_date, todayStr, ch[0].duration_days);
      if (ph && ph !== 'ended') { showAlert("Sizning faol sport challenjingiz bor. Yangi yaratish uchun avvalgisi tugashini kuting."); return; }
    }
    var btn = this; btn.disabled = true; btn.textContent = 'Yuklanmoqda...';
    try {
      var coverUrl = null;
      var coverFile = document.getElementById('sportCoverInput').files[0];
      if (coverFile) {
        var ext = (coverFile.name.split('.').pop() || 'jpg').toLowerCase();
        coverUrl = await sbUploadFile(HUJJATLAR_BUCKET, 'sport/covers/' + Date.now() + '_' + Math.random().toString(36).slice(2) + '.' + ext, coverFile);
      }
      var desc = document.getElementById('sportDesc').value.trim();
      var created = await sbPost('sport_challenges', { title: title, description: desc || null, cover_url: coverUrl, duration_days: duration, created_by_id: ME.id, created_by_name: ME.name, approved: false });
      var cid = created[0].id;
      for (var i = 0; i < exercises.length; i++) {
        await sbPost('sport_exercises', { challenge_id: cid, name: exercises[i].name, total_count: exercises[i].total, daily_count: exercises[i].daily, sort_order: i });
      }
      var marker = currentSignupCohortMarker(cohortTodayStr());
      if (marker) await sbPost('sport_progress', { challenge_id: cid, user_id: ME.id, user_name: ME.name, cohort_start_date: marker });
      vibrate('medium');
      showAlert("Challenj yaratildi! Admin tasdiqlashini kuting.");
      state.view = 'sport'; render();
    } catch (e) { console.error(e); showAlert('Xatolik yuz berdi.'); btn.disabled = false; btn.textContent = 'Yaratish'; }
  });
}

// ===== Tez kunda ekrani =====
function renderComingSoon(icon, title) {
  setBackButton(false);
  renderShell('<div class="coming-soon"><div class="cs-icon">' + icon + '</div><div class="cs-title">' + title + '</div><div class="cs-sub">Tez kunda...</div></div>');
}

// ===== Voqealar (event delegation) =====
document.addEventListener('click', function (e) {
  var goEl = e.target.closest('[data-go]');
  if (goEl) {
    var view = goEl.dataset.go;
    if (_cohortCountdownInterval) { clearInterval(_cohortCountdownInterval); _cohortCountdownInterval = null; }
    if (view === 'bookDetail') { state.bookId = parseInt(goEl.dataset.id, 10); state.detailTab = 'readers'; replyTarget = null; editTarget = null; expandedReplies = {}; noteEditTarget = null; selectedCohortMarker = null; _bdCache = null; }
    if (view === 'userBooks') { state.viewUserId = parseInt(goEl.dataset.userid, 10); state.viewUserName = goEl.dataset.username; }
    if (view === 'sportDetail') { state.sportId = parseInt(goEl.dataset.sportId, 10); state.sportDetailTab = 'participants'; state.selectedSportCohortMarker = null; }
    if (view === 'addSport') { state.view = 'addSport'; render(); return; }
    state.view = view;
    render();
    return;
  }
  var tabEl = e.target.closest('[data-tab]');
  if (tabEl) { state.tab = tabEl.dataset.tab; render(); return; }
});

(function () {
  try {
    var startParam = tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param;
    if (startParam && startParam.indexOf('book_') === 0) {
      var bookIdFromLink = parseInt(startParam.slice(5), 10);
      if (bookIdFromLink) { state.view = 'bookDetail'; state.bookId = bookIdFromLink; state.detailTab = 'readers'; }
    } else if (startParam && startParam.indexOf('sport_') === 0) {
      var sportIdFromLink = parseInt(startParam.slice(6), 10);
      if (sportIdFromLink) { state.view = 'sportDetail'; state.sportId = sportIdFromLink; state.sportDetailTab = 'participants'; }
    }
  } catch (e) { console.error(e); }
})();

render();
</script>
</body>
</html>
