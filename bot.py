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
# CALLBACKS
# =========================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    await query.answer("✅ Tasdiqlandi!")

    now = datetime.now(TIMEZONE)
    time_str = now.strftime("%H:%M")

    # =========================
    # TEST CHECKLIST BUTTON
    # =========================

    if data.startswith("test_chk_"):
        time_key = data[9:]  # "10:00"
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

    # =========================
    # REMINDER BUTTONS
    # =========================

    if data.startswith("confirm_"):

        # "confirm_sirlyinfo_mijoz"
        # "confirm_Muhammadhumoyun_Mudarris_mijoz"
        without_prefix = data[8:]  # "sirlyinfo_mijoz" or "Muhammadhumoyun_Mudarris_mijoz"
        confirm_type = without_prefix.split("_")[-1]  # "mijoz" or "hamkor"
        username = without_prefix[:-(len(confirm_type) + 1)]  # "sirlyinfo" or "Muhammadhumoyun_Mudarris"

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
            await query.message.edit_reply_markup(
                reply_markup=keyboard
            )
        except:
            pass

        action_text = (
            "Mijozlar tekshirildi"
            if confirm_type == "mijoz"
            else "Hamkorlar tekshirildi"
        )

        new_line = f"{AGENTS[username]} {time_str} | {action_text} ni bajardi ✅"
        state["reminder_log_lines"].append(new_line)

        log_text = "\n".join(state["reminder_log_lines"]) + f"\n{NOTIFY_TAGS}"

        # Delete old log message
        if state["reminder_log_message_id"]:
            try:
                await context.bot.delete_message(
                    chat_id=CHAT_ID,
                    message_id=state["reminder_log_message_id"]
                )
            except:
                pass

        if all_confirmed(active, state["confirmations"]):
            log_text += f"\n✅ Barcha supportlar tasdiqladi. 🕐 Keyingi tekshiruv: {get_next_reminder_time()}"
            sent = await context.bot.send_message(chat_id=CHAT_ID, text=log_text)
            state["reminder_log_message_id"] = sent.message_id
            state["reminder_log_lines"] = []
            # Delete reminder message
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

    # =========================
    # CHECKLIST BUTTONS
    # =========================

    if data.startswith("chk_"):

        # "chk_1400_sirlyinfo_0"
        # "chk_1400_Muhammadhumoyun_Mudarris_0"
        without_prefix = data[4:]  # "1400_sirlyinfo_0"
        first_underscore = without_prefix.index("_")
        time_raw = without_prefix[:first_underscore]  # "1400"
        rest = without_prefix[first_underscore + 1:]  # "sirlyinfo_0"
        last_underscore = rest.rindex("_")
        username = rest[:last_underscore]  # "sirlyinfo" or "Muhammadhumoyun_Mudarris"
        task_index = int(rest[last_underscore + 1:])

        time_key = (
            f"{time_raw[:2]}:{time_raw[2:]}"
        )

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

        user_conf = (
            state["checklist_confirmations"][time_key][username]
        )

        if user_conf.get(task_index, False):
            return

        user_conf[task_index] = True

        keyboard = build_checklist_keyboard(
            time_key,
            active,
            state["checklist_confirmations"][time_key]
        )

        try:
            await query.message.edit_reply_markup(
                reply_markup=keyboard
            )
        except:
            pass

        task_text = CHECKLISTS[time_key][task_index]

        new_line = f"{AGENTS[username]} {time_str} | {task_text} ni bajardi ✅"

        if time_key not in state["checklist_log_lines"]:
            state["checklist_log_lines"][time_key] = []
        state["checklist_log_lines"][time_key].append(new_line)

        log_text = "\n".join(state["checklist_log_lines"][time_key]) + f"\n{NOTIFY_TAGS}"

        # Delete old log message
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
            # Delete checklist message
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
        cancel_jobs_by_name(
            context.job_queue,
            f"checklist_{t}"
        )

    now = datetime.now(TIMEZONE)

    next_q_total = (
        ((now.minute // 30) + 1) * 30
    )

    next_q_hour = (
        (now.hour + next_q_total // 60) % 24
    )

    next_q_min = next_q_total % 60

    context.job_queue.run_once(
        reminder_job,
        when=seconds_until_next_30(),
        name="reminder",
        data={"cycle_id": state["cycle_id"]},
    )

    for time_key in CHECKLIST_TIMES:
        hour, minute = map(
            int,
            time_key.split(":")
        )

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
        cancel_jobs_by_name(
            context.job_queue,
            f"checklist_{t}"
        )

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
# ZADACHA STATE
# =========================

zadacha_state = {}
zadacha_tasks = {}
zadacha_counter = [0]

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
            zadacha_tasks[tid] = {
                "creator": task["creator"],
                "creator_username": task["creator_username"],
                "targets": task["targets"],
                "text": task["text"],
                "deadline": datetime.fromisoformat(task["deadline"]).replace(tzinfo=ZoneInfo("Asia/Tashkent")) if datetime.fromisoformat(task["deadline"]).tzinfo is None else datetime.fromisoformat(task["deadline"]),
                "accepted": set(task["accepted"]),
                "done": set(task["done"]),
            }
    except Exception as e:
        logger.error(f"load_tasks error: {e}")

# =========================
# ZADACHA COMMAND
# =========================

async def zadacha_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return

    user_id = update.effective_user.id
    zadacha_state[user_id] = {"step": "target"}

    keyboard = [
        [InlineKeyboardButton("👤 Ozodbek", callback_data="ztarget_sirlyinfo")],
        [InlineKeyboardButton("👤 Muhammadhumoyun", callback_data="ztarget_Muhammadhumoyun_Mudarris")],
        [InlineKeyboardButton("👥 Ikkalasi", callback_data="ztarget_both")],
    ]

    await update.message.reply_text(
        "📌 Vazifa kim uchun?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

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
        zadacha_state[user_id]["step"] = "deadline"

        await update.message.reply_text(
            "📅 Muddatni kiriting\n(masalan: 27.05 14:00)"
        )

    elif step == "deadline":
        raw = update.message.text.strip()

        try:
            now = datetime.now(TIMEZONE)
            dt = datetime.strptime(f"{now.year}.{raw}", "%Y.%d.%m %H:%M")
            dt = dt.replace(tzinfo=TIMEZONE)
        except ValueError:
            await update.message.reply_text(
                "❌ Format noto\'g\'ri. Masalan: 27.05 14:00"
            )
            return

        zadacha_state[user_id]["deadline"] = dt
        zadacha_state[user_id]["step"] = "confirm"

        target = zadacha_state[user_id]["target"]
        text = zadacha_state[user_id]["text"]

        if target == "both":
            target_str = "Ozodbek va Muhammadhumoyun"
        else:
            target_str = AGENTS.get(target, target)

        deadline_str = dt.strftime("%d.%m %H:%M")

        keyboard = [
            [
                InlineKeyboardButton("✅ Tasdiqlash", callback_data="zconfirm_yes"),
                InlineKeyboardButton("❌ Bekor qilish", callback_data="zconfirm_no"),
            ]
        ]

        await update.message.reply_text(
            f"📌 {update.effective_user.first_name} → {target_str}\n\n"
            f"Vazifa: \"{text}\"\n"
            f"Muddati: {deadline_str}\n\n"
            f"Yuborilsinmi?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

# =========================
# ZADACHA CALLBACKS
# =========================

async def zadacha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    await query.answer()

    # Target selection
    if data.startswith("ztarget_"):
        if user_id not in zadacha_state:
            return

        target = data[8:]  # "sirlyinfo", "Muhammadhumoyun_Mudarris", "both"
        zadacha_state[user_id]["target"] = target
        zadacha_state[user_id]["step"] = "text"

        await query.message.reply_text("✏️ Vazifa matnini yozing:")

    # Confirm
    elif data == "zconfirm_yes":
        if user_id not in zadacha_state:
            return

        s = zadacha_state.pop(user_id)
        target = s["target"]
        text = s["text"]
        deadline = s["deadline"]
        creator = query.from_user.first_name
        creator_username = query.from_user.username

        if target == "both":
            targets = list(AGENT_ORDER)
        else:
            targets = [target]

        task_id_counter[0] += 1
        tid = task_id_counter[0]

        tasks[tid] = {
            "creator": creator,
            "creator_username": creator_username,
            "targets": targets,
            "text": text,
            "deadline": deadline,
            "accepted": set(),
            "done": set(),
        }

        deadline_str = deadline.strftime("%d.%m %H:%M")

        if target == "both":
            target_str = "Ozodbek va Muhammadhumoyun"
        else:
            target_str = AGENTS.get(target, target)

        # Send to group
        for username in targets:
            name = AGENTS[username]
            tag = f"@{username}"

            keyboard = [[InlineKeyboardButton("✅ Qabul qildim", callback_data=f"zaccept_{tid}_{username}")]]

            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=(
                    f"📌 {creator} → {name}\n\n"
                    f"Vazifa: \"{text}\"\n"
                    f"Muddati: {deadline_str}\n\n"
                    f"{tag}, iltimos tasdiqlang."
                ),
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        # Schedule accept reminder at task start hour (when agent starts work)
        # Remind at deadline - 2.5 hours (30 min before deadline reminder)
        now = datetime.now(TIMEZONE)

        # Accept reminder: agent work start time or 30 min from now
        accept_remind_time = max(
            now + timedelta(minutes=30),
            deadline.replace(hour=deadline.hour, minute=0) - timedelta(hours=3)
        )

        context.job_queue.run_once(
            zadacha_accept_reminder_job,
            when=(accept_remind_time - now).total_seconds(),
            name=f"zaccept_{tid}",
            data={"task_id": tid, "attempt": 1},
        )

        # Schedule deadline reminder 30 min before
        deadline_remind = deadline - timedelta(minutes=30)
        if deadline_remind > now:
            context.job_queue.run_once(
                zadacha_deadline_reminder_job,
                when=(deadline_remind - now).total_seconds(),
                name=f"zdeadline_{tid}",
                data={"task_id": tid},
            )

        # Schedule deadline notification
        if deadline > now:
            context.job_queue.run_once(
                zadacha_deadline_job,
                when=(deadline - now).total_seconds(),
                name=f"zdue_{tid}",
                data={"task_id": tid},
            )

        await query.message.reply_text("✅ Vazifa yuborildi.")

    elif data == "zconfirm_no":
        zadacha_state.pop(user_id, None)
        await query.message.reply_text("❌ Bekor qilindi.")

    # Accept
    elif data.startswith("zaccept_"):
        parts = data[8:].split("_", 1)
        tid = int(parts[0])
        username = parts[1]

        if tid not in tasks:
            return

        task = tasks[tid]

        if username in task["accepted"]:
            return

        task["accepted"].add(username)

        cancel_jobs_by_name(context.job_queue, f"zaccept_{tid}")

        name = AGENTS[username]
        deadline_str = task["deadline"].strftime("%d.%m %H:%M")

        # Notify creator
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"✅ {name} vazifani qabul qildi.\n\n"
                f"📌 {task['creator']} → {name}\n"
                f"Vazifa: \"{task['text']})\"\n"
                f"Muddati: {deadline_str}\n\n"
                f"@{task['creator_username']}"
            ),
        )

        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except:
            pass

    # Done
    elif data.startswith("zdone_"):
        parts = data[6:].split("_", 1)
        tid = int(parts[0])
        username = parts[1]

        if tid not in tasks:
            return

        task = tasks[tid]
        task["done"].add(username)

        name = AGENTS[username]
        deadline_str = task["deadline"].strftime("%d.%m %H:%M")

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"✅ {name} vazifani bajardi.\n\n"
                f"📌 {task['creator']} → {name}\n"
                f"Vazifa: \"{task['text']})\"\n"
                f"Muddati: {deadline_str}\n\n"
                f"@{task['creator_username']}"
            ),
        )

        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except:
            pass

# =========================
# ZADACHA JOBS
# =========================

async def zadacha_accept_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    tid = context.job.data["task_id"]
    attempt = context.job.data["attempt"]

    if tid not in tasks:
        return

    task = tasks[tid]
    deadline_str = task["deadline"].strftime("%d.%m %H:%M")

    pending = [u for u in task["targets"] if u not in task["accepted"]]

    if not pending:
        return

    if attempt > 3:
        # Notify creator - not accepted
        names = ", ".join(AGENTS[u] for u in pending)
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"⚠️ {names} vazifani qabul qilmadi.\n\n"
                f"📌 Vazifa: \"{task['text']})\"\n"
                f"Muddati: {deadline_str}\n\n"
                f"@{task['creator_username']}"
            ),
        )
        return

    for username in pending:
        name = AGENTS[username]
        tag = f"@{username}"
        keyboard = [[InlineKeyboardButton("✅ Qabul qildim", callback_data=f"zaccept_{tid}_{username}")]]

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"{tag}, vazifani tasdiqladingizmi?\n\n"
                f"📌 Vazifa: \"{task['text']})\"\n"
                f"Muddati: {deadline_str}"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    context.job_queue.run_once(
        zadacha_accept_reminder_job,
        when=1800,
        name=f"zaccept_{tid}",
        data={"task_id": tid, "attempt": attempt + 1},
    )


