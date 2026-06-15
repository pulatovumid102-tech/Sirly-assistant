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

# =========================
# CHECKLIST CONFIG
# =========================

CHECKLIST_CONFIG = {
    "10:15": [
        "Olib ketilmagan statusini tekshiring va guruhga qisqacha hisobot yuboring: soni va nima bo'ldi suhbat paytida",
        "Muammoli mijozlar jadvalini ko'rib chiqing, jarayondagilarni yakunlanganlarga o'tkazing va guruhga @umidpulatov tag qilib qisqacha hisobot yuboring",
        "Bugalteriya jadvalini to'ldiring, shoshмang xato bo'lmasin",
        "Sotuv tablitsasini to'ldiring, xato qilmang, shoshмang",
    ],
}

# Checklist faqat shu xodimga yuboriladi
CHECKLIST_AGENTS = {"sirlyinfo"}

CHECKLIST_TIMES = list(CHECKLIST_CONFIG.keys())

# Checklist verify state: vkey -> {pending_items, verify_msg_id}
checklist_verify_state = {}

WEEKDAY_UZ = {0: "Dushanba", 1: "Seshanba", 2: "Chorshanba", 3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba"}
MONTH_UZ = {1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel", 5: "may", 6: "iyun", 7: "iyul", 8: "avgust", 9: "sentyabr", 10: "oktyabr", 11: "noyabr", 12: "dekabr"}

WEEKDAY_BUTTONS = [
    ("Dush", 0), ("Sesh", 1), ("Chor", 2), ("Pay", 3), ("Juma", 4), ("Shanba", 5), ("Yakshanba", 6),
]

# =========================
# CUSTOM CHECKLIST (yaratilgan checklistlar)
# =========================

CUSTOM_CHECKLISTS_FILE = "custom_checklists.json"
custom_checklists = []  # list of dicts
custom_checklist_state = {}  # user_id -> creation state
custom_checklist_confirmations = {}  # cl_id -> {username: {task_index: bool}}
custom_checklist_verified = {}  # cl_id -> set
custom_checklist_verify_state = {}  # cl_id -> {verify_msg_id}
custom_checklist_message_ids = {}  # cl_id -> message_id

def save_custom_checklists():
    with open(CUSTOM_CHECKLISTS_FILE, "w", encoding="utf-8") as f:
        json.dump(custom_checklists, f, ensure_ascii=False, indent=2)

def load_custom_checklists():
    global custom_checklists
    if not os.path.exists(CUSTOM_CHECKLISTS_FILE):
        return
    try:
        with open(CUSTOM_CHECKLISTS_FILE, "r", encoding="utf-8") as f:
            custom_checklists = json.load(f)
    except Exception as e:
        logger.error(f"load_custom_checklists error: {e}")

def get_next_cl_id():
    if not custom_checklists:
        return 1
    return max(cl["id"] for cl in custom_checklists) + 1

def seconds_until_custom_checklist(cl):
    """Keyingi yuborish vaqtigacha sekundlar"""
    now = datetime.now(TIMEZONE)
    repeat = cl["repeat"]
    hour = cl["hour"]
    minute = 0

    if repeat == "daily":
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()

    elif repeat == "interval":
        days = cl["interval_days"]
        last_sent = cl.get("last_sent")
        if last_sent:
            last_dt = datetime.fromisoformat(last_sent)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=TIMEZONE)
            next_dt = last_dt + timedelta(days=days)
            next_dt = next_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_dt <= now:
                next_dt += timedelta(days=1)
        if next_dt <= now:
            next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=1)
        return max((next_dt - now).total_seconds(), 1)

    elif repeat == "weekly":
        weekday = cl["weekday"]
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = (weekday - now.weekday()) % 7
        if days_ahead == 0 and target <= now:
            days_ahead = 7
        target += timedelta(days=days_ahead)
        return (target - now).total_seconds()

    return 86400

# =========================
# STATE
# =========================

state = {
    "checklist_confirmations": {}, "checklist_message_ids": {}, "checklist_log_message_ids": {}, "checklist_log_lines": {},
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

def get_available_dates_for_targets(targets):
    now = datetime.now(TIMEZONE)
    available = []
    for i in range(14):
        d = now + timedelta(days=i)
        weekday = d.weekday()
        all_work = all(weekday in get_agent_work_schedule(u) for u in targets)
        if all_work:
            available.append(d)
        if len(available) >= 7:
            break
    return available

def get_available_times_for_targets(targets, date_str):
    now = datetime.now(TIMEZONE)
    year = now.year
    d = datetime.strptime(f"{date_str}.{year}", "%d.%m.%Y")
    weekday = d.weekday()
    start_hour = 0
    end_hour = 24
    for username in targets:
        schedule = get_agent_work_schedule(username)
        if weekday not in schedule:
            return []
        s, e = schedule[weekday]
        start_hour = max(start_hour, s)
        end_hour = min(end_hour, e)
    if start_hour >= end_hour:
        return []
    slots = []
    for h in range(start_hour, end_hour):
        if d.date() == now.date() and h <= now.hour:
            continue
        slots.append(f"{h:02d}:00")
    return slots

def zadacha_target_str(targets):
    return " + ".join(AGENTS_DATA.get(u, {}).get("name", u) for u in targets)

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
# CHECKLIST BUILDERS
# =========================

def build_checklist_keyboard(time_key, active_agents, checklist_confs, verified_tasks=None):
    if verified_tasks is None:
        verified_tasks = set()
    keyboard = []
    tasks = CHECKLIST_CONFIG.get(time_key, [])
    for username in get_agent_order():
        if username not in active_agents:
            continue
        user_conf = checklist_confs.get(username, {})
        for i, task in enumerate(tasks):
            done = user_conf.get(i, False)
            verified = i in verified_tasks
            row = [
                InlineKeyboardButton(
                    f"{'✅' if done else '⬜'} {i+1} — Bajardim",
                    callback_data=f"chk_{time_key.replace(':', '')}_{username}_{i}"
                ),
                InlineKeyboardButton(
                    f"{'✅' if verified else '⬜'} Tekshirdim",
                    callback_data=f"chk_verify_{time_key.replace(':', '')}_{username}_{i+1}"
                )
            ]
            keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def build_checklist_text(time_key, active_agents):
    tasks = CHECKLIST_CONFIG.get(time_key, [])
    task_lines = "\n".join(f"{i+1}. {task}" for i, task in enumerate(tasks))
    agent_block = "\n\n".join(get_agent_info(u) for u in get_agent_order() if u in active_agents)
    now = datetime.now(TIMEZONE)
    date_str = f"{now.day} {MONTH_UZ[now.month]}, {WEEKDAY_UZ[now.weekday()]}, {now.strftime('%H:%M')}"
    return (
        f"📋 CHECKLIST — {date_str}\n\n"
        f"{agent_block}\n\n"
        "━━━━━━━━━━━━━━\n"
        f"📝 Vazifalar:\n<tg-spoiler>\n{task_lines}\n</tg-spoiler>\n"
        "━━━━━━━━━━━━━━\n\n"
        "⚠️ Avval o'qing, keyin bosing!\n"
        "Har bir vazifa bajarilgandan so'ng tugmani bosing"
    )

def checklist_all_confirmed(time_key, active_agents, checklist_confs):
    tasks = CHECKLIST_CONFIG.get(time_key, [])
    for username in active_agents:
        user_conf = checklist_confs.get(username, {})
        for i in range(len(tasks)):
            if not user_conf.get(i, False):
                return False
    return True

# =========================
# ZADACHA CLEANUP
# =========================

async def zadacha_cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    now_ts = datetime.now(TIMEZONE).timestamp()
    to_delete = []
    for uid, s in list(zadacha_state.items()):
        created = s.get("created_ts", now_ts)
        if now_ts - created > 600:
            to_delete.append(uid)
    for uid in to_delete:
        msgs = zadacha_state.pop(uid, {}).get("messages", [])
        for mid in msgs:
            try:
                await context.bot.delete_message(chat_id=uid, message_id=mid)
            except:
                pass

# =========================
# ZADACHA — SAVE / LOAD
# =========================

zadacha_state = {}
zadacha_tasks = {}
zadacha_counter = [0]
zadacha_reminder_msgs = {}
zadacha_main_msg = {}
TASKS_FILE = "zadacha_tasks.json"

def save_tasks():
    data = {}
    for tid, task in zadacha_tasks.items():
        data[str(tid)] = {
            "creator": task["creator"],
            "creator_username": task["creator_username"],
            "targets": task["targets"],
            "text": task["text"],
            "deadline": task["deadline"].isoformat(),
            "supervisor": task.get("supervisor", []),
            "accepted_executors": list(task.get("accepted_executors", set())),
            "accepted_supervisors": list(task.get("accepted_supervisors", set())),
            "done": list(task.get("done", set())),
            "main_msg_id": task.get("main_msg_id"),
            "reminder_msg_ids": list(task.get("reminder_msg_ids", [])),
            "created_at": task["created_at"].isoformat() if task.get("created_at") else None,
            "accepted_at": {u: t.isoformat() for u, t in task.get("accepted_at", {}).items()},
            "done_at": {u: t.isoformat() for u, t in task.get("done_at", {}).items()},
            "done_confirmed": list(task.get("done_confirmed", set())),
        }
    with open(TASKS_FILE, "w") as f:
        json.dump({"counter": zadacha_counter[0], "tasks": data}, f, ensure_ascii=False)

def load_tasks():
    if not os.path.exists(TASKS_FILE):
        return
    try:
        with open(TASKS_FILE, "r") as f:
            data = json.load(f)
        zadacha_counter[0] = data.get("counter", 0)
        for tid_str, task in data.get("tasks", {}).items():
            tid = int(tid_str)
            dl = datetime.fromisoformat(task["deadline"])
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=TIMEZONE)
            def parse_dt(s):
                if not s:
                    return None
                dt2 = datetime.fromisoformat(s)
                if dt2.tzinfo is None:
                    dt2 = dt2.replace(tzinfo=TIMEZONE)
                return dt2

            zadacha_tasks[tid] = {
                "creator": task["creator"],
                "creator_username": task["creator_username"],
                "targets": task["targets"],
                "text": task["text"],
                "deadline": dl,
                "supervisor": task.get("supervisor", []),
                "accepted_executors": set(task.get("accepted_executors", [])),
                "accepted_supervisors": set(task.get("accepted_supervisors", [])),
                "done": set(task.get("done", [])),
                "main_msg_id": task.get("main_msg_id"),
                "reminder_msg_ids": list(task.get("reminder_msg_ids", [])),
                "created_at": parse_dt(task.get("created_at")),
                "accepted_at": {u: parse_dt(t) for u, t in task.get("accepted_at", {}).items()},
                "done_at": {u: parse_dt(t) for u, t in task.get("done_at", {}).items()},
                "done_confirmed": set(task.get("done_confirmed", [])),
            }
    except Exception as e:
        logger.error(f"load_tasks error: {e}")

