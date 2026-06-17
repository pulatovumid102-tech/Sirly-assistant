# -*- coding: utf-8 -*-

import json
import logging
import os
import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

TOKEN = "8935324683:AAFrVn1gszbbU5il0Us5dsMHWLLIHNHlVgw"
CHAT_ID = -1003914304171

SB_URL = "https://ubakgpkcemlchpfejmke.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InViYWtncGtjZW1sY2hwZmVqbWtlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzMjc3NzUsImV4cCI6MjA5NTkwMzc3NX0.wkKSmoTB9RwREFjcJfe0dNBzZDEw2DHxNM3G6erHSJU"
SB_HEADERS = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}

async def sb_save_screenshot(username, time_key, status):
    now = datetime.now(TIMEZONE)
    rid = f"{username}_{time_key.replace(':', '')}_{now.strftime('%d%m%Y')}"
    data = {"id": rid, "username": username, "time_key": time_key, "sent_at": now.isoformat(), "status": status, "date": now.strftime("%d.%m.%Y")}
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{SB_URL}/rest/v1/screenshots?id=eq.{rid}", headers=SB_HEADERS)
            if r.json():
                await c.patch(f"{SB_URL}/rest/v1/screenshots?id=eq.{rid}", headers=SB_HEADERS, json={"status": status})
            else:
                await c.post(f"{SB_URL}/rest/v1/screenshots", headers=SB_HEADERS, json=data)
    except Exception as e:
        logger.error(f"sb_save error: {e}")

# =========================
# HUJJATLAR -> "Botga yuborish" navbati
# =========================

async def check_file_send_requests_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{SB_URL}/rest/v1/file_send_requests?status=eq.pending&select=*", headers=SB_HEADERS)
            rows = r.json()
            if not isinstance(rows, list):
                return
            for row in rows:
                rid = row.get("id")
                chat_id = row.get("chat_id")
                kind = row.get("kind") or "file"
                try:
                    if kind == "message":
                        text = row.get("message_text") or ""
                        await context.bot.send_message(chat_id=chat_id, text=text)
                    else:
                        file_url = row.get("file_url")
                        file_name = row.get("file_name") or "fayl"
                        fr = await c.get(file_url)
                        fr.raise_for_status()
                        await context.bot.send_document(chat_id=chat_id, document=fr.content, filename=file_name)
                    await c.patch(f"{SB_URL}/rest/v1/file_send_requests?id=eq.{rid}", headers=SB_HEADERS, json={"status": "sent"})
                except Exception as e:
                    logger.error(f"file_send error for {rid}: {e}")
                    try:
                        await c.patch(f"{SB_URL}/rest/v1/file_send_requests?id=eq.{rid}", headers=SB_HEADERS, json={"status": "error"})
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"check_file_send_requests_job error: {e}")

# =========================
# SEKRETAR -> uchrashuv eslatmalari
# =========================

async def check_bot_reminders_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                f"{SB_URL}/rest/v1/bot_reminders",
                headers=SB_HEADERS,
                params={"status": "eq.pending", "remind_at": f"lte.{now_iso}", "select": "*"}
            )
            rows = r.json()
            if not isinstance(rows, list):
                return
            for row in rows:
                rid = row.get("id")
                chat_id = row.get("chat_id")
                text = row.get("text") or ""
                try:
                    await context.bot.send_message(chat_id=chat_id, text=text)
                    await c.patch(f"{SB_URL}/rest/v1/bot_reminders?id=eq.{rid}", headers=SB_HEADERS, json={"status": "sent"})
                except Exception as e:
                    logger.error(f"bot_reminder error for {rid}: {e}")
                    try:
                        await c.patch(f"{SB_URL}/rest/v1/bot_reminders?id=eq.{rid}", headers=SB_HEADERS, json={"status": "error"})
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"check_bot_reminders_job error: {e}")

# =========================
# KAITEN -> kunlik statistika (10:00 va 20:00)
# =========================

async def kaiten_daily_stats_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        time_label = context.job.data.get("label", "")
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                f"{SB_URL}/rest/v1/biznes_data",
                headers=SB_HEADERS,
                params={"id": "eq.kaiten", "select": "data"}
            )
            rows = r.json()
            if not rows or not isinstance(rows, list) or not rows[0].get("data"):
                return
            data = rows[0]["data"]
            tasks = data.get("tasks", [])
            columns = data.get("columns", [
                {"id": "todo", "title": "Topshiriqlar"},
                {"id": "progress", "title": "Jarayonda"},
                {"id": "done", "title": "Bajarildi"},
                {"id": "accepted", "title": "Qabul qilindi"},
            ])
            now = datetime.now(TIMEZONE)
            date_str = now.strftime("%d.%m.%Y")
            lines = [f"📊 Vazifalar holati — {date_str} ({time_label})",""]
            # Group by dept
            dept_tasks = {}
            for t in tasks:
                dept = t.get("dept") or "Boshqa"
                if dept not in dept_tasks:
                    dept_tasks[dept] = []
                dept_tasks[dept].append(t)
            if not dept_tasks:
                lines.append("Hozircha vazifalar yo'q")
            else:
                col_emojis = {"todo":"📋","progress":"▶️","done":"✅","accepted":"🏆"}
                for dept, dtasks in dept_tasks.items():
                    lines.append(f"📁 {dept}")
                    for col in columns:
                        count = sum(1 for t in dtasks if t.get("status") == col["id"])
                        emoji = col_emojis.get(col["id"], "•")
                        lines.append(f"  {emoji} {col['title']}: {count} ta")
                    lines.append("")
            text = "\n".join(lines).strip()
            await context.bot.send_message(chat_id=CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"kaiten_daily_stats_job error: {e}")

async def kaiten_overdue_check_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                f"{SB_URL}/rest/v1/biznes_data",
                headers=SB_HEADERS,
                params={"id": "eq.kaiten", "select": "data"}
            )
            rows = r.json()
            if not rows or not isinstance(rows, list) or not rows[0].get("data"):
                return
            data = rows[0]["data"]
            tasks = data.get("tasks", [])
            now_utc = datetime.now(timezone.utc)
            changed = False
            for t in tasks:
                if t.get("status") in ("done", "accepted"):
                    continue
                if t.get("overdue_notified"):
                    continue
                deadline = t.get("deadline")
                if not deadline:
                    continue
                try:
                    dl_dt = datetime.fromisoformat(deadline)
                    if dl_dt.tzinfo is None:
                        dl_dt = dl_dt.replace(tzinfo=TIMEZONE)
                    dl_dt_utc = dl_dt.astimezone(timezone.utc)
                except Exception as parse_err:
                    logger.error(f"overdue deadline parse error: {parse_err}")
                    continue
                if dl_dt_utc <= now_utc:
                    dept = t.get("dept") or "Boshqa"
                    assignee = t.get("empFio") or "—"
                    creator = t.get("createdByName")
                    deadline_local = dl_dt.astimezone(TIMEZONE).strftime("%d.%m.%Y %H:%M")
                    if creator:
                        text = (
                            f"{dept}da {creator} tomonidan {assignee} uchun yaratilgan\n"
                            f"\"{t.get('text','')}\" vazifasining muddati {deadline_local}da o'tib ketdi."
                        )
                    else:
                        text = (
                            f"{dept}da {assignee} uchun yaratilgan\n"
                            f"\"{t.get('text','')}\" vazifasining muddati {deadline_local}da o'tib ketdi."
                        )
                    try:
                        await context.bot.send_message(chat_id=CHAT_ID, text=text)
                        t["overdue_notified"] = True
                        changed = True
                    except Exception as send_err:
                        logger.error(f"overdue send error: {send_err}")
            if changed:
                await c.patch(
                    f"{SB_URL}/rest/v1/biznes_data?id=eq.kaiten",
                    headers=SB_HEADERS,
                    json={"data": {"tasks": tasks, "columns": data.get("columns", [])}}
                )
    except Exception as e:
        logger.error(f"kaiten_overdue_check_job error: {e}")

