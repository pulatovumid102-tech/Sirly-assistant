# -*- coding: utf-8 -*-

import json
import logging
import os
from datetime import datetime, timedelta
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

# =========================
# TOKEN
# =========================

TOKEN = "8616037861:AAEpNThIHz2x4KTpMZcTQjCoJa2Hcnf_I0Q"

# =========================
# GROUP CHAT ID
# =========================

CHAT_ID = -5247953376

# =========================
# LOGGING
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# =========================
# TIMEZONE
# =========================

TIMEZONE = ZoneInfo("Asia/Tashkent")

# =========================
# ADMIN
# =========================

ADMIN_USERNAME = "umidpulatov"

NOTIFY_TAGS = "@umidpulatov @kh_nosirov"

# =========================
# AGENTS FILE
# =========================

AGENTS_FILE = "agents.json"

def load_agents():
    default = {
        "sirlyinfo": {
            "name": "Ozodbek",
            "username": "sirlyinfo",
            "phone": "+998 93 798 13 04",
            "work_days": [0, 1, 2, 3, 4, 6],
            "work_hours": {
                "0": [10, 20], "1": [10, 20], "2": [10, 20],
                "3": [10, 20], "4": [10, 20],
                "6": [10, 24],
            },
        },
        "shahnoza": {
            "name": "Shahnoзabonu",
            "username": "shahnoza",
            "phone": "+998 91 016 77 47",
            "work_days": [0, 1, 2, 3, 4, 5],
            "work_hours": {
                "0": [14, 24], "1": [14, 24], "2": [14, 24],
                "3": [14, 24], "4": [14, 24], "5": [14, 24],
            },
        },
    }
    if not os.path.exists(AGENTS_FILE):
        save_agents(default)
        return default
    try:
        with open(AGENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure both default agents exist (add if missing)
        changed = False
        for key, val in default.items():
            if key not in data:
                data[key] = val
                changed = True
        if changed:
            save_agents(data)
        return data
    except Exception as e:
        logger.error(f"load_agents error: {e}")
        return default

def save_agents(agents_data):
    with open(AGENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(agents_data, f, ensure_ascii=False, indent=2)

# Global agents dict (loaded at startup)
AGENTS_DATA = load_agents()

def get_agent_order():
    return list(AGENTS_DATA.keys())

def get_agents():
    return {u: d["name"] for u, d in AGENTS_DATA.items()}

def get_agent_info(username):
    d = AGENTS_DATA.get(username, {})
    name = d.get("name", username)
    phone = d.get("phone", "")
    return f"👨🏻‍💻 {name} @{username}\n📞 {phone}"

# =========================
# CHECKLIST CONFIG
# =========================

CHECKLIST_CONFIG = {
    "10:00": [
        "Admin panel (support) tozalandi",
        "Muammoli mijozlar jadvali to'liq tekshirildi",
        "Umid akaga checklist skrinshoti yuborildi",
        "Olib ketilmagan statusini tekshirildi",
    ],
    "14:00": [
        "Muammoli mijozlar jadvali to'liq tekshirildi",
        "Sotuv tablitsasi to'ldirildi",
        "Umid akaga checklist skrinshoti yuborildi",
    ],
    "18:00": [
        "Muammoli mijozlar jadvali to'liq tekshirildi",
        "Sirly bug va task guruhidagi barcha bug hamda tasklar jadvalga kiritildi",
        "Umid akaga checklist skrinshoti yuborildi",
    ],
    "23:00": [
        "Bugalteriya jadvali to'ldirildi",
        "Bugalteriya kunlik holati hamkorlar telegram guruhlariga yuborildi",
        "Support va telegramdagi murojaatlar qolib ketmadi",
        "Checklist to'liq tekshirildi",
        "To'liq tekshirilgani haqida Sirly STAFF ga xabar yuborildi? Umid akani tag qilib",
    ],
}

CHECKLIST_TIMES = list(CHECKLIST_CONFIG.keys())

# =========================
# NEXT TIME HELPERS
# =========================

def get_next_checklist_time(current_time_key):
    times = CHECKLIST_TIMES
    if current_time_key in times:
        idx = times.index(current_time_key)
        if idx + 1 < len(times):
            return times[idx + 1]
    return None

def get_next_reminder_time():
    now = datetime.now(TIMEZONE)
    next_q_total = ((now.minute // 30) + 1) * 30
    next_q_hour = (now.hour + next_q_total // 60) % 24
    next_q_min = next_q_total % 60
    return f"{next_q_hour:02d}:{next_q_min:02d}"

# =========================
# STATE
# =========================

state = {
    "confirmations": {},
    "reminder_message_id": None,
    "reminder_sent_at": None,
    "reminder_log_message_id": None,
    "reminder_log_lines": [],

    "checklist_confirmations": {},
    "checklist_message_ids": {},
    "checklist_log_message_ids": {},
    "checklist_log_lines": {},

    "cycle_id": 0,
    "stopped": False,
    "reminder_stopped": True,  # Default o'chiq
}

# =========================
# WEEKDAY / MONTH
# =========================

WEEKDAY_UZ = {
    0: "Dushanba",
    1: "Seshanba",
    2: "Chorshanba",
    3: "Payshanba",
    4: "Juma",
    5: "Shanba",
    6: "Yakshanba",
}

WEEKDAY_SHORT = {
    "Dush": 0, "Sesh": 1, "Chor": 2, "Pay": 3,
    "Juma": 4, "Shan": 5, "Yak": 6,
}

MONTH_UZ = {
    1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel",
    5: "may", 6: "iyun", 7: "iyul", 8: "avgust",
    9: "sentyabr", 10: "oktyabr", 11: "noyabr", 12: "dekabr",
}

# =========================
# ACTIVE AGENTS
# =========================

def get_active_agents():
    now = datetime.now(TIMEZONE)
    weekday = now.weekday()
    hour = now.hour
    active = set()
    for username, data in AGENTS_DATA.items():
        work_days = data.get("work_days", [])
        work_hours = data.get("work_hours", {})
        if weekday in work_days:
            wh = work_hours.get(str(weekday), work_hours.get("default", [0, 24]))
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
            wh = work_hours.get(str(weekday), work_hours.get("default", [0, 24]))
            if wh[0] <= hour <= wh[1]:
                active.add(username)
    return active

# =========================
# BUILD REMINDER KEYBOARD
# =========================

def build_reminder_keyboard(active_agents, confirmations):
    keyboard = []
    for username in get_agent_order():
        if username not in active_agents:
            continue
        name = AGENTS_DATA[username]["name"]
        conf = confirmations.get(username, {"mijoz": False, "hamkor": False})
        keyboard.append([InlineKeyboardButton(
            f"{'✅' if conf['mijoz'] else '⬜'} {name} - Mijozlar tekshirildi",
            callback_data=f"confirm_{username}_mijoz"
        )])
        keyboard.append([InlineKeyboardButton(
            f"{'✅' if conf['hamkor'] else '⬜'} {name} - Hamkorlar tekshirildi",
            callback_data=f"confirm_{username}_hamkor"
        )])
    return InlineKeyboardMarkup(keyboard)

# =========================
# BUILD CHECKLIST KEYBOARD
# =========================

def build_checklist_keyboard(time_key, active_agents, checklist_confs):
    keyboard = []
    tasks = CHECKLIST_CONFIG.get(time_key, [])
    for username in get_agent_order():
        if username not in active_agents:
            continue
        name = AGENTS_DATA[username]["name"]
        user_conf = checklist_confs.get(username, {})
        for i, task in enumerate(tasks):
            done = user_conf.get(i, False)
            icon = "✅" if done else "⬜"
            short_task = task if len(task) <= 30 else task[:30] + "..."
            keyboard.append([InlineKeyboardButton(
                f"{icon} {name} — {short_task}",
                callback_data=f"chk_{time_key.replace(':', '')}_{username}_{i}"
            )])
    return InlineKeyboardMarkup(keyboard)

# =========================
# BUILD TEXTS
# =========================

def build_checklist_text(time_key, active_agents):
    tasks = CHECKLIST_CONFIG.get(time_key, [])
    task_lines = "\n".join(f"{i+1}. {task} ☑️" for i, task in enumerate(tasks))
    agent_block = "\n\n".join(
        get_agent_info(u) for u in get_agent_order() if u in active_agents
    )
    return (
        f"📋 CHECKLIST — {time_key}\n\n"
        f"{task_lines}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"{agent_block}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "⚠️ O'qimasdan turib bosmang\n"
        "Pastdagi tugmalarni bosish orqali vazifa bajarilganini tasdiqlang"
    )

def build_reminder_text(active_agents):
    agent_block = "\n\n".join(
        get_agent_info(u) for u in get_agent_order() if u in active_agents
    )
    return (
        f"{agent_block}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "💬 Mijozlardan kelgan murojaatlar tekshirildimi? ☑️\n\n"
        "🤝 Hamkorlardan kelgan murojaatlar tekshirildimi? ☑️\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "⚠️ O'qimasdan turib bosmang\n"
        "Pastdagi tugmalarni bosish orqali vazifa bajarilganini tasdiqlang"
    )

# =========================
# CHECK FUNCTIONS
# =========================

def all_confirmed(active_agents, confirmations):
    for username in active_agents:
        conf = confirmations.get(username, {})
        if not conf.get("mijoz") or not conf.get("hamkor"):
            return False
    return True

def checklist_all_confirmed(time_key, active_agents, checklist_confs):
    tasks = CHECKLIST_CONFIG.get(time_key, [])
    for username in active_agents:
        user_conf = checklist_confs.get(username, {})
        for i in range(len(tasks)):
            if not user_conf.get(i, False):
                return False
    return True

# =========================
# JOB HELPERS
# =========================

def cancel_jobs_by_name(job_queue, name):
    for job in job_queue.get_jobs_by_name(name):
        job.schedule_removal()

def seconds_until_next_30():
    now = datetime.now(TIMEZONE)
    elapsed = now.minute * 60 + now.second + now.microsecond / 1_000_000
    next_30 = ((now.minute // 30) + 1) * 30 * 60
    return max(next_30 - elapsed, 1.0)

def seconds_until_time(hour, minute):
    now = datetime.now(TIMEZONE)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()

# =========================
# SEND REMINDER
# =========================

async def send_reminder(bot, cycle_id):
    if state.get("reminder_stopped"):
        return
    active = get_active_agents()
    if not active:
        return

    if state.get("reminder_log_message_id"):
        try:
            await bot.delete_message(chat_id=CHAT_ID, message_id=state["reminder_log_message_id"])
        except:
            pass
    if state.get("reminder_message_id"):
        try:
            await bot.delete_message(chat_id=CHAT_ID, message_id=state["reminder_message_id"])
        except:
            pass

    state["confirmations"] = {
        username: {"mijoz": False, "hamkor": False} for username in active
    }
    state["reminder_message_id"] = None
    state["reminder_sent_at"] = datetime.now(TIMEZONE)
    state["reminder_log_message_id"] = None
    state["reminder_log_lines"] = []

    text = build_reminder_text(active)
    keyboard = build_reminder_keyboard(active, state["confirmations"])
    sent = await bot.send_message(chat_id=CHAT_ID, text=text, reply_markup=keyboard)
    state["reminder_message_id"] = sent.message_id

# =========================
# SEND CHECKLIST
# =========================

async def send_checklist(bot, time_key):
    active = get_active_agents_for_time(time_key)
    if not active:
        return

    if state["checklist_log_message_ids"].get(time_key):
        try:
            await bot.delete_message(chat_id=CHAT_ID, message_id=state["checklist_log_message_ids"][time_key])
        except:
            pass
        state["checklist_log_message_ids"][time_key] = None
    if state["checklist_message_ids"].get(time_key):
        try:
            await bot.delete_message(chat_id=CHAT_ID, message_id=state["checklist_message_ids"][time_key])
        except:
            pass
        state["checklist_message_ids"][time_key] = None

    state["checklist_confirmations"][time_key] = {username: {} for username in active}
    state["checklist_log_lines"][time_key] = []

    text = build_checklist_text(time_key, active)
    keyboard = build_checklist_keyboard(time_key, active, state["checklist_confirmations"][time_key])
    sent = await bot.send_message(chat_id=CHAT_ID, text=text, reply_markup=keyboard)
    state["checklist_message_ids"][time_key] = sent.message_id

# =========================
# REMINDER JOB
# =========================

async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    cycle_id = context.job.data["cycle_id"]
    if cycle_id != state["cycle_id"] or state["stopped"]:
        return
    await send_reminder(context.bot, cycle_id)
    cancel_jobs_by_name(context.job_queue, "reminder")
    context.job_queue.run_once(
        reminder_job,
        when=seconds_until_next_30(),
        name="reminder",
        data={"cycle_id": cycle_id},
    )

# =========================
# CHECKLIST JOB
# =========================

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
        data={"cycle_id": cycle_id, "time_key": time_key},
    )

# =========================
# CALLBACKS (reminder + checklist)
# =========================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer("✅ Tasdiqlandi!")

    now = datetime.now(TIMEZONE)
    time_str = now.strftime("%H:%M")

    # --- TEST CHECKLIST ---
    if data.startswith("test_chk_"):
        time_key = data[9:]
        active = get_active_agents_for_time(time_key) or set(get_agent_order())
        state["checklist_confirmations"][time_key] = {username: {} for username in active}
        text = build_checklist_text(time_key, active)
        keyboard = build_checklist_keyboard(time_key, active, state["checklist_confirmations"][time_key])
        sent = await context.bot.send_message(chat_id=CHAT_ID, text=text, reply_markup=keyboard)
        state["checklist_message_ids"][time_key] = sent.message_id
        return

    # --- REMINDER BUTTONS ---
    if data.startswith("confirm_"):
        without_prefix = data[8:]
        confirm_type = without_prefix.split("_")[-1]
        username = without_prefix[:-(len(confirm_type) + 1)]

        presser = query.from_user.username
        if presser != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return

        active = set(state["confirmations"].keys()) or get_active_agents()
        if username not in active:
            return
        if username not in state["confirmations"]:
            state["confirmations"][username] = {"mijoz": False, "hamkor": False}
        if state["confirmations"][username][confirm_type]:
            return

        state["confirmations"][username][confirm_type] = True
        keyboard = build_reminder_keyboard(active, state["confirmations"])
        try:
            await query.message.edit_reply_markup(reply_markup=keyboard)
        except:
            pass

        action_text = (
            "Javob berilmagan mijoz qolmadi" if confirm_type == "mijoz"
            else "Javob berilmagan hamkor qolmadi"
        )
        new_line = f"{AGENTS_DATA[username]['name']} {time_str} | {action_text} ✅"
        state["reminder_log_lines"].append(new_line)
        log_text = "\n".join(state["reminder_log_lines"]) + f"\n{NOTIFY_TAGS}"

        if state["reminder_log_message_id"]:
            try:
                await context.bot.delete_message(chat_id=CHAT_ID, message_id=state["reminder_log_message_id"])
            except:
                pass

        if all_confirmed(active, state["confirmations"]):
            log_text += f"\n\n🕐 Keyingi tekshiruv: {get_next_reminder_time()}"
            sent = await context.bot.send_message(chat_id=CHAT_ID, text=log_text)
            state["reminder_log_message_id"] = sent.message_id
            state["reminder_log_lines"] = []
            if state["reminder_message_id"]:
                try:
                    await context.bot.delete_message(chat_id=CHAT_ID, message_id=state["reminder_message_id"])
                except:
                    pass
        else:
            sent = await context.bot.send_message(chat_id=CHAT_ID, text=log_text)
            state["reminder_log_message_id"] = sent.message_id
        return

    # --- CHECKLIST BUTTONS ---
    if data.startswith("chk_"):
        without_prefix = data[4:]
        first_underscore = without_prefix.index("_")
        time_raw = without_prefix[:first_underscore]
        rest = without_prefix[first_underscore + 1:]
        last_underscore = rest.rindex("_")
        username = rest[:last_underscore]
        task_index = int(rest[last_underscore + 1:])
        time_key = f"{time_raw[:2]}:{time_raw[2:]}"

        presser = query.from_user.username
        if presser != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return

        if time_key in state["checklist_confirmations"] and state["checklist_confirmations"][time_key]:
            active = set(state["checklist_confirmations"][time_key].keys())
        else:
            active = get_active_agents_for_time(time_key)

        if username not in active:
            return
        if time_key not in state["checklist_confirmations"]:
            state["checklist_confirmations"][time_key] = {}
        if username not in state["checklist_confirmations"][time_key]:
            state["checklist_confirmations"][time_key][username] = {}

        user_conf = state["checklist_confirmations"][time_key][username]
        if user_conf.get(task_index, False):
            return
        user_conf[task_index] = True

        keyboard = build_checklist_keyboard(time_key, active, state["checklist_confirmations"][time_key])
        try:
            await query.message.edit_reply_markup(reply_markup=keyboard)
        except:
            pass

        tasks = CHECKLIST_CONFIG.get(time_key, [])
        task_text = tasks[task_index] if task_index < len(tasks) else str(task_index)
        new_line = f"{AGENTS_DATA[username]['name']} {time_str} | {task_text} ni bajardi ✅"

        if time_key not in state["checklist_log_lines"]:
            state["checklist_log_lines"][time_key] = []
        state["checklist_log_lines"][time_key].append(new_line)
        log_text = "\n".join(state["checklist_log_lines"][time_key]) + f"\n{NOTIFY_TAGS}"

        if state["checklist_log_message_ids"].get(time_key):
            try:
                await context.bot.delete_message(chat_id=CHAT_ID, message_id=state["checklist_log_message_ids"][time_key])
            except:
                pass

        if checklist_all_confirmed(time_key, active, state["checklist_confirmations"][time_key]):
            next_t = get_next_checklist_time(time_key)
            log_text += f"\n✅ {time_key} checklist yakunlandi."
            if next_t:
                log_text += f" 🕐 Keyingi tekshiruv: {next_t}"
            sent = await context.bot.send_message(chat_id=CHAT_ID, text=log_text)
            state["checklist_log_message_ids"][time_key] = sent.message_id
            state["checklist_log_lines"][time_key] = []
            if state["checklist_message_ids"].get(time_key):
                try:
                    await context.bot.delete_message(chat_id=CHAT_ID, message_id=state["checklist_message_ids"][time_key])
                except:
                    pass
        else:
            sent = await context.bot.send_message(chat_id=CHAT_ID, text=log_text)
            state["checklist_log_message_ids"][time_key] = sent.message_id
        return

# =========================
# ADDAGENT STATE
# =========================

addagent_state = {}
editagent_state = {}

WEEKDAY_BUTTONS = [
    ("Dush (Du)", 0), ("Sesh (Se)", 1), ("Chor (Ch)", 2),
    ("Pay (Pa)", 3), ("Juma (Ju)", 4), ("Shanba (Sh)", 5), ("Yakshanba (Ya)", 6),
]

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
# ADDAGENT COMMAND
# =========================

async def addagent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    user_id = update.effective_user.id
    addagent_state[user_id] = {"step": "username", "messages": []}
    sent = await context.bot.send_message(
        chat_id=user_id,
        text="➕ Yangi hodim qo'shish\n\n1️⃣ Username kiriting (@siz formatida yoki username):"
    )
    addagent_state[user_id]["messages"].append(sent.message_id)

async def addagent_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    user_id = update.effective_user.id
    if user_id not in addagent_state:
        return

    s = addagent_state[user_id]
    step = s.get("step")
    text = update.message.text.strip().lstrip("@")

    if step == "username":
        s["username"] = text
        s["step"] = "name"
        sent = await update.message.reply_text("2. Ismini kiriting (masalan: Ozodbek):")
        s["messages"].append(sent.message_id)

    elif step == "name":
        s["name"] = text
        s["step"] = "phone"
        sent = await update.message.reply_text("3. Telefon raqamini kiriting (masalan: +998 93 798 13 04):")
        s["messages"].append(sent.message_id)

    elif step == "phone":
        s["phone"] = text
        s["step"] = "days"
        s["selected_days"] = []
        sent = await update.message.reply_text(
            "4. Ish kunlarini tanlang:",
            reply_markup=build_days_keyboard(s["selected_days"], prefix="add")
        )
        s["messages"].append(sent.message_id)

    elif step == "start_hour":
        try:
            h = int(text.replace(":", "").strip())
            if ":" in text:
                h = int(text.split(":")[0])
            s["start_hour"] = h
            s["step"] = "end_hour"
            sent = await update.message.reply_text("6. Ish tugash vaqtini kiriting (masalan: 20, yoki 24 = 23:59):")
            s["messages"].append(sent.message_id)
        except:
            sent = await update.message.reply_text("❌ Notogri format. Qayta kiriting (masalan: 10):")
            s["messages"].append(sent.message_id)

    elif step == "end_hour":
        try:
            h = int(text.replace(":", "").strip())
            if ":" in text:
                parts = text.split(":")
                h = int(parts[0])
                if parts[1] in ["59", "45", "30"]:
                    h += 1
            s["end_hour"] = h
            s["step"] = "confirm"

            days_str = ", ".join(WEEKDAY_UZ[d] for d in sorted(s["selected_days"]))
            sent = await update.message.reply_text(
                f"📋 Yangi hodim ma'lumotlari:\n\n"
                f"👤 Username: @{s['username']}\n"
                f"📛 Ismi: {s['name']}\n"
                f"📞 Telefon: {s['phone']}\n"
                f"📅 Ish kunlari: {days_str}\n"
                f"🕐 Ish vaqti: {s['start_hour']:02d}:00 — {s['end_hour']:02d}:00\n\n"
                f"Tasdiqlaysizmi?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Tasdiqlash", callback_data="addconfirm_yes")],
                    [InlineKeyboardButton("❌ Bekor", callback_data="add_cancel")],
                ])
            )
            s["messages"].append(sent.message_id)
        except:
            sent = await update.message.reply_text("❌ Notogri format. Qayta kiriting (masalan: 20):")
            s["messages"].append(sent.message_id)

async def addagent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()

    if data == "add_cancel":
        addagent_state.pop(user_id, None)
        await context.bot.send_message(chat_id=user_id, text="❌ Bekor qilindi.")
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
            await query.message.edit_reply_markup(
                reply_markup=build_days_keyboard(s["selected_days"], prefix="add")
            )
        except:
            pass

    elif data == "adddays_done":
        if not s["selected_days"]:
            await query.answer("❌ Kamida 1 kun tanlang!", show_alert=True)
            return
        s["step"] = "start_hour"
        sent = await context.bot.send_message(
            chat_id=user_id,
            text="5. Ish boshlash vaqtini kiriting (masalan: 10):"
        )
        s["messages"].append(sent.message_id)

    elif data == "addconfirm_yes":
        username = s["username"]
        work_hours = {}
        for d in s["selected_days"]:
            work_hours[str(d)] = [s["start_hour"], s["end_hour"]]

        AGENTS_DATA[username] = {
            "name": s["name"],
            "username": username,
            "phone": s["phone"],
            "work_days": sorted(s["selected_days"]),
            "work_hours": work_hours,
        }
        save_agents(AGENTS_DATA)
        addagent_state.pop(user_id, None)

        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ {s['name']} (@{username}) muvaffaqiyatli qoshildi!"
        )
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"👤 Yangi hodim qoshildi: {s['name']} (@{username})\n📞 {s['phone']}"
        )