# =========================
# ZADACHA — BUILD MAIN MESSAGE
# =========================

def build_zadacha_main_text(task):
    creator = task["creator"]
    targets = task["targets"]
    supervisors = task.get("supervisor", [])
    text = task["text"]
    deadline = task["deadline"]
    target_str = zadacha_target_str(targets)
    supervisor_names = " + ".join(AGENTS_DATA.get(u, {}).get("name", u) for u in supervisors)
    date_str = deadline.strftime("%d.%m")
    time_str = deadline.strftime("%H:%M")
    seen_tags = set()
    tags_list = []
    for u in list(targets) + list(supervisors):
        if u not in seen_tags:
            seen_tags.add(u)
            tags_list.append(f"@{u}")
    all_tags = " ".join(tags_list)
    return (
        f"📌 {creator} → {target_str}\n"
        f"🧑 Nazorat: {supervisor_names}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📝 Vazifa:\n<tg-spoiler>{text}</tg-spoiler>\n"
        f"━━━━━━━━━━━━━━\n"
        f"Deadline: 📅 {date_str}  ⏰ {time_str}\n\n"
        f"{all_tags}"
    )

def build_zadacha_main_keyboard(tid, task):
    targets = task["targets"]
    supervisors = task.get("supervisor", [])
    accepted_exec = task.get("accepted_executors", set())
    accepted_sup = task.get("accepted_supervisors", set())
    keyboard = []
    for username in targets:
        name = AGENTS_DATA.get(username, {}).get("name", username)
        if username in accepted_exec:
            keyboard.append([InlineKeyboardButton(f"{name} – ✅", callback_data="noop")])
        else:
            keyboard.append([InlineKeyboardButton(
                f"⬜ Xop, bajaraman — {name}",
                callback_data=f"zacc_exec_{tid}_{username}"
            )])
    for username in supervisors:
        name = AGENTS_DATA.get(username, {}).get("name", username)
        if username in accepted_sup:
            keyboard.append([InlineKeyboardButton(f"{name} – ✅", callback_data="noop")])
        else:
            keyboard.append([InlineKeyboardButton(
                f"⬜ Xop, nazorat qilaman — {name}",
                callback_data=f"zacc_sup_{tid}_{username}"
            )])
    return InlineKeyboardMarkup(keyboard)

def all_accepted(task):
    targets = task["targets"]
    supervisors = task.get("supervisor", [])
    exec_ok = all(u in task.get("accepted_executors", set()) for u in targets)
    sup_ok = all(u in task.get("accepted_supervisors", set()) for u in supervisors)
    return exec_ok and sup_ok

# =========================
# CHECKLIST JOB
# =========================

async def send_checklist(bot, time_key):
    active = CHECKLIST_AGENTS
    if not active:
        return
    state["checklist_confirmations"][time_key] = {u: {} for u in active}
    state["checklist_log_lines"][time_key] = []
    # checklist_verified ni ham tozalash
    state.setdefault("checklist_verified", {})[time_key] = set()
    sent = await bot.send_message(
        chat_id=CHAT_ID,
        text=build_checklist_text(time_key, active),
        reply_markup=build_checklist_keyboard(time_key, active, state["checklist_confirmations"][time_key]),
        parse_mode="HTML"
    )
    state["checklist_message_ids"][time_key] = sent.message_id

async def checklist_job(context: ContextTypes.DEFAULT_TYPE):
    cycle_id = context.job.data["cycle_id"]
    time_key = context.job.data["time_key"]
    if cycle_id != state["cycle_id"] or state["stopped"]:
        return
    await send_checklist(context.bot, time_key)
    hour, minute = map(int, time_key.split(":"))
    context.job_queue.run_once(
        checklist_job,
        when=seconds_until_time(hour, minute),
        name=f"checklist_{time_key}",
        data={"cycle_id": cycle_id, "time_key": time_key}
    )

# =========================
# ZADACHA ACCEPT REMINDER JOB
# =========================

def is_agent_working_now(username):
    now = datetime.now(TIMEZONE)
    weekday = now.weekday()
    hour = now.hour
    data = AGENTS_DATA.get(username, {})
    work_days = data.get("work_days", [])
    work_hours = data.get("work_hours", {})
    if weekday not in work_days:
        return False
    wh = work_hours.get(str(weekday), [0, 24])
    return wh[0] <= hour < wh[1]

def seconds_until_agent_works(username):
    now = datetime.now(TIMEZONE)
    data = AGENTS_DATA.get(username, {})
    work_days = data.get("work_days", [])
    work_hours = data.get("work_hours", {})
    for days_ahead in range(8):
        check_day = now + timedelta(days=days_ahead)
        wd = check_day.weekday()
        if wd in work_days:
            wh = work_hours.get(str(wd), [0, 24])
            sh, eh = wh[0], wh[1]
            if days_ahead == 0:
                if now.hour >= sh and now.hour < eh:
                    return 0
                if now.hour >= eh:
                    continue
                work_start = check_day.replace(hour=sh, minute=0, second=0, microsecond=0)
            else:
                work_start = check_day.replace(hour=sh, minute=0, second=0, microsecond=0)
            secs = (work_start - now).total_seconds()
            if secs > 0:
                return secs
    return 300

async def zadacha_accept_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    tid = context.job.data["task_id"]
    if tid not in zadacha_tasks:
        return
    task = zadacha_tasks[tid]
    if all_accepted(task):
        return

    targets = task["targets"]
    supervisors = task.get("supervisor", [])
    accepted_exec = task.get("accepted_executors", set())
    accepted_sup = task.get("accepted_supervisors", set())
    deadline_str = task["deadline"].strftime("%d.%m")
    time_str = task["deadline"].strftime("%H:%M")
    text_short = task["text"]
    creator = task["creator"]
    target_names = " + ".join(AGENTS_DATA.get(u, {}).get("name", u) for u in targets)
    sup_names = " + ".join(AGENTS_DATA.get(u, {}).get("name", u) for u in supervisors)

    for mid in task.get("reminder_msg_ids", []):
        try:
            await context.bot.delete_message(chat_id=CHAT_ID, message_id=mid)
        except:
            pass
    task["reminder_msg_ids"] = []

    exec_next = 600
    for username in targets:
        if username in accepted_exec:
            continue
        if not is_agent_working_now(username):
            secs = seconds_until_agent_works(username)
            exec_next = min(exec_next, max(secs, 60))
            continue
        name = AGENTS_DATA.get(username, {}).get("name", username)
        keyboard = [[InlineKeyboardButton(f"⬜ Xop, bajaraman — {name}", callback_data=f"zacc_exec_{tid}_{username}")]]
        sent = await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"🔔 {name} @{username}\n"
                f"Sizga vazifa tayinlandi, hali qabul qilmadingiz!\n\n"
                f"👤 Vazifani bergan: {creator}\n"
                f"🧑 Nazoratchi: {sup_names}\n"
                f"━━━━━━━━━━━━━━\n"
                f"📝 Vazifa: <tg-spoiler>{text_short}</tg-spoiler>\n"
                f"━━━━━━━━━━━━━━\n"
                f"Deadline: 📅 {deadline_str}  ⏰ {time_str}"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        task["reminder_msg_ids"].append(sent.message_id)

    sup_next = 600
    for username in supervisors:
        if username in accepted_sup:
            continue
        if not is_agent_working_now(username):
            secs = seconds_until_agent_works(username)
            sup_next = min(sup_next, max(secs, 60))
            continue
        name = AGENTS_DATA.get(username, {}).get("name", username)
        keyboard = [[InlineKeyboardButton(f"⬜ Xop, nazorat qilaman — {name}", callback_data=f"zacc_sup_{tid}_{username}")]]
        sent = await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"🔔 {name} @{username}\n"
                f"Sizga nazorat qilish uchun vazifa tayinlandi!\n\n"
                f"👤 Vazifani bergan: {creator}\n"
                f"👷 Ijrochi: {target_names}\n"
                f"🧑 Nazoratchi: {name}\n"
                f"━━━━━━━━━━━━━━\n"
                f"📝 Vazifa: <tg-spoiler>{text_short}</tg-spoiler>\n"
                f"━━━━━━━━━━━━━━\n"
                f"Deadline: 📅 {deadline_str}  ⏰ {time_str}"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        task["reminder_msg_ids"].append(sent.message_id)

    save_tasks()

    next_schedule = min(exec_next, sup_next)
    context.job_queue.run_once(
        zadacha_accept_reminder_job,
        when=next_schedule,
        name=f"zaccrem_{tid}",
        data={"task_id": tid}
    )