# =========================
# ORG STRUKTURA -> CHEKLIST ESLATMALARI
# =========================

ORG_CL_DAY_MAP = {0:"mon",1:"tue",2:"wed",3:"thu",4:"fri",5:"sat",6:"sun"}

async def org_checklist_check_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        now_local = datetime.now(TIMEZONE)
        today_key = ORG_CL_DAY_MAP[now_local.weekday()]
        today_str = now_local.strftime("%Y-%m-%d")
        current_hm = now_local.strftime("%H:%M")
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                f"{SB_URL}/rest/v1/biznes_data",
                headers=SB_HEADERS,
                params={"id": "eq.org", "select": "data"}
            )
            rows = r.json()
            if not rows or not isinstance(rows, list) or not rows[0].get("data"):
                return
            org_nodes = rows[0]["data"]
            changed = False
            for node in org_nodes:
                checklist = node.get("checklist") or []
                if not checklist:
                    continue
                for item in checklist:
                    days = item.get("days") or []
                    if today_key not in days:
                        continue
                    item_time = item.get("time")
                    if item_time != current_hm:
                        continue
                    sent_dates = item.get("sent_dates") or []
                    if today_str in sent_dates:
                        continue
                    fio = node.get("fio") or node.get("name") or "—"
                    tg = (node.get("tg") or "").lstrip("@")
                    person_line = fio + (f" @{tg}" if tg else "")
                    text = f"{person_line} uchun eslatma:\n{item.get('text','')}"
                    cl_id = item.get("id") or f"cl_{node.get('id')}_{item_time}"
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Bajarildi", callback_data=f"orgcl_done:{cl_id}:{today_str}")]])
                    try:
                        sent_msg = await context.bot.send_message(chat_id=CHAT_ID, text=text, reply_markup=keyboard)
                        sent_dates.append(today_str)
                        item["sent_dates"] = sent_dates
                        item["last_msg_id"] = sent_msg.message_id
                        changed = True
                    except Exception as send_err:
                        logger.error(f"org_checklist send error: {send_err}")
            if changed:
                await c.patch(
                    f"{SB_URL}/rest/v1/biznes_data?id=eq.org",
                    headers=SB_HEADERS,
                    json={"data": org_nodes}
                )
    except Exception as e:
        logger.error(f"org_checklist_check_job error: {e}")

async def org_checklist_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        _, cl_id, date_str = query.data.split(":")
        await query.answer("Bajarildi deb belgilandi ✓")
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Bajarildi", callback_data="noop")]])
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.error(f"org_checklist_done_callback error: {e}")
        try:
            await query.answer("Xato yuz berdi")
        except Exception:
            pass

async def schedule_daily_stats(application):
    for hour, label in [(10, "Ertalab"), (20, "Kechki")]:
        secs = seconds_until_time(hour, 0)
        application.job_queue.run_once(
            _daily_stats_once,
            when=secs,
            name=f"kaiten_stats_{hour}",
            data={"hour": hour, "label": label}
        )

async def _daily_stats_once(context: ContextTypes.DEFAULT_TYPE):
    await kaiten_daily_stats_job(context)
    hour = context.job.data["hour"]
    label = context.job.data["label"]
    context.application.job_queue.run_once(
        _daily_stats_once,
        when=86400,
        name=f"kaiten_stats_{hour}",
        data={"hour": hour, "label": label}
    )

# =========================
# KAITEN -> guruhga vazifa xabari
# =========================

async def check_group_messages_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        now_utc = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                f"{SB_URL}/rest/v1/bot_group_messages",
                headers=SB_HEADERS,
                params={"status": "eq.pending", "select": "*"}
            )
            rows = r.json()
            if not isinstance(rows, list):
                return
            for row in rows:
                rid = row.get("id")
                text = row.get("text") or ""
                send_at = row.get("send_at")
                if send_at:
                    try:
                        send_dt = datetime.fromisoformat(send_at.replace("Z", "+00:00"))
                        if send_dt.tzinfo is None:
                            send_dt = send_dt.replace(tzinfo=timezone.utc)
                        if send_dt > now_utc:
                            continue
                    except Exception as parse_err:
                        logger.error(f"send_at parse error for {rid}: {parse_err}")
                try:
                    await context.bot.send_message(chat_id=CHAT_ID, text=text)
                    await c.patch(f"{SB_URL}/rest/v1/bot_group_messages?id=eq.{rid}", headers=SB_HEADERS, json={"status": "sent"})
                except Exception as e:
                    logger.error(f"group_message error for {rid}: {e}")
                    try:
                        await c.patch(f"{SB_URL}/rest/v1/bot_group_messages?id=eq.{rid}", headers=SB_HEADERS, json={"status": "error"})
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"check_group_messages_job error: {e}")


logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("Asia/Tashkent")
ADMIN_USERNAME = "umidpulatov"
NOTIFY_TAGS = "@umidpulatov"

# =========================
# AUTO-DELETE HELPER
# =========================

async def delete_messages_after(bot, chat_id, message_ids, delay=10):
    await asyncio.sleep(delay)
    for mid in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=mid)
        except:
            pass

def schedule_delete(bot, chat_id, message_ids, delay=10):
    asyncio.create_task(delete_messages_after(bot, chat_id, message_ids, delay))

# =========================
# AGENTS
# =========================

AGENTS_FILE = "agents.json"

DEFAULT_AGENTS = {
    "sirlyinfo": {
        "name": "Ozodbek", "username": "sirlyinfo", "phone": "+998 93 798 13 04",
        "work_days": [0, 1, 2, 3, 4, 5, 6],
        "work_hours": {"0": [10, 24], "1": [10, 24], "2": [10, 24], "3": [10, 24], "4": [10, 24], "5": [10, 24], "6": [10, 24]},
        "lunch": [13, 14],
    },
    "kh_nosirov": {
        "name": "Xojiakbar", "username": "kh_nosirov", "phone": "",
        "work_days": [0, 1, 2, 3, 4, 5, 6],
        "work_hours": {"0": [10, 24], "1": [10, 24], "2": [10, 24], "3": [10, 24], "4": [10, 24], "5": [10, 24], "6": [10, 24]},
    },
    "umidpulatov": {
        "name": "Umid", "username": "umidpulatov", "phone": "+998 99 477 41 48",
        "work_days": [0, 1, 2, 3, 4],
        "work_hours": {"0": [12, 20], "1": [12, 20], "2": [12, 20], "3": [12, 20], "4": [12, 20]},
    },
    "al_xorazm1y": {
        "name": "Azamjon", "username": "al_xorazm1y", "phone": "+998 99 737 11 99",
        "work_days": [0, 1, 2, 3, 4, 5],
        "work_hours": {"0": [10, 20], "1": [10, 20], "2": [10, 20], "3": [10, 20], "4": [10, 20], "5": [10, 20]},
    },
    "abdurahmon": {
        "name": "Abdurahmon", "username": "abdurahmon", "phone": "+998 91 415 92 55",
        "work_days": [0, 1, 2, 3, 4, 5],
        "work_hours": {"0": [9, 13], "1": [9, 13], "2": [9, 13], "3": [9, 13], "4": [9, 13], "5": [9, 13]},
    },
}

