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
# AGENTS
# =========================

AGENT_ORDER = [
    "sirlyinfo",
    "Muhammadhumoyun_Mudarris",
]

AGENTS = {
    "sirlyinfo": "Ozodbek",
    "Muhammadhumoyun_Mudarris": "Muhammadhumoyun",
}

AGENT_INFO = {
    "sirlyinfo": (
        "👨🏻‍💻 Ozodbek @sirlyinfo\n"
        "📞 93 798 13 04"
    ),
    "Muhammadhumoyun_Mudarris": (
        "👨🏻‍💻 Muhammadhumoyun @Muhammadhumoyun_Mudarris\n"
        "📞 88 811 88 51 • 94 115 88 51"
    ),
}

# =========================
# CHECKLIST
# =========================

CHECKLISTS = {
    "10:00": [
        "Admin panel tozalandi",
        "Muammoli mijozlar jadvali tekshirildi",
        "Checklist screenshot yuborildi",
    ],
    "14:00": [
        "Muammoli mijozlar jadvali tekshirildi",
        "Sotuv jadvali toldirildi",
        "Checklist screenshot yuborildi",
    ],
    "18:00": [
        "Muammoli mijozlar jadvali tekshirildi",
        "Bug va tasklar jadvalga kiritildi",
        "Checklist screenshot yuborildi",
    ],
    "23:00": [
        "Bugalteriya jadvali toldirildi",
        "Kunlik hisobot yuborildi",
    ],
    "23:30": [
        "Telegram murojaatlar tekshirildi",
        "Checklist toliq tekshirildi",
        "STAFF guruhiga xabar yuborildi",
    ],
}

CHECKLIST_TIMES = ["10:00", "14:00", "18:00", "23:00", "23:30"]

# =========================
# NEXT TIME HELPERS
# =========================

def get_next_checklist_time(current_time_key):
    idx = CHECKLIST_TIMES.index(current_time_key)
    if idx + 1 < len(CHECKLIST_TIMES):
        return CHECKLIST_TIMES[idx + 1]
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

MONTH_UZ = {
    1: "yanvar",
    2: "fevral",
    3: "mart",
    4: "aprel",
    5: "may",
    6: "iyun",
    7: "iyul",
    8: "avgust",
    9: "sentyabr",
    10: "oktyabr",
    11: "noyabr",
    12: "dekabr",
}

# =========================
# ACTIVE AGENTS
# =========================

def get_active_agents():
    now = datetime.now(TIMEZONE)
    weekday = now.weekday()
    hour = now.hour

    active = set()

    # Ozodbek
    if weekday <= 4:
        if 10 <= hour < 20:
            active.add("sirlyinfo")
    elif weekday == 5:
        if hour >= 10:
            active.add("sirlyinfo")

    # Muhammadhumoyun
    if weekday <= 4:
        if hour >= 14:
            active.add("Muhammadhumoyun_Mudarris")
    elif weekday == 6:
        if hour >= 10:
            active.add("Muhammadhumoyun_Mudarris")

    return active

# =========================
# ACTIVE AGENTS FOR TIME
# =========================

def get_active_agents_for_time(time_key):
    hour = int(time_key.split(":")[0])

    now = datetime.now(TIMEZONE)
    weekday = now.weekday()

    active = set()

    # Ozodbek
    if weekday <= 4:
        if 10 <= hour < 20:
            active.add("sirlyinfo")
    elif weekday == 5:
        if hour >= 10:
            active.add("sirlyinfo")

    # Muhammadhumoyun
    if weekday <= 4:
        if hour >= 14:
            active.add("Muhammadhumoyun_Mudarris")
    elif weekday == 6:
        if hour >= 10:
            active.add("Muhammadhumoyun_Mudarris")

    return active

# =========================
# BUILD REMINDER KEYBOARD
# =========================

def build_reminder_keyboard(active_agents, confirmations):
    keyboard = []

    for username in AGENT_ORDER:
        if username not in active_agents:
            continue

        name = AGENTS[username]

        conf = confirmations.get(
            username,
            {"mijoz": False, "hamkor": False}
        )

        mijoz_label = (
            f"✅ {name} - Mijozlar tekshirildi"
            if conf["mijoz"]
            else f"⬜ {name} - Mijozlar tekshirildi"
        )

        hamkor_label = (
            f"✅ {name} - Hamkorlar tekshirildi"
            if conf["hamkor"]
            else f"⬜ {name} - Hamkorlar tekshirildi"
        )

        keyboard.append([
            InlineKeyboardButton(
                mijoz_label,
                callback_data=f"confirm_{username}_mijoz"
            )
        ])

        keyboard.append([
            InlineKeyboardButton(
                hamkor_label,
                callback_data=f"confirm_{username}_hamkor"
            )
        ])

    return InlineKeyboardMarkup(keyboard)