# =========================
# BUTTON CALLBACKS
# =========================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "noop":
        return

    # CHECKLIST VERIFY — checklistdagi Tekshirdim tugmasi
    if data.startswith("chk_verify_") and not data.endswith("_all"):
        if query.from_user.username != ADMIN_USERNAME:
            return
        rest = data[11:]
        parts = rest.split("_")
        time_raw = parts[0]
        task_num = int(parts[-1])
        username = "_".join(parts[1:-1])
        time_key = f"{time_raw[:2]}:{time_raw[2:]}"
        vkey = f"{time_key}_{username}"

        # Shu vazifani verified deb belgilaymiz
        task_index = task_num - 1
        state.setdefault("checklist_verified", {}).setdefault(time_key, set()).add(task_index)
        verified_set = state["checklist_verified"][time_key]

        # Checklistni yangilaymiz
        msg_id = state["checklist_message_ids"].get(time_key)
        if msg_id:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=CHAT_ID,
                    message_id=msg_id,
                    reply_markup=build_checklist_keyboard(time_key, CHECKLIST_AGENTS, state["checklist_confirmations"].get(time_key, {}), verified_set)
                )
            except:
                pass

        # Barcha 4 ta tekshirildimi?
        tasks = CHECKLIST_CONFIG.get(time_key, [])
        all_verified = all(i in verified_set for i in range(len(tasks)))

        if all_verified:
            # Verify xabarini o'chir
            vs = checklist_verify_state.get(vkey, {})
            verify_mid = vs.get("verify_msg_id")
            if verify_mid:
                async def delete_verify():
                    await asyncio.sleep(1)
                    try:
                        await context.bot.delete_message(chat_id=CHAT_ID, message_id=verify_mid)
                    except:
                        pass
                asyncio.create_task(delete_verify())
                vs["verify_msg_id"] = None
        return

    # CHECKLIST VERIFY — eski _all format (ignore)
    if data.startswith("chk_verify_") and data.endswith("_all"):
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

    if data == "zadachi_group_cancel":
        stored_id = zadacha_state.get(f"zadachi_group_{query.message.message_id}")
        if stored_id and query.from_user.id != stored_id:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        zadacha_state.pop(f"zadachi_group_{query.message.message_id}", None)
        cmd_msg = query.message.reply_to_message
        try:
            await query.message.delete()
        except:
            pass
        if cmd_msg:
            try:
                await cmd_msg.delete()
            except:
                pass
        return

    # CHECKLIST
    if data.startswith("chk_") and not data.startswith("chk_verify_"):
        without_prefix = data[4:]
        first_underscore = without_prefix.index("_")
        time_raw = without_prefix[:first_underscore]
        rest = without_prefix[first_underscore + 1:]
        last_underscore = rest.rindex("_")
        username = rest[:last_underscore]
        task_index = int(rest[last_underscore + 1:])
        time_key = f"{time_raw[:2]}:{time_raw[2:]}"
        presser = query.from_user.username

        # Faqat Ozodbek bosa ishlaydi, boshqalar — ignore
        if presser != "sirlyinfo":
            return

        state["checklist_confirmations"].setdefault(time_key, {}).setdefault(username, {})
        user_conf = state["checklist_confirmations"][time_key][username]
        if user_conf.get(task_index, False):
            return
        user_conf[task_index] = True

        active = CHECKLIST_AGENTS
        verified_set = state.get("checklist_verified", {}).get(time_key, set())
        try:
            await query.message.edit_reply_markup(
                reply_markup=build_checklist_keyboard(time_key, active, state["checklist_confirmations"][time_key], verified_set)
            )
        except:
            pass

        # Barcha vazifalar bajarilganmi tekshir
        tasks = CHECKLIST_CONFIG.get(time_key, [])
        all_done = all(user_conf.get(i, False) for i in range(len(tasks)))

        if all_done:
            # Faqat shu payt verify xabari yuboriladi
            name = AGENTS_DATA.get(username, {}).get("name", username)
            admin_name = AGENTS_DATA.get(ADMIN_USERNAME, {}).get("name", "Umid")
            vkey = f"{time_key}_{username}"
            if vkey not in checklist_verify_state:
                checklist_verify_state[vkey] = {"pending_items": [], "verify_msg_id": None}
            vs = checklist_verify_state[vkey]

            # Eski verify xabarini o'chir
            if vs.get("verify_msg_id"):
                try:
                    await context.bot.delete_message(chat_id=CHAT_ID, message_id=vs["verify_msg_id"])
                except:
                    pass

            verify_text = (
                f"✅ {name} barcha vazifalarni bajardi!\n"
                f"@{ADMIN_USERNAME} checklistdan tekshiring"
            )
            sent_v = await context.bot.send_message(
                chat_id=CHAT_ID,
                text=verify_text
            )
            vs["verify_msg_id"] = sent_v.message_id
        return

    # ZADACHA ACCEPT — EXECUTOR
    if data.startswith("zacc_exec_"):
        rest = data[10:]
        idx = rest.index("_")
        tid = int(rest[:idx])
        username = rest[idx + 1:]
        if query.from_user.username != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        if tid not in zadacha_tasks:
            return
        task = zadacha_tasks[tid]
        if username in task.get("accepted_executors", set()):
            await query.answer("Siz allaqachon qabul qilgansiz.")
            return
        task.setdefault("accepted_executors", set()).add(username)
        task.setdefault("accepted_at", {})[username] = datetime.now(TIMEZONE)
        if task.get("main_msg_id"):
            try:
                await context.bot.edit_message_reply_markup(chat_id=CHAT_ID, message_id=task["main_msg_id"], reply_markup=build_zadacha_main_keyboard(tid, task))
            except:
                pass
        if query.message.message_id != task.get("main_msg_id"):
            try:
                await query.message.delete()
            except:
                pass
        if task.get("reminder_msg_ids"):
            task["reminder_msg_ids"] = [m for m in task["reminder_msg_ids"] if m != query.message.message_id]
        if all_accepted(task):
            await _on_all_accepted(context.bot, tid, task)
        save_tasks()
        return

    # ZADACHA ACCEPT — SUPERVISOR
    if data.startswith("zacc_sup_"):
        rest = data[9:]
        idx = rest.index("_")
        tid = int(rest[:idx])
        username = rest[idx + 1:]
        if query.from_user.username != username and query.from_user.username != ADMIN_USERNAME:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        if tid not in zadacha_tasks:
            return
        task = zadacha_tasks[tid]
        if username in task.get("accepted_supervisors", set()):
            await query.answer("Siz allaqachon qabul qilgansiz.")
            return
        task.setdefault("accepted_supervisors", set()).add(username)
        if task.get("main_msg_id"):
            try:
                await context.bot.edit_message_reply_markup(chat_id=CHAT_ID, message_id=task["main_msg_id"], reply_markup=build_zadacha_main_keyboard(tid, task))
            except:
                pass
        if query.message.message_id != task.get("main_msg_id"):
            try:
                await query.message.delete()
            except:
                pass
        if task.get("reminder_msg_ids"):
            task["reminder_msg_ids"] = [m for m in task["reminder_msg_ids"] if m != query.message.message_id]
        if all_accepted(task):
            await _on_all_accepted(context.bot, tid, task)
        save_tasks()
        return

    # DONE
    if data.startswith("zdone_"):
        rest = data[6:]
        idx = rest.index("_")
        tid = int(rest[:idx])
        username = rest[idx + 1:]
        if query.from_user.username != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        if tid not in zadacha_tasks:
            return
        task = zadacha_tasks[tid]
        task.setdefault("done", set()).add(username)
        save_tasks()
        name = AGENTS_DATA.get(username, {}).get("name", username)
        supervisors = task.get("supervisor", [])
        sup_tag = " " + " ".join(f"@{u}" for u in supervisors) if supervisors else ""
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"✅ {name} vazifani bajardi.\n🕐 {datetime.now(TIMEZONE).strftime('%d.%m soat %H:%M')}\n📌 <tg-spoiler>{task['text'][:50]}</tg-spoiler>\n@{task['creator_username']}{sup_tag}",
            parse_mode="HTML"
        )
        try:
            await query.message.delete()
        except:
            pass
        return

    # CANCEL
    if data.startswith("zcancel_"):
        rest = data[8:]
        idx = rest.index("_")
        tid = int(rest[:idx])
        username = rest[idx + 1:]
        if query.from_user.username != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        if tid not in zadacha_tasks:
            return
        task = zadacha_tasks[tid]
        task.setdefault("cancelled", set()).add(username)
        save_tasks()
        name = AGENTS_DATA.get(username, {}).get("name", username)
        supervisors = task.get("supervisor", [])
        sup_tag = " " + " ".join(f"@{u}" for u in supervisors) if supervisors else ""
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"❌ {name} vazifani bekor qildi.\n🕐 {datetime.now(TIMEZONE).strftime('%d.%m soat %H:%M')}\n📌 <tg-spoiler>{task['text'][:50]}</tg-spoiler>\n@{task['creator_username']}{sup_tag}",
            parse_mode="HTML"
        )
        try:
            await query.message.delete()
        except:
            pass
        return

    # EXTEND
    if data.startswith("zext_"):
        parts = data[5:].split("_")
        tid = int(parts[0])
        username = parts[1]
        minutes = int(parts[2])
        if query.from_user.username != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        if tid not in zadacha_tasks:
            return
        task = zadacha_tasks[tid]
        task["deadline"] += timedelta(minutes=minutes)
        save_tasks()
        new_dl = task["deadline"].strftime("%d.%m soat %H:%M")
        cancel_jobs_by_name(context.job_queue, f"zdue_{tid}")
        now = datetime.now(TIMEZONE)
        if task["deadline"] > now:
            context.job_queue.run_once(zadacha_deadline_job, when=(task["deadline"] - now).total_seconds(), name=f"zdue_{tid}", data={"task_id": tid})
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except:
            pass
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"⏰ Deadline uzaytirildi.\n📌 <tg-spoiler>{task['text'][:50]}</tg-spoiler>\nYangi deadline: 📅 {new_dl}\n@{task['creator_username']}",
            parse_mode="HTML"
        )
        return

    # ESIMDA
    if data.startswith("zes_"):
        rest = data[4:]
        idx = rest.index("_")
        tid = int(rest[:idx])
        username = rest[idx + 1:]
        if query.from_user.username != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        msg_to_delete = query.message
        async def del10():
            await asyncio.sleep(10)
            try:
                await msg_to_delete.delete()
            except:
                pass
        asyncio.create_task(del10())
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except:
            pass
        return

    # ZADACHI — BAJARDIM
    if data.startswith("ztask_done_"):
        rest = data[11:]
        idx = rest.index("_")
        tid = int(rest[:idx])
        username = rest[idx + 1:]
        if query.from_user.username != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        if tid not in zadacha_tasks:
            return
        task = zadacha_tasks[tid]
        if username in task.get("done", set()):
            await query.answer("Siz allaqachon bajardingiz.")
            return
        now_done = datetime.now(TIMEZONE)
        task.setdefault("done", set()).add(username)
        task.setdefault("done_at", {})[username] = now_done

        name = AGENTS_DATA.get(username, {}).get("name", username)
        supervisors = task.get("supervisor", [])
        creator_username = task["creator_username"]
        seen = set()
        tags_list = []
        for t in ([creator_username] + list(supervisors)):
            if t not in seen:
                seen.add(t)
                tags_list.append(f"@{t}")
        all_tags = " ".join(tags_list)

        created_at = task.get("created_at")
        accepted_at = task.get("accepted_at", {}).get(username)
        created_str = created_at.strftime("%d.%m soat %H:%M") if created_at else "—"
        accepted_str = accepted_at.strftime("%d.%m soat %H:%M") if accepted_at else "—"
        done_str = now_done.strftime("%d.%m soat %H:%M")
        text_short = task["text"]

        msg_text = (
            f"✅ {name} vazifani bajardi!\n"
            f"━━━━━━━━━━━━━━\n"
            f"📌 <tg-spoiler>{text_short}</tg-spoiler>\n"
            f"━━━━━━━━━━━━━━\n"
            f"📋 Vazifa berildi: {created_str}\n"
            f"✅ Qabul qilindi: {accepted_str}\n"
            f"✅ Bajarildi: {done_str}\n"
            f"━━━━━━━━━━━━━━\n"
            f"{all_tags}"
        )

        creator_name = task["creator"]
        keyboard = [[InlineKeyboardButton(f"⬜ Qabul qildim — {creator_name}", callback_data=f"ztask_doneack_{tid}_{creator_username}")]]

        await context.bot.send_message(chat_id=CHAT_ID, text=msg_text, reply_markup=InlineKeyboardMarkup(keyboard))

        if task.get("main_msg_id"):
            try:
                await context.bot.delete_message(chat_id=CHAT_ID, message_id=task["main_msg_id"])
            except:
                pass
        for mid in task.get("reminder_msg_ids", []):
            try:
                await context.bot.delete_message(chat_id=CHAT_ID, message_id=mid)
            except:
                pass
        task["reminder_msg_ids"] = []
        task["main_msg_id"] = None

        save_tasks()

        try:
            await query.message.delete()
        except:
            pass
        return

    # ZADACHI — DONE ACK
    if data.startswith("ztask_doneack_"):
        rest = data[14:]
        idx = rest.index("_")
        tid = int(rest[:idx])
        username = rest[idx + 1:]
        if query.from_user.username != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        if tid not in zadacha_tasks:
            return
        task = zadacha_tasks[tid]
        if username in task.get("done_confirmed", set()):
            await query.answer("Siz allaqachon tasdiqladingiz.")
            return
        task.setdefault("done_confirmed", set()).add(username)
        creator_name = task["creator"]
        try:
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ Qabul qildim — {creator_name}", callback_data="noop")]])
            )
        except:
            pass
        save_tasks()
        return

    if data.startswith("ztask_edit_"):
        tid = int(data[11:])
        if tid not in zadacha_tasks:
            return
        task = zadacha_tasks[tid]
        if query.from_user.username != task["creator_username"] and query.from_user.username != ADMIN_USERNAME:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        keyboard = [
            [InlineKeyboardButton("✏️ Matnni o'zgartir", callback_data=f"ztask_editfield_text_{tid}")],
            [InlineKeyboardButton("📅 Deadlineni o'zgartir", callback_data=f"ztask_editfield_deadline_{tid}")],
            [InlineKeyboardButton("👷 Ijrochini o'zgartir", callback_data=f"ztask_editfield_target_{tid}")],
            [InlineKeyboardButton("❌ Bekor", callback_data="ztask_editcancel")],
        ]
        zadacha_state[f"edit_zadachi_{query.from_user.id}"] = {"zadachi_msg_id": query.message.message_id}
        edit_sent = await query.message.reply_text(
            f"📌 №{tid} | <tg-spoiler>{task['text'][:50]}</tg-spoiler>\n\nNimani o'zgartirmoqchisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        zadacha_state[f"edit_zadachi_{query.from_user.id}"]["edit_msg_id"] = edit_sent.message_id
        return

    if data.startswith("ztask_editfield_"):
        rest = data[16:]
        if rest.startswith("text_"):
            tid = int(rest[5:])
            zadacha_state[query.from_user.id] = {"step": "edit_text", "tid": tid, "messages": [query.message.message_id]}
            sent = await query.message.reply_text(f"Yangi vazifa matnini yozing:")
            zadacha_state[query.from_user.id]["messages"].append(sent.message_id)
        elif rest.startswith("deadline_"):
            tid = int(rest[9:])
            task = zadacha_tasks[tid]
            targets = task["targets"]
            available_dates = get_available_dates_for_targets(targets)
            now2 = datetime.now(TIMEZONE)
            days = []
            for d in available_dates:
                diff = (d.date() - now2.date()).days
                if diff == 0:
                    label = f"📆 Bugun ({d.day} {MONTH_UZ[d.month]})"
                elif diff == 1:
                    label = f"📆 Ertaga ({d.day} {MONTH_UZ[d.month]})"
                else:
                    label = f"📆 {WEEKDAY_UZ[d.weekday()]} ({d.day} {MONTH_UZ[d.month]})"
                days.append([InlineKeyboardButton(label, callback_data=f"ztask_editdate_{tid}_{d.strftime('%d.%m')}")])
            days.append([InlineKeyboardButton("❌ Bekor", callback_data="ztask_editcancel")])
            zadacha_state[query.from_user.id] = {"step": "edit_deadline_date", "tid": tid, "messages": [query.message.message_id]}
            sent = await query.message.reply_text("Yangi deadline sanasini tanlang:", reply_markup=InlineKeyboardMarkup(days))
            zadacha_state[query.from_user.id]["messages"].append(sent.message_id)
        elif rest.startswith("target_"):
            tid = int(rest[7:])
            all_agents = list(AGENTS_DATA.keys())
            keyboard2 = [
                [InlineKeyboardButton(f"👤 {AGENTS_DATA[u]['name']}", callback_data=f"ztask_edittarget_{tid}_{u}")]
                for u in all_agents
            ]
            keyboard2.append([InlineKeyboardButton("❌ Bekor", callback_data="ztask_editcancel")])
            zadacha_state[query.from_user.id] = {"step": "edit_target", "tid": tid, "messages": [query.message.message_id]}
            sent = await query.message.reply_text("Yangi ijrochini tanlang:", reply_markup=InlineKeyboardMarkup(keyboard2))
            zadacha_state[query.from_user.id]["messages"].append(sent.message_id)
        return

    if data.startswith("ztask_editdate_"):
        rest = data[15:]
        idx = rest.index("_")
        tid = int(rest[:idx])
        date_str = rest[idx + 1:]
        task = zadacha_tasks[tid]
        targets = task["targets"]
        available_times = get_available_times_for_targets(targets, date_str)
        slots = [
            [InlineKeyboardButton(f"⏰ {t}", callback_data=f"ztask_edittime_{tid}_{date_str}_{t}")]
            for t in available_times
        ]
        slots.append([InlineKeyboardButton("❌ Bekor", callback_data="ztask_editcancel")])
        user_id2 = query.from_user.id
        if user_id2 in zadacha_state:
            zadacha_state[user_id2]["messages"].append(query.message.message_id)
        sent = await query.message.reply_text("Yangi deadline vaqtini tanlang:", reply_markup=InlineKeyboardMarkup(slots))
        if user_id2 in zadacha_state:
            zadacha_state[user_id2]["messages"].append(sent.message_id)
        return

    if data.startswith("ztask_edittime_"):
        rest = data[15:]
        parts2 = rest.split("_")
        tid = int(parts2[0])
        date_str = parts2[1]
        time_str2 = parts2[2]
        task = zadacha_tasks[tid]
        now3 = datetime.now(TIMEZONE)
        dt = datetime.strptime(f"{date_str}.{now3.year} {time_str2}", "%d.%m.%Y %H:%M").replace(tzinfo=TIMEZONE)
        task["deadline"] = dt
        task["accepted_executors"] = set()
        task["accepted_supervisors"] = set()
        save_tasks()
        cancel_jobs_by_name(context.job_queue, f"zdue_{tid}")
        cancel_jobs_by_name(context.job_queue, f"zpre_{tid}")
        cancel_jobs_by_name(context.job_queue, f"zaccrem_{tid}")
        if dt > now3:
            context.job_queue.run_once(zadacha_deadline_job, when=(dt - now3).total_seconds(), name=f"zdue_{tid}", data={"task_id": tid})
            remind_time = dt - timedelta(minutes=30)
            if remind_time > now3:
                context.job_queue.run_once(zadacha_pre_deadline_job, when=(remind_time - now3).total_seconds(), name=f"zpre_{tid}", data={"task_id": tid})
        if task.get("main_msg_id"):
            try:
                await context.bot.edit_message_text(
                    chat_id=CHAT_ID, message_id=task["main_msg_id"],
                    text=build_zadacha_main_text(task) + "\n\n✏️ (yangilandi)",
                    parse_mode="HTML",
                    reply_markup=build_zadacha_main_keyboard(tid, task)
                )
            except:
                pass
        for mid in task.get("reminder_msg_ids", []):
            try:
                await context.bot.delete_message(chat_id=CHAT_ID, message_id=mid)
            except:
                pass
        task["reminder_msg_ids"] = []
        context.job_queue.run_once(zadacha_accept_reminder_job, when=300, name=f"zaccrem_{tid}", data={"task_id": tid})
        user_id3 = query.from_user.id
        msgs3 = zadacha_state.pop(user_id3, {}).get("messages", [])
        for mid in msgs3:
            try:
                await context.bot.delete_message(chat_id=user_id3, message_id=mid)
            except:
                pass
        await context.bot.send_message(chat_id=user_id3, text=f"✅ Deadline yangilandi: 📅 {date_str} ⏰ {time_str2}")
        return

    if data.startswith("ztask_edittarget_"):
        rest = data[17:]
        idx = rest.index("_")
        tid = int(rest[:idx])
        new_target = rest[idx + 1:]
        task = zadacha_tasks[tid]
        task["targets"] = [new_target]
        task["accepted_executors"] = set()
        task["accepted_supervisors"] = set()
        save_tasks()
        if task.get("main_msg_id"):
            try:
                await context.bot.edit_message_text(
                    chat_id=CHAT_ID, message_id=task["main_msg_id"],
                    text=build_zadacha_main_text(task) + "\n\n✏️ (yangilandi)",
                    parse_mode="HTML",
                    reply_markup=build_zadacha_main_keyboard(tid, task)
                )
            except:
                pass
        for mid in task.get("reminder_msg_ids", []):
            try:
                await context.bot.delete_message(chat_id=CHAT_ID, message_id=mid)
            except:
                pass
        task["reminder_msg_ids"] = []
        cancel_jobs_by_name(context.job_queue, f"zaccrem_{tid}")
        context.job_queue.run_once(zadacha_accept_reminder_job, when=300, name=f"zaccrem_{tid}", data={"task_id": tid})
        user_id4 = query.from_user.id
        msgs4 = zadacha_state.pop(user_id4, {}).get("messages", [])
        for mid in msgs4:
            try:
                await context.bot.delete_message(chat_id=user_id4, message_id=mid)
            except:
                pass
        name_new = AGENTS_DATA.get(new_target, {}).get("name", new_target)
        await context.bot.send_message(chat_id=user_id4, text=f"✅ Ijrochi {name_new} ga o'zgartirildi.")
        return

    if data == "ztask_editcancel":
        user_id5 = query.from_user.id
        msgs5 = zadacha_state.pop(user_id5, {}).get("messages", [])
        for mid in msgs5:
            try:
                await context.bot.delete_message(chat_id=user_id5, message_id=mid)
            except:
                pass
        try:
            await query.message.delete()
        except:
            pass
        return

    if data.startswith("ztask_delete_"):
        tid = int(data[13:])
        if tid not in zadacha_tasks:
            return
        task = zadacha_tasks[tid]
        if query.from_user.username != task["creator_username"] and query.from_user.username != ADMIN_USERNAME:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        keyboard = [
            [InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"ztask_deleteconfirm_{tid}")],
            [InlineKeyboardButton("❌ Yo'q", callback_data="ztask_editcancel")],
        ]
        confirm_sent = await query.message.reply_text(
            f"⚠️ №{tid} vazifani o'chirishni tasdiqlaysizmi?\n<tg-spoiler>{task['text'][:50]}</tg-spoiler>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        zadacha_state[f"del_confirm_{tid}"] = {
            "confirm_msg_id": confirm_sent.message_id,
            "zadachi_msg_id": query.message.message_id,
            "chat_id": query.from_user.id,
        }
        return

    if data.startswith("ztask_deleteconfirm_"):
        tid = int(data[20:])
        if tid not in zadacha_tasks:
            return
        task = zadacha_tasks[tid]
        if query.from_user.username != task["creator_username"] and query.from_user.username != ADMIN_USERNAME:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        cancel_jobs_by_name(context.job_queue, f"zdue_{tid}")
        cancel_jobs_by_name(context.job_queue, f"zpre_{tid}")
        cancel_jobs_by_name(context.job_queue, f"zaccrem_{tid}")
        if task.get("main_msg_id"):
            try:
                await context.bot.delete_message(chat_id=CHAT_ID, message_id=task["main_msg_id"])
            except:
                pass
        for mid in task.get("reminder_msg_ids", []):
            try:
                await context.bot.delete_message(chat_id=CHAT_ID, message_id=mid)
            except:
                pass
        del zadacha_tasks[tid]
        save_tasks()
        try:
            await query.message.delete()
        except:
            pass
        sent_ok = await context.bot.send_message(chat_id=query.from_user.id, text=f"✅ №{tid} vazifa o'chirildi.")
        del_info = zadacha_state.pop(f"del_confirm_{tid}", {})
        zadachi_msg_id = del_info.get("zadachi_msg_id")
        msgs_to_del = [sent_ok.message_id]
        if zadachi_msg_id:
            msgs_to_del.append(zadachi_msg_id)
        schedule_delete(context.bot, query.from_user.id, msgs_to_del, delay=5)
        return