def load_agents():
    if not os.path.exists(AGENTS_FILE):
        save_agents(DEFAULT_AGENTS)
        return dict(DEFAULT_AGENTS)
    try:
        with open(AGENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        changed = False
        for key, val in DEFAULT_AGENTS.items():
            if key not in data:
                data[key] = val
                changed = True
        if changed:
            save_agents(data)
        return data
    except Exception as e:
        logger.error(f"load_agents error: {e}")
        return dict(DEFAULT_AGENTS)

def save_agents(agents_data):
    with open(AGENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(agents_data, f, ensure_ascii=False, indent=2)

AGENTS_DATA = load_agents()

def get_agent_order():
    return list(AGENTS_DATA.keys())

def get_agent_info(username):
    d = AGENTS_DATA.get(username, {})
    name = d.get("name", username)
    phone = d.get("phone", "")
    line = f"👨🏻‍💻 {name} @{username}"
    if phone:
        line += f"\n📞 {phone}"
    return line
WEEKDAY_UZ = {0: "Dushanba", 1: "Seshanba", 2: "Chorshanba", 3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba"}
MONTH_UZ = {1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel", 5: "may", 6: "iyun", 7: "iyul", 8: "avgust", 9: "sentyabr", 10: "oktyabr", 11: "noyabr", 12: "dekabr"}

WEEKDAY_BUTTONS = [
    ("Dush", 0), ("Sesh", 1), ("Chor", 2), ("Pay", 3), ("Juma", 4), ("Shanba", 5), ("Yakshanba", 6),
]

# =========================
# STATE
# =========================

state = {
    "cycle_id": 0, "stopped": False,
}

# =========================
# HELPERS
# =========================

def cancel_jobs_by_name(job_queue, name):
    for job in job_queue.get_jobs_by_name(name):
        job.schedule_removal()

def seconds_until_time(hour, minute):
    now = datetime.now(TIMEZONE)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()

def get_active_agents():
    now = datetime.now(TIMEZONE)
    weekday = now.weekday()
    hour = now.hour
    active = set()
    for username, data in AGENTS_DATA.items():
        work_days = data.get("work_days", [])
        work_hours = data.get("work_hours", {})
        if weekday in work_days:
            wh = work_hours.get(str(weekday), [0, 24])
            if wh[0] <= hour < wh[1]:
                active.add(username)
    return active

def get_active_agents_for_time(time_key):
    hour = int(time_key.split(":")[0])
    now = datetime.now(TIMEZONE)
    weekday = now.weekday()
    active = set()
    for username, data in AGENTS_DATA.items():
        work_days = data.get("work_days", [])
        work_hours = data.get("work_hours", {})
        if weekday in work_days:
            wh = work_hours.get(str(weekday), [0, 24])
            if wh[0] <= hour <= wh[1]:
                active.add(username)
    return active

def get_agent_work_schedule(username):
    data = AGENTS_DATA.get(username, {})
    work_days = data.get("work_days", list(range(7)))
    work_hours = data.get("work_hours", {})
    schedule = {}
    for d in work_days:
        wh = work_hours.get(str(d), [10, 20])
        schedule[d] = (wh[0], wh[1])
    return schedule

def build_days_keyboard(selected_days, prefix="add"):
    keyboard = []
    row = []
    for label, idx in WEEKDAY_BUTTONS:
        icon = "✅" if idx in selected_days else "⬜"
        row.append(InlineKeyboardButton(f"{icon} {label}", callback_data=f"{prefix}day_{idx}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("✅ Tayyor", callback_data=f"{prefix}days_done")])
    keyboard.append([InlineKeyboardButton("❌ Bekor", callback_data=f"{prefix}cancel")])
    return InlineKeyboardMarkup(keyboard)

# =========================
# ADDAGENT / EDITAGENT / DELAGENT
# =========================

addagent_state = {}

# =========================
# BUTTON CALLBACKS
# =========================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "noop":
        return

    # DAVOMAT — Tasdiqlandi
    if data.startswith("att_confirm_"):
        username = data[12:]
        if query.from_user.username != ADMIN_USERNAME:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        admin_name = AGENTS_DATA.get(ADMIN_USERNAME, {}).get("name", "Umid")
        try:
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{admin_name} – ✅", callback_data="noop")]])
            )
        except:
            pass
        schedule_delete(context.bot, CHAT_ID, [query.message.message_id], delay=5)
        return

    # SCREENSHOT — Qabul qildim
    if data.startswith("ss_confirm_"):
        if query.from_user.username != ADMIN_USERNAME:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        admin_name = AGENTS_DATA.get(ADMIN_USERNAME, {}).get("name", "Umid")
        try:
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{admin_name} – ✅", callback_data="noop")]])
            )
        except:
            pass
        rest = data[11:]
        ss_key = f"ss_{rest}"
        ss_info = attendance_state.get("ss_msg_ids", {}).get(ss_key, {})

        parts = rest.split("_", 1)
        time_raw = parts[0]
        sender_from_key = parts[1] if len(parts) > 1 else ""
        time_key_restored = f"{time_raw[:2]}:{time_raw[2:]}"

        to_delete = [query.message.message_id]
        if ss_info.get("photo_msg_id"):
            to_delete.append(ss_info["photo_msg_id"])

        reminder_mid = attendance_state.get("ss_reminder_msg_ids", {}).get(f"{time_key_restored}_{sender_from_key}")
        if not reminder_mid:
            for _u in SCREENSHOT_SCHEDULE.get(time_key_restored, []):
                reminder_mid = attendance_state.get("ss_reminder_msg_ids", {}).get(f"{time_key_restored}_{_u}")
                if reminder_mid:
                    break
        if reminder_mid:
            to_delete.append(reminder_mid)

        async def delete_all():
            import asyncio
            await asyncio.sleep(5)
            for mid in to_delete:
                for cid in [CHAT_ID, query.message.chat.id]:
                    try:
                        await context.bot.delete_message(chat_id=cid, message_id=mid)
                        break
                    except:
                        pass
        asyncio.create_task(delete_all())
        return

    # SCREENSHOT FINE — Qabul qildim
    if data.startswith("ss_fine_confirm_"):
        if query.from_user.username != ADMIN_USERNAME:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        admin_name = AGENTS_DATA.get(ADMIN_USERNAME, {}).get("name", "Umid")
        try:
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{admin_name} – ✅", callback_data="noop")]])
            )
        except:
            pass
        return

# =========================
# ADDAGENT / EDITAGENT / DELAGENT
# =========================

addagent_state = {}
editagent_state = {}

async def addagent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    user_id = update.effective_user.id
    addagent_state[user_id] = {"step": "username", "messages": []}
    sent = await context.bot.send_message(chat_id=user_id, text="➕ Yangi hodim qo'shish\n\n1. Username kiriting (@ belgisisiz):")
    addagent_state[user_id]["messages"].append(sent.message_id)

async def editagent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    user_id = update.effective_user.id
    if not AGENTS_DATA:
        await context.bot.send_message(chat_id=user_id, text="❌ Hodimlar royxati bosh.")
        return
    keyboard = [[InlineKeyboardButton(f"👤 {d['name']} (@{u})", callback_data=f"edit_select_{u}")] for u, d in AGENTS_DATA.items()]
    keyboard.append([InlineKeyboardButton("❌ Bekor", callback_data="edit_cancel")])
    sent = await context.bot.send_message(chat_id=user_id, text="✏️ Qaysi hodimni tahrirlaysiz?", reply_markup=InlineKeyboardMarkup(keyboard))
    cmd_msg_id = update.message.message_id if update.message else None
    editagent_state[user_id] = {"messages": [sent.message_id], "cmd_msg_id": cmd_msg_id}

async def delagent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    user_id = update.effective_user.id
    if not AGENTS_DATA:
        await context.bot.send_message(chat_id=user_id, text="❌ Hodimlar royxati bosh.")
        return
    keyboard = [[InlineKeyboardButton(f"🗑 {d['name']} (@{u})", callback_data=f"delagent_{u}")] for u, d in AGENTS_DATA.items()]
    keyboard.append([InlineKeyboardButton("❌ Bekor", callback_data="delagent_cancel")])
    await context.bot.send_message(chat_id=user_id, text="🗑 Qaysi hodimni ochirmoqchisiz?", reply_markup=InlineKeyboardMarkup(keyboard))

async def addagent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()
    if data == "add_cancel":
        msgs = addagent_state.pop(user_id, {}).get("messages", [])
        sent = await context.bot.send_message(chat_id=user_id, text="❌ Bekor qilindi.")
        schedule_delete(context.bot, user_id, msgs + [sent.message_id])
        return
    if user_id not in addagent_state:
        return
    s = addagent_state[user_id]
    if data.startswith("addday_"):
        day_idx = int(data[7:])
        if day_idx in s["selected_days"]:
            s["selected_days"].remove(day_idx)
        else:
            s["selected_days"].append(day_idx)
        try:
            await query.message.edit_reply_markup(reply_markup=build_days_keyboard(s["selected_days"], prefix="add"))
        except:
            pass
    elif data == "adddays_done":
        if not s["selected_days"]:
            await query.answer("❌ Kamida 1 kun tanlang!", show_alert=True)
            return
        s["step"] = "start_hour"
        sent = await context.bot.send_message(chat_id=user_id, text="5. Ish boshlash vaqtini kiriting (masalan: 10):")
        s["messages"].append(sent.message_id)
    elif data == "addconfirm_yes":
        username = s["username"]
        work_hours = {str(d): [s["start_hour"], s["end_hour"]] for d in s["selected_days"]}
        AGENTS_DATA[username] = {"name": s["name"], "username": username, "phone": s["phone"], "work_days": sorted(s["selected_days"]), "work_hours": work_hours}
        save_agents(AGENTS_DATA)
        msgs = s.get("messages", [])
        addagent_state.pop(user_id, None)
        sent_ok = await context.bot.send_message(chat_id=user_id, text=f"✅ {s['name']} (@{username}) muvaffaqiyatli qoshildi!")
        schedule_delete(context.bot, user_id, msgs + [sent_ok.message_id])
        await context.bot.send_message(chat_id=CHAT_ID, text=f"👤 Yangi hodim qoshildi: {s['name']} (@{username})\n📞 {s['phone']}")

async def editagent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()
    if data == "edit_cancel":
        msgs = editagent_state.pop(user_id, {}).get("messages", [])
        sent = await context.bot.send_message(chat_id=user_id, text="❌ Bekor qilindi.")
        schedule_delete(context.bot, user_id, msgs + [sent.message_id])
        return
    if user_id not in editagent_state:
        return
    s = editagent_state[user_id]
    if data.startswith("edit_select_"):
        username = data[12:]
        s["username"] = username
        d = AGENTS_DATA[username]
        days_str = ", ".join(WEEKDAY_UZ[day] for day in sorted(d["work_days"]))
        keyboard = [
            [InlineKeyboardButton("📛 Ismini ozgartir", callback_data="edit_field_name")],
            [InlineKeyboardButton("👤 Usernameni ozgartir", callback_data="edit_field_username")],
            [InlineKeyboardButton("📞 Telefonni ozgartir", callback_data="edit_field_phone")],
            [InlineKeyboardButton("📅 Ish kunlarini ozgartir", callback_data="edit_field_days")],
            [InlineKeyboardButton("🕐 Ish vaqtini ozgartir", callback_data="edit_field_hours")],
            [InlineKeyboardButton("🍽 Tushlik vaqtini ozgartir", callback_data="edit_field_lunch")],
            [InlineKeyboardButton("❌ Bekor", callback_data="edit_cancel")],
        ]
        sent = await context.bot.send_message(chat_id=user_id, text=f"👤 {d['name']} (@{username})\n📞 {d['phone']}\n📅 {days_str}\n\nNimani ozgartirmoqchisiz?", reply_markup=InlineKeyboardMarkup(keyboard))
        s["messages"].append(sent.message_id)
    elif data == "edit_field_name":
        s["step"] = "name"
        sent = await context.bot.send_message(chat_id=user_id, text="Yangi ismini kiriting:")
        s["messages"].append(sent.message_id)
    elif data == "edit_field_username":
        s["step"] = "username_edit"
        sent = await context.bot.send_message(chat_id=user_id, text="Yangi username kiriting (@ belgisisiz):")
        s["messages"].append(sent.message_id)
    elif data == "edit_field_phone":
        s["step"] = "phone"
        sent = await context.bot.send_message(chat_id=user_id, text="Yangi telefon raqamini kiriting:")
        s["messages"].append(sent.message_id)
    elif data == "edit_field_days":
        s["step"] = "days"
        s["selected_days"] = list(AGENTS_DATA[s["username"]]["work_days"])
        sent = await context.bot.send_message(chat_id=user_id, text="Yangi ish kunlarini tanlang:", reply_markup=build_days_keyboard(s["selected_days"], prefix="editday_"))
        s["messages"].append(sent.message_id)
    elif data == "edit_field_hours":
        s["step"] = "start_hour"
        sent = await context.bot.send_message(chat_id=user_id, text="Yangi boshlash vaqtini kiriting (masalan: 10):")
        s["messages"].append(sent.message_id)
    elif data == "edit_field_lunch":
        s["step"] = "lunch_start"
        username = s.get("username", "")
        lunch = AGENTS_DATA.get(username, {}).get("lunch", None)
        current = f"{lunch[0]:02d}:00 - {lunch[1]:02d}:00" if lunch else "Belgilanmagan"
        sent = await context.bot.send_message(chat_id=user_id, text=f"Hozirgi tushlik vaqti: {current}\n\nYangi tushlik boshlanish vaqtini kiriting (masalan: 13:00):")
        s["messages"].append(sent.message_id)
    elif data.startswith("editday__"):
        day_idx = int(data[9:])
        if day_idx in s["selected_days"]:
            s["selected_days"].remove(day_idx)
        else:
            s["selected_days"].append(day_idx)
        try:
            await query.message.edit_reply_markup(reply_markup=build_days_keyboard(s["selected_days"], prefix="editday_"))
        except:
            pass
    elif data == "editday_days_done":
        username = s["username"]
        AGENTS_DATA[username]["work_days"] = sorted(s["selected_days"])
        new_hours = {}
        for d in s["selected_days"]:
            old_wh = AGENTS_DATA[username]["work_hours"].get(str(d), [10, 20])
            new_hours[str(d)] = old_wh
        AGENTS_DATA[username]["work_hours"] = new_hours
        save_agents(AGENTS_DATA)
        msgs = s.get("messages", [])
        cmd_msg = s.get("cmd_msg_id")
        editagent_state.pop(user_id, None)
        days_str = ", ".join(WEEKDAY_UZ[d] for d in sorted(s["selected_days"]))
        warn = await context.bot.send_message(chat_id=user_id, text="⚠️ Jarayon xabarlari ⏱ 5 soniyadan keyin o'chadi")
        sent = await context.bot.send_message(chat_id=user_id, text=f"✅ Ish kunlari yangilandi: {days_str}")
        del_list = msgs + [sent.message_id, warn.message_id]
        if cmd_msg:
            del_list.append(cmd_msg)
        schedule_delete(context.bot, user_id, del_list)

async def delagent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    if data == "delagent_cancel":
        try:
            await query.message.delete()
        except:
            pass
        sent = await context.bot.send_message(chat_id=query.from_user.id, text="❌ Bekor qilindi.")
        schedule_delete(context.bot, query.from_user.id, [sent.message_id])
        return
    if data.startswith("delagent_confirm_"):
        username = data[17:]
        if username in AGENTS_DATA:
            name = AGENTS_DATA[username]["name"]
            del AGENTS_DATA[username]
            save_agents(AGENTS_DATA)
            sent = await context.bot.send_message(chat_id=query.from_user.id, text=f"✅ {name} (@{username}) ochirildi.")
            try:
                await query.message.delete()
            except:
                pass
            schedule_delete(context.bot, query.from_user.id, [sent.message_id])
        return
    if data.startswith("delagent_"):
        username = data[9:]
        if username not in AGENTS_DATA:
            return
        name = AGENTS_DATA[username]["name"]
        keyboard = [
            [InlineKeyboardButton("✅ Ha, ochirish", callback_data=f"delagent_confirm_{username}")],
            [InlineKeyboardButton("❌ Yo'q", callback_data="delagent_cancel")],
        ]
        await query.message.edit_text(f"⚠️ {name} (@{username}) ni ochirishni tasdiqlaysizmi?", reply_markup=InlineKeyboardMarkup(keyboard))

# =========================
# TEXT HANDLER
# =========================

async def universal_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    text = update.message.text.strip()

    if user_id in addagent_state:
        if username != ADMIN_USERNAME:
            return
        s = addagent_state[user_id]
        step = s.get("step")
        clean = text.lstrip("@")
        if step == "username":
            s["username"] = clean
            s["step"] = "name"
            sent = await context.bot.send_message(chat_id=user_id, text="2. Ismini kiriting:")
            s["messages"].append(sent.message_id)
        elif step == "name":
            s["name"] = clean
            s["step"] = "phone"
            sent = await context.bot.send_message(chat_id=user_id, text="3. Telefon raqamini kiriting:")
            s["messages"].append(sent.message_id)
        elif step == "phone":
            s["phone"] = clean
            s["step"] = "days"
            s["selected_days"] = []
            sent = await context.bot.send_message(chat_id=user_id, text="4. Ish kunlarini tanlang:", reply_markup=build_days_keyboard(s["selected_days"], prefix="add"))
            s["messages"].append(sent.message_id)
        elif step == "start_hour":
            try:
                h = int(text.split(":")[0]) if ":" in text else int(text)
                s["start_hour"] = h
                s["step"] = "end_hour"
                sent = await context.bot.send_message(chat_id=user_id, text="6. Tugash vaqtini kiriting (masalan: 20, yoki 24 = 23:59):")
                s["messages"].append(sent.message_id)
            except:
                await context.bot.send_message(chat_id=user_id, text="❌ Notogri format.")
        elif step == "end_hour":
            try:
                h = int(text.split(":")[0]) if ":" in text else int(text)
                s["end_hour"] = h
                s["step"] = "confirm"
                days_str = ", ".join(WEEKDAY_UZ[d] for d in sorted(s["selected_days"]))
                sent = await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📋 Yangi hodim:\n👤 @{s['username']}\n📛 {s['name']}\n📞 {s['phone']}\n📅 {days_str}\n🕐 {s['start_hour']:02d}:00 — {h:02d}:00\n\nTasdiqlaysizmi?",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tasdiqlash", callback_data="addconfirm_yes")], [InlineKeyboardButton("❌ Bekor", callback_data="add_cancel")]])
                )
                s["messages"].append(sent.message_id)
            except:
                await context.bot.send_message(chat_id=user_id, text="❌ Notogri format.")
        return

    if user_id in editagent_state:
        if username != ADMIN_USERNAME:
            return
        s = editagent_state[user_id]
        step = s.get("step")
        if step == "name":
            AGENTS_DATA[s["username"]]["name"] = text
            save_agents(AGENTS_DATA)
            msgs = s.get("messages", [])
            editagent_state.pop(user_id, None)
            sent = await context.bot.send_message(chat_id=user_id, text=f"✅ Ismi '{text}' ga ozgartirildi.")
            schedule_delete(context.bot, user_id, msgs + [update.message.message_id, sent.message_id])
        elif step == "username_edit":
            new_u = text.lstrip("@")
            old_u = s["username"]
            agent_data = AGENTS_DATA.pop(old_u)
            agent_data["username"] = new_u
            AGENTS_DATA[new_u] = agent_data
            save_agents(AGENTS_DATA)
            msgs = s.get("messages", [])
            editagent_state.pop(user_id, None)
            sent = await context.bot.send_message(chat_id=user_id, text=f"✅ Username '@{old_u}' => '@{new_u}' ga ozgartirildi.")
            schedule_delete(context.bot, user_id, msgs + [update.message.message_id, sent.message_id])
        elif step == "phone":
            AGENTS_DATA[s["username"]]["phone"] = text
            save_agents(AGENTS_DATA)
            msgs = s.get("messages", [])
            editagent_state.pop(user_id, None)
            sent = await context.bot.send_message(chat_id=user_id, text=f"✅ Telefon '{text}' ga ozgartirildi.")
            schedule_delete(context.bot, user_id, msgs + [update.message.message_id, sent.message_id])
        elif step == "start_hour":
            try:
                h = int(text.split(":")[0]) if ":" in text else int(text)
                s["start_hour"] = h
                s["step"] = "end_hour"
                sent = await context.bot.send_message(chat_id=user_id, text="Yangi tugash vaqtini kiriting (masalan: 20):")
                s["messages"].append(sent.message_id)
            except:
                await context.bot.send_message(chat_id=user_id, text="❌ Notogri format.")
        elif step == "end_hour":
            try:
                h = int(text.split(":")[0]) if ":" in text else int(text)
                username_edit = s["username"]
                for d in AGENTS_DATA[username_edit]["work_days"]:
                    AGENTS_DATA[username_edit]["work_hours"][str(d)] = [s["start_hour"], h]
                save_agents(AGENTS_DATA)
                msgs = s.get("messages", [])
                editagent_state.pop(user_id, None)
                sent = await context.bot.send_message(chat_id=user_id, text=f"✅ Ish vaqti {s['start_hour']:02d}:00 — {h:02d}:00 ga ozgartirildi.")
                schedule_delete(context.bot, user_id, msgs + [update.message.message_id, sent.message_id])
            except:
                await context.bot.send_message(chat_id=user_id, text="❌ Notogri format.")
        elif step == "lunch_start":
            try:
                h = int(text.split(":")[0]) if ":" in text else int(text)
                s["lunch_start"] = h
                s["step"] = "lunch_end"
                sent = await context.bot.send_message(chat_id=user_id, text="Tushlik tugash vaqtini kiriting (masalan: 14:00):")
                s["messages"].append(sent.message_id)
            except:
                await context.bot.send_message(chat_id=user_id, text="❌ Notogri format.")
        elif step == "lunch_end":
            try:
                h = int(text.split(":")[0]) if ":" in text else int(text)
                username_edit = s["username"]
                AGENTS_DATA[username_edit]["lunch"] = [s["lunch_start"], h]
                save_agents(AGENTS_DATA)
                msgs = s.get("messages", [])
                editagent_state.pop(user_id, None)
                sent = await context.bot.send_message(chat_id=user_id, text=f"✅ Tushlik vaqti {s['lunch_start']:02d}:00 — {h:02d}:00 ga ozgartirildi.\n⚠️ Bu xabar ⏱ 60 soniyadan keyin o'chadi")
                schedule_delete(context.bot, user_id, msgs + [update.message.message_id, sent.message_id], delay=60)
            except:
                await context.bot.send_message(chat_id=user_id, text="❌ Notogri format.")
        return