# =========================
# BUILD CHECKLIST KEYBOARD
# =========================

def build_checklist_keyboard(time_key, active_agents, checklist_confs):
    tasks = CHECKLISTS[time_key]

    keyboard = []

    for username in AGENT_ORDER:
        if username not in active_agents:
            continue

        name = AGENTS[username]

        user_conf = checklist_confs.get(username, {})

        for i, task in enumerate(tasks):
            done = user_conf.get(i, False)

            icon = "✅" if done else "⬜"

            short_task = (
                task if len(task) <= 30
                else task[:30] + "..."
            )

            keyboard.append([
                InlineKeyboardButton(
                    f"{icon} {name} — {short_task}",
                    callback_data=f"chk_{time_key.replace(':', '')}_{username}_{i}"
                )
            ])

    return InlineKeyboardMarkup(keyboard)

# =========================
# BUILD TEXTS
# =========================

def build_checklist_text(time_key, active_agents):
    tasks = CHECKLISTS[time_key]

    task_lines = "\n".join(
        f"{i+1}. {task} ☑️"
        for i, task in enumerate(tasks)
    )

    agent_block = "\n\n".join(
        AGENT_INFO[u]
        for u in AGENT_ORDER
        if u in active_agents
    )

    return (
        f"📋 {time_key} checklist\n\n"
        f"{task_lines}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"{agent_block}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "⚠️ Pastdagi tugmalarni bosish orqali vazifa bajarilganini tasdiqlang"
    )