async def _on_all_accepted(bot, tid, task):
    for mid in task.get("reminder_msg_ids", []):
        try:
            await bot.delete_message(chat_id=CHAT_ID, message_id=mid)
        except:
            pass
    task["reminder_msg_ids"] = []
    save_tasks()

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

    if user_id not in zadacha_state:
        return
    zs = zadacha_state[user_id]
    step = zs.get("step")

    if step == "text":
        zs["text"] = update.message.text
        zs["step"] = "confirm"
        zs["messages"].append(update.message.message_id)
        targets = zs.get("targets", [])
        supervisors = zs.get("supervisor", [])
        date_str = zs.get("deadline_date", "")
        time_str2 = zs.get("deadline_time", "")
        creator = update.effective_user.first_name or update.effective_user.username
        supervisor_names = " + ".join(AGENTS_DATA.get(u, {}).get("name", u) for u in supervisors)
        sent = await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"📌 {creator} → {zadacha_target_str(targets)}\n"
                f"🧑 Nazorat: {supervisor_names}\n"
                f"Vazifa:\n━━━━━━━━━━━━━━\n"
                f'"{update.message.text}"\n'
                f"━━━━━━━━━━━━━━\n"
                f"Deadline: 📅 {date_str}  ⏰ {time_str2}\n\n"
                f"Yuborilsinmi?"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Tasdiqlash", callback_data="zconfirm_yes")],
                [InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_supervisor")],
                [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")]
            ])
        )
        zs["messages"].append(sent.message_id)

    elif step == "edit_text":
        tid = zs.get("tid")
        if tid in zadacha_tasks:
            zadacha_tasks[tid]["text"] = update.message.text
            zadacha_tasks[tid]["accepted_executors"] = set()
            zadacha_tasks[tid]["accepted_supervisors"] = set()
            save_tasks()
            task = zadacha_tasks[tid]
            if task.get("main_msg_id"):
                try:
                    await context.bot.edit_message_text(
                        chat_id=CHAT_ID, message_id=task["main_msg_id"],
                        text=build_zadacha_main_text(task) + "\n\n✏️ (yangilandi)",
                        parse_mode="HTML",
                        reply_markup=build_zadacha_main_keyboard(tid, task)
                    )
                except:
                    pass
            for mid in task.get("reminder_msg_ids", []):
                try:
                    await context.bot.delete_message(chat_id=CHAT_ID, message_id=mid)
                except:
                    pass
            task["reminder_msg_ids"] = []
            cancel_jobs_by_name(context.job_queue, f"zaccrem_{tid}")
            context.job_queue.run_once(zadacha_accept_reminder_job, when=300, name=f"zaccrem_{tid}", data={"task_id": tid})
        msgs = zs.get("messages", [])
        zadacha_state.pop(user_id, None)
        for mid in msgs:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=mid)
            except:
                pass
        sent = await context.bot.send_message(chat_id=user_id, text="✅ Vazifa matni yangilandi.")
        schedule_delete(context.bot, user_id, [update.message.message_id, sent.message_id])

    # Custom checklist task kiritish
    handled = await custom_checklist_text_handler(user_id, update.message.text, context)
    if handled:
        try:
            await update.message.delete()
        except:
            pass