# =========================
# DAVOMAT TIZIMI
# =========================

import random
import string

ATTENDANCE_AGENTS = {}

def get_attendance_code_time(username):
    now = datetime.now(TIMEZONE)
    weekday = now.weekday()
    schedule = get_agent_work_schedule(username)
    if weekday not in schedule:
        return None, None
    start_h, _ = schedule[weekday]
    code_h = start_h - 1
    code_m = 50
    deadline_h = start_h
    deadline_m = 10
    return f"{code_h:02d}:{code_m:02d}", f"{deadline_h:02d}:{deadline_m:02d}"

SCREENSHOT_SCHEDULE = {
    "10:30": ["sirlyinfo"],
    "11:00": ["sirlyinfo"],
    "11:30": ["sirlyinfo"],
    "12:00": ["sirlyinfo"],
    "12:30": ["sirlyinfo"],
    "13:00": ["sirlyinfo"],
    "13:30": ["sirlyinfo"],
    "14:00": ["sirlyinfo"],
    "14:30": ["sirlyinfo"],
    "15:00": ["sirlyinfo"],
    "15:30": ["sirlyinfo"],
    "16:00": ["sirlyinfo"],
    "16:30": ["sirlyinfo"],
    "17:00": ["sirlyinfo"],
    "17:30": ["sirlyinfo"],
    "18:00": ["sirlyinfo"],
    "18:30": ["sirlyinfo"],
    "19:00": ["sirlyinfo"],
    "19:30": ["sirlyinfo"],
    "20:00": ["sirlyinfo"],
    "20:30": ["sirlyinfo"],
    "21:00": ["sirlyinfo"],
    "21:30": ["sirlyinfo"],
    "22:00": ["sirlyinfo"],
    "22:30": ["sirlyinfo"],
    "23:00": ["sirlyinfo"],
    "23:30": ["sirlyinfo"],
}

