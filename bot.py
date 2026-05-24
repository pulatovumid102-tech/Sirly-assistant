# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
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
# STATE
# =========================

state = {
    "confirmations": {},
    "reminder_message_id": None,
    "reminder_sent_at": None,

    "checklist_confirmations": {},
    "checklist_message_ids": {},

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

def build_checklist_text(time_key):
    tasks = CHECKLISTS[time_key]

    task_lines = "\n".join(
        f"{i+1}. {task} ☑️"
        for i, task in enumerate(tasks)
    )

    return (
        f"📋 {time_key} checklist\n\n"
        f"{task_lines}\n\n"
        "━━━━━━━━━━━━━━"
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
        "━━━━━━━━━━━━━━"
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

    text = build_checklist_text(time_key)

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
    # REMINDER BUTTONS
    # =========================

    if data.startswith("confirm_"):

        _, username, confirm_type = data.split("_", 2)

        active = get_active_agents()

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

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"{AGENTS[username]} {time_str} | {action_text} ni bajardi ✅\n"
                f"{NOTIFY_TAGS}"
            ),
        )

        if all_confirmed(active, state["confirmations"]):
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text="✅ Barcha supportlar tasdiqladi.",
            )

        return

    # =========================
    # CHECKLIST BUTTONS
    # =========================

    if data.startswith("chk_"):

        parts = data.split("_")

        time_raw = parts[1]
        username = parts[2]
        task_index = int(parts[3])

        time_key = (
            f"{time_raw[:2]}:{time_raw[2:]}"
        )

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

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"{AGENTS[username]} {time_str} | {task_text} ni bajardi ✅\n"
                f"{NOTIFY_TAGS}"
            ),
        )

        if checklist_all_confirmed(
            time_key,
            active,
            state["checklist_confirmations"][time_key]
        ):

            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=(
                    f"✅ {time_key} checklist to'liq yakunlandi."
                ),
            )

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
            "🛑 Bot toxtatildi.\n"
            "(@umidpulatov tomonidan)"
        ),
    )

# =========================
# MAIN
# =========================

def main():
    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

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