async def zadacha_deadline_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    tid = context.job.data["task_id"]

    if tid not in tasks:
        return

    task = tasks[tid]
    deadline_str = task["deadline"].strftime("%d.%m %H:%M")

    for username in task["targets"]:
        if username in task["done"]:
            continue

        name = AGENTS[username]
        tag = f"@{username}"

        keyboard = [
            [
                InlineKeyboardButton("✅ Ha, esimda", callback_data=f"zremind_{tid}_{username}"),
                InlineKeyboardButton("✅ Bajardim", callback_data=f"zdone_{tid}_{username}"),
            ]
        ]

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"{tag}, esingizda a?\n\n"
                f"📌 Vazifa: \"{task['text']})\"\n"
                f"Muddati: {deadline_str}"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def zadacha_deadline_job(context: ContextTypes.DEFAULT_TYPE):
    tid = context.job.data["task_id"]

    if tid not in tasks:
        return

    task = tasks[tid]
    deadline_str = task["deadline"].strftime("%d.%m %H:%M")

    not_done = [u for u in task["targets"] if u not in task["done"]]

    if not not_done:
        return

    tags = " ".join(f"@{u}" for u in not_done)
    names = ", ".join(AGENTS[u] for u in not_done)

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            f"⏰ Vazifa muddati tugadi.\n\n"
            f"📌 {task['creator']} → {names}\n"
            f"Vazifa: \"{task['text']})\"\n"
            f"Muddati: {deadline_str}\n\n"
            f"{tags} @{task['creator_username']}"
        ),
    )