attendance_state = {
    "daily_codes": {},
    "arrived": set(),
    "arrived_date": "",
    "screenshot_msg_ids": {},
    "screenshot_done": {},
    "screenshot_date": "",
}

def generate_code():
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=4))

def reset_attendance_if_new_day():
    today = datetime.now(TIMEZONE).strftime("%d.%m.%Y")
    if attendance_state["arrived_date"] != today:
        attendance_state["arrived"] = set()
        attendance_state["arrived_date"] = today
        attendance_state["daily_codes"] = {}
    if attendance_state["screenshot_date"] != today:
        attendance_state["screenshot_done"] = {}
        attendance_state["screenshot_date"] = today

async def send_attendance_code_job(context: ContextTypes.DEFAULT_TYPE):
    username = context.job.data["username"]
    reset_attendance_if_new_day()
    if username in attendance_state["arrived"]:
        context.job_queue.run_once(send_attendance_code_job, when=seconds_until_time(5, 0), name=f"att_code_{username}", data={"username": username})
        return
    code_time, deadline = get_attendance_code_time(username)
    if not code_time:
        now2 = datetime.now(TIMEZONE)
        tomorrow = now2 + timedelta(days=1)
        context.job_queue.run_once(send_attendance_code_job, when=(tomorrow.replace(hour=9, minute=0, second=0) - now2).total_seconds(), name=f"att_code_{username}", data={"username": username})
        return
    agent = ATTENDANCE_AGENTS[username]
    code = generate_code()
    attendance_state["daily_codes"][username] = code
    now = datetime.now(TIMEZONE)
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            f"🔑 {agent['name']} @{username}\n"
            f"📞 {agent['phone']}\n\n"
            f"Bugungi kod: {code}\n\n"
            f"📌 Bajaring:\n"
            f"1. Kodni katta qilib qog'ozga yozing\n"
            f"2. Ofis fonida qog'ozni suratga oling\n"
            f"3. Ofisda ekaningiz suratda bilinsin\n"
            f"4. Suratni guruhga yuboring\n\n"
            f"⚠️ Soat {deadline} gacha surat yuborilmasa {agent['fine']} so'm jarima\n"
            f"ℹ️ Kod har kuni yangilanadi"
        )
    )
    deadline_h, deadline_m = map(int, deadline.split(":"))
    target = now.replace(hour=deadline_h, minute=deadline_m, second=0, microsecond=0)
    if target > now:
        secs = (target - now).total_seconds()
        context.job_queue.run_once(check_attendance_job, when=secs, name=f"att_check_{username}", data={"username": username})
    context.job_queue.run_once(send_attendance_code_job, when=seconds_until_time(5, 0), name=f"att_code_{username}", data={"username": username})