# =========================
# ZADACHA COMMAND + CALLBACKS
# =========================

def get_available_supervisors_for_deadline(targets, date_str, time_str):
    try:
        now = datetime.now(TIMEZONE)
        year = now.year
        d = datetime.strptime(f"{date_str}.{year} {time_str}", "%d.%m.%Y %H:%M")
        weekday = d.weekday()
        deadline_hour = d.hour
    except:
        return list(AGENTS_DATA.keys())

    available = []
    for username, data in AGENTS_DATA.items():
        if username in targets:
            continue
        work_days = data.get("work_days", [])
        work_hours = data.get("work_hours", {})
        if weekday in work_days:
            wh = work_hours.get(str(weekday), [0, 24])
            if wh[0] <= deadline_hour < wh[1]:
                available.append(username)
    return available

async def zadacha_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    chat_type = update.effective_chat.type

    if chat_type in ("group", "supergroup"):
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        sent = await update.message.reply_text(
            f"Bu funksiyadan shaxsiy xabar orqali foydalanishingiz mumkin 👉 @{bot_username}\n\n⚠️ Bu xabar ⏱ 5 daqiqadan keyin o'chadi"
        )
        schedule_delete(context.bot, update.effective_chat.id, [sent.message_id], delay=60)
        return

    zadacha_state[user_id] = {"step": "executor", "messages": [], "creator_username": username}
    if update.message:
        zadacha_state[user_id]["messages"].append(update.message.message_id)
    all_agents = list(AGENTS_DATA.keys())
    keyboard = [[InlineKeyboardButton(f"👤 {AGENTS_DATA[u]['name']}", callback_data=f"ze_{u}")] for u in all_agents]
    keyboard.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])
    sent = await context.bot.send_message(
        chat_id=user_id,
        text="👷 Ijro etuvchi hodimni tanlang:\n\n⚠️ Bu xabar ⏱ 5 daqiqadan keyin o'chadi",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    zadacha_state[user_id]["messages"].append(sent.message_id)
    zadacha_state[user_id]["created_ts"] = datetime.now(TIMEZONE).timestamp()

async def zadacha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()

    if data == "zt_otmen":
        msgs = zadacha_state.get(user_id, {}).get("messages", [])
        for mid in msgs:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=mid)
            except:
                pass
        zadacha_state.pop(user_id, None)
        sent = await context.bot.send_message(chat_id=user_id, text="❌ Vazifa bekor qilindi.\n⚠️ Bu xabar ⏱ 10 soniyadan keyin o'chadi")
        schedule_delete(context.bot, user_id, [sent.message_id])
        return

    if user_id not in zadacha_state and not data.startswith(("zacc_", "zes_", "zdone_", "zext_", "zcancel_", "ztask_")):
        return

    if data.startswith("ze_"):
        target = data[3:]
        targets = [target]
        zadacha_state[user_id]["targets"] = targets
        zadacha_state[user_id]["step"] = "date"
        now2 = datetime.now(TIMEZONE)
        available_dates = get_available_dates_for_targets(targets)
        days = []
        for d in available_dates:
            diff = (d.date() - now2.date()).days
            if diff == 0:
                label = f"📆 Bugun ({d.day} {MONTH_UZ[d.month]})"
            elif diff == 1:
                label = f"📆 Ertaga ({d.day} {MONTH_UZ[d.month]})"
            else:
                label = f"📆 {WEEKDAY_UZ[d.weekday()]} ({d.day} {MONTH_UZ[d.month]})"
            days.append([InlineKeyboardButton(label, callback_data=f"zd_{d.strftime('%d.%m')}")])
        days.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_start")])
        days.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])
        sent = await context.bot.send_message(chat_id=user_id, text="📅 Deadline sanasini tanlang:", reply_markup=InlineKeyboardMarkup(days))
        zadacha_state[user_id]["messages"].append(sent.message_id)

    elif data.startswith("zd_"):
        date_str = data[3:]
        zadacha_state[user_id]["deadline_date"] = date_str
        targets = zadacha_state[user_id].get("targets", [])
        available_times = get_available_times_for_targets(targets, date_str)
        if not available_times:
            sent = await context.bot.send_message(chat_id=user_id, text="❌ Bu sana uchun ish vaqti topilmadi.")
            zadacha_state[user_id]["messages"].append(sent.message_id)
            return
        slots = [[InlineKeyboardButton(f"⏰ {t}", callback_data=f"ztime_{t}")] for t in available_times]
        slots.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_start")])
        slots.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])
        sent = await context.bot.send_message(chat_id=user_id, text="🕐 Deadline vaqtini tanlang:", reply_markup=InlineKeyboardMarkup(slots))
        zadacha_state[user_id]["messages"].append(sent.message_id)

    elif data.startswith("ztime_"):
        time_str = data[6:]
        zadacha_state[user_id]["deadline_time"] = time_str
        zadacha_state[user_id]["step"] = "supervisor"
        targets = zadacha_state[user_id].get("targets", [])
        date_str = zadacha_state[user_id].get("deadline_date", "")
        available_sups = get_available_supervisors_for_deadline(targets, date_str, time_str)
        if not available_sups:
            available_sups = [u for u in AGENTS_DATA.keys() if u not in targets]
        keyboard = [[InlineKeyboardButton(f"👤 {AGENTS_DATA[u]['name']}", callback_data=f"zs_{u}")] for u in available_sups]
        keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_date")])
        keyboard.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])
        sent = await context.bot.send_message(chat_id=user_id, text="🧑 Nazorat qiluvchi hodimni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
        zadacha_state[user_id]["messages"].append(sent.message_id)

    elif data.startswith("zs_"):
        supervisor = data[3:]
        targets = zadacha_state[user_id].get("targets", [])
        if len(targets) == 1 and supervisor == targets[0]:
            await query.answer("⛔ O'zingizga o'zingiz nazoratchi bo'la olmaysiz!", show_alert=True)
            return
        zadacha_state[user_id]["supervisor"] = [supervisor]
        zadacha_state[user_id]["step"] = "text"
        sent = await context.bot.send_message(
            chat_id=user_id,
            text="✏️ Vazifa matnini yozing:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_supervisor")], [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")]])
        )
        zadacha_state[user_id]["messages"].append(sent.message_id)

    elif data.startswith("zback_"):
        where = data[6:]
        all_agents = list(AGENTS_DATA.keys())
        if where == "start":
            keyboard = [[InlineKeyboardButton(f"👤 {AGENTS_DATA[u]['name']}", callback_data=f"ze_{u}")] for u in all_agents]
            keyboard.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])
            sent = await context.bot.send_message(chat_id=user_id, text="👷 Ijro etuvchi hodimni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
            zadacha_state[user_id]["messages"].append(sent.message_id)
        elif where == "date":
            targets = zadacha_state[user_id].get("targets", [])
            now2 = datetime.now(TIMEZONE)
            available_dates = get_available_dates_for_targets(targets)
            days = []
            for d in available_dates:
                diff = (d.date() - now2.date()).days
                if diff == 0:
                    label = f"📆 Bugun ({d.day} {MONTH_UZ[d.month]})"
                elif diff == 1:
                    label = f"📆 Ertaga ({d.day} {MONTH_UZ[d.month]})"
                else:
                    label = f"📆 {WEEKDAY_UZ[d.weekday()]} ({d.day} {MONTH_UZ[d.month]})"
                days.append([InlineKeyboardButton(label, callback_data=f"zd_{d.strftime('%d.%m')}")])
            days.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_start")])
            days.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])
            sent = await context.bot.send_message(chat_id=user_id, text="📅 Deadline sanasini tanlang:", reply_markup=InlineKeyboardMarkup(days))
            zadacha_state[user_id]["messages"].append(sent.message_id)
        elif where == "supervisor":
            targets = zadacha_state[user_id].get("targets", [])
            date_str2 = zadacha_state[user_id].get("deadline_date", "")
            time_str3 = zadacha_state[user_id].get("deadline_time", "")
            available_sups = get_available_supervisors_for_deadline(targets, date_str2, time_str3)
            if not available_sups:
                available_sups = [u for u in AGENTS_DATA.keys() if u not in targets]
            keyboard = [[InlineKeyboardButton(f"👤 {AGENTS_DATA[u]['name']}", callback_data=f"zs_{u}")] for u in available_sups]
            keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_date")])
            keyboard.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])
            sent = await context.bot.send_message(chat_id=user_id, text="🧑 Nazorat qiluvchi hodimni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
            zadacha_state[user_id]["messages"].append(sent.message_id)
        elif where in ("target", "text"):
            sent = await context.bot.send_message(
                chat_id=user_id,
                text="✏️ Vazifa matnini yozing:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_supervisor")], [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")]])
            )
            zadacha_state[user_id]["messages"].append(sent.message_id)

    elif data == "zconfirm_yes":
        if user_id not in zadacha_state:
            return
        s = zadacha_state.pop(user_id)
        targets = s["targets"]
        text = s["text"]
        date_str = s["deadline_date"]
        time_str = s["deadline_time"]
        creator = query.from_user.first_name or query.from_user.username or "Noma'lum"
        creator_username = query.from_user.username
        supervisors = s.get("supervisor", [])
        if isinstance(supervisors, str):
            supervisors = [supervisors]

        now = datetime.now(TIMEZONE)
        dt = datetime.strptime(f"{date_str}.{now.year} {time_str}", "%d.%m.%Y %H:%M").replace(tzinfo=TIMEZONE)

        zadacha_counter[0] += 1
        tid = zadacha_counter[0]

        zadacha_tasks[tid] = {
            "creator": creator,
            "creator_username": creator_username,
            "targets": targets,
            "supervisor": supervisors,
            "text": text,
            "deadline": dt,
            "accepted_executors": set(),
            "accepted_supervisors": set(),
            "done": set(),
            "main_msg_id": None,
            "reminder_msg_ids": [],
            "created_at": datetime.now(TIMEZONE),
            "accepted_at": {},
            "done_at": {},
            "done_confirmed": set(),
        }

        main_sent = await context.bot.send_message(
            chat_id=CHAT_ID,
            text=build_zadacha_main_text(zadacha_tasks[tid]),
            reply_markup=build_zadacha_main_keyboard(tid, zadacha_tasks[tid]),
            parse_mode="HTML"
        )
        zadacha_tasks[tid]["main_msg_id"] = main_sent.message_id

        remind_time = dt - timedelta(minutes=30)
        if remind_time > now:
            context.job_queue.run_once(zadacha_pre_deadline_job, when=(remind_time - now).total_seconds(), name=f"zpre_{tid}", data={"task_id": tid})
        if dt > now:
            context.job_queue.run_once(zadacha_deadline_job, when=(dt - now).total_seconds(), name=f"zdue_{tid}", data={"task_id": tid})

        all_users = targets + supervisors
        earliest = 300
        for u in all_users:
            if is_agent_working_now(u):
                earliest = 300
                break
            secs = seconds_until_agent_works(u)
            if secs < earliest:
                earliest = max(secs, 60)
        context.job_queue.run_once(zadacha_accept_reminder_job, when=earliest, name=f"zaccrem_{tid}", data={"task_id": tid})

        save_tasks()

        target_str = zadacha_target_str(targets)
        sent_ok = await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ Vazifa yuborildi.\n"
                f"📌 {creator} → {target_str}\n"
                f"━━━━━━━━━━━━━━\n"
                f'<tg-spoiler>{text}</tg-spoiler>\n'
                f"━━━━━━━━━━━━━━\n"
                f"Deadline: 📅 {date_str}  ⏰ {time_str}\n\n"
                f"⚠️ Bu xabar ⏱ 10 soniyadan keyin o'chadi, vazifa guruhda qoladi"
            ),
            parse_mode="HTML"
        )
        warn_sent = await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ Jarayon xabarlari ⏱ 10 soniyadan keyin o'chadi"
        )
        await asyncio.sleep(10)
        for mid in s.get("messages", []):
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=mid)
            except:
                pass
        schedule_delete(context.bot, user_id, [warn_sent.message_id, sent_ok.message_id], delay=10)