# =========================
# EDITAGENT COMMAND
# =========================

async def editagent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    user_id = update.effective_user.id

    if not AGENTS_DATA:
        await context.bot.send_message(chat_id=user_id, text="❌ Hodimlar royxati bosh.")
        return

    keyboard = [
        [InlineKeyboardButton(f"👤 {d['name']} (@{u})", callback_data=f"edit_select_{u}")]
        for u, d in AGENTS_DATA.items()
    ]
    keyboard.append([InlineKeyboardButton("❌ Bekor", callback_data="edit_cancel")])

    sent = await context.bot.send_message(
        chat_id=user_id,
        text="✏️ Qaysi hodimni tahrirlaysiz?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    editagent_state[user_id] = {"messages": [sent.message_id]}

async def editagent_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    user_id = update.effective_user.id
    if user_id not in editagent_state:
        return

    s = editagent_state[user_id]
    step = s.get("step")
    text = update.message.text.strip()

    if step == "name":
        s["new_name"] = text
        AGENTS_DATA[s["username"]]["name"] = text
        save_agents(AGENTS_DATA)
        editagent_state.pop(user_id, None)
        await update.message.reply_text(f"✅ Ismi '{text}' ga ozgartirildi.")

    elif step == "username_edit":
        new_username = text.lstrip("@").strip()
        old_username = s["username"]
        # Rename key in AGENTS_DATA
        agent_data = AGENTS_DATA.pop(old_username)
        agent_data["username"] = new_username
        AGENTS_DATA[new_username] = agent_data
        save_agents(AGENTS_DATA)
        editagent_state.pop(user_id, None)
        await update.message.reply_text(f"✅ Username '@{old_username}' => '@{new_username}' ga ozgartirildi.")

    elif step == "phone":
        AGENTS_DATA[s["username"]]["phone"] = text
        save_agents(AGENTS_DATA)
        editagent_state.pop(user_id, None)
        await update.message.reply_text(f"✅ Telefon '{text}' ga ozgartirildi.")

    elif step == "start_hour":
        try:
            h = int(text.split(":")[0]) if ":" in text else int(text)
            s["start_hour"] = h
            s["step"] = "end_hour"
            sent = await update.message.reply_text("Yangi tugash vaqtini kiriting (masalan: 20):")
            s["messages"].append(sent.message_id)
        except:
            await update.message.reply_text("❌ Notogri format.")

    elif step == "end_hour":
        try:
            h = int(text.split(":")[0]) if ":" in text else int(text)
            username = s["username"]
            for d in AGENTS_DATA[username]["work_days"]:
                AGENTS_DATA[username]["work_hours"][str(d)] = [s["start_hour"], h]
            save_agents(AGENTS_DATA)
            editagent_state.pop(user_id, None)
            await update.message.reply_text(f"✅ Ish vaqti {s['start_hour']:02d}:00 — {h:02d}:00 ga ozgartirildi.")
        except:
            await update.message.reply_text("❌ Notogri format.")

async def editagent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()

    if data == "edit_cancel":
        editagent_state.pop(user_id, None)
        await context.bot.send_message(chat_id=user_id, text="❌ Bekor qilindi.")
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
            [InlineKeyboardButton("❌ Bekor", callback_data="edit_cancel")],
        ]

        sent = await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"👤 {d['name']} (@{username})\n"
                f"📞 {d['phone']}\n"
                f"📅 {days_str}\n\n"
                f"Nimani ozgartirmoqchisiz?"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
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
        sent = await context.bot.send_message(
            chat_id=user_id,
            text="Yangi ish kunlarini tanlang:",
            reply_markup=build_days_keyboard(s["selected_days"], prefix="editday_")
        )
        s["messages"].append(sent.message_id)

    elif data == "edit_field_hours":
        s["step"] = "start_hour"
        sent = await context.bot.send_message(chat_id=user_id, text="Yangi boshlash vaqtini kiriting (masalan: 10):")
        s["messages"].append(sent.message_id)

    elif data.startswith("editday__"):
        day_idx = int(data[9:])
        if day_idx in s["selected_days"]:
            s["selected_days"].remove(day_idx)
        else:
            s["selected_days"].append(day_idx)
        try:
            await query.message.edit_reply_markup(
                reply_markup=build_days_keyboard(s["selected_days"], prefix="editday_")
            )
        except:
            pass

    elif data == "editday_days_done":
        username = s["username"]
        AGENTS_DATA[username]["work_days"] = sorted(s["selected_days"])
        new_hours = {}
        for d in s["selected_days"]:
            old = AGENTS_DATA[username]["work_hours"].get(str(d), [10, 20])
            new_hours[str(d)] = old
        AGENTS_DATA[username]["work_hours"] = new_hours
        save_agents(AGENTS_DATA)
        editagent_state.pop(user_id, None)
        days_str = ", ".join(WEEKDAY_UZ[d] for d in sorted(s["selected_days"]))
        await context.bot.send_message(chat_id=user_id, text=f"✅ Ish kunlari yangilandi: {days_str}")