async def check_attendance_job(context: ContextTypes.DEFAULT_TYPE):
    username = context.job.data["username"]
    reset_attendance_if_new_day()
    if username in attendance_state["arrived"]:
        return
    agent = ATTENDANCE_AGENTS[username]
    now = datetime.now(TIMEZONE)
    date_str = now.strftime("%d.%m")
    time_str = now.strftime("%H:%M")
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            f"⚠️ {agent['name']} @{username} ishga vaqtida kelmadi!\n"
            f"📅 {date_str} | 🕐 {time_str}\n\n"
            f"💰 Oyligidan {agent['fine']} so'm jarima\n\n"
            f"@{ADMIN_USERNAME}"
        )
    )

# =========================
# PHOTO HANDLER
# =========================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_ID:
        return
    sender = update.effective_user.username
    if not sender:
        return
    now = datetime.now(TIMEZONE)
    date_str = now.strftime("%d.%m")
    time_str = now.strftime("%H:%M")
    reset_attendance_if_new_day()

    if sender in ATTENDANCE_AGENTS and sender not in attendance_state["arrived"]:
        agent = ATTENDANCE_AGENTS[sender]
        _, deadline_str = get_attendance_code_time(sender)
        if not deadline_str:
            deadline_str = "10:10"
        deadline_h, deadline_m = map(int, deadline_str.split(":"))
        deadline_dt = now.replace(hour=deadline_h, minute=deadline_m, second=0, microsecond=0)
        if now <= deadline_dt:
            attendance_state["arrived"].add(sender)
            cancel_jobs_by_name(context.job_queue, f"att_check_{sender}")
            keyboard = [[InlineKeyboardButton(
                f"⬜ Tasdiqlandi — {AGENTS_DATA.get(ADMIN_USERNAME, {}).get('name', 'Umid')}",
                callback_data=f"att_confirm_{sender}"
            )]]
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=(f"✅ {agent['name']} ishga keldi!\n📅 {date_str} | 🕐 {time_str}\n\n@{ADMIN_USERNAME}"),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

    current_time_key = None
    best_diff = None
    for tk in SCREENSHOT_SCHEDULE:
        if sender in SCREENSHOT_SCHEDULE[tk]:
            tk_h, tk_m = map(int, tk.split(":"))
            tk_dt = now.replace(hour=tk_h, minute=tk_m, second=0, microsecond=0)
            diff = (now - tk_dt).total_seconds()
            if 0 <= diff <= 600:
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    current_time_key = tk

    if current_time_key:
        allowed_senders = set(SCREENSHOT_SCHEDULE.get(current_time_key, []))
        if sender not in allowed_senders:
            names = ", ".join(f"@{u}" for u in allowed_senders)
            await context.bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Screenshot faqat quyidagi profillardan qabul qilinadi: {names}")
            return

        done = attendance_state["screenshot_done"].get(current_time_key, set())
        if sender not in done:
            agent = ATTENDANCE_AGENTS.get(sender, {})
            name = agent.get("name") or AGENTS_DATA.get(sender, {}).get("name", sender)
            keyboard = [[InlineKeyboardButton(
                f"⬜ Qabul qildim — {AGENTS_DATA.get(ADMIN_USERNAME, {}).get('name', 'Umid')}",
                callback_data=f"ss_confirm_{current_time_key.replace(':', '')}_{sender}"
            )]]
            sent = await context.bot.send_message(
                chat_id=CHAT_ID,
                text=(
                    f"📸 Screenshot yuborildi!\n"
                    f"📅 {date_str} | 🕐 {time_str}\n\n"
                    f"1. Admin panelda — javob yozilmagan mijozlar qolmadi\n"
                    f"2. Telegramda — Sirly Infoga murojaat qilgan hamkor va mijozlarning barchasiga javob yozildi"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            agents_for_slot = SCREENSHOT_SCHEDULE.get(current_time_key, [sender])
            for _u in agents_for_slot:
                attendance_state["screenshot_done"].setdefault(current_time_key, set()).add(_u)
            for _u in agents_for_slot:
                cancel_jobs_by_name(context.job_queue, f"ss_fine_{current_time_key.replace(':', '')}_{_u}")
            cancel_jobs_by_name(context.job_queue, f"ss_fine_{current_time_key.replace(':', '')}")
            ss_key = f"ss_{current_time_key.replace(':', '')}_{sender}"
            reminder_mid = attendance_state.get("ss_reminder_msg_ids", {}).get(f"{current_time_key}_{sender}")
            if not reminder_mid:
                for _u in SCREENSHOT_SCHEDULE.get(current_time_key, []):
                    reminder_mid = attendance_state.get("ss_reminder_msg_ids", {}).get(f"{current_time_key}_{_u}")
                    if reminder_mid:
                        break
            attendance_state.setdefault("ss_msg_ids", {})[ss_key] = {
                "confirm_msg_id": sent.message_id,
                "photo_msg_id": update.message.message_id,
                "reminder_msg_id": reminder_mid,
                "chat_id": update.effective_chat.id,
            }
            cancel_jobs_by_name(context.job_queue, f"ss_fine_{current_time_key.replace(':', '')}_{sender}")
            await sb_save_screenshot(sender, current_time_key, 'sent')

# =========================
# SCREENSHOT JOBS
# =========================

async def screenshot_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    time_key = context.job.data["time_key"]
    agents = context.job.data["agents"]
    reset_attendance_if_new_day()

    now_check = datetime.now(TIMEZONE)
    now_wd = now_check.weekday()
    tk_h = int(time_key.split(":")[0])

    def is_working_at_time(username, hour):
        data = AGENTS_DATA.get(username, {})
        work_days = data.get("work_days", list(range(7)))
        work_hours = data.get("work_hours", {})
        if now_wd not in work_days:
            return False
        wh = work_hours.get(str(now_wd), [0, 24])
        return wh[0] <= hour < wh[1]

    agents = [u for u in agents if is_working_at_time(u, tk_h)]

    # Tushlik vaqtini tekshirish — soat va daqiqani hisobga olish
    tk_m = int(time_key.split(":")[1])
    def is_lunch_time(username, hour, minute):
        lunch = AGENTS_DATA.get(username, {}).get("lunch")
        if not lunch:
            return False
        lunch_start_h, lunch_end_h = lunch[0], lunch[1]
        # Tushlik boshlanishidan 10 daqiqa oldin ham so'ramasin
        pre_lunch_minutes = lunch_start_h * 60 - 10
        current_minutes = hour * 60 + minute
        lunch_end_minutes = lunch_end_h * 60
        return pre_lunch_minutes <= current_minutes < lunch_end_minutes

    agents = [u for u in agents if not is_lunch_time(u, tk_h, tk_m)]
    if not agents:
        h, m = map(int, time_key.split(":"))
        context.job_queue.run_once(screenshot_reminder_job, when=seconds_until_time(h, m), name=f"ss_reminder_{time_key}", data={"time_key": time_key, "agents": context.job.data["agents"]})
        return

    now = datetime.now(TIMEZONE)
    done = attendance_state["screenshot_done"].get(time_key, set())
    pending_agents = [u for u in agents if u not in done]
    if not pending_agents:
        return

    if len(pending_agents) > 1:
        names_tags = " | ".join(f"{ATTENDANCE_AGENTS.get(u, {}).get('name', u)} @{u}" for u in pending_agents)
        reminder_sent = await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"📸 {names_tags}\n"
                f"Iltimos screenshot yuboring:\n\n"
                f"1. Admin panelda — javob yozilmagan mijozlar qolmagani\n"
                f"2. Telegramda — Sirly Infoga murojaat qilgan hamkor va mijozlarning barchasiga javob yozilgani\n"
                f"haqida tasdiqlovchi screenshot yuboring\n\n"
                f"⚠️ Vaqt va bugungi sana ko'rinib tursin screenshotda\n"
                f"⚠️ 10 daqiqa ichida yuborilmasa 20,000 so'm jarima"
            )
        )
        for u in pending_agents:
            attendance_state.setdefault("ss_reminder_msg_ids", {})[f"{time_key}_{u}"] = reminder_sent.message_id
        context.job_queue.run_once(screenshot_fine_job, when=600, name=f"ss_fine_{time_key.replace(':', '')}", data={"time_key": time_key, "username": pending_agents[0], "all_agents": pending_agents})
    else:
        username = pending_agents[0]
        agent = ATTENDANCE_AGENTS.get(username, {})
        name = agent.get("name", username)
        reminder_sent = await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"📸 {name} @{username}\n"
                f"Iltimos screenshot yuboring:\n\n"
                f"1. Admin panelda — javob yozilmagan mijozlar qolmagani\n"
                f"2. Telegramda — Sirly Infoga murojaat qilgan hamkor va mijozlarning barchasiga javob yozilgani\n"
                f"haqida tasdiqlovchi screenshot yuboring\n\n"
                f"⚠️ Vaqt va bugungi sana ko'rinib tursin screenshotda\n"
                f"⚠️ 10 daqiqa ichida yuborilmasa 20,000 so'm jarima"
            )
        )
        attendance_state.setdefault("ss_reminder_msg_ids", {})[f"{time_key}_{username}"] = reminder_sent.message_id
        context.job_queue.run_once(screenshot_fine_job, when=600, name=f"ss_fine_{time_key.replace(':', '')}_{username}", data={"time_key": time_key, "username": username, "all_agents": [username]})

    h, m = map(int, time_key.split(":"))
    context.job_queue.run_once(screenshot_reminder_job, when=seconds_until_time(h, m), name=f"ss_reminder_{time_key}", data={"time_key": time_key, "agents": agents})