# =========================
# ZADACHI COMMAND
# =========================

async def zadachi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requester = update.effective_user.username
    chat_type = update.effective_chat.type

    if chat_type in ("group", "supergroup"):
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        keyboard = [[InlineKeyboardButton("❌ Otmen", callback_data="zadachi_group_cancel")]]
        cmd_msg_id = update.message.message_id
        sent = await update.message.reply_text(
            f"📋 Vazifalar ro'yxatini ko'rish va tahrirlash uchun menga shaxsiy xabar yozing 👉 @{bot_username}\n\n⚠️ Bu xabar ⏱ 60 soniyadan keyin o'chadi",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        requester_id = update.effective_user.id
        zadacha_state[f"zadachi_group_{sent.message_id}"] = requester_id
        async def auto_del():
            await asyncio.sleep(60)
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=sent.message_id)
            except:
                pass
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=cmd_msg_id)
            except:
                pass
        asyncio.create_task(auto_del())
        return

    if not zadacha_tasks:
        await update.message.reply_text("📋 Faol vazifalar yoq.")
        return

    lines = ["📋 Vazifalar:\n"]
    keyboards = []

    for tid, task in zadacha_tasks.items():
        deadline_str = task["deadline"].strftime("%d.%m  ⏰ %H:%M")
        creator = task["creator"]
        is_creator = requester == task["creator_username"] or requester == ADMIN_USERNAME

        if requester == ADMIN_USERNAME:
            show_targets = task["targets"]
        else:
            show_targets = [u for u in task["targets"] if u == requester]
            if not show_targets and requester == task["creator_username"]:
                show_targets = task["targets"]
            supervisors_list = task.get("supervisor", [])
            if not show_targets and requester in supervisors_list:
                show_targets = task["targets"]

        for username in show_targets:
            name = AGENTS_DATA.get(username, {}).get("name", username)
            exec_accepted = username in task.get("accepted_executors", set())
            is_done = username in task.get("done", set())
            if is_done:
                status = "✅ Bajardi"
            elif username in task.get("cancelled", set()):
                status = "❌ Bekor"
            else:
                status = "⏳ Bajarilmadi"
            accepted = "✅ Qabul qildi" if exec_accepted else "⏳ Qabul qilmadi"
            text_short = task["text"][:50] + ("..." if len(task["text"]) > 50 else "")

            lines.append(
                f"━━━━━━━━━━━━━━\n"
                f"📌 №{tid} | {creator} → {name}\n"
                f"📝 <tg-spoiler>{text_short}</tg-spoiler>\n"
                f"📅 {deadline_str}\n"
                f"{accepted} | {status}"
            )

            row = []
            if is_creator:
                row.append(InlineKeyboardButton(f"✏️ №{tid}", callback_data=f"ztask_edit_{tid}"))
                row.append(InlineKeyboardButton(f"🗑 №{tid}", callback_data=f"ztask_delete_{tid}"))
            if username == requester and not is_done:
                keyboards.append(row) if row else None
                row = []
                row.append(InlineKeyboardButton(f"✅ Bajardim — №{tid}", callback_data=f"ztask_done_{tid}_{username}"))
            if row:
                keyboards.append(row)

    lines.append("━━━━━━━━━━━━━━")
    lines.append("\n⚠️ Bu xabar ⏱ 30 soniyadan keyin o'chadi")

    sent = await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboards) if keyboards else None,
        parse_mode="HTML"
    )
    try:
        await update.message.delete()
    except:
        pass
    schedule_delete(context.bot, update.effective_chat.id, [sent.message_id], delay=30)

# =========================
# DEADLINE JOBS
# =========================

async def zadacha_pre_deadline_job(context: ContextTypes.DEFAULT_TYPE):
    tid = context.job.data["task_id"]
    if tid not in zadacha_tasks:
        return
    task = zadacha_tasks[tid]
    deadline_str = task["deadline"].strftime("%d.%m soat %H:%M")
    supervisors = task.get("supervisor", [])
    sup_tags = " ".join(f"@{u}" for u in supervisors)
    for username in task["targets"]:
        if username in task.get("done", set()):
            continue
        keyboard = [
            [InlineKeyboardButton("✅ Ha, esimda", callback_data=f"zes_{tid}_{username}"),
             InlineKeyboardButton("✅ Bajardim", callback_data=f"zdone_{tid}_{username}")],
            [InlineKeyboardButton("❌ Bekor qilindi", callback_data=f"zcancel_{tid}_{username}")],
        ]
        sup_line = f"\n🧑 Nazorat: {sup_tags}" if sup_tags else ""
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"📌 @{username}, esingizda a?\n━━━━━━━━━━━━━━\n<tg-spoiler>{task['text']}</tg-spoiler>\nDeadline: 📅 {deadline_str}{sup_line}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