# =========================
# DELAGENT COMMAND
# =========================

async def delagent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return

    user_id2 = update.effective_user.id
    if not AGENTS_DATA:
        await context.bot.send_message(chat_id=user_id2, text="❌ Hodimlar royxati bosh.")
        return

    keyboard = [
        [InlineKeyboardButton(f"🗑 {d['name']} (@{u})", callback_data=f"delagent_{u}")]
        for u, d in AGENTS_DATA.items()
    ]
    keyboard.append([InlineKeyboardButton("❌ Bekor", callback_data="delagent_cancel")])

    await context.bot.send_message(
        chat_id=user_id2,
        text="🗑 Qaysi hodimni ochirmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def delagent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "delagent_cancel":
        await query.message.edit_text("❌ Bekor qilindi.")
        return

    if data.startswith("delagent_confirm_"):
        username = data[17:]
        if username in AGENTS_DATA:
            name = AGENTS_DATA[username]["name"]
            del AGENTS_DATA[username]
            save_agents(AGENTS_DATA)
            await query.message.edit_text(f"✅ {name} (@{username}) ochirildi.")
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
        await query.message.edit_text(
            f"⚠️ {name} (@{username}) ni ochirishni tasdiqlaysizmi?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# =========================
# START COMMAND
# =========================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return

    active = get_active_agents()
    now = datetime.now(TIMEZONE)

    if not active:
        weekday_name = WEEKDAY_UZ[now.weekday()]
        date_str = f"{weekday_name}, {now.day}-{MONTH_UZ[now.month]} {now.year}"
        time_str = now.strftime("%H:%M")

        lines = [
            "🌙 Hozir support ish vaqti emas.\n",
            f"📅 Bugun: {date_str}",
            f"🕐 Hozirgi vaqt: {time_str}\n",
            "──────────────",
        ]

        for username, data in AGENTS_DATA.items():
            weekday = now.weekday()
            if weekday in data["work_days"]:
                wh = data["work_hours"].get(str(weekday), [10, 20])
                lines.append(
                    f"\n{get_agent_info(username)}\n"
                    f"🕐 Bugun ish vaqti: {wh[0]:02d}:00 — {wh[1]:02d}:00"
                )
            else:
                lines.append(f"\n{get_agent_info(username)}\n😴 Bugun dam oladi")
            lines.append("\n──────────────")

        await context.bot.send_message(chat_id=CHAT_ID, text="\n".join(lines))
        return

    state["stopped"] = False
    state["cycle_id"] += 1

    cancel_jobs_by_name(context.job_queue, "reminder")
    for t in CHECKLIST_TIMES:
        cancel_jobs_by_name(context.job_queue, f"checklist_{t}")

    next_q_total = ((now.minute // 30) + 1) * 30
    next_q_hour = (now.hour + next_q_total // 60) % 24
    next_q_min = next_q_total % 60

    context.job_queue.run_once(
        reminder_job,
        when=seconds_until_next_30(),
        name="reminder",
        data={"cycle_id": state["cycle_id"]},
    )

    for time_key in CHECKLIST_TIMES:
        hour, minute = map(int, time_key.split(":"))
        context.job_queue.run_once(
            checklist_job,
            when=seconds_until_time(hour, minute),
            name=f"checklist_{time_key}",
            data={"cycle_id": state["cycle_id"], "time_key": time_key},
        )

    active_text = "\n".join(f"🟢 {AGENTS_DATA[u]['name']}" for u in get_agent_order() if u in active)

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "✅ Bot ishga tushdi\n\n"
            f"👨🏻‍💻 Aktiv supportlar:\n{active_text}\n\n"
            "📋 Cheklistlar: ✅ Yoqiq\n"
            f"🔔 Reminder: {'ON' if not state['reminder_stopped'] else 'OFF'}\n\n"
            f"⏰ Birinchi reminder (agar yoqiq bo'lsa): {next_q_hour:02d}:{next_q_min:02d}"
        ),
    )

# =========================
# STOP COMMAND
# =========================

async def umidstop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return

    state["stopped"] = True
    state["cycle_id"] += 1

    cancel_jobs_by_name(context.job_queue, "reminder")
    for t in CHECKLIST_TIMES:
        cancel_jobs_by_name(context.job_queue, f"checklist_{t}")

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "🛑 Bot toxtatildi.\n\n"
            "Eslatmalar va vazifalar yuborilmaydi.\n\n"
            "Qayta ishga tushirish uchun /start bosing."
        ),
    )

# =========================
# REMINDER START / STOP
# =========================

async def reminder_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    state["reminder_stopped"] = False
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=f"▶️ Reminder yoqildi.\n⏰ Keyingi eslatma: {get_next_reminder_time()}"
    )