def build_reminder_text(active_agents):
    agent_block = "\n\n".join(
        AGENT_INFO[u]
        for u in AGENT_ORDER
        if u in active_agents
    )

    return (
        f"{agent_block}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "💬 Mijozlardan kelgan murojaatlar tekshirildimi? ☑️\n\n"
        "🤝 Hamkorlardan kelgan murojaatlar tekshirildimi? ☑️\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "⚠️ Pastdagi tugmalarni bosish orqali vazifa bajarilganini tasdiqlang"
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
    tasks = CHECKLISTS[time_key]

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

    elapsed = (
        now.minute * 60
        + now.second
        + now.microsecond / 1_000_000
    )

    next_30 = ((now.minute // 30) + 1) * 30 * 60

    return max(next_30 - elapsed, 1.0)

def seconds_until_time(hour, minute):
    now = datetime.now(TIMEZONE)

    target = now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    if target <= now:
        target += timedelta(days=1)

    return (target - now).total_seconds()

# =========================
# SEND REMINDER
# =========================

async def send_reminder(bot, cycle_id):
    active = get_active_agents()

    if not active:
        return

    state["confirmations"] = {
        username: {
            "mijoz": False,
            "hamkor": False
        }
        for username in active
    }

    state["reminder_message_id"] = None
    state["reminder_sent_at"] = datetime.now(TIMEZONE)
    state["reminder_log_message_id"] = None
    state["reminder_log_lines"] = []

    text = build_reminder_text(active)

    keyboard = build_reminder_keyboard(
        active,
        state["confirmations"]
    )

    sent = await bot.send_message(
        chat_id=CHAT_ID,
        text=text,
        reply_markup=keyboard,
    )

    state["reminder_message_id"] = sent.message_id

# =========================
# SEND CHECKLIST
# =========================

async def send_checklist(bot, time_key):
    active = get_active_agents_for_time(time_key)

    if not active:
        return

    state["checklist_confirmations"][time_key] = {
        username: {}
        for username in active
    }

    text = build_checklist_text(time_key, active)

    keyboard = build_checklist_keyboard(
        time_key,
        active,
        state["checklist_confirmations"][time_key]
    )

    sent = await bot.send_message(
        chat_id=CHAT_ID,
        text=text,
        reply_markup=keyboard,
    )

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
        data={
            "cycle_id": cycle_id,
            "time_key": time_key
        },
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
        active = get_active_agents_for_time(time_key) or set(AGENT_ORDER)
        state["checklist_confirmations"][time_key] = {
            username: {} for username in active
        }
        text = build_checklist_text(time_key, active)
        keyboard = build_checklist_keyboard(time_key, active, state["checklist_confirmations"][time_key])
        sent = await context.bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            reply_markup=keyboard,
        )
        state["checklist_message_ids"][time_key] = sent.message_id
        return

    # --- REMINDER BUTTONS ---
    if data.startswith("confirm_"):
        without_prefix = data[8:]
        confirm_type = without_prefix.split("_")[-1]
        username = without_prefix[:-(len(confirm_type) + 1)]

        # Фақат ўз тугмасини боса олади
        presser = query.from_user.username
        if presser != username:
            await query.answer("⛔ Bu tugma siz uchun emas!", show_alert=True)
            return

        active = set(state["confirmations"].keys()) or get_active_agents()

        if username not in active:
            return

        if username not in state["confirmations"]:
            state["confirmations"][username] = {
                "mijoz": False,
                "hamkor": False,
            }

        if state["confirmations"][username][confirm_type]:
            return

        state["confirmations"][username][confirm_type] = True

        keyboard = build_reminder_keyboard(
            active,
            state["confirmations"]
        )

        try:
            await query.message.edit_reply_markup(reply_markup=keyboard)
        except:
            pass

        action_text = (
            "Javob berilmagan mijoz qolmadi"
            if confirm_type == "mijoz"
            else "Javob berilmagan hamkor qolmadi"
        )

        new_line = f"{AGENTS[username]} {time_str} | {action_text} ✅"
        state["reminder_log_lines"].append(new_line)

        log_text = "\n".join(state["reminder_log_lines"]) + f"\n{NOTIFY_TAGS}"

        if state["reminder_log_message_id"]:
            try:
                await context.bot.delete_message(
                    chat_id=CHAT_ID,
                    message_id=state["reminder_log_message_id"]
                )
            except:
                pass

        if all_confirmed(active, state["confirmations"]):
            log_text += f"\n\n🕐 Keyingi tekshiruv: {get_next_reminder_time()}"
            sent = await context.bot.send_message(chat_id=CHAT_ID, text=log_text)
            state["reminder_log_message_id"] = sent.message_id
            state["reminder_log_lines"] = []
            if state["reminder_message_id"]:
                try:
                    await context.bot.delete_message(
                        chat_id=CHAT_ID,
                        message_id=state["reminder_message_id"]
                    )
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

        # Фақат ўз тугмасини боса олади
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

        keyboard = build_checklist_keyboard(
            time_key,
            active,
            state["checklist_confirmations"][time_key]
        )

        try:
            await query.message.edit_reply_markup(reply_markup=keyboard)
        except:
            pass

        task_text = CHECKLISTS[time_key][task_index]

        new_line = f"{AGENTS[username]} {time_str} | {task_text} ni bajardi ✅"

        if time_key not in state["checklist_log_lines"]:
            state["checklist_log_lines"][time_key] = []
        state["checklist_log_lines"][time_key].append(new_line)

        log_text = "\n".join(state["checklist_log_lines"][time_key]) + f"\n{NOTIFY_TAGS}"

        if state["checklist_log_message_ids"].get(time_key):
            try:
                await context.bot.delete_message(
                    chat_id=CHAT_ID,
                    message_id=state["checklist_log_message_ids"][time_key]
                )
            except:
                pass

        if checklist_all_confirmed(
            time_key,
            active,
            state["checklist_confirmations"][time_key]
        ):
            next_t = get_next_checklist_time(time_key)
            log_text += f"\n✅ {time_key} checklist yakunlandi."
            if next_t:
                log_text += f" 🕐 Keyingi tekshiruv: {next_t}"
            sent = await context.bot.send_message(chat_id=CHAT_ID, text=log_text)
            state["checklist_log_message_ids"][time_key] = sent.message_id
            state["checklist_log_lines"][time_key] = []
            if state["checklist_message_ids"].get(time_key):
                try:
                    await context.bot.delete_message(
                        chat_id=CHAT_ID,
                        message_id=state["checklist_message_ids"][time_key]
                    )
                except:
                    pass
        else:
            sent = await context.bot.send_message(chat_id=CHAT_ID, text=log_text)
            state["checklist_log_message_ids"][time_key] = sent.message_id

        return

# =========================
# START COMMAND
# =========================

def get_agent_schedule_today(username):
    now = datetime.now(TIMEZONE)
    weekday = now.weekday()

    if username == "sirlyinfo":
        if weekday <= 4:
            return (10, 20)
        elif weekday == 5:
            return (10, 24)
        else:
            return None

    elif username == "Muhammadhumoyun_Mudarris":
        if weekday <= 4:
            return (14, 24)
        elif weekday == 6:
            return (10, 24)
        else:
            return None

    return None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return

    active = get_active_agents()

    now = datetime.now(TIMEZONE)

    if not active:
        weekday_name = WEEKDAY_UZ[now.weekday()]

        date_str = (
            f"{weekday_name}, "
            f"{now.day}-{MONTH_UZ[now.month]} {now.year}"
        )

        time_str = now.strftime("%H:%M")

        lines = [
            "🌙 Hozir support ish vaqti emas.\n",
            f"📅 Bugun: {date_str}",
            f"🕐 Hozirgi vaqt: {time_str}\n",
            "──────────────",
        ]

        for username in AGENT_ORDER:
            schedule = get_agent_schedule_today(username)
            info = AGENT_INFO[username]

            if schedule:
                start_h, end_h = schedule
                end_str = (
                    "23:59"
                    if end_h == 24
                    else f"{end_h:02d}:00"
                )
                lines.append(
                    f"\n{info}\n"
                    f"🕐 Bugun ish vaqti: "
                    f"{start_h:02d}:00 — {end_str}"
                )
            else:
                lines.append(
                    f"\n{info}\n😴 Bugun dam oladi"
                )

            lines.append("\n──────────────")

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text="\n".join(lines),
        )

        return

    state["stopped"] = False
    state["cycle_id"] += 1

    cancel_jobs_by_name(context.job_queue, "reminder")

    for t in CHECKLIST_TIMES:
        cancel_jobs_by_name(context.job_queue, f"checklist_{t}")

    now = datetime.now(TIMEZONE)

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
            data={
                "cycle_id": state["cycle_id"],
                "time_key": time_key
            },
        )

    active_text = "\n".join(
        f"🟢 {AGENTS[u]}"
        for u in AGENT_ORDER
        if u in active
    )

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "✅ Bot ishga tushdi\n\n"
            f"👨🏻‍💻 Aktiv supportlar:\n"
            f"{active_text}\n\n"
            f"⏰ Birinchi eslatma: "
            f"{next_q_hour:02d}:{next_q_min:02d}"
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
            "🛑 Bot to'xtatildi.\n\n"
            "Eslatmalar va vazifalar yuborilmaydi.\n\n"
            "Qayta ishga tushirish uchun /start bosing."
        ),
    )