# =========================
# ZADACHA AGENTS
# =========================

ZADACHA_AGENTS = {
    "sirlyinfo": "Ozodbek",
    "Muhammadhumoyun_Mudarris": "Muhammadhumoyun",
    "al_xorazm1y": "Azamjon",
}

ZADACHA_AGENT_INFO = {
    "al_xorazm1y": (
        "👨🏻‍💻 Azamjon @al_xorazm1y\n"
        "📞 99 737 11 99"
    ),
}

# =========================
# ZADACHA STATE
# =========================

zadacha_state = {}
# { user_id: { step, target, text, deadline_date, deadline_time, messages: [] } }

zadacha_tasks = {}
# { task_id: { creator, creator_username, targets, text, deadline, accepted, done, extended_deadline } }

zadacha_counter = [0]

DEADLINE_SLOTS = [
    "10:00", "11:00", "12:00", "13:00", "14:00",
    "15:00", "16:00", "17:00", "18:00", "19:00",
    "20:00", "21:00", "22:00",
]

# =========================
# ZADACHA HELPERS
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

async def zadacha_send(update_or_query, text, keyboard=None, state_key=None):
    """Send message and track message_id"""
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    if hasattr(update_or_query, 'message') and update_or_query.message:
        sent = await update_or_query.message.reply_text(text, reply_markup=markup)
    else:
        sent = await update_or_query.reply_text(text, reply_markup=markup)
    
    return sent