async def reminder_stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    state["reminder_stopped"] = True
    if state.get("reminder_message_id"):
        try:
            await context.bot.delete_message(chat_id=CHAT_ID, message_id=state["reminder_message_id"])
        except:
            pass
        state["reminder_message_id"] = None
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text="⏸ Reminder to'xtatildi.\nQayta yoqish uchun /reminder_start bosing."
    )

# =========================
# TEST COMMANDS
# =========================

async def test_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    active = get_active_agents() or set(get_agent_order())
    state["confirmations"] = {
        username: {"mijoz": False, "hamkor": False} for username in active
    }
    text = build_reminder_text(active)
    keyboard = build_reminder_keyboard(active, state["confirmations"])
    await context.bot.send_message(chat_id=CHAT_ID, text=text, reply_markup=keyboard)

async def test_checklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    keyboard = [
        [InlineKeyboardButton(t, callback_data=f"test_chk_{t}")]
        for t in CHECKLIST_TIMES
    ]
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text="🧪 Qaysi checklist vaqtini test qilasiz?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# =========================
# ZADACHA — STATE
# =========================

zadacha_state = {}
zadacha_tasks = {}
zadacha_counter = [0]

TASKS_FILE = "zadacha_tasks.json"

# =========================
# ZADACHA — SAVE / LOAD
# =========================