# =========================
# TEST COMMANDS
# =========================

async def test_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return

    active = get_active_agents() or set(AGENT_ORDER)

    state["confirmations"] = {
        username: {"mijoz": False, "hamkor": False}
        for username in active
    }

    text = build_reminder_text(active)
    keyboard = build_reminder_keyboard(active, state["confirmations"])

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=text,
        reply_markup=keyboard,
    )

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
# ZADACHA — AGENTS
# =========================

ZADACHA_AGENTS = {
    "sirlyinfo": "Ozodbek",
    "Muhammadhumoyun_Mudarris": "Muhammadhumoyun",
    "al_xorazm1y": "Azamjon",
    "kh_nosirov": "Xojiakbar",
    "umidpulatov": "Umid",
}

ZADACHA_AGENT_ROLES = {
    "sirlyinfo": "Support",
    "Muhammadhumoyun_Mudarris": "Support",
    "al_xorazm1y": "Support",
    "kh_nosirov": "CEO",
    "umidpulatov": "COO",
}

ZADACHA_AGENT_INFO = {
    "al_xorazm1y": (
        "👨\u200d💻 Azamjon @al_xorazm1y\n"
        "📞 99 737 11 99"
    ),
    "kh_nosirov": (
        "👨\u200d💼 Xojiakbar @kh_nosirov\n"
        "💼 CEO"
    ),
    "umidpulatov": (
        "👨\u200d💼 Umid @umidpulatov\n"
        "📞 99 477 41 48 | 💼 COO"
    ),
}

# Ижро этувчилар (vazifa yuklatiladi)
EXECUTOR_AGENTS = ["sirlyinfo", "Muhammadhumoyun_Mudarris", "al_xorazm1y"]