# =========================
# ZADACHA COMMAND
# =========================

async def zadacha_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        return

    user_id = update.effective_user.id
    zadacha_state[user_id] = {"step": "target", "messages": []}

    keyboard = [
        [InlineKeyboardButton("👤 Ozodbek", callback_data="zt_sirlyinfo")],
        [InlineKeyboardButton("👤 Muhammadhumoyun", callback_data="zt_Muhammadhumoyun_Mudarris")],
        [InlineKeyboardButton("👤 Azamjon", callback_data="zt_al_xorazm1y")],
        [InlineKeyboardButton("👥 Ozodbek + Muhammadhumoyun", callback_data="zt_both")],
        [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")],
    ]

    sent = await update.message.reply_text(
        "📌 Vazifa kim uchun?",
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

        now = datetime.now(TIMEZONE)
        days = []
        for i in range(7):
            d = now + timedelta(days=i)
            if i == 0:
                label = f"📆 Bugun ({d.day} {MONTH_UZ[d.month]})"
            elif i == 1:
                label = f"📆 Ertaga ({d.day} {MONTH_UZ[d.month]})"
            else:
                label = f"📆 {d.day} {MONTH_UZ[d.month]}"
            days.append([InlineKeyboardButton(label, callback_data=f"zd_{d.strftime('%d.%m')}")])

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

    if user_id not in zadacha_state and data != "zt_otmen":
        return

    s = zadacha_state.get(user_id, {})

    # --- OTMEN ---
    if data == "zt_otmen":
        await zadacha_delete_messages(context.bot, user_id)
        zadacha_state.pop(user_id, None)
        sent = await context.bot.send_message(
            chat_id=user_id,
            text="❌ Vazifa bekor qilindi.",
        )
        return

    # --- TARGET ---
    if data.startswith("zt_"):
        target = data[3:]

        if target == "both":
            targets = ["sirlyinfo", "Muhammadhumoyun_Mudarris"]
        else:
            targets = [target]

        zadacha_state[user_id]["targets"] = targets
        zadacha_state[user_id]["step"] = "text"

        keyboard = [
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_start")],
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

        slots = [
            [InlineKeyboardButton(f"⏰ {t}", callback_data=f"ztime_{t}")]
            for t in DEADLINE_SLOTS
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
            zadacha_state[user_id]["step"] = "target"
            keyboard = [
                [InlineKeyboardButton("👤 Ozodbek", callback_data="zt_sirlyinfo")],
                [InlineKeyboardButton("👤 Muhammadhumoyun", callback_data="zt_Muhammadhumoyun_Mudarris")],
                [InlineKeyboardButton("👤 Azamjon", callback_data="zt_al_xorazm1y")],
                [InlineKeyboardButton("👥 Ozodbek + Muhammadhumoyun", callback_data="zt_both")],
                [InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")],
            ]
            sent = await context.bot.send_message(
                chat_id=user_id,
                text="📌 Vazifa kim uchun?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            zadacha_state[user_id]["messages"].append(sent.message_id)

        elif where == "target":
            zadacha_state[user_id]["step"] = "text"
            keyboard = [
                [InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_start")],
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
            now = datetime.now(TIMEZONE)
            days = []
            for i in range(7):
                d = now + timedelta(days=i)
                if i == 0:
                    label = f"📆 Bugun ({d.day} {MONTH_UZ[d.month]})"
                elif i == 1:
                    label = f"📆 Ertaga ({d.day} {MONTH_UZ[d.month]})"
                else:
                    label = f"📆 {d.day} {MONTH_UZ[d.month]}"
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
            slots = [
                [InlineKeyboardButton(f"⏰ {s} - {e}", callback_data=f"ztime_{e}")]
                for s, e in DEADLINE_SLOTS
            ]
            slots.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="zback_text")])
            slots.append([InlineKeyboardButton("❌ Otmen", callback_data="zt_otmen")])
            sent = await context.bot.send_message(
                chat_id=user_id,
                text="🕐 Deadline vaqtini tanlang:",
                reply_markup=InlineKeyboardMarkup(slots),
            )
            zadacha_state[user_id]["messages"].append(sent.message_id)

    # --- CONFIRM ---
    elif data == "zconfirm_yes":
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
            "text": text,
            "deadline": dt,
            "accepted": set(),
            "done": set(),
        }

        target_str = zadacha_target_str(targets)

        for username in targets:
            name = ZADACHA_AGENTS[username]
            tag = f"@{username}"

            keyboard = [[InlineKeyboardButton("✅ Qabul qildim", callback_data=f"zacc_{tid}_{username}")]]

            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=(
                    f"📌 {creator} → {name}\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"📝 Vazifa:\n"
                    f'"{text}"\n'
                    f"━━━━━━━━━━━━━━\n"
                    f"Deadline: 📅 {date_str}  ⏰ {time_str}\n\n"
                    f"{tag}, iltimos tasdiqlang."
                ),
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        # Schedule deadline-30min reminder
        remind_time = dt - timedelta(minutes=30)
        if remind_time > datetime.now(TIMEZONE):
            context.job_queue.run_once(
                zadacha_pre_deadline_job,
                when=(remind_time - datetime.now(TIMEZONE)).total_seconds(),
                name=f"zpre_{tid}",
                data={"task_id": tid},
            )

        # Schedule deadline job
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

        # Delete all zadacha messages after 5 seconds
        import asyncio
        await asyncio.sleep(5)
        for msg_id in msg_ids:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=msg_id)
            except:
                pass

    # --- ACCEPT ---
    elif data.startswith("zaccept_"):
        rest = data[8:]
        underscore = rest.index("_")
        tid = int(rest[:underscore])
        username = rest[underscore + 1:]

    if tid not in zadacha_tasks:
        return

    task = zadacha_tasks[tid]

    if username in task["accepted"]:
        return

    task["accepted"].add(username)
    save_tasks()

    name = ZADACHA_AGENTS[username]
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
        pass
        rest = data[5:]
        underscore = rest.index("_")
        tid = int(rest[:underscore])
        username = rest[underscore + 1:]

        if tid not in zadacha_tasks:
            return

        task = zadacha_tasks[tid]

        if username in task["accepted"]:
            return

        task["accepted"].add(username)
        save_tasks()
        name = ZADACHA_AGENTS[username]
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
        underscore = rest.index("_")
        tid = int(rest[:underscore])
        username = rest[underscore + 1:]

        if tid not in zadacha_tasks:
            return

        name = ZADACHA_AGENTS[username]
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except:
            pass

    # --- DONE ---
    elif data.startswith("zdone_"):
        rest = data[6:]
        underscore = rest.index("_")
        tid = int(rest[:underscore])
        username = rest[underscore + 1:]

        if tid not in zadacha_tasks:
            return

        task = zadacha_tasks[tid]
        task["done"].add(username)
        save_tasks()
        name = ZADACHA_AGENTS[username]
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
        new_deadline_str = task["deadline"].strftime("%d.%m soat %H:%M")

        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except:
            pass

        # Reschedule deadline job
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
        name = ZADACHA_AGENTS[username]

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
            name = ZADACHA_AGENTS[username]
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
        hour, minute = map(
            int,
            time_key.split(":")
        )

        application.job_queue.run_once(
            checklist_job,
            when=seconds_until_time(hour, minute),
            name=f"checklist_{time_key}",
            data={
                "cycle_id": state["cycle_id"],
                "time_key": time_key
            },
        )

    application.add_handler(
        CommandHandler("start", start_command)
    )

    application.add_handler(
        CommandHandler("umidstop", umidstop_command)
    )

    application.add_handler(
        CommandHandler("test_reminder", test_reminder_command)
    )

    application.add_handler(
        CommandHandler("test_checklist", test_checklist_command)
    )

    application.add_handler(
        CommandHandler("zadacha", zadacha_command)
    )

    application.add_handler(
        CommandHandler("zadachis", zadachis_command)
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, zadacha_text_handler)
    )

    application.add_handler(
        CallbackQueryHandler(zadacha_callback, pattern="^(zt_|zd_|ztime_|zback_|zconfirm_|zacc_|zaccept_|zes_|zdone_|zext_)")
    )

    application.add_handler(
        CallbackQueryHandler(button_callback)
    )

    logger.info("Bot starting...")

    application.run_polling(
        drop_pending_updates=True
    )

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