def save_tasks():
    data = {}
    for tid, task in zadacha_tasks.items():
        data[str(tid)] = {
            "creator": task["creator"],
            "creator_username": task["creator_username"],
            "targets": task["targets"],
            "text": task["text"],
            "deadline": task["deadline"].isoformat(),
            "supervisor": task.get("supervisor", []) if isinstance(task.get("supervisor", []), list) else [task.get("supervisor", "")],
            "accepted": list(task["accepted"]),
            "done": list(task["done"]),
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
            zadacha_tasks[tid] = {
                "creator": task["creator"],
                "creator_username": task["creator_username"],
                "targets": task["targets"],
                "text": task["text"],
                "deadline": dl,
                "supervisor": task.get("supervisor", []),
                "accepted": set(task["accepted"]),
                "done": set(task["done"]),
            }
    except Exception as e:
        logger.error(f"load_tasks error: {e}")

# =========================
# ZADACHA — HELPERS
# =========================

def zadacha_target_str(targets):
    names = [AGENTS_DATA.get(u, {}).get("name", u) for u in targets]
    return " + ".join(names)

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

# =========================
# ZADACHA COMMAND
# =========================

async def zadacha_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    user_id = update.effective_user.id
    zadacha_state[user_id] = {"step": "executor", "messages": []}

    all_agents = list(AGENTS_DATA.keys())
    keyboard = [
        [InlineKeyboardButton(f"👤 {AGENTS_DATA[u]['name']}", callback_data=f"ze_{u}")]
        for u in all_agents
    ]
    keyboard.append([InlineKeyboardButton("👥 Barchasi", callback_data="ze_all")])
    keyboard.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])

    sent = await update.message.reply_text(
        "👷 Ijro etuvchi hodimni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    zadacha_state[user_id]["messages"].append(sent.message_id)

# =========================
# ZADACHA TEXT HANDLER
# =========================

async def zadacha_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return
    user_id = update.effective_user.id

    if user_id in addagent_state:
        await addagent_text_handler(update, context)
        return

    if user_id in editagent_state:
        await editagent_text_handler(update, context)
        return

    if user_id not in zadacha_state:
        return

    step = zadacha_state[user_id].get("step")

    if step == "text":
        zadacha_state[user_id]["text"] = update.message.text
        zadacha_state[user_id]["step"] = "date"

        targets = zadacha_state[user_id].get("targets", [])
        now = datetime.now(TIMEZONE)
        available_dates = get_available_dates_for_targets(targets)
        days = []
        for d in available_dates:
            diff = (d.date() - now.date()).days
            if diff == 0:
                label = f"📆 Bugun ({d.day} {MONTH_UZ[d.month]})"
            elif diff == 1:
                label = f"📆 Ertaga ({d.day} {MONTH_UZ[d.month]})"
            else:
                label = f"📆 {WEEKDAY_UZ[d.weekday()]} ({d.day} {MONTH_UZ[d.month]})"
            days.append([InlineKeyboardButton(label, callback_data=f"zd_{d.strftime('%d.%m')}")])

        if not days:
            sent = await update.message.reply_text("❌ Bu agent uchun yaqin kunlarda ish vaqti topilmadi.")
            zadacha_state[user_id]["messages"].append(sent.message_id)
            return

        days.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_target")])
        days.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])

        sent = await update.message.reply_text(
            "📅 Deadline sanasini tanlang:",
            reply_markup=InlineKeyboardMarkup(days),
        )
        zadacha_state[user_id]["messages"].append(sent.message_id)