# Назорат қилувчилар (nazorat qiladi)
SUPERVISOR_AGENTS = ["kh_nosirov", "umidpulatov"]

# =========================
# ZADACHA — STATE
# =========================

zadacha_state = {}
zadacha_tasks = {}
zadacha_counter = [0]

DEADLINE_SLOTS = [
    "10:00", "11:00", "12:00", "13:00", "14:00",
    "15:00", "16:00", "17:00", "18:00", "19:00",
    "20:00", "21:00", "22:00",
]

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
                "accepted": set(task["accepted"]),
                "done": set(task["done"]),
            }
    except Exception as e:
        logger.error(f"load_tasks error: {e}")

# =========================
# ZADACHA — HELPERS
# =========================

def zadacha_target_str(targets):
    names = [ZADACHA_AGENTS.get(u, u) for u in targets]
    return " + ".join(names)

async def zadacha_delete_messages(bot, user_id):
    msgs = zadacha_state.get(user_id, {}).get("messages", [])
    for msg_id in msgs:
        try:
            await bot.delete_message(chat_id=user_id, message_id=msg_id)
        except:
            pass

def get_agent_work_schedule(username):
    """Агент ҳар куни нечадан ишлашини қайтаради: {weekday: (start_h, end_h)}"""
    if username == "sirlyinfo":
        return {
            0: (10, 20), 1: (10, 20), 2: (10, 20),
            3: (10, 20), 4: (10, 20),
            5: (10, 24),
            # 6 якшанба — ишламайди
        }
    elif username == "Muhammadhumoyun_Mudarris":
        return {
            0: (14, 24), 1: (14, 24), 2: (14, 24),
            3: (14, 24), 4: (14, 24),
            # 5 шанба — ишламайди
            6: (10, 24),
        }
    elif username == "kh_nosirov":
        # Xojiakbar — Dush-Yak, 10:00-23:59
        return {i: (10, 24) for i in range(7)}
    elif username == "umidpulatov":
        # Umid — Dush-Juma, 12:00-20:00
        return {
            0: (12, 20), 1: (12, 20), 2: (12, 20),
            3: (12, 20), 4: (12, 20),
        }
    else:
        # Бошқалар — барча кунлар
        return {i: (9, 24) for i in range(7)}

def get_available_dates_for_targets(targets):
    """Агентлар учун кейинги 7 та иш кунини қайтаради."""
    now = datetime.now(TIMEZONE)
    available = []
    for i in range(14):
        d = now + timedelta(days=i)
        weekday = d.weekday()
        all_work = all(
            weekday in get_agent_work_schedule(u)
            for u in targets
        )
        if all_work:
            available.append(d)
        if len(available) >= 7:
            break
    return available