async def zadacha_deadline_job(context: ContextTypes.DEFAULT_TYPE):
    tid = context.job.data["task_id"]
    if tid not in zadacha_tasks:
        return
    task = zadacha_tasks[tid]
    deadline_str = task["deadline"].strftime("%d.%m soat %H:%M")
    not_done = [u for u in task["targets"] if u not in task.get("done", set())]
    if not not_done:
        return
    for username in not_done:
        name = AGENTS_DATA.get(username, {}).get("name", username)
        keyboard = [
            [InlineKeyboardButton("✅ Bajardim", callback_data=f"zdone_{tid}_{username}")],
            [InlineKeyboardButton("❌ Bekor qilindi", callback_data=f"zcancel_{tid}_{username}")],
            [
                InlineKeyboardButton("⏰ Yana 30 daqiqa", callback_data=f"zext_{tid}_{username}_30"),
                InlineKeyboardButton("⏰ Yana 1 soat", callback_data=f"zext_{tid}_{username}_60"),
                InlineKeyboardButton("⏰ Yana 2 soat", callback_data=f"zext_{tid}_{username}_120"),
            ],
        ]
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"📌 {name}, deadline tugadi.\n━━━━━━━━━━━━━━\n<tg-spoiler>{task['text']}</tg-spoiler>\nDeadline: 📅 {deadline_str}\n\n@{username} @{task['creator_username']}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

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
            "📋 CHECKLIST\n"
            "━━━━━━━━━━━━━━\n"
            "/checklist — Checklistni qo'lda yuborish\n"
            "/cheklistyaratish — Yangi checklist yaratish\n\n"
            "━━━━━━━━━━━━━━\n"
            "📌 VAZIFALAR\n"
            "━━━━━━━━━━━━━━\n"
            "/zadacha — Yangi vazifa yaratish\n"
            "/zadachi — Barcha vazifalarni ko'rish\n\n"
            "━━━━━━━━━━━━━━\n"
            "ℹ️ ESLATMA\n"
            "━━━━━━━━━━━━━━\n"
            "• Checklist har kuni 10:15 da avtomatik yuboriladi\n"
            "• Screenshot har 30 daqiqada so'raladi\n"
            "• Deadline o'tsa — bot avtomatik xabar yuboradi"
        )
        await context.bot.send_message(chat_id=user.id, text=guide_text)
        return

    # Xodimlar qo'llanmasi
    guide_text = (
        f"👋 Salom, {name}!\n\n"
        "━━━━━━━━━━━━━━\n"
        "📌 VAZIFALAR\n"
        "━━━━━━━━━━━━━━\n"
        "/zadacha — Yangi vazifa yaratish\n"
        "• Ijrochi tanlaysiz\n"
        "• Nazoratchi tanlaysiz\n"
        "• Vazifa matnini yozasiz\n"
        "• Deadline belgilaysiz\n\n"
        "/zadachi — Vazifalar ro'yxati\n"
        "• O'zingizga tegishli vazifalar\n"
        "• Bajardim tugmasi\n\n"
        "━━━━━━━━━━━━━━\n"
        "⚠️ ESLATMA\n"
        "━━━━━━━━━━━━━━\n"
        "Vazifa yaratish faqat\n"
        "shaxsiy xabar orqali ishlaydi!"
    )
    await context.bot.send_message(chat_id=user.id, text=guide_text)

async def umidstop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    state["stopped"] = True
    state["cycle_id"] += 1
    for t in CHECKLIST_TIMES:
        cancel_jobs_by_name(context.job_queue, f"checklist_{t}")
    await context.bot.send_message(chat_id=CHAT_ID, text="🛑 Bot toxtatildi.\nQayta ishga tushirish uchun /start bosing.")

async def custom_checklist_job(context: ContextTypes.DEFAULT_TYPE):
    cl_id = context.job.data["cl_id"]
    cl = next((c for c in custom_checklists if c["id"] == cl_id), None)
    if not cl:
        return

    username = cl["username"]
    supervisor = cl["supervisor"]
    tasks = cl["tasks"]
    now = datetime.now(TIMEZONE)
    date_str = f"{now.day} {MONTH_UZ[now.month]}, {WEEKDAY_UZ[now.weekday()]}, {now.strftime('%H:%M')}"
    name = AGENTS_DATA.get(username, {}).get("name", username)

    # Eski xabarni o'chir
    old_mid = custom_checklist_message_ids.get(cl_id)
    if old_mid:
        try:
            await context.bot.delete_message(chat_id=CHAT_ID, message_id=old_mid)
        except:
            pass

    # State reset
    custom_checklist_confirmations[cl_id] = {username: {}}
    custom_checklist_verified[cl_id] = set()
    custom_checklist_verify_state[cl_id] = {"verify_msg_id": None}

    task_lines = "\n".join(f"{i+1}. {t}" for i, t in enumerate(tasks))
    agent_info = get_agent_info(username)
    text = (
        f"📋 CHECKLIST — {date_str}\n\n"
        f"{agent_info}\n\n"
        "━━━━━━━━━━━━━━\n"
        f"📝 Vazifalar:\n<tg-spoiler>\n{task_lines}\n</tg-spoiler>\n"
        "━━━━━━━━━━━━━━\n\n"
        "⚠️ Avval o'qing, keyin bosing!\n"
        "Har bir vazifa bajarilgandan so'ng tugmani bosing"
    )

    keyboard = []
    for i, t in enumerate(tasks):
        keyboard.append([
            InlineKeyboardButton(f"⬜ {i+1} — Bajardim", callback_data=f"ccl_{cl_id}_{username}_{i}"),
            InlineKeyboardButton("⬜ Tekshirdim", callback_data=f"ccl_verify_{cl_id}_{i}")
        ])

    sent = await context.bot.send_message(chat_id=CHAT_ID, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    custom_checklist_message_ids[cl_id] = sent.message_id

    # last_sent yangilash
    cl["last_sent"] = now.isoformat()
    save_custom_checklists()

    # Keyingi schedule
    secs = seconds_until_custom_checklist(cl)
    context.job_queue.run_once(custom_checklist_job, when=secs, name=f"ccl_{cl_id}", data={"cl_id": cl_id})

async def cheklistyaratish_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    user_id = update.effective_user.id
    all_agents = list(AGENTS_DATA.keys())
    keyboard = [[InlineKeyboardButton(f"👤 {AGENTS_DATA[u]['name']}", callback_data=f"ccl_new_agent_{u}")] for u in all_agents]
    keyboard.append([InlineKeyboardButton("❌ Bekor", callback_data="ccl_new_cancel")])
    sent = await context.bot.send_message(
        chat_id=user_id,
        text="👷 Qaysi xodim uchun checklist?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    custom_checklist_state[user_id] = {"step": "agent", "messages": [sent.message_id]}
    if update.message:
        custom_checklist_state[user_id]["messages"].append(update.message.message_id)

async def cheklistyaratish_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()

    if data == "ccl_new_cancel":
        msgs = custom_checklist_state.pop(user_id, {}).get("messages", [])
        for mid in msgs:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=mid)
            except:
                pass
        sent = await context.bot.send_message(chat_id=user_id, text="❌ Bekor qilindi.")
        schedule_delete(context.bot, user_id, [sent.message_id])
        return

    if user_id not in custom_checklist_state:
        return
    s = custom_checklist_state[user_id]

    if data.startswith("ccl_new_agent_"):
        username = data[14:]
        s["username"] = username
        s["step"] = "repeat"
        keyboard = [
            [InlineKeyboardButton("📅 Har kuni", callback_data="ccl_new_repeat_daily")],
            [InlineKeyboardButton("📅 Kun ora", callback_data="ccl_new_repeat_interval")],
            [InlineKeyboardButton("📅 Haftada bir", callback_data="ccl_new_repeat_weekly")],
            [InlineKeyboardButton("❌ Bekor", callback_data="ccl_new_cancel")],
        ]
        sent = await context.bot.send_message(chat_id=user_id, text="🔄 Qanday takrorlansin?", reply_markup=InlineKeyboardMarkup(keyboard))
        s["messages"].append(sent.message_id)

    elif data == "ccl_new_repeat_daily":
        s["repeat"] = "daily"
        s["step"] = "hour"
        await _ccl_ask_hour(context, user_id, s)

    elif data == "ccl_new_repeat_interval":
        s["repeat"] = "interval"
        s["step"] = "interval_days"
        keyboard = [
            [InlineKeyboardButton("2 kun", callback_data="ccl_new_idays_2"), InlineKeyboardButton("5 kun", callback_data="ccl_new_idays_5")],
            [InlineKeyboardButton("10 kun", callback_data="ccl_new_idays_10"), InlineKeyboardButton("15 kun", callback_data="ccl_new_idays_15")],
            [InlineKeyboardButton("❌ Bekor", callback_data="ccl_new_cancel")],
        ]
        sent = await context.bot.send_message(chat_id=user_id, text="🔢 Necha kunda bir yuborilsin?", reply_markup=InlineKeyboardMarkup(keyboard))
        s["messages"].append(sent.message_id)

    elif data.startswith("ccl_new_idays_"):
        s["interval_days"] = int(data[14:])
        s["step"] = "hour"
        await _ccl_ask_hour(context, user_id, s)

    elif data == "ccl_new_repeat_weekly":
        s["repeat"] = "weekly"
        s["step"] = "weekday"
        keyboard = [[InlineKeyboardButton(label, callback_data=f"ccl_new_wd_{idx}")] for label, idx in WEEKDAY_BUTTONS]
        keyboard.append([InlineKeyboardButton("❌ Bekor", callback_data="ccl_new_cancel")])
        sent = await context.bot.send_message(chat_id=user_id, text="📅 Qaysi kuni yuborilsin?", reply_markup=InlineKeyboardMarkup(keyboard))
        s["messages"].append(sent.message_id)

    elif data.startswith("ccl_new_wd_"):
        s["weekday"] = int(data[11:])
        s["step"] = "hour"
        await _ccl_ask_hour(context, user_id, s)

    elif data.startswith("ccl_new_hour_"):
        s["hour"] = int(data[13:])
        s["step"] = "supervisor"
        # Nazoratchi tanlash — xodimdan boshqalar
        username = s["username"]
        sups = [u for u in AGENTS_DATA.keys() if u != username]
        keyboard = [[InlineKeyboardButton(f"👤 {AGENTS_DATA[u]['name']}", callback_data=f"ccl_new_sup_{u}")] for u in sups]
        keyboard.append([InlineKeyboardButton("❌ Bekor", callback_data="ccl_new_cancel")])
        sent = await context.bot.send_message(chat_id=user_id, text="🧑 Nazorat qiluvchi hodimni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
        s["messages"].append(sent.message_id)

    elif data.startswith("ccl_new_sup_"):
        s["supervisor"] = data[12:]
        s["step"] = "tasks"
        s["tasks"] = []
        sent = await context.bot.send_message(
            chat_id=user_id,
            text="✏️ 1-vazifani kiriting:",
        )
        s["messages"].append(sent.message_id)

    elif data == "ccl_new_task_done":
        if not s.get("tasks"):
            await query.answer("❌ Kamida 1 ta vazifa kiriting!", show_alert=True)
            return
        s["step"] = "confirm"
        await _ccl_show_confirm(context, user_id, s)

async def _ccl_ask_hour(context, user_id, s):
    hours = list(range(8, 24))
    keyboard = []
    row = []
    for h in hours:
        row.append(InlineKeyboardButton(f"⏰ {h:02d}:00", callback_data=f"ccl_new_hour_{h}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Bekor", callback_data="ccl_new_cancel")])
    sent = await context.bot.send_message(chat_id=user_id, text="🕐 Qaysi soatda yuborilsin?", reply_markup=InlineKeyboardMarkup(keyboard))
    s["messages"].append(sent.message_id)

async def _ccl_show_confirm(context, user_id, s):
    username = s["username"]
    supervisor = s["supervisor"]
    repeat = s["repeat"]
    hour = s["hour"]
    tasks = s["tasks"]
    name = AGENTS_DATA.get(username, {}).get("name", username)
    sup_name = AGENTS_DATA.get(supervisor, {}).get("name", supervisor)

    if repeat == "daily":
        repeat_str = "Har kuni"
    elif repeat == "interval":
        repeat_str = f"Har {s['interval_days']} kunda bir"
    else:
        repeat_str = f"Haftada bir — {WEEKDAY_UZ[s['weekday']]}"

    task_lines = "\n".join(f"{i+1}. {t}" for i, t in enumerate(tasks))
    text = (
        f"📋 Yangi checklist:\n\n"
        f"👤 Xodim: {name}\n"
        f"🧑 Nazoratchi: {sup_name}\n"
        f"🔄 Takrorlanish: {repeat_str}\n"
        f"🕐 Soat: {hour:02d}:00\n"
        f"📝 Vazifalar:\n{task_lines}\n\n"
        f"Yuborilsinmi?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data="ccl_new_confirm")],
        [InlineKeyboardButton("❌ Bekor", callback_data="ccl_new_cancel")],
    ]
    sent = await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    s["messages"].append(sent.message_id)

async def cheklistyaratish_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data != "ccl_new_confirm":
        return
    if user_id not in custom_checklist_state:
        return
    s = custom_checklist_state.pop(user_id)

    cl_id = get_next_cl_id()
    cl = {
        "id": cl_id,
        "username": s["username"],
        "supervisor": s["supervisor"],
        "repeat": s["repeat"],
        "hour": s["hour"],
        "tasks": s["tasks"],
        "last_sent": None,
    }
    if s["repeat"] == "interval":
        cl["interval_days"] = s["interval_days"]
    if s["repeat"] == "weekly":
        cl["weekday"] = s["weekday"]

    custom_checklists.append(cl)
    save_custom_checklists()

    # Schedule
    secs = seconds_until_custom_checklist(cl)
    context.job_queue.run_once(custom_checklist_job, when=secs, name=f"ccl_{cl_id}", data={"cl_id": cl_id})

    msgs = s.get("messages", [])
    for mid in msgs:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=mid)
        except:
            pass

    name = AGENTS_DATA.get(cl["username"], {}).get("name", cl["username"])
    sent = await context.bot.send_message(chat_id=user_id, text=f"✅ Checklist yaratildi!\n👤 {name}\n🕐 {cl['hour']:02d}:00")
    schedule_delete(context.bot, user_id, [sent.message_id], delay=30)