# =========================
# ZADACHA CALLBACKS
# =========================

async def zadacha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()

    # --- OTMEN ---
    if data == "zt_otmen":
        msgs = zadacha_state.get(user_id, {}).get("messages", [])
        for msg_id in msgs:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=msg_id)
            except:
                pass
        zadacha_state.pop(user_id, None)
        await context.bot.send_message(chat_id=user_id, text="❌ Vazifa bekor qilindi.")
        return

    if user_id not in zadacha_state and not data.startswith(("zacc_", "zes_", "zdone_", "zext_", "zcancel_")):
        return

    # --- EXECUTOR ---
    if data.startswith("ze_"):
        target = data[3:]
        all_agents = list(AGENTS_DATA.keys())
        targets = all_agents if target == "all" else [target]

        zadacha_state[user_id]["targets"] = targets
        zadacha_state[user_id]["step"] = "supervisor"

        keyboard = [
            [InlineKeyboardButton(f"👤 {AGENTS_DATA[u]['name']}", callback_data=f"zs_{u}")]
            for u in all_agents
            if u not in targets  # O'ziga o'zi nazoratchi bo'la olmaydi (agar bitta target)
            or len(targets) > 1
        ]
        keyboard.append([InlineKeyboardButton("👥 Barchasi", callback_data="zs_all")])
        keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_start")])
        keyboard.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])

        sent = await context.bot.send_message(
            chat_id=user_id,
            text="🧑 Nazorat qiluvchi hodimni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        zadacha_state[user_id]["messages"].append(sent.message_id)

    # --- SUPERVISOR ---
    elif data.startswith("zs_"):
        supervisor = data[3:]
        all_agents = list(AGENTS_DATA.keys())
        targets = zadacha_state[user_id].get("targets", [])

        if supervisor == "all":
            supervisors = all_agents
        else:
            # O'ziga o'zi nazoratchi bo'la olmaydi (agar bitta target)
            if len(targets) == 1 and supervisor == targets[0]:
                await query.answer("⛔ O'zingizga o'zingiz nazoratchi bo'la olmaysiz!", show_alert=True)
                return
            supervisors = [supervisor]

        zadacha_state[user_id]["supervisor"] = supervisors
        zadacha_state[user_id]["step"] = "text"

        sent = await context.bot.send_message(
            chat_id=user_id,
            text="✏️ Vazifa matnini yozing:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_supervisor")],
                [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")],
            ]),
        )
        zadacha_state[user_id]["messages"].append(sent.message_id)

    # --- DATE ---
    elif data.startswith("zd_"):
        date_str = data[3:]
        zadacha_state[user_id]["deadline_date"] = date_str
        zadacha_state[user_id]["step"] = "time"

        targets = zadacha_state[user_id].get("targets", [])
        available_times = get_available_times_for_targets(targets, date_str)

        if not available_times:
            sent = await context.bot.send_message(
                chat_id=user_id,
                text="❌ Bu sana uchun ish vaqti topilmadi. Boshqa kun tanlang.",
            )
            zadacha_state[user_id]["messages"].append(sent.message_id)
            zadacha_state[user_id]["step"] = "date"
            return

        slots = [
            [InlineKeyboardButton(f"⏰ {t}", callback_data=f"ztime_{t}")]
            for t in available_times
        ]
        slots.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_text")])
        slots.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])

        sent = await context.bot.send_message(
            chat_id=user_id,
            text="🕐 Deadline vaqtini tanlang:",
            reply_markup=InlineKeyboardMarkup(slots),
        )
        zadacha_state[user_id]["messages"].append(sent.message_id)

    # --- TIME ---
    elif data.startswith("ztime_"):
        time_str = data[6:]
        zadacha_state[user_id]["deadline_time"] = time_str
        zadacha_state[user_id]["step"] = "confirm"

        targets = zadacha_state[user_id]["targets"]
        text = zadacha_state[user_id]["text"]
        date_str = zadacha_state[user_id]["deadline_date"]
        creator = query.from_user.first_name
        target_str = zadacha_target_str(targets)

        sent = await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"📌 {creator} → {target_str}\n"
                f"Vazifa:\n━━━━━━━━━━━━━━\n"
                f'"{text}"\n━━━━━━━━━━━━━━\n'
                f"Deadline: 📅 {date_str}  ⏰ {time_str}\n\nYuborilsinmi?"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Tasdiqlash", callback_data="zconfirm_yes")],
                [InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_date")],
                [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")],
            ]),
        )
        zadacha_state[user_id]["messages"].append(sent.message_id)

    # --- BACK ---
    elif data.startswith("zback_"):
        where = data[6:]
        all_agents = list(AGENTS_DATA.keys())

        if where == "start":
            zadacha_state[user_id]["step"] = "executor"
            keyboard = [
                [InlineKeyboardButton(f"👤 {AGENTS_DATA[u]['name']}", callback_data=f"ze_{u}")]
                for u in all_agents
            ]
            keyboard.append([InlineKeyboardButton("👥 Barchasi", callback_data="ze_all")])
            keyboard.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])
            sent = await context.bot.send_message(
                chat_id=user_id,
                text="👷 Ijro etuvchi hodimni tanlang:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            zadacha_state[user_id]["messages"].append(sent.message_id)

        elif where == "supervisor":
            zadacha_state[user_id]["step"] = "supervisor"
            targets = zadacha_state[user_id].get("targets", [])
            keyboard = [
                [InlineKeyboardButton(f"👤 {AGENTS_DATA[u]['name']}", callback_data=f"zs_{u}")]
                for u in all_agents
                if u not in targets or len(targets) > 1
            ]
            keyboard.append([InlineKeyboardButton("👥 Barchasi", callback_data="zs_all")])
            keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_start")])
            keyboard.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])
            sent = await context.bot.send_message(
                chat_id=user_id,
                text="🧑 Nazorat qiluvchi hodimni tanlang:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            zadacha_state[user_id]["messages"].append(sent.message_id)

        elif where == "target":
            zadacha_state[user_id]["step"] = "text"
            sent = await context.bot.send_message(
                chat_id=user_id,
                text="✏️ Vazifa matnini yozing:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_supervisor")],
                    [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")],
                ]),
            )
            zadacha_state[user_id]["messages"].append(sent.message_id)

        elif where == "text":
            zadacha_state[user_id]["step"] = "date"
            targets = zadacha_state[user_id].get("targets", [])
            now = datetime.now(TIMEZONE)
            available_dates = get_available_dates_for_targets(targets)
            days = []
            for d in available_dates:
                diff = (d.date() - now.date()).days
                if diff == 0:
                    label = f"📆 Bugun ({d.day} {MONTH_UZ[d.month]})"
                elif diff == 1:
                    label = f"📆 Ertaga ({d.day} {MONTH_UZ[d.month]})"
                else:
                    label = f"📆 {WEEKDAY_UZ[d.weekday()]} ({d.day} {MONTH_UZ[d.month]})"
                days.append([InlineKeyboardButton(label, callback_data=f"zd_{d.strftime('%d.%m')}")])
            days.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_target")])
            days.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])
            sent = await context.bot.send_message(
                chat_id=user_id,
                text="📅 Deadline sanasini tanlang:",
                reply_markup=InlineKeyboardMarkup(days),
            )
            zadacha_state[user_id]["messages"].append(sent.message_id)

        elif where == "date":
            zadacha_state[user_id]["step"] = "time"
            targets = zadacha_state[user_id].get("targets", [])
            date_str = zadacha_state[user_id].get("deadline_date", "")
            available_times = get_available_times_for_targets(targets, date_str) if date_str else []
            slots = [
                [InlineKeyboardButton(f"⏰ {t}", callback_data=f"ztime_{t}")]
                for t in available_times
            ]
            slots.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_text")])
            slots.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])
            sent = await context.bot.send_message(
                chat_id=user_id,
                text="🕐 Deadline vaqtini tanlang:",
                reply_markup=InlineKeyboardMarkup(slots),
            )
            zadacha_state[user_id]["messages"].append(sent.message_id)

    # --- CONFIRM YES ---
    elif data == "zconfirm_yes":
        if user_id not in zadacha_state:
            return

        s = zadacha_state.pop(user_id)
        targets = s["targets"]
        text = s["text"]
        date_str = s["deadline_date"]
        time_str = s["deadline_time"]
        creator = query.from_user.first_name
        creator_username = query.from_user.username
        supervisors = s.get("supervisor", [])
        if isinstance(supervisors, str):
            supervisors = [supervisors]

        now = datetime.now(TIMEZONE)
        year = now.year
        dt = datetime.strptime(f"{date_str}.{year} {time_str}", "%d.%m.%Y %H:%M")
        dt = dt.replace(tzinfo=TIMEZONE)

        zadacha_counter[0] += 1
        tid = zadacha_counter[0]

        zadacha_tasks[tid] = {
            "creator": creator,
            "creator_username": creator_username,
            "targets": targets,
            "supervisor": supervisors,
            "text": text,
            "deadline": dt,
            "accepted": set(),
            "done": set(),
        }

        target_str = zadacha_target_str(targets)
        supervisor_names = " + ".join(AGENTS_DATA.get(u, {}).get("name", u) for u in supervisors)

        for username in targets:
            name = AGENTS_DATA.get(username, {}).get("name", username)
            tag = f"@{username}"
            keyboard = [[InlineKeyboardButton("✅ Qabul qildim", callback_data=f"zacc_{tid}_{username}")]]
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=(
                    f"📌 {creator} → {name}\n"
                    f"🧑‍💼 Nazorat: {supervisor_names}\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"📝 Vazifa:\n\"{text}\"\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"Deadline: 📅 {date_str}  ⏰ {time_str}\n\n"
                    f"{tag}, iltimos tasdiqlang."
                ),
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        remind_time = dt - timedelta(minutes=30)
        if remind_time > datetime.now(TIMEZONE):
            context.job_queue.run_once(
                zadacha_pre_deadline_job,
                when=(remind_time - datetime.now(TIMEZONE)).total_seconds(),
                name=f"zpre_{tid}",
                data={"task_id": tid},
            )
        if dt > datetime.now(TIMEZONE):
            context.job_queue.run_once(
                zadacha_deadline_job,
                when=(dt - datetime.now(TIMEZONE)).total_seconds(),
                name=f"zdue_{tid}",
                data={"task_id": tid},
            )

        save_tasks()

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ Vazifa yuborildi.\n"
                f"📌 {creator} → {target_str}\n"
                f"━━━━━━━━━━━━━━\n"
                f"📝 Vazifa:\n\"{text}\"\n"
                f"━━━━━━━━━━━━━━\n"
                f"Deadline: 📅 {date_str}  ⏰ {time_str}"
            ),
        )

        import asyncio
        await asyncio.sleep(5)
        for msg_id in s.get("messages", []):
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=msg_id)
            except:
                pass

    # --- ACCEPT ---
    elif data.startswith("zacc_"):
        rest = data[5:]
        first_underscore = rest.index("_")
        tid = int(rest[:first_underscore])
        username = rest[first_underscore + 1:]

        if query.from_user.username != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        if tid not in zadacha_tasks:
            await query.answer("❌ Vazifa topilmadi.")
            return

        task = zadacha_tasks[tid]
        if username in task["accepted"]:
            await query.answer("Siz allaqachon qabul qilgansiz.")
            return

        task["accepted"].add(username)
        save_tasks()

        name = AGENTS_DATA.get(username, {}).get("name", username)
        now = datetime.now(TIMEZONE)
        deadline_str = task["deadline"].strftime("%d.%m soat %H:%M")

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"✅ {name} vazifani qabul qildi.\n"
                f"🕐 Qabul vaqti: {now.strftime('%d.%m soat %H:%M')}\n"
                f"━━━━━━━━━━━━━━\n"
                f"📌 \"{task['text']}\"\n"
                f"Deadline: 📅 {deadline_str}\n\n"
                f"@{task['creator_username']}"
            ),
        )
        try:
            await query.message.delete()
        except:
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except:
                pass

    # --- ESIMDA ---
    elif data.startswith("zes_"):
        rest = data[4:]
        first_underscore = rest.index("_")
        tid = int(rest[:first_underscore])
        username = rest[first_underscore + 1:]

        if query.from_user.username != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        if tid not in zadacha_tasks:
            return

        import asyncio
        msg_to_delete = query.message

        async def delete_after_10():
            await asyncio.sleep(10)
            try:
                await msg_to_delete.delete()
            except:
                pass

        asyncio.create_task(delete_after_10())
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except:
            pass

    # --- DONE ---
    elif data.startswith("zdone_"):
        rest = data[6:]
        first_underscore = rest.index("_")
        tid = int(rest[:first_underscore])
        username = rest[first_underscore + 1:]

        if query.from_user.username != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        if tid not in zadacha_tasks:
            return

        task = zadacha_tasks[tid]
        task["done"].add(username)
        save_tasks()

        name = AGENTS_DATA.get(username, {}).get("name", username)
        now = datetime.now(TIMEZONE)
        deadline_str = task["deadline"].strftime("%d.%m soat %H:%M")
        supervisors = task.get("supervisor", [])
        if isinstance(supervisors, str):
            supervisors = [supervisors]
        supervisor_tag = " " + " ".join(f"@{u}" for u in supervisors) if supervisors else ""

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"✅ {name} vazifani bajardi.\n"
                f"🕐 Bajarilgan vaqt: {now.strftime('%d.%m soat %H:%M')}\n"
                f"━━━━━━━━━━━━━━\n"
                f"📌 \"{task['text']}\"\n"
                f"Deadline: 📅 {deadline_str}\n\n"
                f"@{task['creator_username']}{supervisor_tag}"
            ),
        )
        try:
            await query.message.delete()
        except:
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except:
                pass

    # --- CANCEL ---
    elif data.startswith("zcancel_"):
        rest = data[8:]
        first_underscore = rest.index("_")
        tid = int(rest[:first_underscore])
        username = rest[first_underscore + 1:]

        if query.from_user.username != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return
        if tid not in zadacha_tasks:
            return

        task = zadacha_tasks[tid]
        task.setdefault("cancelled", set()).add(username)
        save_tasks()

        name = AGENTS_DATA.get(username, {}).get("name", username)
        now = datetime.now(TIMEZONE)
        deadline_str = task["deadline"].strftime("%d.%m soat %H:%M")
        supervisors = task.get("supervisor", [])
        if isinstance(supervisors, str):
            supervisors = [supervisors]
        supervisor_tag = " " + " ".join(f"@{u}" for u in supervisors) if supervisors else ""

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"❌ {name} vazifani bekor qildi.\n"
                f"🕐 Vaqt: {now.strftime('%d.%m soat %H:%M')}\n"
                f"━━━━━━━━━━━━━━\n"
                f"📌 \"{task['text']}\"\n"
                f"Deadline: 📅 {deadline_str}\n\n"
                f"@{task['creator_username']}{supervisor_tag}"
            ),
        )
        try:
            await query.message.delete()
        except:
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except:
                pass

    # --- EXTEND ---
    elif data.startswith("zext_"):
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
        task["deadline"] = task["deadline"] + timedelta(minutes=minutes)
        save_tasks()

        new_deadline_str = task["deadline"].strftime("%d.%m soat %H:%M")
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except:
            pass

        cancel_jobs_by_name(context.job_queue, f"zdue_{tid}")
        now = datetime.now(TIMEZONE)
        if task["deadline"] > now:
            context.job_queue.run_once(
                zadacha_deadline_job,
                when=(task["deadline"] - now).total_seconds(),
                name=f"zdue_{tid}",
                data={"task_id": tid},
            )

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"⏰ Deadline uzaytirildi.\n"
                f"📌 \"{task['text']}\"\n"
                f"Yangi deadline: 📅 {new_deadline_str}\n\n"
                f"@{task['creator_username']}"
            ),
        )