def get_available_times_for_targets(targets, date_str):
    """Берилган сана учун агентлар иш вақтига мос вақт слотларини қайтаради."""
    now = datetime.now(TIMEZONE)
    year = now.year
    from datetime import date as date_cls
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
        # Агар бугун бўлса ўтган вақтни кўрсатмаймиз
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

    keyboard = [
        [InlineKeyboardButton("👤 Ozodbek", callback_data="ze_sirlyinfo")],
        [InlineKeyboardButton("👤 Muhammadhumoyun", callback_data="ze_Muhammadhumoyun_Mudarris")],
        [InlineKeyboardButton("👤 Azamjon", callback_data="ze_al_xorazm1y")],
        [InlineKeyboardButton("👥 Ozodbek + Muhammadhumoyun", callback_data="ze_both")],
        [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")],
    ]

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
            sent = await update.message.reply_text("❌ Ushbu agent uchun yaqin kunlarda ish vaqti topilmadi.")
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
        await zadacha_delete_messages(context.bot, user_id)
        zadacha_state.pop(user_id, None)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Vazifa bekor qilindi.",
        )
        return

    if user_id not in zadacha_state and not data.startswith(("zacc_", "zes_", "zdone_", "zext_")):
        return

    # --- EXECUTOR (ижро этувчи) ---
    if data.startswith("ze_"):
        target = data[3:]

        if target == "both":
            targets = ["sirlyinfo", "Muhammadhumoyun_Mudarris"]
        else:
            targets = [target]

        zadacha_state[user_id]["targets"] = targets
        zadacha_state[user_id]["step"] = "supervisor"

        keyboard = [
            [InlineKeyboardButton("👤 Xojiakbar (CEO)", callback_data="zs_kh_nosirov")],
            [InlineKeyboardButton("👤 Umid (COO)", callback_data="zs_umidpulatov")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_start")],
            [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")],
        ]

        sent = await context.bot.send_message(
            chat_id=user_id,
            text="🧑‍💼 Nazorat qiluvchi hodimni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        zadacha_state[user_id]["messages"].append(sent.message_id)

    # --- SUPERVISOR (назорат қилувчи) ---
    elif data.startswith("zs_"):
        supervisor = data[3:]
        zadacha_state[user_id]["supervisor"] = supervisor
        zadacha_state[user_id]["step"] = "text"

        keyboard = [
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_supervisor")],
            [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")],
        ]

        sent = await context.bot.send_message(
            chat_id=user_id,
            text="✏️ Vazifa matnini yozing:",
            reply_markup=InlineKeyboardMarkup(keyboard),
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

        keyboard = [
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data="zconfirm_yes")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_date")],
            [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")],
        ]

        sent = await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"📌 {creator} → {target_str}\n"
                f"Vazifa:\n"
                f"━━━━━━━━━━━━━━\n"
                f'"{text}"\n'
                f"━━━━━━━━━━━━━━\n"
                f"Deadline: 📅 {date_str}  ⏰ {time_str}\n\n"
                f"Yuborilsinmi?"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        zadacha_state[user_id]["messages"].append(sent.message_id)

    # --- BACK ---
    elif data.startswith("zback_"):
        where = data[6:]

        if where == "start":
            zadacha_state[user_id]["step"] = "executor"
            keyboard = [
                [InlineKeyboardButton("👤 Ozodbek", callback_data="ze_sirlyinfo")],
                [InlineKeyboardButton("👤 Muhammadhumoyun", callback_data="ze_Muhammadhumoyun_Mudarris")],
                [InlineKeyboardButton("👤 Azamjon", callback_data="ze_al_xorazm1y")],
                [InlineKeyboardButton("👥 Ozodbek + Muhammadhumoyun", callback_data="ze_both")],
                [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")],
            ]
            sent = await context.bot.send_message(
                chat_id=user_id,
                text="👷 Ijro etuvchi hodimni tanlang:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            zadacha_state[user_id]["messages"].append(sent.message_id)

        elif where == "supervisor":
            zadacha_state[user_id]["step"] = "supervisor"
            keyboard = [
                [InlineKeyboardButton("👤 Xojiakbar (CEO)", callback_data="zs_kh_nosirov")],
                [InlineKeyboardButton("👤 Umid (COO)", callback_data="zs_umidpulatov")],
                [InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_start")],
                [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")],
            ]
            sent = await context.bot.send_message(
                chat_id=user_id,
                text="🧑‍💼 Nazorat qiluvchi hodimni tanlang:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            zadacha_state[user_id]["messages"].append(sent.message_id)

        elif where == "target":
            zadacha_state[user_id]["step"] = "text"
            keyboard = [
                [InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_supervisor")],
                [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")],
            ]
            sent = await context.bot.send_message(
                chat_id=user_id,
                text="✏️ Vazifa matnini yozing:",
                reply_markup=InlineKeyboardMarkup(keyboard),
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
            available_times = get_available_times_for_targets(targets, date_str) if date_str else DEADLINE_SLOTS
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
            "supervisor": s.get("supervisor", ""),
            "text": text,
            "deadline": dt,
            "accepted": set(),
            "done": set(),
        }

        target_str = zadacha_target_str(targets)

        supervisor = s.get("supervisor", "")
        supervisor_name = ZADACHA_AGENTS.get(supervisor, supervisor)
        supervisor_tag = f"@{supervisor}" if supervisor else ""

        for username in targets:
            name = ZADACHA_AGENTS[username]
            tag = f"@{username}"

            keyboard = [[InlineKeyboardButton("✅ Qabul qildim", callback_data=f"zacc_{tid}_{username}")]]

            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=(
                    f"📌 {creator} → {name}\n"
                    f"🧑‍💼 Nazorat: {supervisor_name}\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"📝 Vazifa:\n"
                    f'"{text}"\n'
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

        msg_ids = s.get("messages", [])
        save_tasks()

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ Vazifa yuborildi.\n"
                f"📌 {creator} → {target_str}\n"
                f"━━━━━━━━━━━━━━\n"
                f"📝 Vazifa:\n"
                f'"{text}"\n'
                f"━━━━━━━━━━━━━━\n"
                f"Deadline: 📅 {date_str}  ⏰ {time_str}"
            ),
        )

        import asyncio
        await asyncio.sleep(5)
        for msg_id in msg_ids:
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

        if tid not in zadacha_tasks:
            await query.answer("❌ Vazifa topilmadi.")
            return

        task = zadacha_tasks[tid]

        if username in task["accepted"]:
            await query.answer("Siz allaqachon qabul qilgansiz.")
            return

        task["accepted"].add(username)
        save_tasks()

        name = ZADACHA_AGENTS.get(username, username)
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
            await query.message.edit_reply_markup(reply_markup=None)
        except:
            pass

    # --- ESIMDA ---
    elif data.startswith("zes_"):
        rest = data[4:]
        first_underscore = rest.index("_")
        tid = int(rest[:first_underscore])
        username = rest[first_underscore + 1:]

        if tid not in zadacha_tasks:
            return

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

        if tid not in zadacha_tasks:
            return

        task = zadacha_tasks[tid]
        task["done"].add(username)
        save_tasks()

        name = ZADACHA_AGENTS.get(username, username)
        now = datetime.now(TIMEZONE)
        deadline_str = task["deadline"].strftime("%d.%m soat %H:%M")

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"✅ {name} vazifani bajardi.\n"
                f"🕐 Bajarilgan vaqt: {now.strftime('%d.%m soat %H:%M')}\n"
                f"━━━━━━━━━━━━━━\n"
                f"📌 \"{task['text']}\"\n"
                f"Deadline: 📅 {deadline_str}\n\n"
                f"@{task['creator_username']}"
            ),
        )

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
            ]
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
        name = ZADACHA_AGENTS.get(username, username)

        keyboard = [
            [InlineKeyboardButton("✅ Bajardim", callback_data=f"zdone_{tid}_{username}")],
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
# ZADACHIS COMMAND
# =========================

async def zadachis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return

    if not zadacha_tasks:
        await update.message.reply_text("📋 Faol vazifalar yo'q.")
        return

    lines = ["📋 Faol vazifalar:\n"]

    for tid, task in zadacha_tasks.items():
        deadline_str = task["deadline"].strftime("%d.%m  ⏰ %H:%M")
        creator = task["creator"]

        for username in task["targets"]:
            name = ZADACHA_AGENTS.get(username, username)
            accepted = "✅ Qabul qildi" if username in task["accepted"] else "⏳ Qabul qilmadi"
            done = "✅ Bajardi" if username in task["done"] else "⏳ Bajarilmadi"
            text_short = task["text"][:50] + ("..." if len(task["text"]) > 50 else "")

            lines.append(
                f"━━━━━━━━━━━━━━\n"
                f"📌 #{tid} | {creator} → {name}\n"
                f"📝 \"{text_short}\"\n"
                f"📅 {deadline_str}\n"
                f"{accepted} | {done}"
            )

    lines.append("━━━━━━━━━━━━━━")
    await update.message.reply_text("\n".join(lines))

# =========================
# MAIN
# =========================

def main():
    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    load_tasks()

    state["cycle_id"] += 1

    application.job_queue.run_once(
        reminder_job,
        when=seconds_until_next_30(),
        name="reminder",
        data={"cycle_id": state["cycle_id"]},
    )

    for time_key in CHECKLIST_TIMES:
        hour, minute = map(int, time_key.split(":"))

        application.job_queue.run_once(
            checklist_job,
            when=seconds_until_time(hour, minute),
            name=f"checklist_{time_key}",
            data={
                "cycle_id": state["cycle_id"],
                "time_key": time_key
            },
        )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("umidstop", umidstop_command))
    application.add_handler(CommandHandler("test_reminder", test_reminder_command))
    application.add_handler(CommandHandler("test_checklist", test_checklist_command))
    application.add_handler(CommandHandler("zadacha", zadacha_command))
    application.add_handler(CommandHandler("zadachis", zadachis_command))

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            zadacha_text_handler
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            zadacha_callback,
            pattern="^(zt_|ze_|zs_|zd_|ztime_|zback_|zconfirm_|zacc_|zes_|zdone_|zext_)"
        )
    )

    application.add_handler(
        CallbackQueryHandler(button_callback)
    )

    logger.info("Bot starting...")

    application.run_polling(drop_pending_updates=True)

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