async def screenshot_fine_job(context: ContextTypes.DEFAULT_TYPE):
    time_key = context.job.data["time_key"]
    username = context.job.data["username"]
    reset_attendance_if_new_day()
    done = attendance_state["screenshot_done"].get(time_key, set())
    if username in done:
        return
    agent = ATTENDANCE_AGENTS.get(username, {})
    name = agent.get("name", username)
    now = datetime.now(TIMEZONE)
    date_str = now.strftime("%d.%m")
    time_str = now.strftime("%H:%M")
    keyboard = [[InlineKeyboardButton(
        f"⬜ Qabul qildim — {AGENTS_DATA.get(ADMIN_USERNAME, {}).get('name', 'Umid')}",
        callback_data=f"ss_fine_confirm_{time_key.replace(':', '')}_{username}"
    )]]
    await sb_save_screenshot(username, time_key, 'missed')
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            f"⚠️ {name} @{username} screenshot yubormadi!\n"
            f"📅 {date_str} | 🕐 {time_str}\n\n"
            f"💰 20,000 so'm jarima\n\n"
            f"@{ADMIN_USERNAME}"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# START / STOP COMMANDS
# =========================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_type = update.effective_chat.type

    # Guruhda /start — hech narsa qilma
    if chat_type in ("group", "supergroup"):
        return

    name = user.first_name or user.username or "Salom"

    # Admin qo'llanmasi
    if user.username == ADMIN_USERNAME:
        guide_text = (
            f"👋 Salom, {name}!\n\n"
            "━━━━━━━━━━━━━━\n"
            "🤖 BOT BOSHQARUVI\n"
            "━━━━━━━━━━━━━━\n"
            "/start — Qo'llanmani ko'rish\n"
            "/umidstop — Botni to'xtatish\n\n"
            "━━━━━━━━━━━━━━\n"
            "👥 HODIMLAR\n"
            "━━━━━━━━━━━━━━\n"
            "/addagent — Hodim qo'shish\n"
            "/editagent — Hodimni tahrirlash\n"
            "/delagent — Hodimni o'chirish\n\n"
            "━━━━━━━━━━━━━━\n"
            "ℹ️ ESLATMA\n"
            "━━━━━━━━━━━━━━\n"
            "• Screenshot har 30 daqiqada so'raladi\n"
            "• Deadline o'tsa — bot avtomatik xabar yuboradi"
        )
        await context.bot.send_message(chat_id=user.id, text=guide_text)
        return

    # Xodimlar qo'llanmasi
    guide_text = (
        f"👋 Salom, {name}!\n\n"
        "Sirly Tizim boti orqali davomat va screenshot\n"
        "eslatmalari yuboriladi. Savollar bo'lsa, admin bilan\n"
        "bog'laning."
    )
    await context.bot.send_message(chat_id=user.id, text=guide_text)