# =========================
# ZADACHA JOBS
# =========================

async def zadacha_pre_deadline_job(context: ContextTypes.DEFAULT_TYPE):
    tid = context.job.data["task_id"]
    if tid not in zadacha_tasks:
        return

    task = zadacha_tasks[tid]
    deadline_str = task["deadline"].strftime("%d.%m soat %H:%M")

    for username in task["targets"]:
        if username in task["done"]:
            continue
        tag = f"@{username}"
        keyboard = [
            [
                InlineKeyboardButton("✅ Ha, esimda", callback_data=f"zes_{tid}_{username}"),
                InlineKeyboardButton("✅ Bajardim", callback_data=f"zdone_{tid}_{username}"),
            ],
            [InlineKeyboardButton("❌ Bekor qilindi", callback_data=f"zcancel_{tid}_{username}")],
        ]
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"📌 {tag}, esingizda a?\n"
                f"━━━━━━━━━━━━━━\n"
                f'"{task["text"]}"\n'
                f"Deadline: 📅 {deadline_str}"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

async def zadacha_deadline_job(context: ContextTypes.DEFAULT_TYPE):
    tid = context.job.data["task_id"]
    if tid not in zadacha_tasks:
        return

    task = zadacha_tasks[tid]
    deadline_str = task["deadline"].strftime("%d.%m soat %H:%M")
    not_done = [u for u in task["targets"] if u not in task["done"]]

    if not not_done:
        return

    for username in not_done:
        tag = f"@{username}"
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
            text=(
                f"📌 {name}, deadline tugadi.\n"
                f"━━━━━━━━━━━━━━\n"
                f'"{task["text"]}"\n'
                f"Deadline: 📅 {deadline_str}\n\n"
                f"{tag} @{task['creator_username']}"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

# =========================
# ZADACHI COMMAND
# =========================

async def zadachi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requester = update.effective_user.username

    if not zadacha_tasks:
        await update.message.reply_text("📋 Faol vazifalar yoq.")
        return

    lines = []
    for tid, task in zadacha_tasks.items():
        deadline_str = task["deadline"].strftime("%d.%m  ⏰ %H:%M")
        creator = task["creator"]

        if requester == ADMIN_USERNAME:
            show_targets = task["targets"]
        else:
            show_targets = [u for u in task["targets"] if u == requester]

        for username in show_targets:
            name = AGENTS_DATA.get(username, {}).get("name", username)
            accepted = "✅ Qabul qildi" if username in task["accepted"] else "⏳ Qabul qilmadi"
            cancelled = task.get("cancelled", set())
            if username in task.get("done", set()):
                status = "✅ Bajardi"
            elif username in cancelled:
                status = "❌ Bekor qilindi"
            else:
                status = "⏳ Bajarilmadi"
            text_short = task["text"][:50] + ("..." if len(task["text"]) > 50 else "")
            lines.append(
                f"━━━━━━━━━━━━━━\n"
                f"📌 #{tid} | {creator} → {name}\n"
                f"📝 \"{text_short}\"\n"
                f"📅 {deadline_str}\n"
                f"{accepted} | {status}"
            )

    if not lines:
        await update.message.reply_text("📋 Sizga tegishli faol vazifalar yoq.")
        return

    lines.insert(0, "📋 Vazifalar:\n")
    lines.append("━━━━━━━━━━━━━━")
    await update.message.reply_text("\n".join(lines))

# =========================
# MAIN
# =========================

def main():
    application = Application.builder().token(TOKEN).build()

    load_tasks()

    state["cycle_id"] += 1

    # Reminder default o'chiq — faqat checklist ishlaydi
    for time_key in CHECKLIST_TIMES:
        hour, minute = map(int, time_key.split(":"))
        application.job_queue.run_once(
            checklist_job,
            when=seconds_until_time(hour, minute),
            name=f"checklist_{time_key}",
            data={"cycle_id": state["cycle_id"], "time_key": time_key},
        )

    # Reminder job ham scheduled bo'ladi lekin reminder_stopped=True bo'lgani uchun xabar yuborilmaydi
    application.job_queue.run_once(
        reminder_job,
        when=seconds_until_next_30(),
        name="reminder",
        data={"cycle_id": state["cycle_id"]},
    )

    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("umidstop", umidstop_command))
    application.add_handler(CommandHandler("reminder_start", reminder_start_command))
    application.add_handler(CommandHandler("reminder_stop", reminder_stop_command))
    application.add_handler(CommandHandler("test_reminder", test_reminder_command))
    application.add_handler(CommandHandler("test_checklist", test_checklist_command))
    application.add_handler(CommandHandler("zadacha", zadacha_command))
    application.add_handler(CommandHandler("zadachi", zadachi_command))
    application.add_handler(CommandHandler("addagent", addagent_command))
    application.add_handler(CommandHandler("editagent", editagent_command))
    application.add_handler(CommandHandler("delagent", delagent_command))

    # Text handler
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            zadacha_text_handler
        )
    )

    # Callback handlers
    application.add_handler(CallbackQueryHandler(
        addagent_callback,
        pattern="^(addday_|adddays_done|addconfirm_yes|add_cancel)"
    ))
    application.add_handler(CallbackQueryHandler(
        editagent_callback,
        pattern="^(edit_)"
    ))
    application.add_handler(CallbackQueryHandler(
        delagent_callback,
        pattern="^(delagent_)"
    ))
    application.add_handler(CallbackQueryHandler(
        zadacha_callback,
        pattern="^(zt_|ze_|zs_|zd_|ztime_|zback_|zconfirm_|zacc_|zes_|zdone_|zext_|zcancel_)"
    ))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot starting...")
    application.run_polling(drop_pending_updates=True)

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
