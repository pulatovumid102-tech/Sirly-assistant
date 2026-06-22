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
    main()