async def custom_checklist_text_handler(user_id, text, context):
    """Custom checklist task kiritish"""
    if user_id not in custom_checklist_state:
        return False
    s = custom_checklist_state[user_id]
    if s.get("step") != "tasks":
        return False

    s["tasks"].append(text)
    task_num = len(s["tasks"]) + 1
    keyboard = [[InlineKeyboardButton("✅ Tayyor", callback_data="ccl_new_task_done")]]
    sent = await context.bot.send_message(
        chat_id=user_id,
        text=f"✏️ {task_num}-vazifani kiriting:\n(Tugatish uchun \"Tayyor\" bosing)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    s["messages"].append(sent.message_id)
    return True

async def ccl_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Custom checklist Bajardim va Tekshirdim tugmalari"""
    query = update.callback_query
    data = query.data
    await query.answer()

    # BAJARDIM
    if data.startswith("ccl_") and not data.startswith("ccl_verify_") and not data.startswith("ccl_new_"):
        parts = data[4:].split("_")
        cl_id = int(parts[0])
        username = parts[1]
        task_index = int(parts[2])
        presser = query.from_user.username

        if presser != username:
            return

        cl = next((c for c in custom_checklists if c["id"] == cl_id), None)
        if not cl:
            return

        custom_checklist_confirmations.setdefault(cl_id, {}).setdefault(username, {})
        user_conf = custom_checklist_confirmations[cl_id][username]
        if user_conf.get(task_index, False):
            return
        user_conf[task_index] = True

        verified_set = custom_checklist_verified.get(cl_id, set())
        tasks = cl["tasks"]

        # Keyboard yangilash
        keyboard = []
        for i, t in enumerate(tasks):
            done = user_conf.get(i, False)
            verified = i in verified_set
            keyboard.append([
                InlineKeyboardButton(f"{'✅' if done else '⬜'} {i+1} — Bajardim", callback_data=f"ccl_{cl_id}_{username}_{i}"),
                InlineKeyboardButton(f"{'✅' if verified else '⬜'} Tekshirdim", callback_data=f"ccl_verify_{cl_id}_{i}")
            ])
        try:
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass

        # Barcha vazifalar bajariladimi?
        all_done = all(user_conf.get(i, False) for i in range(len(tasks)))
        if all_done:
            name = AGENTS_DATA.get(username, {}).get("name", username)
            vs = custom_checklist_verify_state.get(cl_id, {})
            old_vmid = vs.get("verify_msg_id")
            if old_vmid:
                try:
                    await context.bot.delete_message(chat_id=CHAT_ID, message_id=old_vmid)
                except:
                    pass
            sent_v = await context.bot.send_message(
                chat_id=CHAT_ID,
                text=f"✅ {name} barcha vazifalarni bajardi!\n@{ADMIN_USERNAME} checklistdan tekshiring"
            )
            custom_checklist_verify_state[cl_id] = {"verify_msg_id": sent_v.message_id}
        return

    # TEKSHIRDIM
    if data.startswith("ccl_verify_") and not data.startswith("ccl_verify_"):
        pass

    if data.startswith("ccl_verify_"):
        if query.from_user.username != ADMIN_USERNAME:
            return
        parts = data[11:].split("_")
        cl_id = int(parts[0])
        task_index = int(parts[1])

        cl = next((c for c in custom_checklists if c["id"] == cl_id), None)
        if not cl:
            return

        custom_checklist_verified.setdefault(cl_id, set()).add(task_index)
        verified_set = custom_checklist_verified[cl_id]
        tasks = cl["tasks"]
        username = cl["username"]
        user_conf = custom_checklist_confirmations.get(cl_id, {}).get(username, {})

        # Keyboard yangilash
        keyboard = []
        for i, t in enumerate(tasks):
            done = user_conf.get(i, False)
            verified = i in verified_set
            keyboard.append([
                InlineKeyboardButton(f"{'✅' if done else '⬜'} {i+1} — Bajardim", callback_data=f"ccl_{cl_id}_{username}_{i}"),
                InlineKeyboardButton(f"{'✅' if verified else '⬜'} Tekshirdim", callback_data=f"ccl_verify_{cl_id}_{i}")
            ])
        msg_id = custom_checklist_message_ids.get(cl_id)
        if msg_id:
            try:
                await context.bot.edit_message_reply_markup(chat_id=CHAT_ID, message_id=msg_id, reply_markup=InlineKeyboardMarkup(keyboard))
            except:
                pass

        # Barcha tekshirildimi?
        all_verified = all(i in verified_set for i in range(len(tasks)))
        if all_verified:
            vs = custom_checklist_verify_state.get(cl_id, {})
            vmid = vs.get("verify_msg_id")
            if vmid:
                async def del_v():
                    await asyncio.sleep(1)
                    try:
                        await context.bot.delete_message(chat_id=CHAT_ID, message_id=vmid)
                    except:
                        pass
                asyncio.create_task(del_v())
                custom_checklist_verify_state[cl_id]["verify_msg_id"] = None
        return

async def checklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    await send_checklist_now(update, context)

async def send_checklist_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_key = "10:15"
    active = CHECKLIST_AGENTS

    # Eski checklistni o'chir
    old_msg_id = state["checklist_message_ids"].get(time_key)
    if old_msg_id:
        try:
            await context.bot.delete_message(chat_id=CHAT_ID, message_id=old_msg_id)
        except:
            pass

    state["checklist_confirmations"][time_key] = {u: {} for u in active}
    state.setdefault("checklist_verified", {})[time_key] = set()
    for u in active:
        vkey = f"{time_key}_{u}"
        checklist_verify_state[vkey] = {"pending_items": [], "verify_msg_id": None}

    sent = await context.bot.send_message(
        chat_id=CHAT_ID,
        text=build_checklist_text(time_key, active),
        reply_markup=build_checklist_keyboard(time_key, active, state["checklist_confirmations"][time_key]),
        parse_mode="HTML"
    )
    state["checklist_message_ids"][time_key] = sent.message_id

    if update.effective_chat.id != CHAT_ID:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="✅ Checklist guruhga yuborildi."
        )

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

    # Kaiten -> kunlik statistika (10:00 va 20:00)
    for _hour, _label in [(10, "Ertalab"), (20, "Kechki")]:
        application.job_queue.run_once(
            _daily_stats_once,
            when=seconds_until_time(_hour, 0),
            name=f"kaiten_stats_{_hour}",
            data={"hour": _hour, "label": _label}
        )

    # ✅ CHECKLIST JOB — har kuni avtomatik ishlaydi
    for time_key in CHECKLIST_TIMES:
        h, m = map(int, time_key.split(":"))
        application.job_queue.run_once(
            checklist_job,
            when=seconds_until_time(h, m),
            name=f"checklist_{time_key}",
            data={"cycle_id": state["cycle_id"], "time_key": time_key}
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

    # Custom checklist jobs
    load_custom_checklists()
    for cl in custom_checklists:
        secs = seconds_until_custom_checklist(cl)
        application.job_queue.run_once(custom_checklist_job, when=secs, name=f"ccl_{cl['id']}", data={"cl_id": cl["id"]})

    application.add_handler(MessageHandler(filters.PHOTO & filters.Chat(CHAT_ID), photo_handler))
    application.add_handler(MessageHandler(filters.Document.IMAGE & filters.Chat(CHAT_ID), photo_handler))

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("umidstop", umidstop_command))
    application.add_handler(CommandHandler("checklist", checklist_command))
    application.add_handler(CommandHandler("cheklistyaratish", cheklistyaratish_command))
    application.add_handler(CommandHandler("addagent", addagent_command))
    application.add_handler(CommandHandler("editagent", editagent_command))
    application.add_handler(CommandHandler("delagent", delagent_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, universal_text_handler))

    application.add_handler(CallbackQueryHandler(addagent_callback, pattern="^(addday_|adddays_done|addconfirm_yes|add_cancel)"))
    application.add_handler(CallbackQueryHandler(editagent_callback, pattern="^(edit_)"))
    application.add_handler(CallbackQueryHandler(delagent_callback, pattern="^(delagent_)"))
    application.add_handler(CallbackQueryHandler(cheklistyaratish_callback, pattern="^ccl_new_"))
    application.add_handler(CallbackQueryHandler(cheklistyaratish_confirm_callback, pattern="^ccl_new_confirm$"))
    application.add_handler(CallbackQueryHandler(ccl_button_callback, pattern="^ccl_"))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot starting...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