async def umidstop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    state["stopped"] = True
    state["cycle_id"] += 1
    await context.bot.send_message(chat_id=CHAT_ID, text="🛑 Bot toxtatildi.\nQayta ishga tushirish uchun /start bosing.")

# =========================
# MAIN
# =========================

def main():
    application = Application.builder().token(TOKEN).build()
    state["cycle_id"] += 1

    # Hujjatlar -> "Botga yuborish" navbati
    application.job_queue.run_repeating(check_file_send_requests_job, interval=1, first=1)

    # Sekretar -> uchrashuv eslatmalari
    application.job_queue.run_repeating(check_bot_reminders_job, interval=30, first=10)

    # Kaiten -> guruhga vazifa xabari
    application.job_queue.run_repeating(check_group_messages_job, interval=2, first=2)

    # Kaiten -> muddati o'tgan vazifalar
    application.job_queue.run_repeating(kaiten_overdue_check_job, interval=60, first=15)

    # Org struktura -> cheklist eslatmalari
    application.job_queue.run_repeating(org_checklist_check_job, interval=60, first=20)

    # Kaiten -> kunlik statistika (10:00 va 20:00)
    for _hour, _label in [(10, "Ertalab"), (20, "Kechki")]:
        application.job_queue.run_once(
            _daily_stats_once,
            when=seconds_until_time(_hour, 0),
            name=f"kaiten_stats_{_hour}",
            data={"hour": _hour, "label": _label}
        )

    # Davomat jobs
    for username in ATTENDANCE_AGENTS:
        code_time, _ = get_attendance_code_time(username)
        if code_time:
            h, m = map(int, code_time.split(":"))
            application.job_queue.run_once(send_attendance_code_job, when=seconds_until_time(h, m), name=f"att_code_{username}", data={"username": username})
        else:
            application.job_queue.run_once(send_attendance_code_job, when=seconds_until_time(5, 0), name=f"att_code_{username}", data={"username": username})

    # Screenshot reminder jobs
    for time_key, agents in SCREENSHOT_SCHEDULE.items():
        h, m = map(int, time_key.split(":"))
        application.job_queue.run_once(screenshot_reminder_job, when=seconds_until_time(h, m), name=f"ss_reminder_{time_key}", data={"time_key": time_key, "agents": agents})

    application.add_handler(MessageHandler(filters.PHOTO & filters.Chat(CHAT_ID), photo_handler))
    application.add_handler(MessageHandler(filters.Document.IMAGE & filters.Chat(CHAT_ID), photo_handler))

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("umidstop", umidstop_command))
    application.add_handler(CommandHandler("addagent", addagent_command))
    application.add_handler(CommandHandler("editagent", editagent_command))
    application.add_handler(CommandHandler("delagent", delagent_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, universal_text_handler))

    application.add_handler(CallbackQueryHandler(addagent_callback, pattern="^(addday_|adddays_done|addconfirm_yes|add_cancel)"))
    application.add_handler(CallbackQueryHandler(org_checklist_done_callback, pattern="^orgcl_done:"))
    application.add_handler(CallbackQueryHandler(editagent_callback, pattern="^(edit_)"))
    application.add_handler(CallbackQueryHandler(delagent_callback, pattern="^(delagent_)"))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot starting...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
